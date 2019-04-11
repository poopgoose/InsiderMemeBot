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

    def update(self):
        """
        Updates the template request feature
        """
        cur_time = time.time()
        if cur_time < self.prev_update_time + TemplateRequestFeature.UPDATE_INTERVAL:
            return # Not time to update yet

        print("Updating Template Request Feature!")

        # Update the pending requests.
        # A pending request means it has been registered in the AWS Database,
        # but InsiderMemeBot has yet to create a comment with the request information.
        # Once the request comment is posted, the request is removed from the pending request
        # list, and added to the active requests list.
        # The pending requests are stored as a dictionary, keyed by the requested Submission IDs
        if cur_time < self.prev_pending_requests_post_time + TemplateRequestFeature.PENDING_REQUESTS_POST_INTERVAL:
            pending_requests = self.bot.data_access.get_variable("templaterequest_pending_requests")
            if len(pending_requests) > 0:
                self.process_pending_requests(pending_requests)

        self.prev_update_time = int(time.time())

    def process_pending_requests(self, pending_requests):
        """
        Processes the pending requests from the !IMTRequest command.
        """

        num_requests = len(pending_requests)

        if num_requests == 1:
            # Create a post for a single request
            comment_id = pending_requests.keys()[0]
            request_dict = pending_requests[comment_id]
            subreddit_name = request_dict["subreddit_name"]

            post_title = "New template request from r/" + request_dict["subreddit_name"] + "!"
            post_body = "TODO"
        else:
            # Create a post for multiple requests
            post_title = str(num_requests) + " new template requests!"

            post_body = "TODO"
            #for submission_id in pending_requests:
            #    request_dict = pending_requests[submisison_id]

            #    post_body = "[{}]({}) from r/{}, requested by u/{} Reward: {}  Filled: No".format(
            #    )




        self.prev_pending_requests_post_time = time.time()