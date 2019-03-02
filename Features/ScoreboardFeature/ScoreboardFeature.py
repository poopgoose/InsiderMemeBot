from Features.Feature import Feature
import decimal
import praw
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import json
import re
import time
from datetime import datetime
from Utils.DataAccess import DataAccess

class ScoreboardFeature(Feature):
    """
    This class is responsible for keeping track of the scoreboard data, and for 
    posting the scoreboard in a comment several times per day
    """

    SCOREBOARD_HEADER = \
        "Ranking | Name | Score\n" + \
        ":------:|:-----|:-----"


    # TODO - Replace with exact times
    POST_INTERVAL =  1 * 60 # Post every minute for debugging 

    # Time interval constants, in seconds
    LAST_DAY = 60 * 60 * 24
    LAST_WEEK = LAST_DAY * 7
    LAST_MONTH = LAST_DAY * 30
    LAST_YEAR = LAST_DAY * 365

    def __init__(self, bot):
        super(ScoreboardFeature, self).__init__(bot) # Call super constructor

        self.prev_post_time = 0

    def update(self):
        """
        Updates the scoreboard feature
        """

        if time.time() < self.prev_post_time + ScoreboardFeature.POST_INTERVAL:
            # It isn't time to update yet, so just return
            return

        # 1. Get the users from the user database
        user_data = self.bot.data_access.scan(DataAccess.Tables.USERS)['Items']

        # 2. Sort by score types
        users_by_total = sorted(user_data, key=lambda x: x['total_score'], reverse=True)
        users_by_submission = sorted(user_data, key=lambda x: x['submission_score'], reverse=True)
        users_by_distribution = sorted(user_data, key=lambda x: x['distribution_score'], reverse=True)

        # 3. Create the map for each user's rank
        ranking_map = {}
        for i in range(0, len(users_by_total)):
            user = users_by_total[i]
            ranking_map[user['user_id']] = {
                'total' : decimal.Decimal(i + 1),
                'submission' : decimal.Decimal(0),
                'distribution' : decimal.Decimal(0)
            }

        for i in range(0, len(users_by_submission)):
            user = users_by_submission[i]
            ranking_map[user['user_id']]['submission'] = decimal.Decimal(i + 1)
        for i in range(0, len(users_by_distribution)):
            user = users_by_distribution[i]
            ranking_map[user['user_id']]['distribution'] = decimal.Decimal(i + 1)

        # 4. Update each User's Rank
        for user_id in ranking_map:
            ranking_dict = ranking_map[user_id]
            key = {'user_id' : user_id}
            expr = "set ranking = :dict"
            attrs = {":dict" : ranking_dict}
            self.bot.data_access.update_item(DataAccess.Tables.USERS, key, expr, attrs)   

        # 5. Post the scoreboard
        self.__create_scoreboard_comment(users_by_total, users_by_submission, users_by_distribution)

        self.prev_post_time = int(time.time())

    def on_finished_tracking(self, item):
        """
        Handle when a post has finished tracking
        item: The item that has finished tracking
        """

        # Get the user info for the post that finished tracking
        user_info = self.bot.data_access.query(DataAccess.Tables.USERS,
            key_condition_expr = Key('user_id').eq(item['author_id']))['Items'][0]


        # See how the post compares with posts from the same day
        key_expr = Key('key').eq("last_day")
        top_yesterday = self.bot.data_access.query(DataAccess.Tables.TOP_POSTS, key_expr)['Items'][0]
        if item['is_example']:
            pass # TODO
        else:
            # Submissions
            top_items = top_yesterday['submissions']
            new_items = top_items
            for i in range(0, len(top_items)):
                top_item = top_items[i]
                if top_item['submission_id'] == "No Data": 
                    # There's no data for the time period, so take the slot
                    new_item = {
                        'submission_id' : item['submission_id'],
                        'user_id' : user_info['user_id'],
                        'username' : user_info['username'],
                        'score' : item['score'],
                        'permalink' : 'TODO',
                        'scoring_time' : decimal.Decimal(int(time.time())),
                        'title' : 'TODO'
                    }
                    new_items[i] = new_item
                    
                    # Update the data table
                    update_key = {'key' : 'last_day'}
                    update_expr = "set submissions = :new_items"
                    update_attrs = {":new_items" : new_items}
                    self.bot.data_access.update_item(
                        DataAccess.Tables.TOP_POSTS, update_key, update_expr, update_attrs)

                    return

        #print("-" * 40)
        #print(" ----- TOP SUBMISSIONS ----")
        #print(top_submissions)
        #print("-" * 40)


        ### Add the item to the Top Submission database ###


        item = {
            'submission_id' : item['submission_id'],
            'is_example' : item['is_example'],
            'permalink' : "TODO",
            'scoring_time' : int(time.time()),
            'author_id' : item['author_id'],
            'username' : user_info['username'],
            'score' : item['score']
        }

        # self.bot.data_access.put_item(DataAccess.Tables.TOP_SUBMISSIONS, item)



    def __create_scoreboard_comment(self, users_by_total, users_by_submission, users_by_distribution):
        """
        Helper function for update. Creates the comment for the scoreboard

        users_by_total: The list of all users, sorted by total_score, descending
        users_by_submission: The list of all users, sorted by submission_score, descending
        users_by_distribution: The list of all users, sorted by distribution score, descending
        """
        now = datetime.now()
        time_str =  now.strftime("%a, %b %d, %Y %H:%M %Z")

        # The number of users to include in the scoreboard. users_by_total, users_by_submission, and
        # users_by_distribution are all the same length, just different orderings, so we can just use
        # users_by_total to determine the number of places to show
        num_places = min(len(users_by_total), 10)

        #########################################
        ##### Construct the scoreboard text #####
        #########################################

        ### Overall Score ###
        scoreboard_text = ScoreboardFeature.SCOREBOARD_HEADER + "\n|| **OVERALL** |"
        for i in range(0, num_places):
            row_text = str(i + 1) + " | " + users_by_total[i]['username'] + " | " + str(users_by_total[i]['total_score'])
            scoreboard_text = scoreboard_text + "\n" + row_text

        ### Submission Score ###
        scoreboard_text = scoreboard_text + "\n | |  " + \
            "\n || **TOP SUBMITTERS** |"
        for i in range(0, num_places):
            row_text = str(i + 1) + " | " + users_by_submission[i]['username'] + " | " + str(users_by_submission[i]['submission_score'])
            scoreboard_text = scoreboard_text + "\n" + row_text

        ### Distribution Score ###
        scoreboard_text = scoreboard_text + "\n | |  " + \
            "\n || **TOP DISTRIBUTORS** |"
        for i in range(0, num_places):
            row_text = str(i + 1) + " | " + users_by_distribution[i]['username'] + " | " + str(users_by_distribution[i]['distribution_score'])
            scoreboard_text = scoreboard_text + "\n" + row_text


        ### Best posts ###
        scoreboard_text = scoreboard_text + "\n\n" + self.__create_top_post_markup()    

        print("POSTING SCOREBOARD: " + time_str)
        #self.bot.subreddit.submit(
        #    title = "SCOREBOARD: " + time_str,
        #    selftext = scoreboard_text)

    def __create_top_post_markup(self):
        """
        Helper function to show the top posts
        """

        markup_str = "------\n"
        markup_str = markup_str + "**Best Templates**\n\n" + \
            "**Yesterday** \n\n" + \
            "  1. TODO \n\n" + \
            "  2. TODO \n\n" + \
            "  3. TODO \n\n" + \
            "**This week** \n\n" + \
            "  1. TODO \n\n" + \
            "  2. TODO \n\n" + \
            "  3. TODO \n\n" + \
            "**This month** \n\n" + \
            "  1. TODO\n\n"  + \
            "  2. TODO\n\n" + \
            "  3. TODO\n\n" + \
            "**All time** \n\n" + \
            "  1. TODO\n\n" + \
            "  2. TODO\n\n" + \
            "  3. TODO\n\n" + \
            "------" + \
            "**Best Examples**"

        return markup_str