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

empty_list = [empty_item, empty_item, empty_item]

top_table.put_item(Item={'key' : "last_day", "submissions" : empty_list, "examples" : empty_list})
top_table.put_item(Item={'key' : "last_week", "submissions" : empty_list, "examples" : empty_list})
top_table.put_item(Item={'key' : "last_month", "submissions" : empty_list, "examples" : empty_list})
top_table.put_item(Item={'key' : "last_year", "submissions" : empty_list, "examples" : empty_list})
top_table.put_item(Item={'key' : "all_time", "submissions" : empty_list, "examples" : empty_list})


