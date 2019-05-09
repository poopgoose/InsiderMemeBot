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
        self.client = boto3.client('dynamodb', region_name='us-east-2')

        # Determine if we're using the actual data, or the development data
        if not test_mode:
            self.user_table = self.dynamodb.Table('Users')
            self.tracking_table = self.dynamodb.Table('Tracking')
            self.vars_table = self.dynamodb.Table('Vars')
            self.template_request_table = self.dynamodb.Table('TemplateRequests')
        else:
            self.user_table = self.dynamodb.Table('Users-dev')
            self.tracking_table = self.dynamodb.Table('Tracking-dev')
            self.vars_table = self.dynamodb.Table('Vars-dev')
            self.template_request_table = self.dynamodb.Table('TemplateRequests-dev')

    ###########################################################################
    ###                         CORE FUNCTIONS                              ###
    ###########################################################################

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

    def get_item(self, table_id, key):
        """
        Gets an item from the AWS database
        table_id: One of the IDs defined in the Tables subclass
        key: The boto3 Key item for identifying the item to get
        """
        try:
            return self.get_table(table_id).get_item(Key=key)
        except Exception as e:
            message = "Unable to get item!\n" + \
                "    Table: " + self.tableIdToString(table_id) + "\n" + \
                "    Key: " + str(key) + "\n"
            print(message)
            print("Error: " + str(e))
            traceback.print_exc()
            return None


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
            return None

    def scan(self, table_id):
        """
        Scans the AWS database
        table_id: One of the IDs defined in the Tables subclass
        """ 
        try:
            return self.get_table(table_id).scan()
        except Exception as e:
            print("Unable to scan table: " + self.tableIdToString(table_id))
            print("Error: " + str(e))
            traceback.print_exc()

    def describe_table(self, table_id):
        """
        Gets the table description from the AWS database
        table_id: One of the IDs defined in the Tables subclass
        """
        try:
            return self.client.describe_table(TableName = self.tableIdToString(table_id))
        except Exception as e:
            print("Unable to get table description: " + self.tableIdToString(table_id))
            print("Error: " + str(e))
            traceback.print_exc()


    #############################################################################
    ###                      CONVENIENCE FUNCTIONS                            ###
    #############################################################################

    def get_variable(self, var_name):
        """
        Shortcut method for getting the value of a variable defined in the Vars table
        """
        key = {"key" : var_name}
        response = self.get_item(DataAccess.Tables.VARS, key)

        if response != None:
            # If the variable doesn't exist, return None
            if not 'Item' in response:
                print("No such variable: " + var_name)
                return None
            # If the variable exists, return it
            value = response['Item']['val']
            return value
        else:
            return None

    def set_variable(self, var_name, var_value):
        """
        Shortcut method for setting the value of a variable defined in the Vars table
        """
        item = {
            "key" : var_name,
            "val" : var_value
        }
        self.put_item(DataAccess.Tables.VARS, item)

    def create_new_user(self, redditor):
        """
        Creates a new user for the Redditor
        Returns True if successful, false otherwise

        redditor: The Redditor instance to make a user for
        """
        print("Creating user: " + str(redditor))

        new_user_item = {
            'user_id' : redditor.id,
            'username' : redditor.name,
            'submission_score' : 0,
            'distribution_score' :0,
            'total_score' : 0
        }
        if self.put_item(DataAccess.Tables.USERS, new_user_item):
            print("Created user: " + str(redditor))
            return True
        else:
            print("Failed to create user: " + str(redditor))
            return False


    def is_user(self, redditor):
        """
        Returns true if the given redditor is a user in the DynamoDB database.
        """
        
        # Query the table to get any user with a user_id matching the author's id
        response = self.query(DataAccess.Tables.USERS, Key('user_id').eq(author.id))
        num_matches = len(response['Items'])
        
        # If there is a match, then the author is already a user
        return num_matches > 0

    ###########################################################################
    ###                    Private Helper Functions                         ###
    ###########################################################################

    # Helper function
    def get_table(self, table_id):
        if table_id == DataAccess.Tables.USERS:
            return self.user_table
        elif table_id == DataAccess.Tables.TRACKING:
            return self.tracking_table
        elif table_id == DataAccess.Tables.VARS:
            return self.vars_table
        elif table_id == DataAccess.Tables.TEMPLATE_REQUESTS:
            return self.template_request_table
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
        elif id == DataAccess.Tables.VARS:
            return self.vars_table.name
        elif id == DataAccess.Tables.TEMPLATE_REQUESTS:
            return self.template_request_table.name
        else:
            print("Invalid ID for idToString: " + str(id))
            return "unknown"

    class Tables:
        """
        This helper class defines IDs for the tables that can be accessed
        """
        USERS = 0
        TRACKING = 1
        VARS = 2
        TEMPLATE_REQUESTS = 3
