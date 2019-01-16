from Features.Feature import Feature
import praw
import boto3
from botocore.exceptions import ClientError
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
        print("Running ScoreboardFeature with subreddit: " + self.subreddit_name)
        
        # Get the latest 100 comments
        for comment in self.subreddit.comments(limit=10):
            
            # Determine if the comment is an action
            if comment.body.strip() == "!new":
                self.create_new_user(comment)
                        
        
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
            
        
        except ClientError as e:
            print(e.response['Error']['Message'])
            
            
    ################## Helper functions ##################
    def is_user(self, author):
        """
        Returns true if the author is already a user in the DynamoDB database.
        """
        
        # TODO
        return False