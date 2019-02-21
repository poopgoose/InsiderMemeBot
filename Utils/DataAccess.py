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
            response = self.get_table(table_id).put_item(Item=item)
            return True
        except Exception as e:
            message = "Unable to add item to " + self.tableIdToString(table_id) + " table:\n" + str(item)
            print(message)
            print("Error: " + str(e))
            traceback.print_exc()

            return False

    def update_item(self, table_id, key, update_expr, expr_attr_vals):
        """
        Updates the item in the database
        table_id: One of the IDs defined in the Tables subclass
        key: The boto3 Key item for identifying the item to update
        update_expr: The boto3 UpdateExpression for updating the item
        expr_attr_vals: The boto3 ExpressionAttributeValues for updating the item

        Returns whether or not the update was successful
        """

        try:
            
            response = self.get_table(table_id).update_item(
                Key=key, UpdateExpression=update_expr, ExpressionAttributeValues=expr_attr_vals)

            return True
        except Exception as e:
            message = "Unable to update item!\n" + \
                "    Table: " + self.tableIdToString(table_id) + "\n" + \
                "    Key: " + str(key) + "\n" + \
                "    UpdateExpression: " + str(update_expr) + "\n" + \
                "    ExpressionAttributeVallues: " + str(expr_attr_vals)
            print(message)
            print("Error: " + str(e))
            traceback.print_exc()
            return False

    def delete_item(self, table_id, key):
        """
        Deletes an item in the database
        table_id: One of the IDs defined in the Tables subclass
        key: The boto3 Key item for identifying the item to delete

        Returns whether or not the delete was successful
        """
        try:
            response = self.get_table(table_id).delete_item(Key=key)
            return True
        except Exception as e:
            message = "Unable to delete item!\n" + \
                "    Table: " + self.tableIdToString(table_id) + "\n" + \
                "    Key: " + str(key) + "\n"
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
            return self.get_table(table_id).query(KeyConditionExpression=key_condition_expr)
        except Exception as e:
            message = "Unable to query table: " + self.tableIdToString(table_id) + \
                "table:\n" + "Key condition expr: " + str(key_condition_expr)
            print(message)
            print("Error: " + str(e))
            traceback.print_exc()

    def scan(self, table_id):
        """
        Scans the AWS database
        table_id: One of the IDs defined in the Tables subclass
        """ 
        try:
            return self.get_table(table_id).scan()
        except Exception as e:
            message = "Unable to scan table: " + self.tableIdToString(table_id)

    
    # Helper function
    def get_table(self, table_id):
        if table_id == DataAccess.Tables.USERS:
            return self.user_table
        elif table_id == DataAccess.Tables.TRACKING:
            return self.tracking_table
        else:
            raise RuntimeError("Bad Table Id: " + str(table_id))




    def tableIdToString(self, id):
        """
        Helper function for returning the string representation for the table
        id: The ID of the table to get the string representation for
        """
        if id == DataAccess.Tables.USERS:
            return self.user_table.name
        elif id == DataAccess.Tables.TRACKING:
            return self.tracking_table.name
        else:
            print("Invalid ID for idToString: " + str(id))
            return "unknown"

    class Tables:
        """
        This helper class defines IDs for the tables that can be accessed
        """
        USERS = 0
        TRACKING = 1
