from Features.Feature import Feature
import praw
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import json

class ScoreboardFeature(Feature):
    """
    A feature that keeps score for the subreddit users
    """   
    
    def __init__(self, reddit, subreddit_name):
        super(ScoreboardFeature, self).__init__(reddit, subreddit_name) # Call super constructor
        
        # Initialize the Amazon Web Service DynamoDB.
        # For this to work, the AWS credentials must be present on the system.
        # This can be done by using "pip install awscli", and then running "aws configure"
        self.dynamodb = boto3.resource('dynamodb')
        self.user_table = self.dynamodb.Table('Users')
            
    def check_condition(self):
        return True
    
    def perform_action(self):
        self.check_submissions()
        self.check_comments()
    
    def check_submissions(self):
        # Get the 10 latest comments
        for submission in self.subreddit.new(limit=10):
            if self.is_old(submission):
                continue
            #if submission.created_utc < self.start_time:
                # Ignore submissions that are over a day old
                #print("Old post: " + str(submission.title))
                #print("Submission time: " + str(submission.created_utc))
                #print("Script start   : " + str(self.start_time))
                #continue
             
            print("New submission: " + str(submission))
            if self.is_processed_recently(submission):
                # Ignore submissions that the ScoreboardFeature has already processed
                continue
                        
               
            print("new submission: " + str(submission))
            # Mark the submission as processed so we don't look at it again
            self.mark_item_processed(submission)

        
    def check_comments(self):
        # Get the latest 100 comments
        for comment in self.subreddit.comments(limit=100):
            if self.is_processed_recently(comment):
                # Ignore comments that the ScoreboardFeature has already processed
                continue
            # Determine if the comment is an action
            if comment.body.strip() == "!new":
                self.create_new_user(comment)
                
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
            return
            
        # If we get here, then the user doesn't have an account already, so we create one
        print("Creating user: " + str(author))
        try:
            response = self.user_table.put_item(
                Item={
                   'user_id' : author.id,
                   'username' : author.name,
                   'score' : 0
                }
            )
            
            print("Create user succeeded:")
            print(" Response: " + str(response))
            
            # Respond to the comment that the account was created
            comment.reply("New user registered for " + author.name + ". You have 0 points.")
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