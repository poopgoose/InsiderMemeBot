# Set up sys.path so it can find the utilities
import os, sys
top_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
print(top_dir)
sys.path.append(top_dir)


import praw
import time
from Utils.DataAccess import DataAccess

class InboxListener:
    """
    This class continuously monitors the bot's inbox and processes messages.
    """
    ID_STORE_LIMIT = 1000 # The number of recent comment/submission IDs stored by the listener

    def __init__(self, reddit, test_mode):
        self.reddit = reddit
        self.test_mode = test_mode
        self.data_access = DataAccess(test_mode)
        self.my_id = self.reddit.user.me().id

        self.imt_subreddit_name = "InsiderMemeBot_Test" if test_mode else "InsiderMemeTrading"
        self.imt_subreddit = self.reddit.subreddit(self.imt_subreddit_name)

    def run(self):
        """
        Runs the inbox listener
        """
        while True:
            for item in self.reddit.inbox.unread(limit=None):
                if isinstance(item, praw.models.Message):
                    self.process_message(item)
                    item.mark_read()
            time.sleep(1)

    def process_message(self, message):
        """
        Processes an unread Message
        """
        print("Received message: " + message.id)
        print("  Subject: " + message.subject)
        print("  Author: " + message.author.name)
        print("  Body: " + message.body)