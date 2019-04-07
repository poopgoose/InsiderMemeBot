from Features.Feature import Feature
from Utils.DataAccess import DataAccess
import os
import praw

class AutoFlairFeature(Feature):
    """
    Service to manage flair and automatically select the correct flair
    """
    def __init__(self, bot):
        super(AutoFlairFeature, self).__init__(bot)
        