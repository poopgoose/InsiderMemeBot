"""
This application runs as its own process, and continuously monitors the subreddits defined
in the AWS DynamoDB Database for IMT template requests
"""
import os
import praw
from TemplateRequestListener import TemplateRequestListener


###########################
##     AUTHENTICATION    ##
###########################

# Authenticate and create reddit instance
reddit = praw.Reddit(client_id = os.environ['IMT_CLIENT_ID'],
                     client_secret = os.environ['IMT_CLIENT_SECRET'],
                     password=os.environ['IMT_PASSWORD'],
                     user_agent="InsiderMemeBotScript by " + os.environ['IMT_USERNAME'],
                     username=os.environ['IMT_USERNAME'])

TEST_MODE = os.environ['IMT_TEST_MODE'] == "true"

request_listener = TemplateRequestListener(reddit, TEST_MODE)

request_listener.run()

