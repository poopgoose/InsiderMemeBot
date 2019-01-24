###########
# Class: InsiderMemeBot.py
# Description: Main class for the bot. Implements a list of Feature objects,
#              each of which is executed in its own thread.

import praw
import time

from Features.ActivityTracker import ActivityTracker
from Features.ScoreboardFeature.ScoreboardFeature import ScoreboardFeature

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
        #self.features.append(ActivityTracker(self.reddit, self.subreddit_name))
        self.features.append(ScoreboardFeature(self.reddit, self.subreddit_name))
        
    def run(self):
        """
        Runs the bot
        """
        while True:
            for feature in self.features:
                if feature.check_condition():
                    feature.perform_action()
                    
                # Run the next loop in 1 second
                #time.sleep(1)

