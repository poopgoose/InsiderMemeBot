from Features.Feature import Feature
import decimal
import praw
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import time
from Utils.DataAccess import DataAccess
import math
import os
import re
import Utils.Parsing
import traceback

class TemplateRequestFeature(Feature):
    """
    This class supports template requests from !IMTRequest commands
    picked up by TemplateRequestListener
    """


    # CONSTANTS

    # The minimum number of seconds permitted between posting request notifications.
    # If multiple requests are received within the minimum interval, they are bundled
    # together and posted together as a single submission
    PENDING_REQUESTS_POST_INTERVAL = 120

    # How often to update
    UPDATE_INTERVAL =  1 * 5 # Update every 60 seconds

    REQUEST_REWARD = 500 # The amount of points to award for fulfilling a request

    def __init__(self, bot):
        super(TemplateRequestFeature, self).__init__(bot)

        self.prev_update_time = 0 # The time that the bot previously ran its update loop
        self.prev_pending_requests_post_time = 0 # The time that the bot previously posted pending template requests

        # Get the flair ID
        self.flair_id = self.bot.data_access.get_variable("templaterequest_flair_id")

        # Get the mods to notify for when a template request is made or fulfilled
        notified_names = self.bot.data_access.get_variable("templaterequest_notified_mods")
        self.notified_mods = []
        for name in notified_names:
            self.notified_mods.append(self.bot.reddit.redditor(name))


    def update(self):
        """
        Updates the template request feature
        """
        cur_time = time.time()
        if cur_time < self.prev_update_time + TemplateRequestFeature.UPDATE_INTERVAL:
            return # Not time to update yet

        # Update the pending requests.
        # A pending request means it has been registered in the AWS Database,
        # but InsiderMemeBot has yet to create a comment with the request information.
        # Once the request comment is posted, the request is removed from the pending request
        # list, and added to the active requests list.
        # The pending requests are stored as a dictionary, keyed by the requested Submission IDs
        if cur_time >= self.prev_pending_requests_post_time + TemplateRequestFeature.PENDING_REQUESTS_POST_INTERVAL:
            pending_requests = self.bot.data_access.get_variable("templaterequest_pending_requests")
            if len(pending_requests) > 0:
                self.process_pending_requests(pending_requests)

        # See if there are templates any that have been mod-approved and are waiting for processing.
        mod_approved_requests = self.bot.data_access.get_variable("templaterequest_approved_requests")
        if len(mod_approved_requests) > 0:
            self.process_approved_requests(mod_approved_requests)

        self.prev_update_time = int(time.time())

    def process_comment(self, comment):
        """
        Processes comments
        """

        if self.is_active_request_reply(comment):
            # The comment was a reply to an active request
            self.process_active_reply(comment)

        elif self.is_fulfilled_request_reply(comment):
            # The comment was a reply to a fulfilled request
            self.process_fulfilled_reply(comment)

    def process_pending_requests(self, pending_requests):
        """
        Processes the pending requests from the !IMTRequest command.
        """
        num_requests = len(pending_requests)

        print("Processing " + str(num_requests) + " template requests")

        # Get the current active requests. We will append all of the pending requests to this dict
        active_requests = self.bot.data_access.get_variable("templaterequest_active_requests")

        # Create a cross-post for each request
        for submission_id in pending_requests:
            try:
                request_dict = pending_requests[submission_id]
                subreddit_name = request_dict["subreddit_name"]
                submission = self.bot.reddit.submission(id=submission_id)

                # Crosspost the post to the IMT subreddit
                request_submission = submission.crosspost(
                    self.bot.subreddit,
                    title = "New template request from r/" + str(request_dict["subreddit_name"]) + "!")

                request_submission.mod.flair(text='Template Request')

                # Add the sticky comment to the submission
                reply_msg = "A template has been requested for this meme!\n\n" + \
                            "Original Post: [" + request_dict["submission_title"] + "](" + request_dict["permalink"] + ")\n\n\n\n" + \
                            "To supply a template, repond to this comment with the '!template' command, followed by a link to the template.\n\n\n\n" + \
                            "Example:\n\n `!template https://imgur.com/...`\n\n\n\n" + \
                            "The first user to fulfill the request will receive **" + str(TemplateRequestFeature.REQUEST_REWARD) + "** points.\n\n\n\n" + \
                            "*Your link MUST be to the requested template, or it will be removed! Repeated incorrect templates can result in your score " + \
                            "being reset to 0 or getting banned!*"

                bot_comment = self.bot.reply(request_submission, reply_msg, is_sticky=True)

                # Create an entry in active_requests
                active_request_dict = request_dict
                active_request_dict["imt_bot_comment_id"] = bot_comment.id
                active_request_dict["imt_request_submission_id"] = request_submission.id
                active_request_dict["imt_request_submission_title"] = request_submission.title

                active_requests[submission_id] = active_request_dict
            except Exception as e:
                print("!!!! Unable to process request!   Submission ID: " + str(submission_id))
                print(e)
                traceback.print_exc()

        # Update the active requests and pending requests
        self.bot.data_access.set_variable("templaterequest_active_requests", active_requests)
        self.bot.data_access.set_variable("templaterequest_pending_requests", {})
        self.prev_pending_requests_post_time = time.time()

    def process_approved_requests(self, comment_request_pairs):
        """
        Processes a list of comments that have been marked by the mods as fulfilled template requests,
        paired with the key for the active request that they fulfill

        comment_request_pairs: A list of pairs, where the first item is the ID of the Comment in which
        a template request is fulfilled, and the second item is the ID of the request in the 
        templaterequest_active_requests dictionary in the AWS database.
        """

        # TODO - Cleanup comment_request_pairs. The second item is no longer required
        
        print("Processing approved requests: " + str(comment_request_pairs))
        for pair in comment_request_pairs:

            try:
                comment_id = pair[0]
                comment = self.bot.reddit.comment(id=comment_id)

                if comment.author is not None:
                    # If the user is in the 'templaterequest_approved_users' list, then the 
                    # moderator approved them as new approved users.
                    approved_users = self.bot.data_access.get_variable('templaterequest_approved_users')
                    is_new_approved = comment.author.id in approved_users
                    self.submit_template(comment, is_mod_approved=True, is_new_approved_user=is_new_approved)
            except Exception as e:
                print("Error while processing approved request " + comment_id + ": " + str(e))
                traceback.print_exc()

        # Clear the approved requests after processing
        self.bot.data_access.set_variable("templaterequest_approved_requests", [])

    def process_active_reply(self, comment):
        """
        Processes a reply made to the bot in an active template request post
        """

        comment_redditor = comment.author
        if comment_redditor is None:
            return # The comment was deleted, so there's nothing for us to do

        comment_str = comment.body.strip()
        if not comment_str.lower().startswith("!template"):
            return # Nothing to process, since the reply wasn't a command

        urls = Utils.Parsing.get_urls(comment_str)

        # Make sure that exactly 1 unique URL was provided
        if len(urls) == 0:
            self.bot.reply(comment, "I couldn't detect any URLs in the template you provided! Please try again " + \
                "with a valid URL.")
            return
        elif len(urls) > 1:
            self.bot.reply(comment, "I detected more than one URL in your template command, so I can't determine " + \
                "which URL belongs to the template. Please try again with just a single URL!")
            return
        else:
            # The command was formatted correctly!
            bot_response = "" # The bot's response to the user's comment

            # Create a new user for the comment author if they don't already have one
            created_new_account = False
            if not self.bot.data_access.is_user(comment_redditor):
                self.bot.data_access.create_new_user(comment_redditor)
                created_new_account = True

            # Check to see if the user is approved for fulfilling templates without mod review
            approved_template_submitters = self.bot.data_access.get_variable("templaterequest_approved_users")
            if not comment_redditor.id in approved_template_submitters:
                # The user isn't approved to submit the templates directly, so submit it for mod review
                self.submit_for_mod_review(comment)
                bot_response = "Thanks for submitting the template! Since you are not yet an approved template submitter, a " + \
                    "moderator will be back shortly to review the link you provided."
            else:
                # The user is approved to submit templates without needing mod review
                self.submit_template(comment)
                bot_response = "TODO"

            # If a new account was created for the user, append the message in the footer
            if created_new_account:
                bot_response  += "\n\n*New user registered for " + comment_redditor.name + "*"

            self.bot.reply(comment, bot_response)


    def submit_for_mod_review(self, comment):
        """
        Submits a fulfilled template request for moderator review
        """

        # Construct the commands for the mods to copy/paste into a response
        approve_cmd = "!approve"
        approve_all_cmd = "!approve -all"
        reject_cmd = "!reject"
        reject_msg_cmd = "!reject -message <message>"

        # An example for adding a reject message
        reject_example = "!reject -message Thanks for the template! We appreciate the effort, but your " + \
            "submission could not be accepted because the website it links to isn't one of our approved platforms."

        # Notify the mods
        notification_subj = "Fulfilled template request <{},{}>".format(comment.id, comment.submission.id)
        notification_msg = "A [template request]({}) has been fulfilled by u/{}!\n\n " + \
            "Please respond to this message with one of the commands below:\n\n\n\n" + \
            "**To approve this template:**\n\n" + \
            "`" + approve_cmd + "`\n\n\n\n" + \
            "**To approve this template, and all future templates for this user:**\n\n" + \
            "`" + approve_all_cmd + "`\n\n\n\n" + \
            "**To reject this template:**\n\n" + \
            "`" + reject_cmd + "`\n\n\n\n" + \
            "**To reject this template, and provide a message explaining why:**\n\n" + \
            "`" + reject_msg_cmd + "`\n\n"  + \
            "Anything after the `-message` flag is what will be sent to the author of the template.\n\n" + \
            "Example:\n\n `" + reject_example + "`" 

        notification_msg = notification_msg.format(comment.permalink, comment.author.name)
        for mod_redditor in self.notified_mods:
            mod_redditor.message(notification_subj, notification_msg)

    def submit_template(self, comment, is_mod_approved = False, is_new_approved_user = False):
        """
        Submits a template to fulfill a templaterequest
        comment: The comment in which the template has been provided
        is_mod_approved: Whether this template had been approved by a moderator for an unapproved template submitter
        is_new_approved_user: Whether the user is a new approved template submitter
        """

        # 1. Get the active request information that corresponds to this comment
        active_requests = self.bot.data_access.get_variable("templaterequest_active_requests")
        request_info = None
        active_request_id = ""
        for request_id in active_requests:
            if active_requests[request_id]['imt_request_submission_id'] == comment.submission.id:
                active_request_id = request_id
                request_info = active_requests[request_id]
                break

        # 2. Distribute the points to the user who submitted the template
        total_points = TemplateRequestFeature.REQUEST_REWARD # The total points to award
        distribution_points = int(total_points / 2) # Distribute evenly between distribution and submission score
        submission_points = total_points - distribution_points

        user_data = self.bot.data_access.query(DataAccess.Tables.USERS, Key('user_id').eq(comment.author.id))['Items'][0]
        user_key = {'user_id' : user_data['user_id']}
        user_update_expr = "set distribution_score = :dist, submission_score = :sub, total_score = :tot"
        user_expr_attrs = {
            ":dist" : decimal.Decimal(int(user_data['distribution_score']) + distribution_points),
            ":sub"  : decimal.Decimal(int(user_data['submission_score']) + submission_points),
            ":tot"  : decimal.Decimal(int(user_data['total_score']) + total_points)
        }
        self.bot.data_access.update_item(
            DataAccess.Tables.USERS, user_key, user_update_expr, user_expr_attrs)

        # 3. Remove from the active templates, and add to the Templates table
        fulfilled_request = {
            'id' : comment.submission.id,
            'request_permalink' :  request_info["permalink"],
            'imt_permalink' : comment.submission.permalink,
            'template_url' : "TODO",
            'fulfilled_by' : comment.author.id
        }
        self.bot.data_access.put_item(DataAccess.Tables.TEMPLATE_REQUESTS, fulfilled_request)
        del active_requests[active_request_id]
        self.bot.data_access.set_variable("templaterequest_active_requests", active_requests)

        ######################### Update Comments, Submissions, and Flairs ########################

        ### Reply to IMT comment
        comment_reply = "Your template was approved! You have been awarded **{}** points".format(total_points) 
        if is_new_approved_user:
            comment_reply += "\n\n*You are now approved for template request fulfillment, and will no longer " + \
                "require moderator approval for provided templates.*"
        comment.reply(comment_reply)

        ### Reply to the original comment(s) requesting the IMT Template
        for request_comment_id in request_info['requestor_comments']:
            request_comment = self.bot.reddit.comment(id=request_comment_id)
            request_comment_reply = "The template has been provided by u/" + user_data['username'] + "!\n\n" + \
               "TODO: Add link to the template here"
            request_comment.reply(request_comment_reply)

        ### Update the bot's sticky post to say the template was fulfilled
        # TODO

        ### Flair the template request as fulfilled
        # TODO

        
    def process_fulfilled_reply(self, comment):
        """
        Processes a reply made to the bot in a template request post that has already been filled
        """
        pass # TODO

    def is_active_request_reply(self, comment):
        """
        Returns true if the comment is a reply to the bot on an active template request post
        """
        active_requests = self.bot.data_access.get_variable("templaterequest_active_requests")
        active_ids = []
        for request_dict in active_requests.values():
            active_ids.append(request_dict["imt_request_submission_id"])

        return self.__is_request_reply(comment, active_ids)

    def is_fulfilled_request_reply(self, comment):
        """
        Returns true if the comment is a reply to the bot's sticky post on a fulfilled request
        """
        fulfilled_ids = [] # TODO
        return self.__is_request_reply(comment, fulfilled_ids)

    def __is_request_reply(self, comment, request_submission_ids):
        """
        Helper method for is_active_request_reply and is_fulfilled_request_reply
        """
        if comment.parent().author == None:
            return False # Author can be none if a comment was deleted somehow, so add a check just to be safe
        elif comment.parent().author.id != self.bot.reddit.user.me().id:
            return False # The reply wasn't made to the bot
        else:
            # Return true if the comment is a reply to the bot, and the comment's submission is one of the requests in the given list
            submission_id = comment.submission.id
            return submission_id in request_submission_ids