from Features.Feature import Feature
import praw
import boto3


class ScoreboardFeature(Feature):
    """
    A feature that keeps score for the subreddit users
    """
    
    def __init__(self, reddit, subreddit_name):
        super(ScoreboardFeature, self).__init__(reddit, subreddit_name) # Call super constructor
        
        # Initialize the Amazon Web Service DynamoDB.
        # For this to work, the AWS credentials must be present on the system.
        # This can be done by using "pip install awscli", and then running "aws configure"
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('User')
        
       
        # Print out the first element from the table
        response = table.get_item(
            Key={'user': 'poopgoose1'}
        )
        item = response['Item']
        print(item)
    
    def check_condition(self):
        return True
    
    def perform_action(self):
        print("Running ScoreboardFeature with subreddit: " + self.subreddit_name)