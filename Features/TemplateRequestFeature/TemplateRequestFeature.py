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

        # An active request is one that has already been received by the bot, and 
        # a submission has been posted to the subreddit with the request information.
        self.active_requests = {}

        # Get the flair ID
        self.flair_id = self.bot.data_access.get_variable("templaterequest_flair_id")


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

        self.prev_update_time = int(time.time())

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
            request_dict = pending_requests[submission_id]
            subreddit_name = request_dict["subreddit_name"]
            submission = self.bot.reddit.submission(id=submission_id)

            # Crosspost the post to the IMT subreddit
            request_submission = submission.crosspost(
                self.bot.subreddit,
                title = "New template request from r/" + str(request_dict["subreddit_name"]) + "!")

            request_submission.mod.flair(text='Template Request')

            # Create an entry in active_requests
            active_request_dict = request_dict
            active_request_dict["imt_request_submission_id"] = request_submission.id
            active_request_dict["imt_request_submission_title"] = request_submission.title

            active_requests[submission_id] = active_request_dict

        # Update the active requests
        self.bot.data_access.set_variable("templaterequest_active_requests", active_requests)
        self.bot.data_access.set_variable("templaterequest_pending_requests", {})

        self.prev_pending_requests_post_time = time.time()

