from Features.Feature import Feature
import praw
import time
# Activity Tracker by /u/TheTanooki-reddit
# BETA - Be Careful!!!

class ActivityTracker(Feature):
    """
    Tracks which mods are active.
    """
    ## Be careful-not fully impl'd yet
    def check_condition(self):
        return True
    def __init__(self, reddit, subreddit_name):
        self.reddit = reddit
        self.subreddit_name = subreddit_name
        # Mods that are excluded - UNIMPLEMENTED
        self.excludedMods = []
        self.remindedMods = []
        self.remindedRBPMods = []

    def getAllMods(self):
        modList = []
        for mod in self.reddit.subreddit(self.subreddit_name).moderator():
            if mod.name not in self.excludedMods:
                modList.append(mod)
        return modList
    def remindMod(self, moderator):
        self.reddit.redditor(moderator.name).message('Inactivity on r/' + self.subreddit_name, "You've been inactive for 24 hours on r/" + self.subreddit_name)
        self.remindedMods.append(moderator.name)
    def remindRBP(self, moderator):
        self.reddit.redditor('RoseBladePhantom').message('User inactivity', "u/" + moderator.name + " has been inactive for 48 hours on r/" + self.subreddit_name)
        self.remindedRBPMods.append(moderator)
    def perform_action(self):
        mods = ActivityTracker.getAllMods(self)
        for moderator in mods:
            for entry in self.reddit.subreddit(self.subreddit_name).mod.log(mod=moderator, limit=1):
                UNIXTimestamp = entry.created_utc
                if (time.time() - (24 * 3600)) > UNIXTimestamp and moderator not in self.remindedMods:
                    # Mod has been inactive for too long - PM them
                    ActivityTracker.remindMod(self, moderator)
                else:
                    self.remindedMods.remove(moderator)
                if (time.time() - (48 * 3600)) > UNIXTimestamp and moderator not in self.remindedRBPMods:
                    ActivityTracker.remindRBP(self,moderator)
