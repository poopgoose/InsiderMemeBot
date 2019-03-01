from Features.Feature import Feature
import decimal
import praw
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import json
import re
import time
from Utils.DataAccess import DataAccess

class ScoreboardFeature(Feature):
    """
    This class is responsible for keeping track of the scoreboard data, and for 
    posting the scoreboard in a comment several times per day
    """


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

        # 3. Update each User's Rank
        for user_id in ranking_map:
            ranking_dict = ranking_map[user_id]
            key = {'user_id' : user_id}
            expr = "set ranking = :dict"
            attrs = {":dict" : ranking_dict}
            self.bot.data_access.update_item(DataAccess.Tables.USERS, key, expr, attrs)   

        # for i in range(0, len(users_by_total)):

        #     user = users_by_total[i]

        #     # Create the map for the user if it doesn't exist
            

        #     key = {'user_id' : user['user_id']}
        #     expr = "set ranking.total = :rank"
        #     attrs = {":rank" : decimal.Decimal(i)}
        #     self.bot.data_access.update_item(DataAccess.Tables.USERS, key, expr, attrs)

        # for i in range(0, len(users_by_submission)):
        #     user = users_by_submission[i]
        #     key = {'user_id' : user['user_id']}
        #     expr = "set ranking.submission = :rank"
        #     attrs = {":rank" : decimal.Decimal(i)}
        #     self.bot.data_access.update_item(DataAccess.Tables.USERS, key, expr, attrs)

        # for i in range(0, len(users_by_distribution)):
        #     user = users_by_distribution[i]
        #     key = {'user_id' : user['user_id']}
        #     expr = "set ranking.distribution = :rank"
        #     attrs = {":rank" : decimal.Decimal(i)}
        #     self.bot.data_access.update_item(DataAccess.Tables.USERS, key, expr, attrs)



        self.prev_post_time = int(time.time())