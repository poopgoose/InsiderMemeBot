from Features.Feature import Feature
import decimal
import praw
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import time
from Utils.DataAccess import DataAccess
import os

class GiftFeature(Feature):
    """
    This class supports the !gift command, allowing one user
    to award points to another user by replying to their post or the
    comment.
    """


    def __init__(self, bot):
        super(GiftFeature, self).__init__(bot)


    def process_comment(self, comment):
        # Determine if the comment is the action
        if comment.body.strip().startswith("!gift"):
            print("GIFT!")

            if comment.parent().author == None or comment.parent().author.id == self.bot.reddit.user.me().id:
                print("Can't gift to a deleted post or the bot!")
            elif comment.parent().author.id == comment.author.id:
                print("Can't gift to yourself!")