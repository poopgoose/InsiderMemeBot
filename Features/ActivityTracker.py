from Features.Feature import Feature
import praw
import time
# Activity Tracker by /u/TheTanooki-reddit
# BETA - Be Careful!!!

class ActivityTracker(Feature):
    """
    Tracks which mods are active.
    """
    # Mods that are excluded - UNIMPLEMENTED
    # excludedMods = []
    hoursOfInactivityPermitted = 24
    def check_condition(self):
        return True
    def __init__(self, reddit, subreddit_name):
        self.reddit = reddit
        self.subreddit_name = subreddit_name
        # Mods that are excluded - UNIMPLEMENTED
        # self.excludedMods = []
        self.hoursOfInactivityPermitted = 24

    def getAllMods(self):
        modList = []
        for mod in self.reddit.subreddit(self.subreddit_name).moderator():
            modList.append(mod)
        return modList
    def perform_action(self):
        mods = ActivityTracker.getAllMods(self)
        for moderator in mods:
            for entry in self.reddit.subreddit(self.subreddit_name).mod.log(mod=moderator, limit=1):
                UNIXTimestamp = entry.created_utc
                if (time.time() - (self.hoursOfInactivityPermitted * 3600)) > UNIXTimestamp:
                    # Mod has been inactive for too long
                    print("/u/" + moderator.name + " has been inactive for too long")
