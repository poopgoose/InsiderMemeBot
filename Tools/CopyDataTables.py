"""
This script empties the development tables, and re-populates with the current contents of the real,
production databases
"""


import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
import decimal

dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
users_table = dynamodb.Table("Users")
tracking_table = dynamodb.Table("Tracking")

users_dev = dynamodb.Table("Users-dev")
tracking_dev = dynamodb.Table("Tracking-dev")


try:

    # Users
    response = users_table.scan()

    for item in response["Items"]:
        users_dev.put_item(Item=item)

    # Tracking
    response = tracking_table.scan()
    for item in response["Items"]:
        tracking_dev.put_item(Item=item)
        
except ClientError as e:
    print(e.response['Error']['Message'])
