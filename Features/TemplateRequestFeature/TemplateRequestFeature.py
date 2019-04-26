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

        # Check inbox to see if any mods have approved of any submitted requests
        self.check_inbox()      

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
                active_reuest_dict["imt_request_submission_title"] = request_submission.title

                active_requests[submission_id] = active_request_dict
            except Exception as e:
                print("!!!! Unable to process request!   Submission ID: " + str(submission_id))
                print(e)

        # Update the active requests
        self.bot.data_access.set_variable("templaterequest_active_requests", active_requests)
        self.bot.data_access.set_variable("templaterequest_pending_requests", {})
        self.prev_pending_requests_post_time = time.time()

    def process_active_reply(self, comment):
        """
        Processes a reply made to the bot in an active template request post
        """
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

            # Notify the mods
            notification_subj = "Fulfilled template request <{}>".format(comment.id)
            notification_msg = "A [template request]({}) has been fulfilled by u/{}!\n\n " + \
                "Please respond to this message with \n\n`!approve`\n\n to approve this template." + \
                "Respond with \n\n`!approve user`\n\n to approve this template and all future template " + \
                "requests fulfilled by this user.\n\n" + \
                "To reject the template, respond to this message with \n\n`!reject <message>`\n\n, where `message` " + \
                "is optional feedback to give to the user.\n\n" + \
                "Example:\n\n`!reject The template you supplied is valid, but we don't approve of links to that website`\n\n" + \
                "Everything below this line is used by the bot."

            notification_msg = notification_msg.format(comment.permalink, comment.author.name)
            for redditor in self.notified_mods:
                msg = redditor.message(notification_subj, notification_msg)
                print("Sent message: " + str(msg))
                print(vars(msg))


            #self.bot.reply(comment, "Thanks for submitting the template! A moderator will be back shortly ")
            #print("Success!") # TODO

        
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

        print("Active IDs: " + str(active_ids))
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
            print("Submission ID: " + str(submission_id))
            return submission_id in request_submission_ids

    def check_inbox(self):
        """
        Checks the inbox to see if any mods have approved of a template request fulfillment
        """
        inbox = self.bot.reddit.inbox

        #for message in inbox.messages(limit=20):
        #    print(vars(message))
        #    print(message.subject)
        #    print(message.body)
        #    print("-" * 40)