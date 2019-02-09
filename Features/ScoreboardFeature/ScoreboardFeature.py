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

class ScoreboardFeature(Feature):
    """
    A feature that keeps score for the subreddit users
    """
    
    # When true, all comment replies will just be printed to stdout, instead of actually replying
    DEBUG_MODE_NO_COMMENT = False

    # Allow any submission as an example
    DEBUG_MODE_ALLOW_ALL_EXAMPLES = False
    
    # Text constants
    NEW_SUBMISSION_REPLY = "Thank you for posting your meme creation!\n\n" + \
                           "Distributors may reply to this comment with the command\n\n" + \
                           "\n\n" + \
                           "!example <link to example>\n\n" + \
                           "\n\n" + \
                           "Additional text can follow the command if desired. Only examples that are direct replies to " + \
                           "this comment will be processed.\n\n" + \
                           "\n\n" + \
                           "NOTE TO DISTRIBUTORS:\n\n" + \
                           "Only links to cross-posts in other subreddits can be scored.\n\n " + \
                           "If your link leads anywhere that is NOT a subreddit or one of our approved websites, then the commment will automatically be" + \
                           "removed. This rule is to protect everyone's security.\n\n"



    def __init__(self, reddit, subreddit_name):
        super(ScoreboardFeature, self).__init__(reddit, subreddit_name) # Call super constructor
        
        # Initialize the Amazon Web Service DynamoDB.
        # For this to work, the AWS credentials must be present on the system.
        # This can be done by using "pip install awscli", and then running "aws configure"
        self.dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
        self.user_table = self.dynamodb.Table('Users')
        self.submissions_table = self.dynamodb.Table('Submissions')
        
        # The score tracker
        self.tracker = Tracker(self.reddit, self.dynamodb) 

        self.last_update = 0
                
    def process_submission(self, submission):
        # The sticky reply to respond with
        reply_str = ScoreboardFeature.NEW_SUBMISSION_REPLY

        # Create an account for the user if they don't have one
        if not self.is_user(submission.author):
            self.create_new_user(submission.author)
            
            reply_str = reply_str + "\n\n\n\n*New user created for " + submission.author.name + "*"
        # Reply to the submission
        if not ScoreboardFeature.DEBUG_MODE_NO_COMMENT:
            reply = submission.reply(reply_str)
            reply.mod.distinguish(how='yes', sticky=True)



        # Track the submission for scoring
        self.tracker.track_submission(submission)
        print("New submission: " + str(submission.title))
                
        
    def process_comment(self, comment):             
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
        try:
            author_id = comment.author.id
            response = self.user_table.query(
                KeyConditionExpression=Key('user_id').eq(author_id)
            )
            print("Score query succeeded:")

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
                "  Submission:   " + str(total_submission_score) + "\n\n" + \
                "  Distribution: " + str(total_distribution_score))
                        
        
        except ClientError as e:
            print(e.response['Error']['Message'])

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
            self.reply_to_comment(comment, "Thanks for the example, but I couldn't find a URL in your comment.")
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
            # TODO - Update % with actual number
            parent_submission = comment.submission
            self.reply_to_comment(comment, "Thank you for the example!\n\n\n\n" + \
                "I'll check your post periodically over the next 24 hours and update your score. " + \
                "A 20% commission will go to the creator of the meme template.")
            self.tracker.track_example(parent_submission, example_submission, comment.author.id)

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
        try:
            response = self.user_table.put_item(
                Item={
                   'user_id' : redditor.id,
                   'username' : redditor.name,
                   'submission_score' : 0,
                   'distribution_score' :0
                }
            )
            
            print("Create user succeeded:")
            print(" Response: " + str(response))

            return True         
        
        except ClientError as e:
            print(e.response['Error']['Message'])
            return False

    def is_user(self, author):
        """
        Returns true if the author is already a user in the DynamoDB database.
        """
        
        # Query the table to get any user with a user_id matching the author's id
        response = self.user_table.query(
            KeyConditionExpression=Key('user_id').eq(author.id))
        num_matches = len(response['Items'])
        
        # If there is a match, then the author is already a user
        return num_matches > 0

    def reply_to_comment(self, comment, reply):
        """
        Replies to the comment with the given reply
        comment: The PRAW Comment object to reply to
        reply: The string with which to reply
        """

        # Add footer
        reply_with_footer = reply + "\n\n*InsiderMemeBot is in beta testing. Please message the mods if you think I'm making a mistake!*"

        if not ScoreboardFeature.DEBUG_MODE_NO_COMMENT:
            comment.reply(reply_with_footer)
        else:
            print("-" * 40)
            print("Comment: " + comment.body)
            print("Reply: " + reply_with_footer)
            print("-" * 40)

    def comment_on_example(self, original, example):
        """
        Adds a comment to the example, with a reference to the template
        original: The Submission of the original template
        example:  The Submission of the posted example
        """
        pass

        # TODO - Uncomment after beta test
        #reply = "This is an inside meme! See the [template](" + original.permalink + ") on r/InsiderMemeTrading.\n\n" + \
        #        "*Beep boop beep! I'm a bot!*"
        #example.reply(reply)

    def update(self):
        # Update the submissions being tracked
        cur_time = int(time.time())
        if cur_time >= self.last_update + self.tracker.SCORE_UPDATE_INTERVAL:
            print("Update!")
            self.tracker.update_scores()   
            self.last_update = cur_time