"""
This script is used to initialize the TopPosts data with empty information
"""


import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
import decimal

dynamodb = boto3.resource('dynamodb', region_name='us-east-2')

top_table = dynamodb.Table("TopPosts-dev")


empty_map = {
    ":items" : [
      {
        'submission_id' : 'No Data',
        'user_id' : 'No Data',
        'username' : 'No Data',
        'score' : decimal.Decimal(0),
        'permalink' : 'No Data',
        'scoring_time' : decimal.Decimal(0)
      },
      {
        'submission_id' : 'No Data',
        'user_id' : 'No Data',
        'username' : 'No Data',
        'score' : decimal.Decimal(0),
        'permalink' : 'No Data',
        'scoring_time' : decimal.Decimal(0)
      },
      {
        'submission_id' : 'No Data',
        'user_id' : 'No Data',
        'username' : 'No Data',
        'score' : decimal.Decimal(0),
        'permalink' : 'No Data',
        'scoring_time' : decimal.Decimal(0)
      },
    ]
}

top_table.put_item(Item={'key' : "last_day", "items" : empty_map})
top_table.put_item(Item={'key' : "last_week", "items" : empty_map})
top_table.put_item(Item={'key' : "last_month", "items" : empty_map})
top_table.put_item(Item={'key' : "last_year", "items" : empty_map})
top_table.put_item(Item={'key' : "all_time", "items" : empty_map})

