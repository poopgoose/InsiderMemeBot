from Features.Feature import Feature
import decimal
import praw
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import json
import re
import time
from Utils.DataAccess import DataAccess
import os

class BaseScoringFeature(Feature):
    """
    A feature that keeps score for the subreddit users
    """
    
    ### Constants ###
    NEW_SUBMISSION_REPLY = "Thank you for posting your meme template!\n\n" + \
                           "All bot commands must be *direct* replies to this comment. " + \
                           "\n\n" + \
                           "**TO DISTRIBUTE THIS TEMPLATE:**\n\n" + \
                           "Reply with  `!example`, followed by a link to your example post. Only links to posts in other subreddits can be scored. " + \
                           "Imgur examples are appreciated, but will not give you any points!\n\n" + \
                           "**RULES FOR DISTRIBUTION:**\n\n" + \
                           "1. The link you provide after `!example` **MUST** be an actual example of the template. " + \
                           "Links to unrelated content will be removed by the mods, and repeated offenses " + \
                           "may result in your score being reset to 0 or being banned from the subreddit.\n\n" + \
                           "2. Examples must be your own posts to be scored. Links to someone else's posts are okay, but they won't get you any points.\n\n" + \
                           "3. Example posts must be less than 24 hours old to be scored.\n\n" + \
                           "\n\n" + \
                           "**If your post is not a template, it will be removed.** If you have a post based on an IMT template, " + \
                           "you may be qualified to post it on r/IMTOriginals\n\n\n\n" + \
                           "[Join us on discord!](https://discordapp.com/invite/q3mtAmj)"

    # The duration, in seconds, for which to track each post
    TRACK_DURATION_SECONDS = 24 * 60 * 60 # 24 hours (in seconds)

    # How often to check the Tracking database for expired submisisons
    CHECK_EXPIRED_INTERVAL = 2 * 60 # Every 2 minutes 

    # The amount of the distributor's score that goes to the creator
    CREATOR_COMMISSION = 0.20
    

    def __init__(self, bot):
        super(BaseScoringFeature, self).__init__(bot) # Call super constructor

        self.last_expire_check = 0 # The last time that we checked for expired submissions

    def process_submission(self, submission):
        # The sticky reply to respond with
        reply_str = BaseScoringFeature.NEW_SUBMISSION_REPLY

        bot_reply = None

        # Create an account for the user if they don't have one
        if not self.is_user(submission.author):
            self.create_new_user(submission.author)            
            reply_str = reply_str + "\n\n\n\n*New user created for " + submission.author.name + "*"
        
        # Reply to the submission
        bot_reply = self.bot.reply(submission, reply_str, is_sticky=True) #submission.reply(reply_str)

        # Add the submission to the Tracking Database for Tracker to pick up
        item={
            'submission_id' : submission.id,
            'author_id': submission.author.id,
            'expire_time' : decimal.Decimal(submission.created_utc + BaseScoringFeature.TRACK_DURATION_SECONDS),
            'is_example' : False,
            'template_id' : " ",
            'distributor_id' : " ",
            'bot_comment_id' : bot_reply.id,
            'last_update' : 0,
            'score' : 0
            }
        try:
            self.bot.data_access.put_item(DataAccess.Tables.TRACKING, item)
        except Exception as e:
            print("!!!! Could not add submission for tracking! " + str(submission.id))
            print(e)

        print("Processed new submission: " + str(submission.title))
                
        
    def process_comment(self, comment):        

        # Ignore any comment that isn't a direct reply to the top-level InsiderMemeBot comment
        # for a submission
        if not self.is_direct_reply(comment):
            return

        # Determine if the comment is an action
        if comment.body.strip() == "!new":
            self.process_new(comment)
        elif comment.body.strip() == "!score":
            self.process_score(comment)
        elif comment.body.strip().startswith("!example"):
            self.process_example(comment)
                
    ############# Process actions #############
    
    def process_new(self, comment):
        author = comment.author
        if self.is_user(author):
            # The user already has an account
            self.bot.reply(comment, "There is already an account for " + author.name)
            return

        if self.create_new_user(author):
            # Respond to the comment that the account was created
            self.bot.reply(comment, "New user registered for " + author.name) 
        else:
            # Shouldn't happen, hopefully
            self.bot.reply(comment, "Something went wrong, please try again!")

    def process_score(self, comment):
        """
        Update and report the score for the user
        """

        try:
            author_id = comment.author.id
            
            ##############################################        
            ### Get the score stored in the User table ###
            ##############################################
            key_condition_expr = Key('user_id').eq(author_id)
            response = self.bot.data_access.query(DataAccess.Tables.USERS, key_condition_expr)
            # If there isn't a user, then reply as such and return.
            if len(response['Items']) == 0:
                self.bot.reply(comment, "You don't have an account yet!\n\n" + \
                    "Reply with '!new' to create one.")
                return
            user = response['Items'][0]
            submission_score_from_users = user['submission_score']
            distribution_score_from_users = user['distribution_score']

            ##########################################################
            ### Add scores currently tracked in the Tracking table ###
            ##########################################################
            submission_score_from_tracking = 0
            distribution_score_from_tracking = 0
            response = self.bot.data_access.scan(DataAccess.Tables.TRACKING)
            for item in response['Items']:
                if item['author_id'] == author_id:
                    if item['is_example']:
                        distribution_score_from_tracking = distribution_score_from_tracking + int(item['score'])
                    else:
                        submission_score_from_tracking = submission_score_from_tracking + int(item['score'])

            ############################
            ###  Report Total scores ###
            ############################
            total_submission_score = submission_score_from_users + submission_score_from_tracking
            total_distribution_score = distribution_score_from_users + distribution_score_from_tracking 

            # Respond to the comment that the account was created
            self.bot.reply(comment, "**Score for " + comment.author.name + ":**\n\n" + \
                "  Your submission score is " + str(total_submission_score) + "\n\n" + \
                "  Your distribution score is " + str(total_distribution_score) + "\n\n" + \
                "**Total Score:      " + str(total_submission_score + total_distribution_score) + "**")
        except Exception as e:
            print("!!!!! Could not get score!")
            print("    Comment ID: " + str(comment.id))
            print("    Author: " + str(author_id))
            print("Error: " + str(e))

    def process_example(self, comment):
        """
        Processes the "!example" command
        """
        print("Processing example: " + str(comment.body))
  
        # Check to make sure the example is valid. If not, respond with the reason why it's invalid.
        example_submission, validation_msg = self.__validate_example(comment)
        if example_submission is None:
            self.bot.reply(comment, validation_msg)
            return

        # At this point, we know that the example is valid
        try:        
            # Even if the example is valid, we need to check that the template submission itself hasn't been deleted
            template_submission = comment.submission
            if template_submission.author is None:
                self.bot.reply(comment, "I cannot track examples for templates that have been deleted!")
                return

            # At this point, the example and the template are both valid.
            bot_reply = self.bot.reply(comment, "Thank you for the example!\n\n\n\n" + \
                "I'll check your post periodically until the example is 24 hours old, and update your score. " + \
                "A 20% commission will go to the creator of the meme template.")

            item = {
               'submission_id' : example_submission.id,
               'author_id' : comment.author.id,
               'expire_time' : decimal.Decimal(example_submission.created_utc + self.TRACK_DURATION_SECONDS),
               'is_example' : True,
               'template_id' : template_submission.id,
               'template_author_id' : template_submission.author.id,
               'bot_comment_id' : bot_reply.id,
               'last_update' : 0,
               'score' : 0
            }
            success = self.bot.data_access.put_item(DataAccess.Tables.TRACKING, item)
            if not success:
                print("!!!!! Unable to add example to tracking database: " + example_submission.id)

            self.comment_on_example(template_submission, example_submission)

        except praw.exceptions.ClientException as e:
            print("Could not get submission from URL: " + example_url)
            self.bot.reply(comment, "Thanks for the example, but I couldn't find any Reddit post " + \
                "from the URL tht you provided. Only links to example posts on other subreddits can be scored.")
            return

        print("\n")

    def __validate_example(self, comment):
        """
        Helper method for process_comment.

        Given the comment text, this function parses out the example URL, and determines if it's 
        a valid example submission.

        The function returns two values: (submission, msg)

        If the exmaple is valid, then submission is the praw Submission object of the posted example.
        If the example is invalid, then the submission is None, and "msg" is the string response to 
        reply to the comment with, explaining why it's invalid. 
        """

        # First, check to see if teh submitter is a user
        if not self.is_user(comment.author):
            print("No account for user: " + str(comment.author.name))
            return (None, "You don't have an account yet!\n\nReply with '!new' to create one.")

        # Next, parse the example for URLs
        url_matches = re.findall(r"https\:\/\/www\.[a-zA-Z0-9\.\/_\\]+", comment.body)

        if url_matches is None or len(url_matches) == 0:
            print("Invalid example: " + comment.body)
            return (None, "Thanks for the example, but I couldn't find any Reddit post " + \
                "from the URL tht you provided. Only links to example posts on other subreddits can be scored.")
            
        # Remove duplicate submissions. This can happen if the actual hyperlink is used as the comment body 
        # TODO: This is a messy workaround. It would be better to use an HTML parser or something to grab
        # the actual URL from a link, and ignore the text itself.
        unique_urls = []
        seen_ids = []

        for url in url_matches:
            try:
                submission_id = praw.models.Submission.id_from_url(url)
                if submission_id not in seen_ids:
                    # The URL is a submission that hasn't been encountered yet
                    unique_urls.append(url)
                    seen_ids.append(submission_id)

            except praw.exceptions.ClientException as e:
                # The URL isn't to a reddit submission, so just add it
                unique_urls.append(url)
                
        if len(unique_urls) > 1:
            print("Invalid example: " + comment.body)
            return (None, "Thanks for the example, but there are too many URLS in your comment.\n\n" + \
               "Please only include one link per example, so I can score it properly.")
            return

        # At this point, there is only one unique url
        example_url = unique_urls[0]

        try:
            # Try to get the example submission
            submission_id = praw.models.Submission.id_from_url(example_url)
            submission = self.bot.reddit.submission(id=submission_id)

            if submission.author is None:
                print("Submission has been deleted: " + str(submission))
                return(None, "The example that you posted has been deleted, so I cannot track it!")

             # Verify that the example was posted by the comment author
            if(comment.author.id != submission.author.id):
                print("Comment author mismatch!")
                return(None, "Thanks for the example, but only submissions that you posted yourself can be scored.")
                            
            # Verify that the example isn't already being tracked
            response = self.bot.data_access.query(DataAccess.Tables.TRACKING, Key('submission_id').eq(submission_id))
            for item in response['Items']:
                if item['is_example'] == True:
                    return(None, "The example you provided is already being scored!")
                
            # Verify that the post isn't too old to be tracked
            cur_time = int(time.time())
            if cur_time > submission.created_utc + self.TRACK_DURATION_SECONDS:
                return (None, "The example you provided is too old for me to track the score!\n\n" + \
                    "Only examples that were posted within the last 24 hours are valid.")
            
            # Validation passed, so return the Submission
            return (submission, "")

        except praw.exceptions.ClientException as e:
            print("Could not get submission from URL: " + example_url)
            return(None, "Thanks for the example, but I couldn't find any Reddit post " + \
                "from the URL tht you provided. Only links to example posts on other subreddits can be scored.")

        
    ################## Helper functions ##################
    def create_new_user(self, redditor):
        """
        Creates a new user for the comment author.
        Returns True if successful, false otherwise

        redditor: The Redditor instance to make a user for
        """
        
        # If we get here, then the user doesn't have an account already, so we create one
        print("Creating user: " + str(redditor))

        new_user_item = {
            'user_id' : redditor.id,
            'username' : redditor.name,
            'submission_score' : 0,
            'distribution_score' :0
        }
        if self.bot.data_access.put_item(DataAccess.Tables.USERS, new_user_item):
            print("Created user: " + str(redditor))
            return True
        else:
            print("Failed to create user: " + str(redditor))
            return False

    def is_user(self, author):
        """
        Returns true if the author is already a user in the DynamoDB database.
        """
        
        # Query the table to get any user with a user_id matching the author's id
        response = self.bot.data_access.query(DataAccess.Tables.USERS, Key('user_id').eq(author.id))
        num_matches = len(response['Items'])
        
        # If there is a match, then the author is already a user
        return num_matches > 0

    def is_direct_reply(self, comment):
        """
        Returns true if this comment is a direct reply to InsiderMemeBot
        """
        return comment.parent().author != None and comment.parent().author.id == self.bot.reddit.user.me().id

    def comment_on_example(self, original, example):
        """
        Adds a comment to the example, with a reference to the template
        original: The Submission of the original template
        example:  The Submission of the posted example
        """

        # This functionality should ONLY be activated in deployment, not beta testing.
        reply = "[Template](" + original.permalink + ")"
        if not self.bot.test_mode:
            print("Replying to example: " + example.permalink)
            self.bot.reply(example, reply, suppress_footer = True)
        else:
            # If we're in test mode, just print that we would be replying
            print("[IMT_TEST]: Mock reply for example post: " + example.permalink)
            print("[IMT_TEST]:    Reply: " + reply)

    def update(self):
        # TODO - Check if any examples need to be deleted
        cur_time = int(time.time())
        if cur_time - self.last_expire_check < BaseScoringFeature.CHECK_EXPIRED_INTERVAL:
            # Not time to check yet, so just return
            return

        # Check the database for expired posts
        expired_items = []
        tracked_items = self.bot.data_access.scan(DataAccess.Tables.TRACKING)['Items']

        for item in tracked_items:
            if item['expire_time'] <= item['last_update']:
                self.untrack_item(item)

        self.last_expire_check = cur_time

    def untrack_item(self, item):
        """
        Untracks an expired submission or example.

        item: The item from the Tracking database that has expired
        """

        print("-" * 40)
        print("Item has expired: " + str(item))

        ############################################
        ### Update Users database with the score ###
        ############################################
        user_key = item['author_id']
        creator_commission = int(int(round(item['score']) * self.CREATOR_COMMISSION)) # The commision of the score that would go to the creator. Only used when item['is_example'] is True
        if item['is_example']:
            # For examples, the commission for the template creator needs to be deducted from the score
            field_name = 'distribution_score'
            score = int(item['score']) - creator_commission
        else:
            field_name = 'submission_score'
            score = int(item['score'])

        # Update the score for the user who submitted the submission/example
        user_key = {'user_id' : item['author_id']}
        user_update_expr = "set {} = {} + :score".format(field_name, field_name)
        user_expr_attrs = {":score" : decimal.Decimal(score)}
        self.bot.data_access.update_item(
            DataAccess.Tables.USERS, user_key, user_update_expr, user_expr_attrs)

        self.update_total_score(item['author_id'])

        if item['is_example']:
            # Update score for the template creator as well
            creator_key = {'user_id' : item['template_author_id']}
            creator_update_expr = "set submission_score = submission_score + :score"
            creator_expr_attrs = {":score" : decimal.Decimal(creator_commission)}
            self.bot.data_access.update_item(
                DataAccess.Tables.USERS, creator_key, creator_update_expr, creator_expr_attrs)

            self.update_total_score(item['template_author_id'])

        ##########################
        ### Trigger Callback   ###
        ##########################
        # Trigger the callback so that other features have a chance to process the item
        # before deleting it
        self.bot.finished_tracking_callback(item)

        ############################################
        ###   Remove from the Tracking Database  ###
        ############################################
        self.bot.data_access.delete_item(
            DataAccess.Tables.TRACKING, {'submission_id' : item['submission_id']})

        ############################################
        ###       Update the bot comment         ###
        ############################################
        bot_comment = self.bot.reddit.comment(id=item['bot_comment_id'])

        # Construct the message to update the comment with
        if item['is_example']:
            message = "**Update**\n\nYour example has finished scoring! It received a total of **" + \
            str(int(item['score'])) + "** points.\n\n"
            if item['author_id'] != item['template_author_id']:
                message = message + "You received **" + str(score) + "** points, and **" + \
                 str(creator_commission) + "** of the points went to the creator of the template."
            else:
                message = message + "Since this is your template, you receive all of the points! **" + \
                str(score) + "** points have gone to your distribution score, and **" + \
                str(creator_commission) + "** points have gone to your submission score."
        else:
            message ="**Update**\n\nYour template has finished scoring! You received **" + \
            str(int(item["score"])) + "** points.\n\n*This does not include points gained from " + \
            "example commissions. Commission scores will be reported in the comments beneath the examples.*"
          
        edited_body = bot_comment.body + "\n\n" + message
        try:
            bot_comment.edit(edited_body)
        except Exception as e:
            print("!!!!Unable to edit bot comment!")
            print("    Comment ID: " + bot_comment.id)
            print("    Error: " + str(e))

    def update_total_score(self, user_id):
        """
        Helper function for untrack_item. Updates the "total_score" column in the database for the given user
        """

        user_item = self.bot.data_access.query(DataAccess.Tables.USERS, 
            key_condition_expr = Key('user_id').eq(user_id))['Items'][0]

        total_score = int(user_item['distribution_score']) + int(user_item['submission_score'])


        user_key = {'user_id' : user_id}
        user_update_expr = "set total_score = :total"
        user_expr_attrs = {":total" : decimal.Decimal(total_score)}
        self.bot.data_access.update_item(
            DataAccess.Tables.USERS, user_key, user_update_expr, user_expr_attrs)