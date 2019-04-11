# Set up sys.path so it can find the utilities
import os, sys
top_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
print(top_dir)
sys.path.append(top_dir)


import praw
from datetime import datetime, timedelta
import time
from Utils.DataAccess import DataAccess
from boto3.dynamodb.conditions import Key
import decimal
from sortedcontainers import SortedSet
import traceback

class TemplateRequestListener:
    """
    This class continuously monitors subreddits for "!IMTRequest" commands
    """
    ID_STORE_LIMIT = 1000 # The number of recent comment/submission IDs stored by the listener

    def __init__(self, reddit, test_mode):
        self.reddit = reddit
        self.test_mode = test_mode
        self.data_access = DataAccess(test_mode)
        self.my_id = self.reddit.user.me().id


        # Store the IDs of the last 1000 comments that the RequestListener has processed.

        # For efficiency the IDs are stored twice, in two different orders.
        # -  One set is a simple list that keeps the comments in the order they were processed, so that we can
        #    easily know which comment to pop off the collection once 1000 comments are exceeded.
        # 
        # -  One set is sorted by the hash of the comment. This makes it easy to determine if a 
        #    given comment has already been processed, without having to iterate over the entire list.
        #
        # These collections shouldn't be used directly by implementing classes.
        self.__processed_ids_by_time = []
        self.__processed_ids_by_hash = SortedSet()


    def run(self):
        """
        Runs the template request listener
        """
        self.__start__()


        while True:

            for sub in self.subreddits:

                ### Get new comments and process them ###
                for comment in sub.comments(limit=10):
                    try:
                        if self.is_processed_recently(comment):
                            continue
                        # Ignore own comments, old comments, and comments already replied to
                        elif comment.author.id == self.my_id or self.is_old(comment) or self.did_reply(comment):
                            self.mark_item_processed(comment)
                            continue

                        if comment.body.strip().lower().startswith("!imtrequest"):
                            self.process_request(comment)

                        self.mark_item_processed(comment)

                    except Exception as e:
                        print("Unable to process comment: " + str(comment))
                        print(e)
                        traceback.print_exc()
                        self.mark_item_processed(comment)

            time.sleep(1)

    def process_request(self, request_comment):

        active_requests = self.data_access.get_variable("templaterequest_active_requests")
        pending_requests = self.data_access.get_variable("templaterequest_pending_requests")
        #fulfilled_requests = self.data_access.get_variable("templaterequest_filled_requests") TODO
        fulfilled_requests = []

        comment_id = request_comment.id
        submission_id = request_comment.submission.id


        # Case 1: There is already a pending request for the requested template
        if submission_id in pending_requests:
            request_dict = pending_requests[submission_id]
            request_dict["requestor_ids"].append(request_comment.author.id)
            request_dict["requestor_names"].append(request_comment.author.name)
            request_dict["requestor_comments"].append(request_comment.id)
            pending_requests[submission_id] = request_dict

            self.data_access.set_variable("templaterequest_pending_requests", pending_requests)
            
        # Case 2: There is already an active request for the template
        elif submission_id in active_requests:
            pass # TODO
        # Case 3: There is a completed request for the requested template
        elif submission_id in fulfilled_requests:
            pass # TODO
        # Case 4: This is a new request
        else:
            request_dict = {
                "requestor_ids" : [request_comment.author.id],
                "requestor_names" : [request_comment.author.name],
                "requestor_comments" : [request_comment.id],
                "created_utc" : decimal.Decimal(request_comment.created_utc),
                "permalink" : request_comment.permalink,
                "submission_title" : request_comment.submission.title,
                "subreddit_name" : request_comment.subreddit.name
            }

            pending_requests[submission_id] = request_dict # Key by the submission ID

            self.data_access.set_variable("templaterequest_pending_requests", pending_requests)


            print("=" * 40)
            print("TemplateRequestListener: Received request\n")
            print("Permalink: " + str(request_comment.permalink))
            print("Author: " + str(request_comment.author))
            print("=" * 40)

            # Respond to the comment
            request_comment.reply(
                "Your template request has been received by r/InsiderMemeTrading!\n\n" + \
                "I will update this comment and send a message to your inbox when the request is fulfilled."
            )


    def __start__(self):
        """
        Performs initialization
        """

        # Get the subreddits to listen on
        self.subreddit_names = self.data_access.get_variable("templaterequest_monitored_subreddits")
        print("=" * 40)
        print("Starting Template Request Listener\n")
        print("Monitored subreddits:")
        for sub in self.subreddit_names:
            print("    r/" + sub)

        self.subreddits = []
        for sub in self.subreddit_names:
            self.subreddits.append(self.reddit.subreddit(sub))


    def did_reply(self, comment):
        """
        Returns whether or not the given comment contains a reply from InsiderMemeBot
        """
        comment.refresh()
        replies = comment.replies

        replies.replace_more(limit=None)
        for reply in replies:
            if reply.author.id == self.reddit.user.me().id:
                return True
        return False
        

    def is_processed_recently(self, obj):
        """
        Returns whether or not the given submission or comment ID was processed by the Feature (Not the entire bot)
        within the previous 1000 comments
        
        obj: The Comment or Submission that we are testing whether or not was processed
        """
        return obj.id in self.__processed_ids_by_hash

    def mark_item_processed(self, item):
        """ Marks that the item has been processed by the feature
        
        item: The Comment or Submission that has been processed
        """
      
        if item.id in self.__processed_ids_by_hash:
            # The edge case is if we're replying to a comment that's already been replied to.
            # Having duplicate comment IDs in the collections can make things messy, so we don't want to add it again.
            # In this case, we will have to traverse the entire comments_by_time collection ( O(n) ) to find and remove the comment
            self.__processed_ids_by_time.remove(item.id)
            self.__processed_ids_by_time.append(item.id) # Add it back on the end     
        else:    
            # This is the usual case, where a comment hasn't already been replied to.
            self.__processed_ids_by_time.append(item.id)
            self.__processed_ids_by_hash.add(item.id)
        
        if len(self.__processed_ids_by_time) > TemplateRequestListener.ID_STORE_LIMIT:
            oldest_id = self.__processed_ids_by_time.pop(0) # Pop oldest comment at 0
            self.__processed_ids_by_hash.remove(oldest_id)

    def is_old(self, obj):
        """
        Returns true if the given comment or submission is more than 10 minutes old.
        """
        
        time_diff = timedelta(
            seconds=(datetime.now() - datetime.fromtimestamp(obj.created_utc)).total_seconds())

        return time_diff.seconds//60 > 10