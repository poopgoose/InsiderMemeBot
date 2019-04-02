# Set up sys.path so it can find the utilities
import os, sys
top_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
print(top_dir)
sys.path.append(top_dir)


import praw
import time
from Utils.DataAccess import DataAccess
from boto3.dynamodb.conditions import Key
import decimal

class TemplateRequestListener:
    """
    This class continuously monitors subreddits for "!IMTRequest" commands
    """

    def __init__(self, reddit, test_mode):
        self.reddit = reddit
        self.test_mode = test_mode
        self.data_access = DataAccess(test_mode)


    def run(self):
        """
        Runs the template request listener
        """
        self.__start__()

        while(True):
            self.__update__()
            time.sleep(1)


    def __start__(self):
        """
        Performs initialization
        """
        print("Start!")

    def __update__(self):
        """
        Performs an update
        """
        print("Update!")