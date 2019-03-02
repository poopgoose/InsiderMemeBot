###########
# Class: Feature.py
# Description: Top-level class for a single Feature. Will be overridden by implementing classes
import praw

class Feature:

    def __init__(self, bot):
        """
        Creates a new instance of the Feature.
        @param bot: The InsiderMemeBot instance
        """
        self.bot = bot
            

    def update(self):
        """
        Called every cycle for the features to perform routine updates
        """
        pass

    def process_comment(self, comment):
        """
        Processes a new comment
        """
        pass

    def process_submission(self, submission):
        """
        Processes a new submission
        """
        pass

    def on_finished_tracking(self, item):
        """ 
        Handler function for when a submission or example has finished tracking
        item: The Item from the Tracking table that has finished tracking, and has the final
        score available.
        """
        pass