from Features.Feature import Feature
import praw


class DebugFeature(Feature):
    """
    A debug feature that plays through a scenario to 
    create new posts and comments for testing other features.
    """
    
    def __init__(self, debug_scenario):
        self.debug_scenario
    
    def check_condition(self):
        return True
    
    def perform_action(self):
    
    
#    def run(self):
#        for submission in self.subreddit.stream.submissions():
#            # TODO: Test with more than 32 comments
#            for comment in submission.comments.list():
#                if "!InsiderMemeBot" in comment.body:
#                    # The comment is requesting action from InsiderMemeBot. Write a response!
#                    print("Replying to comment!")
#                    comment.reply("Did somebody call InsiderMemeBot? This is just a test response. More features to come!")