import praw
from getpass import getpass


# CONSTANTS
CLIENT_ID = "i-LOKCs1KuHE6Q"
USER_AGENT = "InsiderMemeBotScript by /u/InsiderMemeBot"
USERNAME = "InsiderMemeBot"


# The CLIENT SECRET is kept secret, and not stored in this repo.
# It must be provided by the user at runtime.
CLIENT_SECRET = getpass("Client secret: ")

# Likewise, the password for the InsiderMemeBot is also kept secret, and 
# must be provided by the user at runtime.
PASSWORD = getpass("Password: ")


# Authenticate and create reddit instance
reddit = praw.Reddit(client_id = CLIENT_ID,
                     client_secret = CLIENT_SECRET,
                     password=PASSWORD,
					 user_agent=USER_AGENT,
					 username=USERNAME)


# Verify that we are authenticated
print(reddit.user.me())