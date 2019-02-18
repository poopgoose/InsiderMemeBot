import praw
from getpass import getpass
from InsiderMemeBot import InsiderMemeBot
import json
import os
import sys

###########################
##     AUTHENTICATION    ##
###########################

# Authenticate and create reddit instance
reddit = praw.Reddit(client_id = os.environ['IMT_CLIENT_ID'],
                     client_secret = os.environ['IMT_CLIENT_SECRET'],
                     password=os.environ['IMT_PASSWORD'],
                     user_agent="InsiderMemeBotScript by " + os.environ['IMT_USERNAME'],
                     username=os.environ['IMT_USERNAME'])

TEST_MODE = os.environ['IMT_TEST_MODE']

# Create a new instance of InsiderMemeBot.
bot = InsiderMemeBot(reddit, TEST_MODE)
bot.run() # Run the bot
