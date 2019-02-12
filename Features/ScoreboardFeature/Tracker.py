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
        self.DEBUG = False
    
        # The duration, in seconds, for which to track each post
        self.TRACK_DURATION_SECONDS = 24 * 60 * 60 # 24 hours (in seconds)
    
        # How often to check the submission to update the score
        self.SCORE_UPDATE_INTERVAL =  1 * 60 # 1 minute

        # The amount of the distributor's score that goes to the creator
        self.CREATOR_COMMISSION = 0.20

        # If debugging, use debug values
        if self.DEBUG:
            self.TRACK_DURATION_SECONDS = Debug.TRACK_DURATION_SECONDS
            self.SCORE_UPDATE_INTERVAL = Debug.SCORE_UPDATE_INTERVAL

        # Initialize the variables
        self.reddit = reddit
        self.dynamodb = dynamodb
        self.last_update_time = 0 # The time the submissions were last checked (Unix Epoch Time)
        self.submission_tracking_dict = {}
        self.example_tracking_dict = {}
        
        # The tables that we'll be using
        self.users_table = self.dynamodb.Table("Users")
        self.tracking_table = self.dynamodb.Table("Tracking")

        # Loads any submissions being tracked from AWS DynamoDB.
        # This is a failsafe: if the bot crashes and comes back up, it can
        # read from the database to pick up where it left off
        self.load_tracking_data()

        
    def track_submission(self, submission, update_database = True):
        """
        Adds a new submission to be tracked
        submission: The PRAW Submission object
        """
        cur_time = int(time.time())
        create_time = submission.created_utc
        
        # Create an entry in the submission_tracking_dict so we know when to update
        tracking_dict = {
           "next_update" : cur_time + self.SCORE_UPDATE_INTERVAL,
           "expire_time" : create_time + self.TRACK_DURATION_SECONDS,
           "score" : submission.score,
           "user_id" : submission.author.id
        }

        print("Tracking submission: " )
        print(tracking_dict)
        self.submission_tracking_dict[submission.id] = tracking_dict

        if update_database:
            """
            Update the tracking table
            """
            try:
                response = self.tracking_table.put_item(
                    Item={
                       'submission_id' : submission.id,
                       'expire_time' : decimal.Decimal(create_time + self.TRACK_DURATION_SECONDS),
                       'is_example' : False,
                       'template_id' : " ",
                       'distributor_id' : " "
                    }
                )
            except Exception as e:
                print("Unable to add example to tracking database: " + submission.id)
                print(e)
            
        
    def track_example(self, template_submission, example_submission, 
        distributor_user_id, update_database = True):
        """
        Adds a new example to be tracked
        template_submission: The submission of the original template. The user will get a % of the score from the 
            distributed example.

        example_submission: The submission of the distributed example
        """

        # Create an entry in the example_tracking_dict so we know when to update
        cur_time = int(time.time())
        create_time = example_submission.created_utc
        tracking_dict = {
            "next_update" : cur_time + self.SCORE_UPDATE_INTERVAL,
            "expire_time" : create_time + self.TRACK_DURATION_SECONDS,
            "score" : example_submission.score,
            "distributor_user_id" : distributor_user_id,
            "creator_user_id" : template_submission.author.id
        }

        print("Tracking Example: " )
        print(tracking_dict)
        self.example_tracking_dict[example_submission.id] = tracking_dict

        if update_database:
            """
            Update the tracking table
            """
            try:
                response = self.tracking_table.put_item(
                    Item={
                       'submission_id' : example_submission.id,
                       'expire_time' : decimal.Decimal(create_time + self.TRACK_DURATION_SECONDS),
                       'is_example' : True,
                       'template_id' : template_submission.id,
                       'distributor_id' : distributor_user_id
                    }
                )
            except Exception as e:
                print("Unable to add example to tracking database: " + example_submission.id)
                print(e)
            

    def is_example_tracked(self, submission_id):
        """
        Returns True if the given submission ID is already the ID of a tracked example submission
        """
        return submission_id in self.example_tracking_dict


    def update_scores(self):
    
        cur_time = int(time.time())
        
        # For each dictionary in the tracking dicts, update the score if the current time is >= the next update time.
        # If any tracked submission/example has expired, add it to a list for removal.

        expired_submission_ids = []
        expired_example_ids = []

        for submission_id in self.submission_tracking_dict:
            tracking_dict = self.submission_tracking_dict[submission_id]
            
            if cur_time >= tracking_dict["next_update"]:
                submission = self.reddit.submission(submission_id)
                updated_score = submission.score
                tracking_dict["next_update"] = cur_time + self.SCORE_UPDATE_INTERVAL
                tracking_dict["score"] = updated_score

                # If we have passed the expiration time, then remove the submission from tracking after this update
                if cur_time >= tracking_dict["expire_time"]:
                    expired_submission_ids.append(submission_id)
             
         # Examples
        for example_id in self.example_tracking_dict:
            tracking_dict = self.example_tracking_dict[example_id]

            if cur_time >= tracking_dict["next_update"]:
                example = self.reddit.submission(example_id)
                updated_score = example.score
                tracking_dict["next_update"] = cur_time + self.SCORE_UPDATE_INTERVAL
                tracking_dict["score"] = updated_score

                # If we have passed the expiration time, then remove the submission from tracking after this update
                if cur_time >= tracking_dict["expire_time"]:
                    expired_example_ids.append(example_id)


                print("updated_score: " + str(updated_score))
        # Remove any submissions and examples that have expired
        for submission_id in expired_submission_ids:
            self.untrack_submission(submission_id)

        for example_id in expired_example_ids:
            self.untrack_example(example_id)


    def get_tracking_submission_score(self, user_id):
        """
        Returns the total score of all submissions being tracked for the user
        """
        total_submission_score = 0

        for submission_id in self.submission_tracking_dict:
            tracking_dict = self.submission_tracking_dict[submission_id]

            # The tracked item is for the requested user
            if tracking_dict["user_id"] == user_id:
                total_submission_score = total_submission_score + tracking_dict["score"]

        # Add commissions from any examples being tracked
        for example_id in self.example_tracking_dict:
            tracking_dict = self.example_tracking_dict[example_id]
            if tracking_dict["creator_user_id"] == user_id:
                total_submission_score = total_submission_score + \
                    int(round(tracking_dict["score"] * self.CREATOR_COMMISSION))


        print("Score from tracked submissions: " + str(total_submission_score))
        return total_submission_score

    def get_tracking_example_score(self, user_id):
        """
        Returns the total score of all distributed examples being tracked for the user
        """
        total_distribution_score = 0
        for example_id in self.example_tracking_dict:
            tracking_dict = self.example_tracking_dict[example_id]
            print("Checking dict: " + str(tracking_dict) + "(user_id = " + user_id + ")")
            if tracking_dict["distributor_user_id"] == user_id:
                print("User matched! " + user_id)
                # Take out the commission for the content creator
                total_distribution_score = total_distribution_score + \
                    int(round(tracking_dict["score"] * (1 - self.CREATOR_COMMISSION)))

        return total_distribution_score

    def untrack_submission(self, submission_id):
        print("Submission has expired: " + submission_id)
        tracking_dict = self.submission_tracking_dict[submission_id]
        print("Final score: " + str(tracking_dict["score"]))
        print("Adding score to user: " + tracking_dict["user_id"])
        # Update the score for the user before we untrack
        try:
            response = self.users_table.update_item(
                Key={'user_id' : tracking_dict["user_id"]},
                UpdateExpression = "set submission_score = submission_score + :score",
                ExpressionAttributeValues = {":score" : decimal.Decimal(tracking_dict["score"])})

            # Remove from the tracking table
            response = self.tracking_table.delete_item(
                   Key={'submission_id' : submission_id})
            
        except ClientError as e:
            print(e.response['Error']['Message'])
            traceback.print_exc()

        del self.submission_tracking_dict[submission_id]

    def untrack_example(self, example_id):
        print("Example has expired: " + example_id)
        tracking_dict = self.example_tracking_dict[example_id]
        print("Final score: " + str(tracking_dict["score"]))
        print("Adding distribution score to user: " + tracking_dict["distributor_user_id"])
        print("Adding commission score to user: " + tracking_dict["creator_user_id"])
 
        total_score = tracking_dict["score"]
        distributor_score = int(round(total_score * (1 - self.CREATOR_COMMISSION)))
        creator_score = int(round(total_score * self.CREATOR_COMMISSION))

        # Update the scores
        try:
            # The distributor
            response = self.users_table.update_item(
                Key={'user_id' : tracking_dict["distributor_user_id"]},
                UpdateExpression = "set distribution_score = distribution_score + :score",
                ExpressionAttributeValues = {":score" : decimal.Decimal(distributor_score)}
            )

            # The content creator
            response = self.users_table.update_item(
                Key={'user_id' : tracking_dict["creator_user_id"]},
                UpdateExpression = "set submission_score = submission_score + :score",
                ExpressionAttributeValues = {":score" : decimal.Decimal(creator_score)}
            )

            # Remove from the tracking table
            response = self.tracking_table.delete_item(
                   Key={'submission_id' : example_id})

            del self.example_tracking_dict[example_id]

        except ClientError as e:
            print(e.response['Error']['Message'])
            traceback.print_exc()

    def load_tracking_data(self):
        """
        Loads tracking data from the AWS Database. Only called once on initialize,
        to pick up previously tracked posts in case the bot crashes and comes back up
        """
        try:
            response = self.tracking_table.scan()
            print("Retrieved tracking data!")

            for item in response['Items']:
                submission_id = item['submission_id']
                expire_time = item['expire_time']
                is_example = item['is_example']

                if is_example:
                    template_id = item['template_id']
                    example_submission = self.reddit.submission(id=submission_id)
                    template_submission = self.reddit.submission(id=template_id)
                    distributor_id = item['distributor_id']

                    # No need to update the database if we're just reading from it
                    self.track_example(template_submission, example_submission, 
                        distributor_id, update_database=False)
                
                else:
                    submission = self.reddit.submission(id=submission_id)
                    self.track_submission(submission, update_database=False)

        except Exception as e:
            print("Could not load tracking  data!")
            print(e)