"""
This test case simulates the following scenario:

user1, user2, user3, and user4 all have a template and example being tracked.
All examples are based on a template posted by a fifth user, user5.

The examples and templates are as follows:

user1_template  : 10 points
user1_example   : 10 points

user2_template  : 9 points
user2_example   : 19 points

user3_template  : 11 points
user3_example   : 8 points

user4_template  : 6 points
user4_example   : 20 points


The examples and templates finish scoring in order, and are added using the 'on_finished_tracking' method.

The expected top-3 ranking is:

Templates:        Examples:
1. user3          1. user4
2. user1          2. user2
3. user2          3. user1


After 10 seconds, the user2 template and example are set to be 25 hours old, at which point they should be
considered 'expired' from the "last_day" TopPosts data entry.

The new expected top-3 ranking is:

Templates:       Examples:
1. user3         1. user4
2. user1         2. user1
3. user4         3. user3

"""

# Set up path
import os, sys
cur_dir = os.path.dirname(os.path.realpath(__file__))
root_dir = os.path.abspath(os.path.join(cur_dir, '../../..'))
sys.path.insert(0, root_dir)

import praw
import decimal
import boto3
from boto3.dynamodb.conditions import Key
from InsiderMemeBot import InsiderMemeBot
from Features.ScoreboardFeature.ScoreboardFeature import ScoreboardFeature
import unittest
import time


# Resets the top scores in case there's anything in there
from Tools import CreateEmptyTopPosts

