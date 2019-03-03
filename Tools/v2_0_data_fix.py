###
# This script fixes the data tables used in InsiderMemeBot v1.2 so that they'll becompatible
# with v2.0
###

### 1. Create the 'total_score' column
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
import decimal


USER_TABLE_NAME = "Users-dev"


dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
users_table = dynamodb.Table(USER_TABLE_NAME)
users = users_table.scan()['Items']

for user in users:
    if not 'total_score' in user:
        # This is an old item, needs to be updated!
        total_score = user['distribution_score'] + user['submission_score']

        key = {'user_id' : user['user_id']}
        update_expr = "set total_score = :total"
        expr_attr_vals = {":total" : decimal.Decimal(total_score)}
        users_table.update_item(Key=key, UpdateExpression=update_expr, ExpressionAttributeValues=expr_attr_vals)