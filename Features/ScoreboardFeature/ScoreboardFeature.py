from Features.Feature import Feature
import decimal
import praw
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import json
import re
import time
from datetime import datetime, timedelta, tzinfo
from Utils.DataAccess import DataAccess
import pytz

class ScoreboardFeature(Feature):
    """
    This class is responsible for keeping track of the scoreboard data, and for 
    posting the scoreboard in a comment several times per day
    """

    UPDATE_INTERVAL =  1 * 60 # Update once per minute
    POST_TIME_TOLERANCE = 2 * 60 # Can post within 2 minutes on either side of the target

    # Time interval constants, in seconds
    LAST_DAY = 60 * 60 * 24
    LAST_WEEK = LAST_DAY * 7
    LAST_MONTH = LAST_DAY * 30
    LAST_YEAR = LAST_DAY * 365

    # Times, relative to midnight (in seconds) UTC to post the scoreboarddatetime.utcnow
    

    #SCOREBOARD_POST_TIMES = \
    #[
    #    1 * 60 * 60, # 1AM UTC (7 AM EST)
    #    7 * 60 * 60,  # 7AM UTC
    #    13 * 60 * 60, # 1PM UTC
    #    19 * 60 * 60, # 7PM UTC
    #]
    # POST EVERY HOUR FOR TESTING
    SCOREBOARD_POST_TIMES = \
    [
        0 * 60 * 60
        1 * 60 * 60,
        2 * 60 * 60,
        3 * 60 * 60,
        4 * 60 * 60,
        5 * 60 * 60,
        6 * 60 * 60,
        7 * 60 * 60,
        8 * 60 * 60,
        9 * 60 * 60,
        10 * 60 * 60,
        11 * 60 * 60,
        12 * 60 * 60,
        13 * 60 * 60,
        14 * 60 * 60,
        15 * 60 * 60,
        16 * 60 * 60,
        17 * 60 * 60,
        18 * 60 * 60,
        19 * 60 * 60,
        20 * 60 * 60,
        21 * 60 * 60,
        22 * 60 * 60,
        23 * 60 * 60
    ]

    def __init__(self, bot):
        super(ScoreboardFeature, self).__init__(bot) # Call super constructor

        self.prev_update_time = 0
        self.timezone = pytz.timezone('US/Eastern')
        self.already_posted = False # Set to true when a scoreboard has just been posted, so it isn't posted again until the next target time

    def update(self):
        """
        Updates the scoreboard feature
        """

        if time.time() >= self.prev_update_time + ScoreboardFeature.UPDATE_INTERVAL:
            self.__flush_old_items() # Flush out any expired items from the database

            now = datetime.utcnow()
            seconds_since_midnight = (now - now.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()
            m,s = divmod(seconds_since_midnight, 60)
            h,m = divmod(m, 60)  
            is_in_post_range = False # Whether or not we're within a valid time interval to post the scoreboard
            for post_time in ScoreboardFeature.SCOREBOARD_POST_TIMES:
                if abs(seconds_since_midnight - post_time) <= ScoreboardFeature.POST_TIME_TOLERANCE:
                    is_in_post_range = True
                    break

            if is_in_post_range:
                if not self.already_posted:
                    # We're in range of a target time and haven't posted yet, so post the scoreboard!
                    print("Posting scoreboard...")
                    update_begin = int(time.time())
                    self.post_scoreboard()
                    update_end = int(time.time())
                    print("Time to create scoreboard: " + str(update_end - update_begin) + " seconds.")
                    self.already_posted = True
            else:
                self.already_posted = False # Reset until we're in the next valid posting range
            self.prev_update_time = int(time.time())

    def post_scoreboard(self):
        """
        Posts the Scoreboard to Reddit
        """

        # Get the users from the user database
        user_data = self.bot.data_access.scan(DataAccess.Tables.USERS)['Items']

        # Sort by score types
        users_by_total = sorted(user_data, key=lambda x: x['total_score'], reverse=True)
        users_by_submission = sorted(user_data, key=lambda x: x['submission_score'], reverse=True)
        users_by_distribution = sorted(user_data, key=lambda x: x['distribution_score'], reverse=True)

        # Create the map for each user's rank
        ranking_map = {}
        for i in range(0, len(users_by_total)):
            user = users_by_total[i]
            ranking_map[user['user_id']] = {
                'total' : decimal.Decimal(i + 1),
                'submission' : decimal.Decimal(0),
                'distribution' : decimal.Decimal(0)
            }

        for i in range(0, len(users_by_submission)):
            user = users_by_submission[i]
            ranking_map[user['user_id']]['submission'] = decimal.Decimal(i + 1)
        for i in range(0, len(users_by_distribution)):
            user = users_by_distribution[i]
            ranking_map[user['user_id']]['distribution'] = decimal.Decimal(i + 1)

        # Update each User's Rank
        # NOTE: If posting the scoreboard is slow, it's probably because this loop is causing the 
        # AWS DynamoDB service to throttle write requests.
        for user_id in ranking_map:
            ranking_dict = ranking_map[user_id]
            key = {'user_id' : user_id}
            expr = "set ranking = :dict"
            attrs = {":dict" : ranking_dict}
            self.bot.data_access.update_item(DataAccess.Tables.USERS, key, expr, attrs)
        print("Updated ranking for " + str(len(ranking_map)) + " users.")


        # Post the scoreboard
        self.__create_scoreboard_comment(users_by_total, users_by_submission, users_by_distribution)


    def on_finished_tracking(self, tracking_item):
        """
        Handle when a post has finished tracking
        tracking_item: The item that has finished tracking
        """

        self.__flush_old_items() # Get rid of any outdated posts in the high score list

        # Get the user info for the post that finished tracking
        user_info = self.bot.data_access.query(DataAccess.Tables.USERS,
            key_condition_expr = Key('user_id').eq(tracking_item['author_id']))['Items'][0]

        # The item that will be stored in the TopPosts database if it has a high score
        new_top_item = {
            'submission_id' : tracking_item['submission_id'],
            'user_id' : user_info['user_id'],
            'username' : user_info['username'],
            'score' : tracking_item['score'],
            'permalink' : tracking_item['permalink'],
            'scoring_time' : decimal.Decimal(int(time.time())),
            'title' : tracking_item['title'],
            'is_example' : tracking_item['is_example']
        }

        # Return if the post doesn't have a high score for the day
        if not self.__compare_with_posts(new_top_item, "last_day"):
            return

        # After updating the last-day high scores, return if the post isn't a high score for the week
        if not self.__compare_with_posts(new_top_item, "last_week"):
            return

        # After updating the last week high scores, return if the post isn't a high score for the month
        if not self.__compare_with_posts(new_top_item, "last_month"):
            return

        # After updating the last month high scores, return if the post isn't a high score for the year
        if not self.__compare_with_posts(new_top_item, "last_year"):
            return

        # After updating the last year high scores, check and update if the post is a high score of all time
        self.__compare_with_posts(new_top_item, "all_time")


    def __compare_with_posts(self, item, key_name):
        """
        Helper function for on_finished_tracking.
        Compares the given item with the TopPosts data table, against the data with the given key_name.
        Updates the database with the new TopPosts, if the given item has a high score.

        item: The item to compare with the list
        key_name: A string, one of "last_day", "last_week", "last_month", "last_year", or "all_time".

        Returns: True if the post is a high score and the database was updated. False otherwise
        """

        key_expr = Key('key').eq(key_name)
        top_row = self.bot.data_access.query(DataAccess.Tables.TOP_POSTS, key_expr)['Items'][0]
        items_key = 'examples' if item['is_example'] else 'submissions'

        # Items, sorted by score (highest first)
        top_items = sorted(top_row[items_key], key=lambda x: x['score'], reverse=True)
        updated_items = top_items

        is_updated = False
        for i in range(0, len(top_items)):
            top_item = top_items[i]
            if top_item['submission_id'] == "No Data":
                # There's no data for the time period, so just take the slot
                updated_items[i] = item
                is_updated = True
                break
            elif top_item['score'] < item['score']:
                # Insert the new item, and push out the one in last place
                updated_items.insert(i, item)
                del updated_items[-1]
                is_updated = True
                break

        if is_updated:
            # Update the database
            update_key = {'key' : key_name}
            update_expr = "set " + items_key + " = :updated_items"
            update_attrs = {":updated_items" : updated_items}
            self.bot.data_access.update_item(
                DataAccess.Tables.TOP_POSTS, update_key, update_expr, update_attrs)

        return is_updated

    def __create_scoreboard_comment(self, users_by_total, users_by_submission, users_by_distribution):
        """
        Helper function for update. Creates the comment for the scoreboard

        users_by_total: The list of all users, sorted by total_score, descending
        users_by_submission: The list of all users, sorted by submission_score, descending
        users_by_distribution: The list of all users, sorted by distribution score, descending
        """

        # Create the post title from the timezone
        #now = self.timezone.localize(datetime.utcnow())
        now = datetime.now(tz=self.timezone)
        date_str =  now.strftime("%a, %b %d, %Y:")
        time_str = now.strftime("%I:%M %p %Z")
        title_str = "SCOREBOARD: " + date_str + "\n\n" + time_str

        # The number of users to include in the scoreboard. users_by_total, users_by_submission, and
        # users_by_distribution are all the same length, just different orderings, so we can just use
        # users_by_total to determine the number of places to show
        num_places = min(len(users_by_total), 10)

        #########################################
        ##### Construct the scoreboard text #####
        #########################################

        ### Overall Score ###
        table_header = \
        "Ranking | Name | Score\n" + \
        ":------:|:-----|:-----"

        scoreboard_text = "#Top Traders\n  " + table_header + "\n|| **OVERALL** |"
        for i in range(0, num_places):
            row_text = str(i + 1) + " | " + users_by_total[i]['username'] + " | " + str(users_by_total[i]['total_score'])
            scoreboard_text = scoreboard_text + "\n" + row_text

        ### Submission Score ###
        scoreboard_text = scoreboard_text + "\n | |  " + \
            "\n || **TOP SUBMITTERS** |"
        for i in range(0, num_places):
            row_text = str(i + 1) + " | " + users_by_submission[i]['username'] + " | " + str(users_by_submission[i]['submission_score'])
            scoreboard_text = scoreboard_text + "\n" + row_text

        ### Distribution Score ###
        scoreboard_text = scoreboard_text + "\n | |  " + \
            "\n || **TOP DISTRIBUTORS** |"
        for i in range(0, num_places):
            row_text = str(i + 1) + " | " + users_by_distribution[i]['username'] + " | " + str(users_by_distribution[i]['distribution_score'])
            scoreboard_text = scoreboard_text + "\n" + row_text

        ### Top posts ###
        scoreboard_text = scoreboard_text + "\n\n" + self.__create_top_post_markup()    

        print("POSTING SCOREBOARD: " + time_str)
        self.bot.subreddit.submit(
            title = title_str,
            selftext = scoreboard_text)

    def __create_top_post_markup(self):
        """
        Helper function to show the top posts
        """
        markup_str = "------\n"
        markup_str = markup_str + "#Top Posts\n  " 
        markup_str = markup_str + "Templates | Examples\n" + \
                                  ":-------- | :-------\n"
        markup_str = markup_str + self.__create_top_post_list_markup("Yesterday", "last_day") + "\n &nbsp; | \n "
        markup_str = markup_str + self.__create_top_post_list_markup("This week", "last_week") + "\n &nbsp; |\n "
        markup_str = markup_str + self.__create_top_post_list_markup("This month", "last_month") + "\n &nbsp; |\n "
        markup_str = markup_str + self.__create_top_post_list_markup("This Year", "last_year") + "\n &nbsp; |\n "
        markup_str = markup_str + self.__create_top_post_list_markup("All Time", "all_time") + "\n"
        return markup_str

    def __create_top_post_list_markup(self, title, key):
        """
        Helper funcdtion to show the top posts for a single list in the TopPosts data table
        title: The title for the table in the comment
        key: The key for the table in the database
        """
        markup_str = "**" + title + "** ||"

        top_posts = self.bot.data_access.query(DataAccess.Tables.TOP_POSTS, Key('key').eq(key))['Items'][0]

        # Examples and Submissions, sorted by score
        top_examples = sorted(top_posts["examples"], key=lambda x: x['score'], reverse=True)
        top_templates = sorted(top_posts["submissions"], key=lambda x: x['score'], reverse=True)
        
        for i in range(0, 3):
            markup_str = markup_str + "\n" + \
              "**" + str(i + 1) + ":** [" + top_templates[i]['title'] + "](" + top_templates[i]['permalink'] + ") | " + \
              "**" + str(i + 1) + ":** [" + top_examples[i]['title'] + "](" + top_examples[i]['permalink'] + ")\n" + \
              "&nbsp;" * 4 + "Author: " + top_templates[i]['username'] + " | " + \
              "&nbsp;" * 4 + "Author: " + top_examples[i]['username'] + "\n" + \
              "&nbsp;" * 4 + "Score: " + str(top_templates[i]['score']) + " | " + \
              "&nbsp;" * 4 + "Score: " + str(top_examples[i]['score'])

        return markup_str

    def __flush_old_items(self):
        """
        Flushes old items from the TopPosts data table.
        i.e, it will remove a 25-hour old post from the "last_day" list.
        """
        self.__flush_old_items_from_list("last_day", ScoreboardFeature.LAST_DAY)
        self.__flush_old_items_from_list("last_week", ScoreboardFeature.LAST_WEEK)
        self.__flush_old_items_from_list("last_month", ScoreboardFeature.LAST_MONTH)
        self.__flush_old_items_from_list("last_year", ScoreboardFeature.LAST_YEAR)
    def __flush_old_items_from_list(self, key_name, max_age):
        """
        Helper function for __flush_old_items.
        key_name: The key of the lists to flush from the TopPosts table
        max_age: The maximum age, in seconds, to permit in the table.
        """

        # Items are never removed from the top score list, they're just replaced with empty placeholders
        empty_item =  {
            'submission_id' : 'No Data',
            'user_id' : 'No Data',
            'username' : 'No Data',
            'score' : decimal.Decimal(0),
            'permalink' : 'No Data',
            'scoring_time' : decimal.Decimal(0),
            'title' : 'No Data'
        }

        key_expr = Key('key').eq(key_name)
        data_row = self.bot.data_access.query(DataAccess.Tables.TOP_POSTS, key_expr)['Items'][0]

        # Flush examples and submissions
        item_keys = ["submissions", "examples"]
        for item_key in item_keys:
            item_list = data_row[item_key]
            updated_list = item_list
            is_updated = False
            for i in range(0, len(item_list)):
                item = item_list[i]
                item_age = int(time.time()) - int(item['scoring_time'])
                if item_age >= max_age and item['submission_id'] != 'No Data':
                    print("Removing expired item from high score table.")
                    print("  Submission: " + item['submission_id'])
                    print("  List: " + key_name)
                    print("  Age (s): " + str(item_age))
                    updated_list[i] = empty_item
                    is_updated = True

            if is_updated:

                # Sort the updated list by score, descending
                updated_list = sorted(updated_list, key=lambda x: x['score'], reverse=True)

                # Update the database
                update_key = {'key' : key_name}
                update_expr = "set " + item_key + " = :updated_items"
                update_attrs = {":updated_items" : updated_list}
                self.bot.data_access.update_item(
                    DataAccess.Tables.TOP_POSTS, update_key, update_expr, update_attrs)
