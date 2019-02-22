import praw
import time
from Utils.DataAccess import DataAccess
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
        self.__load_tracking_data__()

    def __update__(self):
        """
        Updates the items being tracked
        """
        cur_time = int(time.time())


        self.__track_new_items__() # Track any new items that may have been added

        for item in self.tracked_items:
            self.__update_item__(item)

        self.__untrack_old_items__() # Untrack any expired items

        end_time = int(time.time())
        time_elapsed = end_time - cur_time

        print("Update cycle time: " + str(time_elapsed) + " seconds" )

    def __update_item__(self, item):
        """
        Updates a single tracked item
        """

        is_example = item['is_example']

        if(is_example):
            self.__update_example__(item)
        else:
            self.__update_submission__(item)

    def __update_example__(self, example_item):
        """
        Updates an example
        """
        pass

    def __update_submission__(self, item):
        """
        Updates a submission
        """

        submission_id = item['submission_id']
        expire_time = decimal.Decimal(item['expire_time'])
        bot_comment_id = " " if not 'bot_comment_id' in item else item['bot_comment_id']
        last_update = decimal.Decimal(0) if not 'last_update' in item else decimal.Decimal(item['last_update'])

        submission = self.reddit.submission(id=submission_id)
        new_score = decimal.Decimal(submission.score)
        update_time = decimal.Decimal(int(time.time()))
        author = '[None]' if submission.author == None else submission.author.name

        print("Submission: " + submission_id + "  (" + submission.title + ")")
        print("    Author: " + author)
        print("    Update Time: " + str(update_time))
        print("    Score: " + str(new_score))


        key = {'submission_id' : submission_id}
        update_expr = 'set last_update = :update, score = :score'
        expr_vals = {':update' : update_time, ':score' : new_score}
        try:
            response = self.data_access.update_item(DataAccess.Tables.TRACKING, key, update_expr, expr_vals)
        except Exception as e:
            print("Failed to update submission!")
            print(e)


    def __load_tracking_data__(self):
        """
        Loads tracking data from the AWS Database. Only called once on initialize,
        to pick up previously tracked posts in case the bot crashes and comes back up
        """

        cur_time = int(time.time())
        try:
            response = self.data_access.scan(DataAccess.Tables.TRACKING)

            for item in response['Items']:
                self.tracked_items.append(item)
        except Exception as e:
            print("Could not load tracking  data!")
            print(e)
            sys.exit(1)

        end_time = int(time.time())
        time_elapsed = end_time - cur_time
        print("Time to load data: " + str(time_elapsed) + " seconds")


    def __track_new_items__(self):
        """
        Helper function for finding new items and tracking them
        """
        pass # TODO

    def __untrack_old_items__(self):
        """
        Helper function for untracking old items
        """
        pass # TODO