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
            
    #def check_condition(self):
    #    return True
    
    #def perform_action(self):
    #    self.check_submissions()
    #    self.check_comments()
    
    def process_submission(self, submission):
        # Reply to the submission
        if not ScoreboardFeature.DEBUG_MODE_NO_COMMENT:
            reply = submission.reply(ScoreboardFeature.NEW_SUBMISSION_REPLY)
            reply.mod.distinguish(how='yes', sticky=True)

        # Track the submission for scoring
        self.tracker.track_submission(submission)
        print("New submission: " + str(submission.title))
             
        # Update the submissions being tracked
        self.tracker.update_scores()        

        
    def process_comment(self, comment):
        # Get the latest 100 comments
                
            # Determine if the comment is an action
            if comment.body.strip() == "!new":
                self.create_new_user(comment)
            elif comment.body.strip() == "!score":
                self.process_score(comment)
            elif comment.body.strip().startswith("!example"):
                self.process_example(comment)
                
    
    ############# Process actions #############
    def create_new_user(self, comment):
        """
        Creates a new user for the comment author
        """
        
        author = comment.author
        if self.is_user(author):
            # The user already has an account
            self.reply_to_comment(comment, "There is already an account for " + author.name)
            return
            
        # If we get here, then the user doesn't have an account already, so we create one
        print("Creating user: " + str(author))
        try:
            response = self.user_table.put_item(
                Item={
                   'user_id' : author.id,
                   'username' : author.name,
                   'submission_score' : 0,
                   'distribution_score' :0
                }
            )
            
            print("Create user succeeded:")
            print(" Response: " + str(response))
            
            # Respond to the comment that the account was created
            self.reply_to_comment(comment, "New user registered for " + author.name + ". You have 0 points.")            
        
        except ClientError as e:
            print(e.response['Error']['Message'])
            
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
            self.reply_to_comment("Thank you for the example!\n\n\n\n" + \
                "I'll check your post periodically over the next 24 hours and update your score. " + \
                "A 20% commission will go to the creator of the meme template.")
            self.tracker.track_example(parent_submission, example_submission)

        except praw.exceptions.ClientException as e:
            print("Could not get submission from URL: " + example_url)
            self.reply_to_comment(comment, "Thanks for the example, but I couldn't find any Reddit post " + \
                "from the URL tht you provided. Only links to example posts on other subreddits can be scored.")
            return

        print("\n")

    ################## Helper functions ##################
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