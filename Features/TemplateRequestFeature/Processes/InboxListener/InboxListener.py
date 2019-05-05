# Set up sys.path so it can find the utilities
import os, sys
top_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
print(top_dir)
sys.path.append(top_dir)


import decimal
import praw
import time
from Utils.DataAccess import DataAccess
from Utils import RedditUtils
import re
import traceback

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
            try:
                for item in self.reddit.inbox.unread(limit=None):
                    if isinstance(item, praw.models.Message):
                        try:
                            self.process_message(item)
                            item.mark_read()
                        except Exception as e:
                            print("Error processing message: " + str(item))
                            traceback.print_exc()
                time.sleep(1)
            except Exception as e:
                print("Error reading inbox: " + str(e))
                traceback.print_exc()

    def process_message(self, message):
        """
        Processes an unread Message
        """
        print("Received message: " + message.id)
        print("  Subject: " + message.subject)
        print("  Author: " + message.author.name)
        print("  Body: " + message.body)

        # Regular expression for moderator response to a fulfilled template request
        fulfilled_response_subject_regex = r"re: Fulfilled template request <(\S+),(\S+)>"
        match = re.match(fulfilled_response_subject_regex, message.subject)
        if match is not None:            
            # Get the comment ID from the subject line that the command is referring to
            comment_id = match.groups()[0]
            imt_submission_id = match.groups()[1]
            self.__process_fulfilled_template_request_mod_reply(comment_id, imt_submission_id, message)

    def __process_fulfilled_template_request_mod_reply(self, comment_id, imt_submission_id, message):
        """
        Helper method for process_message. Processes a message that is a reply
        from a moderator about a submitted template for a template request

        comment_id: The ID of the comment for the submitted feature on the bot's feature request post
        imt_submission_id: The Submission ID for the Template Request post on IMT
        """

        # Validation Step 1: Make sure the author is actually a moderator
        if not RedditUtils.is_moderator(self.subreddit, message.author):
            return # Don't respond at all if the user isn't a moderator

        # Validation Step 2: Get the comment, and make sure it hasn't been deleted by the author
        comment = self.reddit.comment(id=comment_id)
        if comment is None or comment.author is None:
            # The comment was deleted
            msg = "The comment for this template request has been deleted, and can no longer be processed."
            message.reply(msg)
            return

        # Validation Step 3: Make sure that the comment ID exists as an
        # active request in the database. (If another mod had already approved the submission,
        # then it would have been removed)
        active_request_dict = self.data_access.get_variable("templaterequest_active_requests")

        # Note: The dictionary is keyed by the Submission ID of the posts in which there has been a request, not on the
        # submission ID of the corresponding bot post on IMT for the request.
        request_submission_id = None
        for submission_id in active_request_dict: 
            request_dict = active_request_dict[submission_id]
            if request_dict['imt_request_submission_id'] == imt_submission_id:
                request_submission_id = submission_id 
        
        if request_submission_id == None:
            # Inform the moderator that the template request is no longer active.
            msg = "This template request is no longer active. This could mean that the submitted template has already been approved or rejected " + \
            "by another moderator, or that the template request has been fulfilled by a different user. " + \
            "Please contact the bot team if you believe this is in error."
            message.reply(msg)
            return

        # Validation Step 4: Make sure that the command in the body is valid
        command_text = message.body.strip()

        if command_text =="!approve":
            self.__process_template_approval(request_submission_id, imt_submission_id, comment, False)
        elif command_text == "!approve --all":
            self.__process_template_approval(request_submission_id, imt_submission_id, comment, True)
        elif command_text == "!reject" or command_text.startswith("!reject --message"):
            pass # TODO
        else:
            # Inform the moderator that the command was invalid.
            msg = "I could not understand your command. Accepted commands are:\n\n" + \
            "`!approve`: To approve this template\n\n" + \
            "`!approve --all`: To approve this template, and all future templates submitted by this user\n\n" + \
            "`!reject`: To reject this template\n\n" + \
            "`!reject --message <Message Text>`: To reject the template and add a message with an explanation"
            message.reply(msg)
            return


    def __process_template_approval(self, request_submission_id, imt_submission_id, comment, approve_all_future=False):
        """
        Helper method for approving a template

        request_submission_id: The ID of the submission for which a template was requested
        imt_submission_id: The ID of the template request submission posted by InsiderMemeBot
        comment: The Comment where the user provided the requested template
        approve_all_future: Whether or not to automatically approve all future requests by this user

        Returns True if processing was successful, False otherwise.
        """
        pass

        # 2. Distribute the points to the user who submitted the template
        #user_key = {'user_id' : item['author_id']}
        #user_update_expr = "set {} = {} + :score".format(field_name, field_name)
        #user_expr_attrs = {":score" : decimal.Decimal(score)}
        #self.bot.data_access.update_item(
        #    DataAccess.Tables.USERS, user_key, user_update_expr, user_expr_attrs)