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


        print("POSTING SCOREBOARD: " + time_str)
        self.bot.subreddit.submit(
            title = "SCOREBOARD: " + time_str,
            selftext = scoreboard_text)
