from Features.Feature import Feature
import praw
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import json
from Features.ScoreboardFeature.Tracker import Tracker
from Features.ScoreboardFeature import Debug
import re
import time
from Utils.DataAccess import DataAccess
import os

class ScoreboardFeature(Feature):
    """
    A feature that keeps score for the subreddit users
    """
    
    # Text constants
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
                           "[Join us on discord!](https://discordapp.com/invite/q3mtAmj)" + \
                           "\n\n^(InsiderMemeBot v1.1)"


    # When true, all comment replies will just be printed to stdout, instead of actually replying
    DEBUG_MODE_NO_COMMENT = False

    # Allow any submission as an example
    DEBUG_MODE_ALLOW_ALL_EXAMPLES = False
    

    def __init__(self, reddit, subreddit_name, data_access):
        super(ScoreboardFeature, self).__init__(reddit, subreddit_name) # Call super constructor
        
        # Initialize the data access
        self.data_access = data_access
        
        # The score tracker
        self.tracker = Tracker(self.reddit, self.data_access) 

        self.last_update = 0
                
    def process_submission(self, submission):
        # The sticky reply to respond with
        reply_str = ScoreboardFeature.NEW_SUBMISSION_REPLY

        bot_reply = None

        # Create an account for the user if they don't have one
        if not self.is_user(submission.author):
            self.create_new_user(submission.author)
            
            reply_str = reply_str + "\n\n\n\n*New user created for " + submission.author.name + "*"
        # Reply to the submission
        if not ScoreboardFeature.DEBUG_MODE_NO_COMMENT:
            bot_reply = submission.reply(reply_str)
            try:
                # Attempt to make post sticky if we have permissions to do so
                bot_reply.mod.distinguish(how='yes', sticky=True)
            except Exception as e:
                pass


        # Track the submission for scoring
        self.tracker.track_submission(submission, bot_reply.id)
        print("New submission: " + str(submission.title))
                
        
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
            self.reply_to_comment(comment, "There is already an account for " + author.name)
            return

        if self.create_new_user(author):
            # Respond to the comment that the account was created
            self.reply_to_comment(comment, "New user registered for " + author.name) 
        else:
            # Shouldn't happen, hopefully
            self.reply_to_comment(comment, "Something went wrong, please try again!")

    def process_score(self, comment):
        """
        Update and report the score for the user
        """
        
        ### Submission Score ###
        author_id = comment.author.id
        key_condition_expr = Key('user_id').eq(author_id)
        response = self.data_access.query(DataAccess.Tables.USERS, key_condition_expr)

        if response != None:                

            # If there isn't a user, then reply as such and return.
            if len(response['Items']) == 0:
                self.reply_to_comment(comment, "You don't have an account yet!\n\n" + \
                    "Reply with '!new' to create one.")
                return

            user = response['Items'][0]
           
           ### Compute submission score ###
            # The scores for any items that have already finished tracking
            submission_score_from_db = user['submission_score']

            # The scores for items that are currently being tracked
            submission_score_from_tracking = \
                self.tracker.get_tracking_submission_score(author_id)

            total_submission_score = submission_score_from_db + submission_score_from_tracking

            ### Compute distribution score ###
            distribution_score_from_db = user['distribution_score']
            distribution_score_from_tracking = \
                self.tracker.get_tracking_example_score(author_id)

            total_distribution_score = distribution_score_from_db + distribution_score_from_tracking

            # The scores for items that are 

            # Respond to the comment that the account was created
            self.reply_to_comment(comment, "**Score for " + comment.author.name + ":**\n\n" + \
                "  Your submission score is " + str(total_submission_score) + "\n\n" + \
                "  Your distribution score is " + str(total_distribution_score) + "\n\n" + \
                "**Total Score:      " + str(total_submission_score + total_distribution_score) + "**")
        else:
            print("!!!!! Could not get score!")
            print("    Comment ID: " + str(comment.id))
            print("    Author: " + str(author_id))

    def process_example(self, comment):
        """
        Processes the "!example" command
        """
        print("Processing example: " + str(comment.body))

        if not self.is_user(comment.author):
            self.reply_to_comment(comment, "You don't have an account yet!\n\n" + \
                "Reply with '!new' to create one.")
            return

        url_matches = re.findall(r"https\:\/\/www\.[a-zA-Z0-9\.\/_\\]+", comment.body)

        if url_matches is None or len(url_matches) == 0:
            print("Invalid example: " + comment.body)
            print("\n")
            self.reply_to_comment(comment, "Thanks for the example, but I couldn't find any Reddit post " + \
                "from the URL tht you provided. Only links to example posts on other subreddits can be scored.")
            return

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
            print("\n")
            self.reply_to_comment(comment, "Thanks for the example, but there are too many URLS in your comment.\n\n" + \
               "Please only include one link per example, so I can score it properly.")
            return

        # At this point, there is only one unique url
        example_url = unique_urls[0]

        try:
            # Try to get the example submission, and track it
            submission_id = praw.models.Submission.id_from_url(example_url)
            example_submission = self.reddit.submission(id=submission_id)

            if not ScoreboardFeature.DEBUG_MODE_ALLOW_ALL_EXAMPLES:
                # Verify that the example was posted by the comment author
                if(comment.author.id != example_submission.author.id):
                    print("Comment author mismatch!")
                    self.reply_to_comment(comment, "Thanks for the example, but only submissions that you posted yourself can be scored.")
                    return
                
                # Verify that the example isn't already being tracked
                if self.tracker.is_example_tracked(example_submission.id):
                    self.reply_to_comment(comment, "The example you provided is already being scored!")
                    return

                # Verify that the post isn't too old to be tracked
                cur_time = int(time.time())
                if cur_time > example_submission.created_utc + self.tracker.TRACK_DURATION_SECONDS:
                    self.reply_to_comment(comment, "The example you provided is too old for me to track the score!\n\n" + \
                        "Only examples that were posted within the last 24 hours are valid.")
                    return


            # If the example passed all the verification, track it!
            parent_submission = comment.submission
            bot_reply = self.reply_to_comment(comment, "Thank you for the example!\n\n\n\n" + \
                "I'll check your post periodically until the example is 24 hours old, and update your score. " + \
                "A 20% commission will go to the creator of the meme template.")

            self.tracker.track_example(parent_submission, example_submission, comment.author.id, bot_reply.id)

            self.comment_on_example(parent_submission, example_submission)

        except praw.exceptions.ClientException as e:
            print("Could not get submission from URL: " + example_url)
            self.reply_to_comment(comment, "Thanks for the example, but I couldn't find any Reddit post " + \
                "from the URL tht you provided. Only links to example posts on other subreddits can be scored.")
            return

        print("\n")

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
        if self.data_access.put_item(DataAccess.Tables.USERS, new_user_item):
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
        response = self.data_access.query(DataAccess.Tables.USERS, Key('user_id').eq(author.id))
        num_matches = len(response['Items'])
        
        # If there is a match, then the author is already a user
        return num_matches > 0

    def is_direct_reply(self, comment):
        """
        Returns true if this comment is a direct reply to InsiderMemeBot
        """
        return comment.parent().author.id == self.reddit.user.me().id


    def reply_to_comment(self, comment, reply):
        """
        Replies to the comment with the given reply
        comment: The PRAW Comment object to reply to
        reply: The string with which to reply

        Returns the Comment made by the bot
        """

        # Add footer
        reply_with_footer = reply + "\n\n\n\n^(InsiderMemeBot v1.1)"

        # The reply Comment made by the bot
        bot_reply = None

        if not ScoreboardFeature.DEBUG_MODE_NO_COMMENT:
            bot_reply = comment.reply(reply_with_footer)
        
        print("-" * 40)
        print("Comment: " + comment.body)
        print("Reply: " + reply_with_footer)
        print("-" * 40)

        return bot_reply

    def comment_on_example(self, original, example):
        """
        Adds a comment to the example, with a reference to the template
        original: The Submission of the original template
        example:  The Submission of the posted example
        """

        # This functionality should ONLY be activated in deployment, not beta testing.
        reply = "[Template](" + original.permalink + ")"
        if not os.environ['IMT_TEST_MODE']:
            print("Replying to example: " + example.permalink)
            example.reply(reply)
        else:
            # If we're in test mode, just print that we would be replying
            print("[IMT_TEST]: Mock reply for example post: " + example.permalink)
            print("[IMT_TEST]:    Reply: " + reply)

    def update(self):
        # Update the submissions being tracked
        cur_time = int(time.time())
        if cur_time >= self.last_update + self.tracker.SCORE_UPDATE_INTERVAL:
            self.tracker.update_scores()   
            self.last_update = cur_time