# Set up sys.path so it can find the utilities
import os, sys
top_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
print(top_dir)
sys.path.append(top_dir)


import praw
import time
from Utils.DataAccess import DataAccess
from Utils import RedditUtils
import re

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

        self.subreddit_name = "InsiderMemeBot_Test" if test_mode else "InsiderMemeTrading"
        self.subreddit = self.reddit.subreddit(self.subreddit_name)

    def run(self):
        """
        Runs the inbox listener
        """
        while True:
            for item in self.reddit.inbox.unread(limit=None):
                if isinstance(item, praw.models.Message):
                    self.process_message(item)
                    #item.mark_read()
            time.sleep(1)

    def process_message(self, message):
        """
        Processes an unread Message
        """
        print("Received message: " + message.id)
        print("  Subject: " + message.subject)
        print("  Author: " + message.author.name)
        print("  Body: " + message.body)

        # Regular expression for moderator response to a fulfilled template request
        fulfilled_response_subject_regex = r"re: Fulfilled template request <(\S+)>"
        match = re.match(fulfilled_response_subject_regex, message.subject)
        if match is not None:
            # Get the comment ID from the subject line that the command is referring to
            comment_id = match.groups()[0]
            self.__process_fulfilled_template_request_mod_reply(comment_id, message)

    def __process_fulfilled_template_request_mod_reply(self, comment_id, message):
        """
        Helper method for process_message. Processes a message that is a reply
        from a moderator about a submitted template for a template request
        """

        # Validation Step 1: Make sure the author is actually a moderator
        if not RedditUtils.is_moderator(self.subreddit, message.author):
            return
        else:
            print("Moderator!")

        # Validation Step 2: Make sure that the comment ID exists in the database.
        # (If another mod had already approved the submission, then it would be removed)

        # Validation Step 3: Make sure that the command in the body is valid



