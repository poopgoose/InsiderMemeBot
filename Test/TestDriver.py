import praw
import json
import os
import sys
from pprint import pprint

class TestDriver:
    """
    Main class for driving a test case for InsiderMemeBot
    """
    
    def __init__(self, test_config_file, test_case_file):
        """
        Creates a new instance of TestDriver
        @param test_config_file: The relative path to the test_config JSON file
        @param test_case_file:   The relative path to the test_case JSON file
        """
        
        # Load the dictionaries from JSON
        with open(test_config_file, 'r') as f:   
            self.config_dict = json.load(f)
            
        with open(test_case_file, 'r') as f:
            self.test_dict = json.load(f)
            
        # Initialize the test case data
        self.__init_test_case()
            
        # Initalize the Reddit instance
        self.connect()
            
    def __init_test_case(self):
        """
        Helper function for __init__   
        """              
        self.test_name = self.test_dict["test_name"]
        
        # Build the description string - TODO: Will only work properly if the description 
        # is given as a list. Add logic to simplify it if it's already just a single string
        self.test_description = ""
        for line in self.test_dict["description"]:
            self.test_description = self.test_description + line + "\n"
            
        self.test_scenario = self.test_dict["scenario"] # The test scenario dictionary
        

        
                    
    def connect(self):
        """
        Uses the credentials in test_config_file to connect to Reddit
        """
        self.reddit = praw.Reddit(
            client_id = self.config_dict["user"]["client_id"],
            client_secret = self.config_dict["user"]["client_secret"],
            password = self.config_dict["user"]["password"],
            user_agent = self.config_dict["user"]["user_agent"],
            username= self.config_dict["user"]["username"])
        
        
        subreddit_name = self.config_dict["subreddit"]
        self.subreddit = self.reddit.subreddit(subreddit_name)
        
        # Verify that we are authenticated
        print("Authenticated Reddit user: " + str(self.reddit.user.me()))
        print("Using Subreddit: " + subreddit_name)
        
            
    def execute(self):
        """
        Execute the test case
        """
        print("Executing Test Case: " + self.test_name)
        print("Description: ")
        
        # Execute each action in the scenario
        for action_dict in self.test_scenario:
            action_type = action_dict["action"]
            # Determine the type of action, and call the appropriate handler
            if action_type == "submission":
                self.__execute_submission(action_dict)
            else:
                print("Error: Unknown action type: " + str(action_type))
                exit(1)
            
    def __execute_submission(self, submission_dict):
        """
        Executes the "submission" action
        """
        
        # Create a submission to the subreddit
        submission_title = submission_dict["title"]
        submission_text  = submission_dict["text"]
        comment_dict = submission_dict["comments"]
        
        submission = self.subreddit.submit(submission_title, selftext=submission_text, send_replies=False)
        
        # Create the comment tree on the submission
        self.__create_comment_tree(comment_dict, submission)
        
        
    def __create_comment_tree(self, comment_dict, parent):
        """
        Creates a tree of comments defined in comment_dict on the provided parent
        @param comment_dict: The comment dictionary
        @param parent: The parent item for the comment. Either a Submission or another Comment.
        """
        
        for comment_item in comment_dict:
            # Create the comment
            comment_text = comment_item["text"]
            comment = parent.reply(comment_text)
            
            # If the comment has child comments, continue recursively
            if "comments" in comment_item:
                child_dict = comment_item["comments"]
                self.__create_comment_tree(child_dict, comment)
            
        
        


if __name__ == "__main__" :
    # Create a new TestDriver with the args
    if len(sys.argv) != 3:
        print("Usage: TestDriver.py <test_config_file> <test_case_file>")
        print("    test_config_file: Relative path to the test_config JSON file")
        print("    test_case_file:   Relative path to the test_case JSON file")
        exit(1)
        
    test_config_file = sys.argv[1]
    test_case_file = sys.argv[2]
    td = TestDriver(test_config_file, test_case_file)
    td.execute()