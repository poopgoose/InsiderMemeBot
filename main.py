import praw
from getpass import getpass
from InsiderMemeBot import InsiderMemeBot
import json
import os
import sys


###########################
##    TEST-MODE FLAG     ##
###########################
# When TEST_MODE is True, the bot will use r/InsiderMemeBot_Test, to 
# verify behavior before staging on the real subreddit.
# TEST_MODE should always be set to true until a feature has been tested and deemed complete.
# When TEST_MODE is false, the bot will use r/InsiderMemeTrading.
TEST_MODE = True



################################
##     HELPER FUNCTIONS       ##
################################
def parseCredentials(jsonConfig):
    """
    Helper method for parsing a JSON Credentials file. The format of the JSON file must be as follows:
    {
        "password" : "my_password",
        "client_secret" : "my_client_secret"
    }
    
    @param jsonConfig: The path, relative to the working directory, of the credentials JSON config file
    """
    client_secret = ""
    password = ""
    with open(jsonConfig) as f:
        data = json.load(f)     
        try:
            client_secret = data["client_secret"]
            password = data["password"]
        except e:
            print("Invalid JSON credentials file. Make sure the 'client_secret' and 'password' fields are both present.")
            sys.exit(1)
    return (client_secret, password)        
        

###########################
##     AUTHENTICATION    ##
###########################

CLIENT_ID = "i-LOKCs1KuHE6Q"
USER_AGENT = "InsiderMemeBotScript by /u/InsiderMemeBot"
USERNAME = "InsiderMemeBot"

if len(sys.argv) > 1:
    # If the user provided a credentials JSON file, then use that to get the information
    CLIENT_SECRET, PASSWORD = parseCredentials(sys.argv[1])
else:
    # Prompt user for client secret and the password
    CLIENT_SECRET = getpass("Client secret: ")
    PASSWORD = getpass("Password: ")

# Authenticate and create reddit instance
reddit = praw.Reddit(client_id = CLIENT_ID,
                     client_secret = CLIENT_SECRET,
                     password=PASSWORD,
                     user_agent=USER_AGENT,
                     username=USERNAME)


# Verify that we are authenticated
print(reddit.user.me())

#########################

# Create a new instance of InsiderMemeBot.
bot = InsiderMemeBot(reddit, TEST_MODE)
bot.run() # Run the bot
