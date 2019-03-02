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
            
            gift_amount, validation_message = self.__validate_comment(comment)
            if validation_message != "":
                # Validation failed.
                self.bot.reply(comment, validation_message)


    def __validate_comment(self, comment):
        """
        Validates the !gift command. Returns the amount to gift, and the validation message, if any.
        Successful validation can be determined if the validation message is an empty string.

        comment: The praw Comment with the gift command to validate
        """

        # 1. Make sure the user has an account
        if not self.bot.is_user(comment.author):
            print("GiftFeature: No account for user: " + str(comment.author.name) + ". Comment ID: " + comment.id)
            return (0, "You can't give points because you don't have an account yet!\n\nReply with '!new' to create one.")

        # 2. Make sure that the command wasn't a reply to a deleted post or comment
        if comment.parent().author == None:
            print("GiftFeature: Cannot gift points to deleted post. Comment ID: " + comment.id)
            return(0, "The author has deleted their post, so it cannot be gifted points.")

        # 3. Make sure that the gift recipient isn't the same user
        if comment.parent().author.id == comment.author.id:
            print("GiftFeature: Unable to gift points to same user. Comment ID: " + comment.id)
            return(0, "You can't send a gift to yourself!")

        # 4. Make sure that the gift isn't to the bot
        if comment.parent().author.id == self.bot.reddit.user.me().id:
            print("GiftFeature: Unable to gift points to bot account. Comment ID: " + comment.id)
            return(0, "Thanks for the thought, but I'm a bot and can't accept gifts!")

        # 5. Make sure that the gift amount can be parsed from the command
