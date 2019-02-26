from Features.Feature import Feature
import praw
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import json
import decimal
import time
import collections
import traceback
from Utils.DataAccess import DataAccess

class Tracker:
    """
    A helper class for ScoreboardFeature. Keeps track of all submissions and 
    comments, and keeps track of the scores.
    """
    
    def __init__(self, reddit, data_access):
    
        # The duration, in seconds, for which to track each post
        self.TRACK_DURATION_SECONDS = 24 * 60 * 60 # 24 hours (in seconds)

        # The amount of the distributor's score that goes to the creator
        self.CREATOR_COMMISSION = 0.20

        # Initialize the variables
        self.reddit = reddit
        self.data_access = data_access
        self.submission_tracking_dict = {}
        self.example_tracking_dict = {}

        # The update queue
        self.update_queue = collections.deque()

        # Loads any submissions being tracked from AWS DynamoDB.
        # This is a failsafe: if the bot crashes and comes back up, it can
        # read from the database to pick up where it left off
        self.load_tracking_data()
        
    def track_submission(self, submission, bot_comment_id=None, update_database = True):
        """
        Adds a new submission to be tracked
        submission: The PRAW Submission object
        bot_comment: The comment made by the bot that will be updated after the submission is scored
        """
        cur_time = int(time.time())
        create_time = submission.created_utc
        
        # Create an entry in the submission_tracking_dict so we know when to update
        tracking_dict = {
           "expire_time" : create_time + self.TRACK_DURATION_SECONDS,
           "score" : submission.score,
           "user_id" : submission.author.id,
           "bot_comment_id" : bot_comment_id
        }

        self.submission_tracking_dict[submission.id] = tracking_dict
        
        # Append ID to the right side of the update queue
        # (Submission_ID, is_example = False))
        self.update_queue.append((submission.id, False))

        print("-" * 40)
        print("Tracking submission")
        print(str(submission.id) + ": " + str(tracking_dict))
        print("-" * 40)

        if update_database:
            """
            Update the tracking table
            """

            item={
               'submission_id' : submission.id,
               'expire_time' : decimal.Decimal(create_time + self.TRACK_DURATION_SECONDS),
               'is_example' : False,
               'template_id' : " ",
               'distributor_id' : " ",
               'bot_comment_id' : bot_comment_id if bot_comment_id != None else " " 
            }
            success = self.data_access.put_item(DataAccess.Tables.TRACKING, item)
            if not success:
                print("!!!!! Unable to add example to tracking database: " + submission.id)
            
        
    def track_example(self, template_submission, example_submission, 
        distributor_user_id, bot_comment_id=None, update_database = True):
        """
        Adds a new example to be tracked
        template_submission: The submission of the original template. The user will get a % of the score from the 
            distributed example.

        example_submission: The submission of the distributed example
        distributor_user_id: The user ID of the distributor
        bot_comment: The comment of the bot that will be updated after the example is tracked
        """

        # Create an entry in the example_tracking_dict so we know when to update
        cur_time = int(time.time())
        create_time = example_submission.created_utc
        tracking_dict = {
            "expire_time" : create_time + self.TRACK_DURATION_SECONDS,
            "score" : example_submission.score,
            "distributor_user_id" : distributor_user_id,
            "creator_user_id" : template_submission.author.id,
            "bot_comment_id" : bot_comment_id
        }

        print("-" * 40)
        print("Tracking Example: " )
        print(str(example_submission.id) + ": " + str(tracking_dict))
        print("-" * 40)

        self.example_tracking_dict[example_submission.id] = tracking_dict
        
        # Append ID to the right side of the update queue
        # (Submission_ID, is_example = True))
        self.update_queue.append((example_submission.id, True))

        if update_database:
            """
            Update the tracking table
            """
            item = {
               'submission_id' : example_submission.id,
               'expire_time' : decimal.Decimal(create_time + self.TRACK_DURATION_SECONDS),
               'is_example' : True,
               'template_id' : template_submission.id,
               'distributor_id' : distributor_user_id,
               'bot_comment_id' : bot_comment_id if bot_comment_id != None else " "
                    }
            success = self.data_access.put_item(DataAccess.Tables.TRACKING, item)
            if not success:
                print("!!!!! Unable to add example to tracking database: " + example_submission.id)    
            

    def is_example_tracked(self, submission_id):
        """
        Returns True if the given submission ID is already the ID of a tracked example submission
        """
        return submission_id in self.example_tracking_dict


    def update_scores(self, max_updates=5):
        """
        Updates the scores in the tracking dictionary
        max_updates: The maximum number of scores to update before returning.
                     If too many scores are updated at once, it will prevent the bot from 
                     replying to comments and new submissions in a timely manner
        """
        expired_submission_ids = []
        expired_example_ids = []

        if len(self.update_queue) == 0:
            # Nothing to update, so just return
            return

        # Update the maximum number allowed at once, or all of them if the length of the queue
        # is less than the maximum.
        num_updates = min(max_updates, len(self.update_queue))
        for i in range(0, num_updates):

            update_item = self.update_queue.popleft()
            submission_id = update_item[0]
            is_example = update_item[1]

            # Get the latest score from reddit
            updated_score = self.reddit.submission(submission_id).score

            # Get the tracking dict and update
            if(is_example):
                tracking_dict = self.example_tracking_dict[submission_id]
            else:
                tracking_dict = self.submission_tracking_dict[submission_id]

            tracking_dict["score"] = updated_score

            # See if it's time for the tracking to finish
            cur_time = int(time.time())
            if cur_time > tracking_dict["expire_time"]:
                if(is_example):
                    expired_example_ids.append(submission_id)
                else:
                    expired_submission_ids.append(submission_id)
            
            else:
                # Add item to the end of the queue to be updated again
                self.update_queue.append(update_item)

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

        return total_submission_score

    def get_tracking_example_score(self, user_id):
        """
        Returns the total score of all distributed examples being tracked for the user
        """
        total_distribution_score = 0
        for example_id in self.example_tracking_dict:
            tracking_dict = self.example_tracking_dict[example_id]
            if tracking_dict["distributor_user_id"] == user_id:
                # Take out the commission for the content creator
                total_distribution_score = total_distribution_score + \
                    int(round(tracking_dict["score"] * (1 - self.CREATOR_COMMISSION)))

        return total_distribution_score

    def untrack_submission(self, submission_id):
        print("-" * 40)
        print("Submission has expired: " + submission_id)

        tracking_dict = self.submission_tracking_dict[submission_id]
        print("Final score: " + str(tracking_dict["score"]))
        print("Adding score to user: " + tracking_dict["user_id"])
        
        # Update the score for the user before we untrack
        user_key = {'user_id' : tracking_dict["user_id"]}
        user_update_expr = "set submission_score = submission_score + :score"
        user_expr_attrs = {":score" : decimal.Decimal(tracking_dict["score"])}
        success = self.data_access.update_item(
            DataAccess.Tables.USERS, user_key, user_update_expr, user_expr_attrs)

        if not success:
            print("!!!!! Unable to update creator score!")
            print("    User: " + str(tracking_dict["user_id"]))
            print("    Score: " + str(tracking_dict["score"]))

        # Remove from tracking database
        success = self.data_access.delete_item(
            DataAccess.Tables.TRACKING, {'submission_id' : submission_id})

        if not success:
            print("!!!!! Unable to delete item from tracking table!")
            print("    submission_id: " + str(submission_id))
        del self.submission_tracking_dict[submission_id]
        print("-" * 40)

        if tracking_dict['bot_comment_id'] != None:
            # Update the bot comment
            bot_comment = self.reddit.comment(id=tracking_dict['bot_comment_id'])

            try:
                edited_body = bot_comment.body + "\n\n" + \
                    "**Update**\n\n" + \
                    "Your template has finished scoring! You received **" + str(tracking_dict["score"]) + "** points.\n\n" + \
                    "*This does not include points gained from example commissions. Commission scores will be reported in the comments beneath the examples.*"
                bot_comment.edit(edited_body)

            except Exception as e:
                print("!!!!Unable to edit bot comment!")
                print("    Comment ID: " + bot_comment.id)
                print("    Error: " + str(e))


    def untrack_example(self, example_id):
        print("-" * 40)
        print("Example has expired: " + example_id)
        tracking_dict = self.example_tracking_dict[example_id]
        print("Final score: " + str(tracking_dict["score"]))
        print("Adding distribution score to user: " + tracking_dict["distributor_user_id"])
        print("Adding commission score to user: " + tracking_dict["creator_user_id"])
 
        total_score = tracking_dict["score"]
        distributor_score = int(round(total_score * (1 - self.CREATOR_COMMISSION)))
        creator_score = int(round(total_score * self.CREATOR_COMMISSION))

        ### Update the scores ###

        # Distributor
        distributor_key = {'user_id' : tracking_dict["distributor_user_id"]}
        distributor_update_expr = "set distribution_score = distribution_score + :score"
        distributor_expr_attrs = {":score" : decimal.Decimal(distributor_score)}
        success = self.data_access.update_item(
            DataAccess.Tables.USERS, distributor_key, distributor_update_expr, distributor_expr_attrs)

        if not success:
            print("!!!!! Unable to update distributor score!")
            print("    User: " + str(tracking_dict["distributor_user_id"]))
            print("    Score: " + str(distributor_score))

        
        # Content creator
        creator_key = {'user_id' : tracking_dict["creator_user_id"]}
        creator_update_expr = "set submission_score = submission_score + :score"
        creator_expr_attrs = {":score" : decimal.Decimal(creator_score)}
        success = self.data_access.update_item(
            DataAccess.Tables.USERS, creator_key, creator_update_expr, creator_expr_attrs)

        if not success:
            print("!!!!! Unable to update creator score!")
            print("    User: " + str(tracking_dict["creator_user_id"]))
            print("    Score: " + str(creator_score))

        # Remove from the tracking table
        success = self.data_access.delete_item(DataAccess.Tables.TRACKING, {'submission_id' : example_id})
        if not success:
            print("!!!!! Unable to delete item from tracking table!")
            print("    submission_id: " + str(submission_id))
        del self.example_tracking_dict[example_id]
        print("-" * 40)

        if tracking_dict['bot_comment_id'] != None:
            # Update the bot comment
            bot_comment = self.reddit.comment(id=tracking_dict['bot_comment_id'])

            try:
                edited_body = bot_comment.body + "\n\n" + \
                    "**Update**\n\n" + \
                    "Your example has finished scoring! It received a total of **" + str(total_score) + "** points.\n\n" + \
                    "You received **" + str(distributor_score) + "** points, and **" + str(creator_score) + "** of the points went to the creator of the template."
                bot_comment.edit(edited_body)
                
            except Exception as e:
                print("!!!!Unable to edit bot comment!")
                print("    Comment ID: " + bot_comment.id)
                print("    Error: " + str(e))


    def load_tracking_data(self):
        """
        Loads tracking data from the AWS Database. Only called once on initialize,
        to pick up previously tracked posts in case the bot crashes and comes back up
        """
        try:
            response = self.data_access.scan(DataAccess.Tables.TRACKING)

            for item in response['Items']:
                submission_id = item['submission_id']
                expire_time = item['expire_time']
                is_example = item['is_example']

                if 'bot_comment_id' in item:
                    bot_comment = item['bot_comment_id']
                else:
                    bot_comment = None

                try:

                    if is_example:
                        template_id = item['template_id']
                        example_submission = self.reddit.submission(id=submission_id)
                        template_submission = self.reddit.submission(id=template_id)
                        distributor_id = item['distributor_id']

                        # No need to update the database if we're just reading from it
                        self.track_example(template_submission, example_submission, 
                            distributor_id, bot_comment_id=bot_comment, update_database=False)
                    
                    else:
                        submission = self.reddit.submission(id=submission_id)
                        if submission.author != None:
                            self.track_submission(submission, update_database=False)
                        else:
                            # TODO - Remove post w/ deleted author from tracking database
                            print("Author is none for post: " + str(submission))

                except Exception as e:
                    print("Unable to load item: " + str(item))
                    print(e)
                    traceback.print_exc()

        except Exception as e:
            print("Could not load tracking  data!")
            print(e)

        print("=" * 40)
        print("LOADED TRACKING DATA:")
        print("-" * 40)
        print("example_tracking_dict:")
        print(str(self.example_tracking_dict))
        print("-" * 40)
        print("submission_tracking_dict:")
        print(str(self.submission_tracking_dict))
        print("=" * 40)