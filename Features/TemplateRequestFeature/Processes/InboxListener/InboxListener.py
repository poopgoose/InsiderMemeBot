# Set up sys.path so it can find the utilities
import os, sys
top_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
print(top_dir)
sys.path.append(top_dir)


from boto3.dynamodb.conditions import Key
import decimal
import praw
import time
from Features.TemplateRequestFeature import TemplateRequestFeature
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
        request_info_dict = None
        for submission_id in active_request_dict: 
            info_dict = active_request_dict[submission_id]
            if info_dict['imt_request_submission_id'] == imt_submission_id:
                request_info_dict = info_dict
        
        if request_info_dict == None:
            # Inform the moderator that the template request is no longer active.
            msg = "This template request is no longer active. This could mean that the submitted template has already been approved or rejected " + \
            "by another moderator, or that the template request has been fulfilled by a different user. " + \
            "Please contact the bot team if you believe this is in error."
            message.reply(msg)
            return

        # Validation Step 4: Make sure that the command in the body is valid
        command_text = message.body.strip()

        if command_text =="!approve":
            self.__process_template_approval(request_info_dict, comment, message, False)
        elif command_text == "!approve -all":
            self.__process_template_approval(request_info_dict, imt_submission_id, comment, message, True)
        elif command_text == "!reject" or command_text.startswith("!reject -message"):
            pass # TODO
        else:
            # Inform the moderator that the command was invalid.
            msg = "I could not understand your command. Accepted commands are:\n\n" + \
            "`!approve`: To approve this template\n\n" + \
            "`!approve -all`: To approve this template, and all future templates submitted by this user\n\n" + \
            "`!reject`: To reject this template\n\n" + \
            "`!reject -message <Message Text>`: To reject the template and add a message with an explanation"
            message.reply(msg)
            return


    def __process_template_approval(self, request_dict, comment, message, approve_all_future=False):
        """
        Helper method for approving a template

        request_dict: The dictionary for the request from the templaterequest_active_requests map
        comment: The Comment where the user provided the requested template
        message: The approval message from the moderator that the bot will reply to
        approve_all_future: Whether or not to automatically approve all future requests by this user
        """

        ##########################  Update Database ##########################
    
        # 1. Distribute the points to the user who submitted the template
        total_points = TemplateRequestFeature.TemplateRequestFeature.REQUEST_REWARD # The total points to award
        distribution_points = int(total_points / 2) # Distribute evenly between distribution and submission score
        submission_points = total_points - distribution_points

        user_data = self.data_access.query(DataAccess.Tables.USERS, Key('user_id').eq(comment.author.id))['Items'][0]
        user_key = {'user_id' : user_data['user_id']}
        user_update_expr = "set distribution_score = :dist, submission_score = :sub, total_score = :tot"
        user_expr_attrs = {
            ":dist" : decimal.Decimal(int(user_data['distribution_score']) + distribution_points),
            ":sub"  : decimal.Decimal(int(user_data['submission_score']) + submission_points),
            ":tot"  : decimal.Decimal(int(user_data['total_score']) + total_points)
        }
        self.data_access.update_item(
            DataAccess.Tables.USERS, user_key, user_update_expr, user_expr_attrs)

        if approve_all_future:
            # Add the user to the approved users list
            item_key = {'key' : 'templaterequest_approved_users'}
            item_update_expr = "SET val = list_append(val, :i)"
            item_expr_attrs = {':i' : [user_data['user_id']]}
            self.data_access.update_item(DataAccess.Tables.VARS, item_key, item_update_expr, item_expr_attrs)

        # Move the active template to fulfilled
        # TODO

        ######################### Update Comments, Submissions, and Flairs ########################

        ### Reply to IMT comment and moderator message
        comment_reply = "Your template was approved! You have been awarded **{}** points".format(total_points) 
        message_reply = "Thank you, the template has been approved."
        if approve_all_future:
            comment_reply += "\n\n*You are now approved for template request fulfillment, and will no longer " + \
                "require moderator approval for provided templates.*"
            message_reply += " u/" + user_data['username'] + " has been added to the list of approved template providers."
        comment.reply(comment_reply)
        message.reply(message_reply)

        ### Reply to the original comment(s) requesting the IMT Template
        for request_comment_id in request_dict['requestor_comments']:
            request_comment = self.reddit.comment(id=request_comment_id)
            request_comment_reply = "The template has been provided by u/" + user_data['username'] + "!\n\n" + \
               "TODO: Add link to the template here"
            request_comment.reply(request_comment_reply)

        ### Update the bot's sticky post to say the template was fulfilled
        # TODO

        ### Flair the template request as fulfilled
        # TODO