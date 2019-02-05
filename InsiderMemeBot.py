###########
# Class: InsiderMemeBot.py
# Description: Main class for the bot. Implements a list of Feature objects,
#              each of which is executed in its own thread.

from datetime import datetime, timedelta
import praw
from sortedcontainers import SortedSet
import time
import traceback

from Features.ActivityTracker import ActivityTracker
from Features.ScoreboardFeature.ScoreboardFeature import ScoreboardFeature

class InsiderMemeBot:

    ID_STORE_LIMIT = 1000 # The number of recent comment/submission IDs stored by the feature

    def __init__(self, reddit, test_mode):
        """
        Creates a new instance of InsiderMemeBot.

        @param reddit: The authenticated praw.Reddit instance.
        @param test_mode: A boolean indicating whether InsiderMemeBot will be running in testing mode or for real.
        """

        # Initialize fields
        self.reddit = reddit
        self.test_mode = test_mode
        self.features = []
        self.test_mode = test_mode
        self.subreddit_name = "InsiderMemeBot_Test" if test_mode else "InsiderMemeTrading"
        self.subreddit = self.reddit.subreddit(self.subreddit_name)

    
        # Store the IDs of the last 1000 comments that the feature has processed.
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
        # Initialize the features
        self.init_features()



    def init_features(self):
        """
        Initializes the list of Features that the bot will implement
        """
        #self.features.append(ActivityTracker(self.reddit, self.subreddit_name))
        self.features.append(ScoreboardFeature(self.reddit, self.subreddit_name))
        
        
    def run(self):
        """
        Runs the bot
        """

        while True:

            # Get new submissions and process them
            try:
                for submission in self.subreddit.new(limit=10):
                
                    if self.is_processed_recently(submission):
                        # Skip over anything we've already looked at
                        continue
                            
                    elif self.is_old(submission) or self.did_comment(submission):
                        # Nothing to be done for old posts or posts that the bot has already commented on
                        self.mark_item_processed(submission)
                        continue

                    for feature in self.features:
                        feature.process_submission(submission)


                # Get new comments
                for comment in self.subreddit.comments(limit=100):
                    if self.is_processed_recently(comment):
                        continue
                    elif self.is_old(comment) or self.did_reply(comment):
                        self.mark_item_processed(comment)
                        continue

                    for feature in self.features:
                        feature.process_comment(comment)


            except Exception as e:
                print(e)
                traceback.print_exc()    

            time.sleep(1)

        #while True:
        #    for feature in self.features:
        #        if feature.check_condition():
        #            feature.perform_action()


    ##################### Utility Functions #######################
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
        
        if len(self.__processed_ids_by_time) > InsiderMemeBot.ID_STORE_LIMIT:
            oldest_id = self.__processed_ids_by_time.pop(0) # Pop oldest comment at 0
            self.__processed_ids_by_hash.remove(oldest_id)
    
    def is_processed_recently(self, obj):
        """
        Returns whether or not the given submission or comment ID was processed by the Feature (Not the entire bot)
        within the previous 1000 comments
        
        obj: The Comment or Submission that we are testing whether or not was processed
        """
        return obj.id in self.__processed_ids_by_hash

    def did_comment(self, submission):
        """
        Returns whether or not the given submission already contains a top-level comment by InsiderMemeBot
        """
        for comment in submission.comments:
            if comment.author.id == self.reddit.user.me().id:
                # The comment was by this bot
                print("Already responded to post: " + submission.title)
                return True
                
        return False
        
    def did_reply(self, comment):
        """
        Returns whether or not the given comment contains a reply from InsiderMemeBot
        """
        replies = comment.replies
        replies.replace_more(limit=None)
        for reply in replies:
            if reply.author.id == self.reddit.user.me().id:
                print("Already replied to comment: " + comment.body + "(" + comment.author.name +")")
                return True
        return False
        
    def is_old(self, obj):
        """
        Returns true if the given submission or comment is over a day old
        """
        
        time_diff = timedelta(
            seconds=(datetime.now() - datetime.fromtimestamp(obj.created_utc)).total_seconds())

        return time_diff.days >= 1