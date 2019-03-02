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


        # TODO: If the user has already maxed out their gifts to the user today, then don't allow it

        # Bring the gift amount down to the maximum if it's too high
        amount_to_send = min(gift_amount, GiftFeature.GIFT_MAX)
        
        # Check to make sure the sender has enough points
        if amount_to_send > sender['total_score']:
            self.bot.reply(comment, "You don't have enough points to gift that much!\n\n" + \
                "You have **" + str(sender['total_score']) + "** points.")
            return

        # Transfer the points
        self.__transfer_points(sender, recipient, amount_to_send)

    def __transfer_points(self, sender, recipient, amount):
        """
        Helper function for __process_gift. Makes the transfer of points from one user to another
        """
       
        ####################################################################
        ### Determine how many points to draw from the submission score, ###
        ### and how many to draw from the distribution score             ###
        ####################################################################
        split_amt = math.ceil(amount / 2)
        if sender['submission_score'] >= split_amt and sender['distribution_score'] >= split_amt:
            distribution_amt = split_amt
            submission_amt   = amount - split_amt # Subtract from total in case we have an odd number of points
        elif sender['submission_score'] < split_amt:
            # If the submission score is below the threshold, then use all of them
            submission_amt = int(sender['submission_score'])
            distribution_amt = amount - submission_amt
        elif sender['distribution_score'] < split_amt:
            # If the distribution score is below the threshold, then use all of them
            distribution_amt = int(sender['distribution_score'])
            submission_amt   = amount - dsitribution_amt
        else:
            # Shouldn't get here, since we've already checked for a sufficient balance
            raise RuntimeError("Not enough points to send gift!")

        #############################################
        ### Transfer the amounts to the recipient ###
        #############################################

        # Deduct from sender
        sender_key = {'user_id' : sender['user_id']}
        sender_update_expr = "set distribution_score = :dist, submission_score = :sub, total_score = :tot"
        sender_expr_attrs = {
            ":dist" : decimal.Decimal(int(sender['distribution_score']) - distribution_amt),
            ":sub"  : decimal.Decimal(int(sender['submission_score']) - submission_amt),
            ":tot"  : decimal.Decimal(int(sender['total_score']) - amount)
        }
        self.bot.data_access.update_item(DataAccess.Tables.USERS, sender_key, sender_update_expr, sender_expr_attrs)

        # Add to the recipient
        recip_key = {'user_id' : recipient['user_id']}
        recip_update_expr = "set distribution_score = :dist, submission_score = :sub, total_score = :tot"
        recip_expr_attrs = {
            ":dist" : decimal.Decimal(int(recipient['distribution_score']) + distribution_amt),
            ":sub"  : decimal.Decimal(int(recipient['submission_score']) + submission_amt),
            ":tot"  : decimal.Decimal(int(recipient['total_score']) + amount)
        }
        self.bot.data_access.update_item(DataAccess.Tables.USERS, recip_key, recip_update_expr, recip_expr_attrs)

        # TODO: Update gifts dictionary

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