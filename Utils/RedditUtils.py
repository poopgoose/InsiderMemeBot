"""
This module contains a set of helper functions that can be used by other features of 
InsiderMemeBot.
"""


def is_moderator(subreddit, user):
    """
    Returns True if the given redditor is a moderator of the given subreddit

    subreddit: The praw.models.Subreddit instance for the subreddit
    user:  The praw.models.Redditor instance for the user

    Returns true if 'user' is a moderator of 'subreddit'
	"""
    modlist = subreddit.moderator(redditor=user)
    return len(modlist) > 0