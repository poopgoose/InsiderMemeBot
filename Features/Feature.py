###########
# Class: Feature.py
# Description: Top-level class for a single Feature. Will be overridden by implementing classes
import praw
from sortedcontainers import SortedSet

class Feature:

    COMMENT_STORE_LIMIT = 1000 # The number of recent comment IDs stored by the feature

    def __init__(self, reddit, subreddit_name):
        """
        Creates a new instance of the Feature.
        @param reddit: The authenticated praw.Reddit instance
        @param subreddit_name: The name of the subreddit we are using.
        """
        self.reddit = reddit
        self.subreddit_name = subreddit_name
        self.subreddit = self.reddit.subreddit(subreddit_name)
        
        # Initialize data structures used by utility methods
        
        # Store the IDs of the last 1000 comments that the feature has processed.
        # For efficiency the IDs are stored twice, in two different orders.
        # -  One set is a simple list that keeps the comments in the order they were processed, so that we can
        #    easily know which comment to pop off the collection once 1000 comments are exceeded.
        # 
        # -  One set is sorted by the hash of the comment. This makes it easy to determine if a 
        #    given comment has already been processed, without having to iterate over the entire list.
        #
        # These collections shouldn't be used directly by implementing classes.
        self.__processed_comments_by_time = []
        self.__processed_comments_by_hash = SortedSet()
        
    def check_condition(self):
        """
        When this function returns True, the feature will be activated
        """
        return False

    def perform_action(self):
        """
        Performs the action of the feature
        """
        pass
        
    ##################### Utility Functions #######################
    def mark_comment_processed(self, comment):
        """ Marks that the comment has been processed by the feature
        
        comment: The Comment that has been processed
        """
      
        if comment.id in self.__processed_comments_by_hash:
            # The edge case is if we're replying to a comment that's already been replied to.
            # Having duplicate comment IDs in the collections can make things messy, so we don't want to add it again.
            # In this case, we will have to traverse the entire comments_by_time collection ( O(n) ) to find and remove the comment
            self.__processed_comments_by_time.remove(comment.id)
            self.__processed_comments_by_time.append(comment.id) # Add it back on the end     
        else:    
            # This is the usual case, where a comment hasn't already been replied to.
            self.__processed_comments_by_time.append(comment.id)
            self.__processed_comments_by_hash.add(comment.id)
        
        if len(self.__processed_comments_by_time) > Feature.COMMENT_STORE_LIMIT:
            oldest_comment_id = self.__processed_comments_by_time.pop(0) # Pop oldest comment at 0
            self.__processed_comments_by_hash.remove(oldest_comment_id)
            
        # DEBUGGING
        #print("=" * 40)
        #print("By Time:")
        #print(self.__processed_comments_by_time)
        #print("-" * 40)
        #print("By hash:")
        #print(self.__processed_comments_by_hash)
        #print("=" * 40)
    
    def is_processed_recently(self, comment):
        """
        Returns whether or not the given comment_id was processed by the Feature (Not the entire bot)
        within the previous 1000 comments
        
        comment: The Comment that we are testing whether or not was processed
        """
        return comment.id in self.__processed_comments_by_hash
