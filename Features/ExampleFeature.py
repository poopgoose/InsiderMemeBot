from Features.Feature import Feature
import praw


class ExampleFeature(Feature):
    """
    An example feature. Doesn't do very much.
    """
    
    
    def run(self):
        for submission in self.subreddit.stream.submissions():
            # TODO: Test with more than 32 comments
            for comment in submission.comments.list():
                if "!InsiderMemeBot" in comment.body:
                    # The comment is requesting action from InsiderMemeBot. Write a response!
                    print("Replying to comment!")
                    comment.reply("Did somebody call InsiderMemeBot? This is just a test response. More features to come!")