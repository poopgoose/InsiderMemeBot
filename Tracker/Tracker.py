import praw
import time
from Utils.DataAccess import DataAccess
from boto3.dynamodb.conditions import Key
import decimal

class Tracker:
    """
    This class continuously tracks items in the Tracking Database, and
    updates them with scores retrieved from PRAW
    """

    def __init__(self, reddit, test_mode):
        self.reddit = reddit
        self.test_mode = test_mode
        self.data_access = DataAccess(test_mode)

        self.tracked_items = []

    def run(self):
        """
        Runs the tracker
        """
        self.__start__()

        while(True):
            self.__update__()
            time.sleep(1)



    ######### Private helper functions ###########

    def __start__(self):
        """
        Begins the tracker
        """
        print("*" * 40)
        print("RUNNING TRACKER")
        print("Tracking Database: " + str(self.data_access.tracking_table.name))
        print("*" * 40)

    def __update__(self):
        """
        Updates the items being tracked
        """
        cur_time = int(time.time())
        
        # Get the items in the database being tracked
        tracked_items = []
        try:
            response = self.data_access.scan(DataAccess.Tables.TRACKING)
            for item in response['Items']:
                tracked_items.append(item)
        except Exception as e:
            print("Could not load tracking  data!")
            print(e)
            return

        for item in tracked_items:
            self.__update_item__(item)

        end_time = int(time.time())
        time_elapsed = end_time - cur_time

        print("=" * 40)
        print("Update cycle time: " + str(time_elapsed) + " seconds" )
        print("=" * 40)

    def __update_item__(self, item):
        """
        Updates a single tracked item
        """
        begin_time = time.time()
        try:

            if not 'expire_time' in item:
                """
                In the case that the tracker adds an item at the same time as one is removed by InsiderMemeBot, it is
                possible that a remnant will remain, with only the "submission_id", "last_update", and "score" fields defined.

                This check catches any such instance, as all non-deleted items will have the "expire_time" field defined.
                If an entry without this field is found, it should simply be removed from the database since InsiderMemeBot is 
                finished with it.
                """
                self.data_access.delete_item(DataAccess.Tables.TRACKING, {'submission_id' : item['submission_id']})
                print("Removing invalid item: " + str(item))
                return

            submission_id = item['submission_id']
            expire_time = decimal.Decimal(item['expire_time'])
            last_update = decimal.Decimal(0) if not 'last_update' in item else decimal.Decimal(item['last_update'])

            submission = self.reddit.submission(id=submission_id)
            new_score = decimal.Decimal(submission.score)
            update_time = decimal.Decimal(int(time.time()))
            author = '[None]' if submission.author == None else submission.author.name

            key = {'submission_id' : submission_id}
            update_expr = 'set last_update = :update, score = :score'
            expr_vals = {':update' : update_time, ':score' : new_score}

            # Make sure the item still exists since we added it to the list of items to update.
            # If it's been removed from the tracking database, then we don't need to update it anymore
            key_condition_expr = Key('submission_id').eq(submission_id)
            response = self.data_access.query(DataAccess.Tables.TRACKING, key_condition_expr)
            item_exists = len(response['Items']) == 1

            if item_exists:
                self.data_access.update_item(DataAccess.Tables.TRACKING, key, update_expr, expr_vals)
                end_time = time.time()
                update_duration = round(end_time - begin_time, 2)

            else:
                print("Submission has been removed from tracking: " + str(submission_id))
        except Exception as e:
            print("Failed to update submission: " + submission_id)
            print(e)


