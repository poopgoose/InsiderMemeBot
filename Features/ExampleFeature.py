from Features.Feature import Feature
import praw


class ExampleFeature(Feature):
    """
    An example feature. Doesn't do very much.
    """
    
    
    def run(self):
        print("Running on Subreddit: " + self.subreddit_name)