"""
This script is used to initialize the TopPosts data with empty information
"""


import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
import decimal

dynamodb = boto3.resource('dynamodb', region_name='us-east-2')

top_table = dynamodb.Table("TopPosts-dev")

empty_item =  {
        'submission_id' : 'No Data',
        'user_id' : 'No Data',
        'username' : 'No Data',
        'score' : decimal.Decimal(0),
        'permalink' : 'No Data',
        'scoring_time' : decimal.Decimal(0),
        'title' : 'No Data'
      }


# The number of items to populate the list with.
# The scoreboard will only show the top 3, but storing a larger number is necessary to store 
# "runner up" posts, that will take the place of the ones at the top if they expire.
num_items = 10

empty_list = [empty_item] * num_items

top_table.put_item(Item={'key' : "last_day", "submissions" : empty_list, "examples" : empty_list})
top_table.put_item(Item={'key' : "last_week", "submissions" : empty_list, "examples" : empty_list})
top_table.put_item(Item={'key' : "last_month", "submissions" : empty_list, "examples" : empty_list})
top_table.put_item(Item={'key' : "last_year", "submissions" : empty_list, "examples" : empty_list})
top_table.put_item(Item={'key' : "all_time", "submissions" : empty_list, "examples" : empty_list})


