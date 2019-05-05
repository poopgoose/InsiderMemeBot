"""
This application runs as its own process, and continuously monitors the bot's inbox
for messages. When a message is received, it is stored in the AWS database for processing
"""
import os
import praw
from InboxListener import InboxListener


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

inbox_listener = InboxListener(reddit, TEST_MODE)
inbox_listener.run()