class ExpirePostTest(unittest.TestCase):


    def setup(self):
        ###################### Initialize the Feature under test #################
        reddit = praw.Reddit(client_id = os.environ['IMT_CLIENT_ID'],
                             client_secret = os.environ['IMT_CLIENT_SECRET'],
                             password=os.environ['IMT_PASSWORD'],
                             user_agent="InsiderMemeBotScript by " + os.environ['IMT_USERNAME'],
                             username=os.environ['IMT_USERNAME'])

        test_mode = True
        test_bot = InsiderMemeBot(reddit, test_mode)
        self.scoreboard_feature = ScoreboardFeature(test_bot)

        # Initialize database
        dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
        self.user_table = dynamodb.Table('Users-dev')
        self.top_posts_table = dynamodb.Table('TopPosts-dev')

        self.add_user('user1')
        self.add_user('user2')
        self.add_user('user3')
        self.add_user('user4')
        self.add_user('user5')

        user1_template = self.make_data('user1', 10, False)
        user1_example  = self.make_data('user1', 10, True)
        user2_template = self.make_data('user2', 9, False)
        user2_example  = self.make_data('user2', 19, True)
        user3_template = self.make_data('user3', 11, False)
        user3_example  = self.make_data('user3', 8, True)
        user4_template = self.make_data('user4', 6, False)
        user4_example  = self.make_data('user4', 20, True)


        self.scoreboard_feature.on_finished_tracking(user1_template)
        self.scoreboard_feature.on_finished_tracking(user1_example)
        self.scoreboard_feature.on_finished_tracking(user2_template)
        self.scoreboard_feature.on_finished_tracking(user2_example)
        self.scoreboard_feature.on_finished_tracking(user3_template)
        self.scoreboard_feature.on_finished_tracking(user3_example)
        self.scoreboard_feature.on_finished_tracking(user4_template)
        self.scoreboard_feature.on_finished_tracking(user4_example)


    ########## Functions for initializing Test Data #################

    def add_user(self, user):
        self.user_table.put_item(Item=
            {
               'user_id' : user,
               'distribution_score' : decimal.Decimal(0),
               'submission_score' : decimal.Decimal(0),
               'total_score' : decimal.Decimal(0),
               'username' : user,
               'attributes' : ['TEST', 'ExpirePostTest'],
               'ranking' : {'distribution' : decimal.Decimal(0),
                            'submission' : decimal.Decimal(0),
                            'total' : decimal.Decimal(0)}
            })

    def make_data(self, user, score, is_example):
        return {
            'submission_id' : user + "_template_id",
            'author_id' : user,
            'template_id' : "template_for_" + user + ("_example" if is_example else " "),
            'template_author_id': 'user5_id' if is_example else ' ', 
            'bot_comment_id' : 'bot_comment_' + user + ('_example' if is_example else '_template'),
            'expire_time' : decimal.Decimal(1550000000),
            'is_example' : is_example,
            'last_update' : decimal.Decimal(0),
            'permalink' : 'r/InsiderMemeBotTest/' + user + ('_example' if is_example else '_template'),
            'score' : decimal.Decimal(score),
            'title' : user + (" Example" if is_example else " Template")
        }

    def set_scoring_time(self, key_name, user, age):
        """
        Sets the scoring time of a user's posts to the given age
        """

        row = self.top_posts_table.query(KeyConditionExpression=Key('key').eq(key_name))['Items'][0]
        updated_examples = row['examples']
        updated_submissions = row['submissions']

        new_scoring_time = decimal.Decimal(int(time.time() - age)) # Set the scoring time to 'age' seconds ago

        for i in range(0, len(updated_examples)):
            example = updated_examples[i]
            if example['user_id'] == user:
                example['scoring_time'] = new_scoring_time

        for i in range(0, len(updated_submissions)):
            submission = updated_submissions[i]
            if submission['user_id'] == user:
                submission['scoring_time'] = new_scoring_time

        key = {'key' : key_name}
        expr = "set examples = :updated_examples, submissions = :updated_submissions"
        attrs = {":updated_examples" : updated_examples, ":updated_submissions" : updated_submissions}
        self.top_posts_table.update_item(Key=key, 
            UpdateExpression=expr, ExpressionAttributeValues=attrs)



    ########################### TESTS ########################

    def test_top_data(self):
        self.setup()


        last_day_data = self.top_posts_table.query(KeyConditionExpression=Key('key').eq('last_day'))['Items'][0]
        last_week_data = self.top_posts_table.query(KeyConditionExpression=Key('key').eq('last_week'))['Items'][0]

        # Verify the data
        self.assertEqual(last_day_data['submissions'][0]['user_id'], 'user3')
        self.assertEqual(int(last_day_data['submissions'][0]['score']), 11)
        self.assertEqual(last_day_data['submissions'][1]['user_id'], 'user1')
        self.assertEqual(int(last_day_data['submissions'][1]['score']), 10)
        self.assertEqual(last_day_data['submissions'][2]['user_id'], 'user2')
        self.assertEqual(int(last_day_data['submissions'][2]['score']), 9)
        self.assertEqual(last_day_data['submissions'][3]['user_id'], 'user4')
        self.assertEqual(int(last_day_data['submissions'][3]['score']), 6)

        self.assertEqual(last_day_data['examples'][0]['user_id'], 'user4')
        self.assertEqual(int(last_day_data['examples'][0]['score']), 20)
        self.assertEqual(last_day_data['examples'][1]['user_id'], 'user2')
        self.assertEqual(int(last_day_data['examples'][1]['score']), 19)
        self.assertEqual(last_day_data['examples'][2]['user_id'], 'user1')
        self.assertEqual(int(last_day_data['examples'][2]['score']), 10)
        self.assertEqual(last_day_data['examples'][3]['user_id'], 'user3')
        self.assertEqual(int(last_day_data['examples'][3]['score']), 8)

        ### Mark user2 template and example as 25 hours old
        for key_name in ["last_day", "last_week", "last_month", "last_year", "all_time"]:
            self.set_scoring_time(key_name, 'user2', 25*60*60)

        # Perform the next update
        self.scoreboard_feature.update()

        # Verify the data
        self.assertEqual(last_day_data['submissions'][0]['user_id'], 'user3')
        self.assertEqual(int(last_day_data['submissions'][0]['score']), 11)
        self.assertEqual(last_day_data['submissions'][1]['user_id'], 'user1')
        self.assertEqual(int(last_day_data['submissions'][1]['score']), 10)
        self.assertEqual(last_day_data['submissions'][2]['user_id'], 'user4')
        self.assertEqual(int(last_day_data['submissions'][2]['score']), 6)

        self.assertEqual(last_day_data['examples'][0]['user_id'], 'user4')
        self.assertEqual(int(last_day_data['examples'][0]['score']), 20)
        self.assertEqual(last_day_data['examples'][1]['user_id'], 'user1')
        self.assertEqual(int(last_day_data['examples'][1]['score']), 10)
        self.assertEqual(last_day_data['examples'][2]['user_id'], 'user3')
        self.assertEqual(int(last_day_data['examples'][2]['score']), 8)

        # Verify that last_week data wasn't touched, because 25h is still within the week
        self.assertEqual(last_week_data['submissions'][0]['user_id'], 'user3')
        self.assertEqual(int(last_week_data['submissions'][0]['score']), 11)
        self.assertEqual(last_week_data['submissions'][1]['user_id'], 'user1')
        self.assertEqual(int(last_week_data['submissions'][1]['score']), 10)
        self.assertEqual(last_week_data['submissions'][2]['user_id'], 'user2')
        self.assertEqual(int(last_week_data['submissions'][2]['score']), 9)
        self.assertEqual(last_week_data['submissions'][3]['user_id'], 'user4')
        self.assertEqual(int(last_week_data['submissions'][3]['score']), 6)

        self.assertEqual(last_week_data['examples'][0]['user_id'], 'user4')
        self.assertEqual(int(last_week_data['examples'][0]['score']), 20)
        self.assertEqual(last_week_data['examples'][1]['user_id'], 'user2')
        self.assertEqual(int(last_week_data['examples'][1]['score']), 19)
        self.assertEqual(last_week_data['examples'][2]['user_id'], 'user1')
        self.assertEqual(int(last_week_data['examples'][2]['score']), 10)
        self.assertEqual(last_week_data['examples'][3]['user_id'], 'user3')
        self.assertEqual(int(last_week_data['examples'][3]['score']), 8)
            
##### Run the test #####
if __name__ == '__main__':
    unittest.main()