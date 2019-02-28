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

    def __init__(self, bot):
        super(ScoreboardFeature, self).__init__(bot) # Call super constructor



    def update(self):
        """
        Updates the scoreboard feature
        """

        print("Scoreboard!")