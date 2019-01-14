from Features.Feature import Feature
import praw
import time
import json
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
        # Mods that are excluded
        self.excludedMods = []
        self.remindedMods = self.getRemindedMods()
        self.remindedRBPMods =  self.getRemindedRBPMods()

    def getRemindedMods(self):
        f = open("./remindedMods", "r")
        st = json.load(f)
        print(st)
        f.close()
        return st
    def getRemindedRBPMods(self):
        f = open("./remindedRBPMods", "r")
        st = json.load(f)
        f.close()
        return st
    def storeRemindedMods(self, remindedMods):
        f = open("./remindedMods", "w")
        json.dump(remindedMods, f)
        f.close()
    def getAllMods(self):
        modList = []
        for mod in self.reddit.subreddit(self.subreddit_name).moderator():
            if mod.name not in self.excludedMods:
                modList.append(mod)
        return modList
    def remindMod(self, moderator):
        if moderator.name not in self.remindedMods:
            self.reddit.redditor(moderator.name).message('Inactivity on r/' + self.subreddit_name, "You've been inactive for 24 hours on r/" + self.subreddit_name)
            self.remindedMods.append(moderator.name)
            ActivityTracker.storeRemindedMods(self,self.remindedMods)
    def remindRBP(self, moderator):
        if moderator.name not in self.remindedMods:
            self.reddit.redditor('RoseBladePhantom').message('User inactivity', "u/" + moderator.name + " has been inactive for 48 hours on r/" + self.subreddit_name)
            self.remindedRBPMods.append(moderator.name)
            ActivityTracker.storeRemindedMods(self, self.remindedRBPMods)
    def perform_action(self):
        mods = ActivityTracker.getAllMods(self)
        for moderator in mods:
            for entry in self.reddit.subreddit(self.subreddit_name).mod.log(mod=moderator, limit=1):
                UNIXTimestamp = entry.created_utc
                if (time.time() - (24 * 3600)) > UNIXTimestamp and moderator.name not in self.remindedMods:
                    # Mod has been inactive for too long - PM them
                    ActivityTracker.remindMod(self, moderator)
                    #print(self.remindedMods)
                    print(moderator.name)
                #if (time.time() - (24 * 3600)) < UNIXTimestamp:
                    #self.remindedMods.remove(moderator)
                if (time.time() - (48 * 3600)) > UNIXTimestamp and moderator.name not in self.remindedRBPMods:
                    ActivityTracker.remindRBP(self,moderator)
                    print(moderator.name)
