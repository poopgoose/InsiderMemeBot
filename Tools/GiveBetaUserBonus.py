"""
This script is used to give a one-time point bonus to one or more users
"""

import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
import decimal

dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
users_table = dynamodb.Table("Users")

bonus_amount = 1000

try:

    # Beta testers
    fe = Attr('attributes').contains("beta")
    response = users_table.scan(
        FilterExpression=fe
    )

    beta_ids = []
    for item in response["Items"]:
        beta_ids.append(item["user_id"])

    print(len(beta_ids))

    # Give the bonus to the beta users
    for user_id in beta_ids:
        response = users_table.update_item(
            Key={'user_id' : user_id},
            UpdateExpression = "set submission_score = submission_score + :score, distribution_score = distribution_score + :score",
            ExpressionAttributeValues = {":score" : decimal.Decimal(bonus_amount)})
        
except ClientError as e:
    print(e.response['Error']['Message'])
