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