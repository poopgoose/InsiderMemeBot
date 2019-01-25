from Features.Feature import Feature
import praw
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import json
import decimal

class SubmissionTracker(Feature):
    """
    A helper class for ScoreboardFeature. Keeps track of all submissions made within the last 24h,
    and keeps track of the scores.
    """   
    
    def __init__(self, dynamodb):
        # Initialize the variables
        self.dynamodb = dynamodb
        self.last_update_time = 0 # The time the submissions were last checked (Unix Epoch Time)
        self.tracked_submissions = []
        
        # The tables that we'll be using
        self.submissions_table = self.dynamodb.Table("Submissions")
        
        
        
    def add_submission(self, submission):
        """
        Adds a new submission to be tracked
        submission: The PRAW Submission object
        """
        submission_id = submission.id
        user = submission.author
        user_id = user.id
        create_time = submission.created_utc
        permalink = submission.permalink
        title = submission.title
        score = submission.score
        
        # Add the submission information to the database
        try:
            response = self.submissions_table.put_item(
                Item={
                   'submission_id' : submission_id,
                   'title' : title,
                   'created_utc' : decimal.Decimal(create_time),
                   'user_id' : user_id,
                   'permalink' : permalink,
                   'score' : decimal.Decimal(score)
                }
            )
            
            print("Tracking post: " + title)
            
        except ClientError as e:
            print(e.response['Error']['Message'])
        
        