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
        
        with open(test_config_file, 'r') as f:   
            self.config_dict = json.load(f)
            
        with open(test_case_file, 'r') as f:
            self.test_case_dict = json.load(f)
            
        pprint(self.test_case_dict)
        





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