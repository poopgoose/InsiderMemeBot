import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import decimal
import time
import traceback

class DataAccess:
    """
    This class provides read/write access to the AWS DynamoDB Service
    """

    def __init__(self, test_mode):
    
        # Initialize the Amazon Web Service DynamoDB.
        # For this to work, the AWS credentials must be present on the system.
        # This can be done by using "pip install awscli", and then running "aws configure"
        self.dynamodb = boto3.resource('dynamodb', region_name='us-east-2')

        # Determine if we're using the actual data, or the development data
        if not test_mode:
            self.user_table = self.dynamodb.Table('Users')
            self.tracking_table = self.dynamodb.Table('Tracking')
        else:
            self.user_table = self.dynamodb.Table('Users-dev')
            self.tracking_table = self.dynamodb.Table('Tracking-dev')


    def put_item(self, table_id, item):
        """
        Adds the item to the database
        table_id: One of the IDs defined in the Tables subclass
        item: The boto3 item dictionary

        returns: True if successful, false otherwise 
        """
        try:
            if table_id == DataAccess.Tables.USERS:
                response = self.user_table.put_item(Item=item)
            elif table_id == DataAccess.Tables.TRACKING:
                response = self.tracking_table.put_item(Item=item)
            else:
                raise RuntimeError("Bad Table Id: " + str(table_id))

            return True

        except Exception as e:
            message = "Unable to add item to " + Tables.idToString(table_id) + " table:\n" + str(item)
            print(message)
            print("Error: " + str(e))
            traceback.print_exc()

            return False

    def query(self, table_id, key_condition_expr):
        """
        Queries the AWS database
        table_id: One of the IDs defined in the Tables subclass
        key_condition_expr: The KeyConditionExpression to query with
        """
        try:
            if table_id == DataAccess.Tables.USERS:
                response = self.user_table.query(KeyConditionExpression=key_condition_expr)
                return response
            elif table_id == DataAccess.Tables.TRACKING:
                response = self.tracking_table.query(KeyConditionExpression=key_condition_expr)
                return response
            else:
                raise RuntimeError("Bad Table Id: " + str(table_id))
        except Exception as e:
            message = "Unable to query table: " + Tables.idToString(table_id) + \
                "table:\n" + "Key condition expr: " + str(key_condition_expr)
            print(message)
            print("Error: " + str(e))
            traceback.print_exc()     

    class Tables:
        """
        This helper class defines IDs for the tables that can be accessed
        """
        USERS = 0
        TRACKING = 1

        def idToString(self, id):
            """
            Returns the string representation for the table
            id: The ID of the table to get the string representation for
            """
            if id == DataAccess.Tables.USERS:
                return self.user_table.name
            elif id == DataAccess.Tables.TRACKING:
                return self.tracking_table.name
            else:
                print("Invalid ID for idToString: " + str(id))
                return "unknown"