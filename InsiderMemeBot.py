###########
# Class: InsiderMemeBot.py
# Description: Main class for the bot. Implements a list of Feature objects,
#              each of which is executed in its own thread.

import praw

class InsiderMemeBot:

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
        
        # Initialize the features
        self.init_features()
        
        
    
    def init_features(self):
        """
        Initializes the list of Features that the bot will implement
        """
        pass
        
    def run(self):
        """
        Runs the bot
        """
        pass
