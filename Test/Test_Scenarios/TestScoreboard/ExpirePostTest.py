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




###################### Initialize the Feature under test #################
reddit = praw.Reddit(client_id = os.environ['IMT_CLIENT_ID'],
                     client_secret = os.environ['IMT_CLIENT_SECRET'],
                     password=os.environ['IMT_PASSWORD'],
                     user_agent="InsiderMemeBotScript by " + os.environ['IMT_USERNAME'],
                     username=os.environ['IMT_USERNAME'])

test_mode = True
test_bot = InsiderMemeBot(reddit, test_mode)
scoreboard_feature = ScoreboardFeature(test_bot)

# Initialize database
dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
user_table = dynamodb.Table('Users-dev')
top_posts_table = dynamodb.Table('TopPosts-dev')

################## Initialize Test Data #################

def add_user(user):
    user_table.put_item(Item=
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

def make_data(user, score, is_example):
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

add_user('user1')
add_user('user2')
add_user('user3')
add_user('user4')
add_user('user5')

user1_template = make_data('user1', 10, False)
user1_example  = make_data('user1', 10, True)
user2_template = make_data('user2', 9, False)
user2_example  = make_data('user2', 19, True)
user3_template = make_data('user3', 11, False)
user3_example  = make_data('user3', 8, True)
user4_template = make_data('user4', 6, False)
user4_example  = make_data('user4', 20, True)


scoreboard_feature.on_finished_tracking(user1_template)
scoreboard_feature.on_finished_tracking(user1_example)
scoreboard_feature.on_finished_tracking(user2_template)
scoreboard_feature.on_finished_tracking(user2_example)
scoreboard_feature.on_finished_tracking(user3_template)
scoreboard_feature.on_finished_tracking(user3_example)
scoreboard_feature.on_finished_tracking(user4_template)
scoreboard_feature.on_finished_tracking(user4_example)
