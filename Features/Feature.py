###########
# Class: Feature.py
# Description: Top-level class for a single Feature. Will be overridden by implementing classes
import praw

class Feature:

    def __init__(self, reddit, subreddit_name):
        """
        Creates a new instance of the Feature.
        @param reddit: The authenticated praw.Reddit instance
        @param subreddit_name: The name of the subreddit we are using.
        """
        self.reddit = reddit
        self.subreddit_name = subreddit_name
        self.subreddit = self.reddit.subreddit(subreddit_name)
        
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