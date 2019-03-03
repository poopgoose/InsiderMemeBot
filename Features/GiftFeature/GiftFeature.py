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
    GIFT_RESET_TIME = 24 * 60 * 60 # How long, in seconds, before a gift can be sent to a user again.

    def __init__(self, bot):
        super(GiftFeature, self).__init__(bot)


    def process_comment(self, comment):
        # Determine if the comment is the action
        if comment.body.strip().startswith("!gift"):
            gift_amount, validation_message = self.__validate_comment(comment)

            if validation_message != "":
                # Validation failed.
                self.bot.reply(comment, validation_message)
            else:
                # Now that we've validated the comment and know the gift amount, we can continue with processing
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
            return(0, "Unable to process your gift command! The correct syntax is '!gift <amount>'\n\n" + \
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
            # Update with the fresh data
            sender = self.bot.data_access.query(DataAccess.Tables.USERS, Key('user_id').eq(sender['user_id']))['Items'][0]

        if not 'gifts' in recipient:
            self.__initialize_gift_data(recipient['user_id'])
            # Update with the fresh data
            recipient = self.bot.data_access.query(DataAccess.Tables.USERS, Key('user_id').eq(recipient['user_id']))['Items'][0]

        # If the sender has already given a gift to the recipient in the last 24 hours, then they can't send another
        sent_gift_dict = sender['gifts']['sent']
        if recipient['user_id'] in sent_gift_dict:
            last_gift_time = sent_gift_dict[recipient['user_id']]['send_time']
            time_since_gift = int(time.time()) - last_gift_time
            if time_since_gift < GiftFeature.GIFT_RESET_TIME:
                # Compute how much time the sender needs to wait until they can send another gift to the user
                remaining_time = seconds = GiftFeature.GIFT_RESET_TIME - time_since_gift
                m, s = divmod(remaining_time, 60)
                h, m = divmod(m, 60)
                self.bot.reply(comment, "You have already sent a gift to " + recipient['username'] + " today!" + \
                    "You may send another gift in **" + str(h) + "** hours and **" + str(m) + "** minutes.")
                return

        # Bring the gift amount down to the maximum if it's too high
        amount_to_send = min(gift_amount, GiftFeature.GIFT_MAX)
        
        # Check to make sure the sender has enough points
        if amount_to_send > sender['total_score']:
            self.bot.reply(comment, "You don't have enough points to give that much!  \n  " + \
                "You have **" + str(sender['total_score']) + "** points that you can give.  \n  " + \
                "*You can only give points from posts that have finished scoring, so this number may be " + \
                "smaller than your reported score if you have recently submitted a template or example*")
            return

        # Transfer the points
        self.__transfer_points(sender, recipient, amount_to_send)

        # Update with the fresh data
        sender = self.bot.data_access.query(DataAccess.Tables.USERS, Key('user_id').eq(comment.author.id))['Items'][0]

        # Reply with a comment
        if amount_to_send == gift_amount:
            self.bot.reply(comment, "Your gift of **" + str(amount_to_send) + "** points was sent to " + recipient['username'] + "!  \n  " + \
                "Your giftable point balance is now **" + str(sender['total_score']) + "** points.  \n  ")
        else:
            self.bot.reply(comment, "Your gift amount was too high, so I sent the maximum gift of **" + \
                str(GiftFeature.GIFT_MAX) + "** points instead!\n\n" + \
                "Your giftable point balance is now **" + str(sender['total_score']) + "** points.")

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

        ### Updated sender dictionary ###
        updated_sender_dict = sender['gifts']
        sent_item_dict = updated_sender_dict['sent']
        sent_item_dict[recipient['user_id']] = {
            "amount" : decimal.Decimal(amount),
            "send_time" : decimal.Decimal(int(time.time()))
        }
        updated_sender_dict['sent'] = sent_item_dict

        ### Deduct from sender ###
        sender_key = {'user_id' : sender['user_id']}
        sender_update_expr = "set distribution_score = :dist, submission_score = :sub, total_score = :tot, gifts=:gift_dict"
        sender_expr_attrs = {
            ":dist" : decimal.Decimal(int(sender['distribution_score']) - distribution_amt),
            ":sub"  : decimal.Decimal(int(sender['submission_score']) - submission_amt),
            ":tot"  : decimal.Decimal(int(sender['total_score']) - amount),
            ":gift_dict" : updated_sender_dict
        }
        self.bot.data_access.update_item(DataAccess.Tables.USERS, sender_key, sender_update_expr, sender_expr_attrs)

        ### Updated recipient dictionary ###
        updated_receive_dict = recipient['gifts']
        receive_item_dict = updated_receive_dict['received']
        receive_item_dict[sender['user_id']] = {
            "amount" : decimal.Decimal(amount),
            "receive_time" : decimal.Decimal(int(time.time()))
        }
        updated_receive_dict['received'] = sent_item_dict

        ### Add to the recipient ###
        recip_key = {'user_id' : recipient['user_id']}
        recip_update_expr = "set distribution_score = :dist, submission_score = :sub, total_score = :tot, gifts = :gift_dict"
        recip_expr_attrs = {
            ":dist" : decimal.Decimal(int(recipient['distribution_score']) + distribution_amt),
            ":sub"  : decimal.Decimal(int(recipient['submission_score']) + submission_amt),
            ":tot"  : decimal.Decimal(int(recipient['total_score']) + amount),
            ":gift_dict" : updated_receive_dict
        }
        self.bot.data_access.update_item(DataAccess.Tables.USERS, recip_key, recip_update_expr, recip_expr_attrs)

        print(str(amount) + " points were gifted from " + sender['username'] + " to " + recipient['username'])

    def __initialize_gift_data(self, user_id):
        """
        Creates empty gift data for the user
        """
        user_key = {'user_id' : user_id}
        user_update_expr = "set gifts = :gift_dict"
        user_expr_attrs = {
            ":gift_dict" : 
            {
               "sent" : {},
               "received" : {}
            }}
        self.bot.data_access.update_item(
            DataAccess.Tables.USERS, user_key, user_update_expr, user_expr_attrs)