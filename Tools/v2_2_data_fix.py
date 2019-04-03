# This script migrates the TopPosts data table into the Vars table, with the 
# new data format required for version 2.2


import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
import decimal


# Copy the TopPosts data table into the new format in the Vars table
dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
top_table = dynamodb.Table("TopPosts")
vars_table = dynamodb.Table("Vars-dev")


old_all_time = top_table.get_item(Key={'key' : "all_time"})['Item']
old_last_day = top_table.get_item(Key={'key' : "last_day"})['Item']
old_last_week = top_table.get_item(Key={'key' : "last_week"})['Item']
old_last_month = top_table.get_item(Key={'key' : "last_month"})['Item']

def create_new_dict(old_dict, new_key):
    return {
        "key" : new_key,
        "val" :
        {
           "examples" : old_dict["examples"],
           "submissions" : old_dict["submissions"]
        }

    }


new_all_time_dict = create_new_dict(old_all_time, "scoreboard_top_all_time")
new_last_day_dict = create_new_dict(old_all_time, "scoreboard_top_last_day")
new_last_week_dict = create_new_dict(old_all_time, "scoreboard_top_last_week")
new_last_month_dict = create_new_dict(old_all_time, "scoreboard_top_last_month")
new_last_year_dict = create_new_dict(old_all_time, "scoreboard_top_last_year")

vars_table.put_item(Item=new_all_time_dict)
vars_table.put_item(Item=new_last_day_dict)
vars_table.put_item(Item=new_last_week_dict)
vars_table.put_item(Item=new_last_month_dict)
vars_table.put_item(Item=new_last_year_dict)