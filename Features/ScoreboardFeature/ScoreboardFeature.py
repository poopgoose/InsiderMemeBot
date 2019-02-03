from Features.Feature import Feature
import praw
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import json
from Features.ScoreboardFeature.Tracker import Tracker
from Features.ScoreboardFeature import Debug

class ScoreboardFeature(Feature):
    """
    A feature that keeps score for the subreddit users
    """   
    
    
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
            
    def check_condition(self):
        return True
    
    def perform_action(self):
        self.check_submissions()
        self.check_comments()
    
    def check_submissions(self):
        # Get the 10 latest submissions
        for submission in self.subreddit.new(limit=10):
        
            if self.is_processed_recently(submission):
                # Skip over anything we've already looked at
                continue
                    
            elif self.is_old(submission) or self.did_comment(submission):
                # Nothing to be done for old posts or posts that the bot has already commented on
                self.mark_item_processed(submission)
                continue
            
            # Reply to the submission
            reply = submission.reply(ScoreboardFeature.NEW_SUBMISSION_REPLY)
            reply.mod.distinguish(how='yes', sticky=True)
            # Track the submission for scoring
            self.tracker.track_submission(submission)
            print("New submission: " + str(submission.title))
            
            # Mark the submission as processed so we don't look at it again
            self.mark_item_processed(submission)
            
         
        # Update the submissions being tracked
        self.tracker.update_scores()        

        
    def check_comments(self):
        # Get the latest 100 comments
        for comment in self.subreddit.comments(limit=100):
            if self.is_processed_recently(comment):
                # Ignore comments that the ScoreboardFeature has already processed
                # TODO - Add check for did_reply
                continue
                
            # Determine if the comment is an action
            if comment.body.strip() == "!new":
                self.create_new_user(comment)
            elif comment.body.strip() == "!score":
                self.process_score(comment)
                
            # Mark the comment as processed so we don't look at it again
            self.mark_item_processed(comment)

                
    
    ############# Process actions #############
    def create_new_user(self, comment):
        """
        Creates a new user for the comment author
        """
        
        author = comment.author
        if self.is_user(author):
            # The user already has an account
            comment.reply("There is already an account for " + author.name)
            self.mark_item_processed(comment)
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
            comment.reply("New user registered for " + author.name + ". You have 0 points.")
            self.mark_item_processed(comment)
            
        
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
                comment.reply("You don't have an account yet!\n\n" + \
                    "Reply with '!new' to create one.")
                self.mark_item_processed(comment)
                return

            user = response['Items'][0]
           
            # The scores for any items that have already finished tracking
            submission_score_from_db = user['submission_score']

            # The scores for items that are currently being tracked
            submission_score_from_tracking = \
                self.tracker.get_tracking_submission_score(author_id)

            total_submission_score = submission_score_from_db + submission_score_from_tracking

            # Respond to the comment that the account was created
            comment.reply("**Score for " + comment.author.name + ":**\n\n" + \
                "  **Submissions:**   " + str(total_submission_score) + "\n\n" + \
                "  **Distributions:** " + str(0)) # TODO
            self.mark_item_processed(comment)
                        
        
        except ClientError as e:
            print(e.response['Error']['Message'])
            
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