from Features.Feature import Feature
import praw
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import json
import decimal
import time

class SubmissionTracker(Feature):
    """
    A helper class for ScoreboardFeature. Keeps track of all submissions made within the last 24h,
    and keeps track of the scores.
    """
    
    # The duration, in seconds, for which to track each post
    TRACK_DURATION_SECONDS = 24 * 60 * 60 # 24 hours (in seconds)
    
    # How often to check the submission to update the score
    SCORE_UPDATE_INTERVAL =  1 * 60 # 1 minute
    
    def __init__(self, dynamodb):
        # Initialize the variables
        self.dynamodb = dynamodb
        self.last_update_time = 0 # The time the submissions were last checked (Unix Epoch Time)
        self.tracking_dicts = {}
        
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
        
        
        # Create an entry in the tracking_dict so we know when to update
        tracking_dict = {
           "next_update" : create_time + SubmissionTracker.SCORE_UPDATE_INTERVAL,
           "expire_time" : create_time + SubmissionTracker.TRACK_DURATION_SECONDS
        }
        self.tracking_dicts[submission_id] = tracking_dict
        
    def update_scores(self, reddit):
    
        cur_time = int(time.time())
        
        # For each dictionary in the tracking dict, update the score if the current time is >= the next update time.
        # If the tracked submission has expired, add it to expired_ids for removal.
        expired_ids = []
        for submission_id in self.tracking_dicts:
            tracking_dict = self.tracking_dicts[submission_id]
            
            if cur_time >= tracking_dict["next_update"]:
                submission = reddit.submission(submission_id)
                updated_score = submission.score
                print("Updated Score for submission: " + submission.title + "(" + submission_id + ")   score: " + str(updated_score))
                tracking_dict["next_update"] = cur_time + SubmissionTracker.SCORE_UPDATE_INTERVAL
                
            if cur_time >= tracking_dict["expire_time"]:
                expired_ids.append(submission_id)
             
         
        # Remove any submissions that have expired
        for submission_id in expired_ids:
            print("Submission has expired: " + submission_id)
            del self.tracking_dicts[submission_id]


            