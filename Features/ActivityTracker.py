from Features.Feature import Feature
import praw

# Activity Tracker by /u/TheTanooki-reddit
# BETA - Be Careful!!!

class ActivityTracker(Feature):
    """
    Tracks which mods are active.
    """
    # Mods that are excluded
    excludedMods = []
    hoursOfInactivityPermitted = 24
    def check_condition(self):
        return True
    def __init__(self):
        run()
    def getAllMods(self):
        modList = []
        for mod in subreddit.moderator():
            modList.append(mod)
        return modList
    def run(self):
        mods = getAllMods()
        for moderator in mods:
            for entry in reddit.subreddit(subreddit_name).mod.log(mod=moderator, limit=1):
                UNIXTimestamp = entry.created_utc
                if (time.time() - (hoursOfInactivityPermitted * 3600)) > UNIXTimestamp:
                    # Mod has been inactive for too long
                    print("/u/" + moderator + " has been inactive for too long")
