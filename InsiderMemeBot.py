###########
# Class: InsiderMemeBot.py
# Description: Main class for the bot. Implements a list of Feature objects,
#              each of which is executed in its own thread.

from datetime import datetime, timedelta
from praw.models.reddit.submission import Submission
from praw.models.reddit.comment import Comment
from sortedcontainers import SortedSet
import time
import traceback

from Features.ActivityTracker import ActivityTracker
from Features.BaseScoringFeature.BaseScoringFeature import BaseScoringFeature
from Features.ScoreboardFeature.ScoreboardFeature import ScoreboardFeature
from Features.GiftFeature.GiftFeature import GiftFeature

from Utils.DataAccess import DataAccess
from boto3.dynamodb.conditions import Key
import decimal

class InsiderMemeBot:

    VERSION = "1.2" # The version of InsiderMemeBot

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
        self.my_id = self.reddit.user.me().id


        print("User: " + self.reddit.user.me().name)
        print("Subreddit: " + self.subreddit_name)

        self.data_access = DataAccess(test_mode)
  
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

        print("Initialization Complete")

    def init_features(self):
        """
        Initializes the list of Features that the bot will implement
        """
        self.features.append(BaseScoringFeature(self))
        self.features.append(ScoreboardFeature(self))
        self.features.append(GiftFeature(self))
        
        
    def run(self):
        """
        Runs the bot
        """

        while True:
            try:
                ### Perform any periodic updates ###
                for feature in self.features:
                    feature.update()

                ### Get new submissions and process them ###
                for submission in self.subreddit.new(limit=10):
                
                    if self.is_processed_recently(submission):
                        # Skip over anything we've already looked at
                        continue

                    elif (submission.is_self and not self.test_mode):
                        # Skip over text-only submisisons (Announcements, etc.)
                        # Allow processing of text-only submissions in test-mode only
                        self.mark_item_processed(submission)
                        continue
                            
                    elif self.is_old(submission) or self.did_comment(submission):
                        # Nothing to be done for old posts or posts that the bot has already commented on
                        self.mark_item_processed(submission)
                        continue

                    for feature in self.features:
                        feature.process_submission(submission)

                    self.mark_item_processed(submission)


                ### Get new comments and process them ###
                for comment in self.subreddit.comments(limit=10):
                    if self.is_processed_recently(comment):
                        continue
                    # Ignore own comments, old comments, and comments already replied to
                    elif comment.author.id == self.my_id or \
                    self.is_old(comment) or self.did_reply(comment):
                        self.mark_item_processed(comment)
                        continue

                    for feature in self.features:
                        feature.process_comment(comment)

                    self.mark_item_processed(comment)

            except Exception as e:
                print(e)
                traceback.print_exc()    

            time.sleep(1)

    ######################## Callbacks ############################
    def finished_tracking_callback(self, item):
        """
        This callback is triggered whenever an item (submission or example)
        has finished tracking, and has its final score available.

        item: The item from the Tracking database that has finished tracking
        """
        for feature in self.features:
            # Call the handlers
            feature.on_finished_tracking(item)


    ##################### Utility Functions #######################

    def reply(self, item, reply, is_sticky=False, suppress_footer = False):
        """
        Replies to a comment with the given reply
        item: The PRAW Comment or Submission object to reply to
        reply: The string with which to reply.

        is_sticky: Whether or not the comment should be sticky. Only applicable if reply is a Submission
        If item is a Comment, then the bot will directly reply to the comment.
        If item is a Submission, then the bot will create a top-level comment.

        Returns the Comment object made by the bot
        """

        # Add footer
        if not suppress_footer:
            reply_with_footer = reply + "\n\n\n\n^(InsiderMemeBot v" + InsiderMemeBot.VERSION + ")"
        else:
            reply_with_footer = reply
            
        # The reply Comment made by the bot
        try:
            bot_reply = item.reply(reply_with_footer)
            print("Responded to item: " + str(item))
            print("Response: " + str(bot_reply))
        except Exception as e:
            print("Could not post reply!")
            print("  Replying to: " + str(item))
            print("  Response: " + str(reply))
            print("Error: " + str(e))

        if is_sticky:
            try:
                # Attempt to make post sticky if we have permissions to do so
                bot_reply.mod.distinguish(how='yes', sticky=True)
            except Exception as e:
                print("Could not make post sticky!")
                print(e)

        return bot_reply

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
    

    def is_user(self, author):
        """
        Returns true if the given author is a user in the DynamoDB database.
        """
        
        # Query the table to get any user with a user_id matching the author's id
        response = self.data_access.query(DataAccess.Tables.USERS, Key('user_id').eq(author.id))
        num_matches = len(response['Items'])
        
        # If there is a match, then the author is already a user
        return num_matches > 0

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
            if comment.author.id == self.my_id:
                # The comment was by this bot
                return True
        return False
        
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
        
    def is_old(self, obj):
        """
        Returns true if the given comment or submission is more than 10 minutes old.
        """
        
        time_diff = timedelta(
            seconds=(datetime.now() - datetime.fromtimestamp(obj.created_utc)).total_seconds())

        return time_diff.seconds//60 > 10