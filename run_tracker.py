"""
This application runs as its own service, and continuously tracks the 
items in the AWS Tracking database. It updates the scores in the database as it reads the updated values
from PRAW
"""
import os
import praw
from Tracker.Tracker import Tracker


###########################
##     AUTHENTICATION    ##
###########################

# Authenticate and create reddit instance
reddit = praw.Reddit(client_id = os.environ['IMT_CLIENT_ID'],
                     client_secret = os.environ['IMT_CLIENT_SECRET'],
                     password=os.environ['IMT_PASSWORD'],
                     user_agent="InsiderMemeBotScript by " + os.environ['IMT_USERNAME'],
                     username=os.environ['IMT_USERNAME'])

TEST_MODE = os.environ['IMT_TEST_MODE'] != "false"

tracker = Tracker(reddit, TEST_MODE)

tracker.run()