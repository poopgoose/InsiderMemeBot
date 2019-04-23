"""
This module contains a set of helper functions for parsing comments and other strings
"""
import praw
import re

def get_urls(text):
    """
    Returns a link of unique URLs parsed from the given text
    """
    url_regex = r"https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,6}\b(?:[-a-zA-Z0-9@:%_\+.~#?&//=]*)"
    url_matches = re.findall(url_regex, text)

    if url_matches is None or len(url_matches) == 0:
        return []
        
    # Remove duplicate URLs/submissions. This can happen if the actual hyperlink is used as the comment body 
    # TODO: This is a messy workaround. It would be better to use an HTML parser or something to grab
    # the actual URL from a link, and ignore the text itself.
    unique_urls = []
    seen_ids = []

    for url in url_matches:
        try:
            submission_id = praw.models.Submission.id_from_url(url)
            if submission_id not in seen_ids:
                # The URL is a submission that hasn't been encountered yet
                unique_urls.append(url)
                seen_ids.append(submission_id)

        except praw.exceptions.ClientException as e:
            # The URL isn't to a reddit submission, so just add it if it's unique
            if not url in unique_urls:
                unique_urls.append(url)

    return unique_urls
