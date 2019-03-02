from Features.Feature import Feature
import decimal
import praw
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import time
from Utils.DataAccess import DataAccess
import os
import re

class GiftFeature(Feature):
    """
    This class supports the !gift command, allowing one user
    to award points to another user by replying to their post or the
    comment.
    """


    # Constants
    GIFT_MAX = 100 # The maximum amount that can be sent in a gift

    def __init__(self, bot):
        super(GiftFeature, self).__init__(bot)


    def process_comment(self, comment):
        # Determine if the comment is the action
        if comment.body.strip().startswith("!gift"):
            gift_amount, validation_message = self.__validate_comment(comment)

            if validation_message != "":
                # Validation failed.
                self.bot.reply(comment, validation_message)

            # Now that we've validated the comment and know the gift amount, we can validate the gift itself
            self.__process_gift(comment, gift_amount)


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

        # 4. Make sure that the recipient has an account
        if not self.bot.is_user(comment.parent().author):
            print("GiftFeature: Unable to gift points to user without account. Comment ID: " + comment.id)
            return(0, "I couldn't send your gift, because the author doesn't have an account yet!")

        # 5. Make sure that the gift isn't to the bot. Gifting to bot is permitted in test mode
        if not self.bot.test_mode:
            if comment.parent().author.id == self.bot.reddit.user.me().id:
                print("GiftFeature: Unable to gift points to bot account. Comment ID: " + comment.id)
                return(0, "Thanks for the thought, but I'm a bot and can't accept gifts!")

        # 6. Make sure that the gift amount can be parsed from the command
        gift_regex = "!gift\s+(\d+)\s*$"
        match = re.match(gift_regex, comment.body)
        if match == None:
            print("GiftFeature: Invalid command: " + comment.body + "   Comment ID: " + comment.id)
            return(0, "Unable to process your gift command! The correct syntax is '!gift <amount>'\n" + \
                      "Example:  !gift 10")

        gift_amount = int(match.groups()[0])
        return(gift_amount, "")

    def __process_gift(self, comment, gift_amount):
        """
        Processes the gift. This should only be called with a comment that has already passed 
        __validate_comment().

        """
        sender = self.bot.data_access.query(DataAccess.Tables.USERS, Key('user_id').eq(comment.author.id))['Items'][0]
        recipient = self.bot.data_access.query(DataAccess.Tables.USERS, Key('user_id').eq(comment.parent().author.id))['Items'][0]

        # If a user has never sent or received a gift, then new gift data will need to be created
        if not 'gifts' in sender:
            self.__initialize_gift_data(sender['user_id'])
        if not 'gifts' in recipient:
            self.__initialize_gift_data(recipient['user_id'])


    def __initialize_gift_data(self, user_id):
        """
        Creates empty gift data for the user
        """
        user_key = {'user_id' : user_id}
        user_update_expr = "set gifts = :gift_dict"
        user_expr_attrs = {
            ":gift_dict" : 
            {
               "sent" : [],
               "received" : []
            }}
        self.bot.data_access.update_item(
            DataAccess.Tables.USERS, user_key, user_update_expr, user_expr_attrs)