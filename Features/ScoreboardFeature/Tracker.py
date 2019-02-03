from Features.Feature import Feature
from Features.ScoreboardFeature import Debug
import praw
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import json
import decimal
import time
import collections
import traceback

class Tracker:
    """
    A helper class for ScoreboardFeature. Keeps track of all submissions and 
    comments, and keeps track of the scores.
    """
    
    def __init__(self, reddit, dynamodb):

        # Constants
        # Enables/Disables debug mode for SubmissionTracker
        self.DEBUG = True
    
        # The duration, in seconds, for which to track each post
        self.TRACK_DURATION_SECONDS = 24 * 60 * 60 # 24 hours (in seconds)
    
        # How often to check the submission to update the score
        self.SCORE_UPDATE_INTERVAL =  1 * 60 # 1 minute

        # If debugging, use debug values
        if self.DEBUG:
            self.TRACK_DURATION_SECONDS = Debug.TRACK_DURATION_SECONDS
            self.SCORE_UPDATE_INTERVAL = Debug.SCORE_UPDATE_INTERVAL

        # Initialize the variables
        self.reddit = reddit
        self.dynamodb = dynamodb
        self.last_update_time = 0 # The time the submissions were last checked (Unix Epoch Time)
        self.tracking_dicts = {}
        
        # The tables that we'll be using
        self.users_table = self.dynamodb.Table("Users")
        self.submissions_table = self.dynamodb.Table("Submissions")
        self.tracking_table = self.dynamodb.Table("Tracking")            
        
    def track_submission(self, submission):
        """
        Adds a new submission to be tracked
        submission: The PRAW Submission object
        """
        create_time = submission.created_utc
        
        # Create an entry in the tracking_dict so we know when to update
        tracking_dict = {
           "next_update" : create_time + self.SCORE_UPDATE_INTERVAL,
           "expire_time" : create_time + self.TRACK_DURATION_SECONDS,
           "score" : submission.score,
           "user_id" : submission.author.id
        }

        print("Tracking submission: " )
        print(tracking_dict)
        self.tracking_dicts[submission.id] = tracking_dict
        
    def track_comment(self, comment):
        """
        Adds a new comment to be tracked
        comment: The PRAW Comment object
        """
        pass

    def update_scores(self):
    
        cur_time = int(time.time())
        
        # For each dictionary in the tracking dict, update the score if the current time is >= the next update time.
        # If the tracked submission has expired, add it to expired_ids for removal.
        expired_ids = []
        for submission_id in self.tracking_dicts:
            tracking_dict = self.tracking_dicts[submission_id]
            
            if cur_time >= tracking_dict["next_update"]:
                submission = self.reddit.submission(submission_id)
                updated_score = submission.score
                tracking_dict["next_update"] = cur_time + self.SCORE_UPDATE_INTERVAL
                tracking_dict["score"] = updated_score

                # If we have passed the expiration time, then remove the submission from tracking after this update
                if cur_time >= tracking_dict["expire_time"]:
                    expired_ids.append(submission_id)
             
         
        # Remove any submissions that have expired
        for submission_id in expired_ids:
            self.untrack_submission(submission_id)


    def get_tracking_submission_score(self, user_id):
        """
        Returns the total score of all submissions being tracked for the user
        """
        total_submission_score = 0

        for submission_id in self.tracking_dicts:
            tracking_dict = self.tracking_dicts[submission_id]

            # The tracked item is for the requested user
            if tracking_dict["user_id"] == user_id:
                total_submission_score = total_submission_score + tracking_dict["score"]

        print("Score from tracked submissions: " + str(total_submission_score))
        return total_submission_score

    def untrack_submission(self, submission_id):
        print("Submission has expired: " + submission_id)
        tracking_dict = self.tracking_dicts[submission_id]
        print("Final score: " + str(tracking_dict["score"]))
        print("Adding score to user: " + tracking_dict["user_id"])
        # Update the score for the user before we untrack
        try:
            response = self.users_table.update_item(
                Key={'user_id' : tracking_dict["user_id"]},
                UpdateExpression = "set submission_score = submission_score + :score",
                ExpressionAttributeValues = {":score" : decimal.Decimal(tracking_dict["score"])}
            )
        except ClientError as e:
            print(e.response['Error']['Message'])
            traceback.print_exc()

        del self.tracking_dicts[submission_id]


            