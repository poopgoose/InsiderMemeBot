#!/usr/bin/python

##Bot checks for quickly rising posts and returns info about them.
import praw
import time
from datetime import datetime

# Create the Reddit instance, includes all info so no praw file is needed. Keep this stuff secret.
reddit = praw.Reddit(client_id='<TODO>',2
                     client_secret='<TODO>', password='<TODO>',
                     user_agent='<TODO>', username='<TODO>',
                     check_for_updates=True,
                     comment_kind='t1', message_kind='t4',
                     redditor_kind='t2', submission_kind='t3',
                     subreddit_kind='t5',
                     oauth_url="https://oauth.reddit.com",
                     reddit_url="https://www.reddit.com",
                     short_url="https://redd.it")
        

posts_checked = [] #list to hold already alerted posts

with open('postids.txt', 'r') as f: #gets previous posts checked as not to repeat
    data = f.read()
    lines = data.splitlines()
    [posts_checked.append(x) for x in lines]
    
def getTime(postTime):  #returns seconds since submission was posted
    present = datetime.now()
    timeDifference = (present - postTime)
    #print(timeDifference.total_seconds()) #debug
    return int(timeDifference.total_seconds())

def getUPM(postTime, postScore): #gets upvotes per minute on popular post
    upm = float(postScore) / (float(postTime)/60)
    return upm

def getRise(upm): #returns certain phrase depending on the upvotes per minute
    if upm >= 2.5:
        return 'Rapidly Rising'
    if upm < 2.5 and upm >= 1.7:
        return 'Fast Rising'
    if upm < 1.7 and upm >= 1.3:
        return 'Steadily Rising'
    if upm < 1.3:
        return 'Slow Rising'
    
bot_diction = {} #holds info about rising posts and the bots subsequent posts/comments for it

##This loop runs the bot
while True:
    
    for submission in reddit.subreddit('memeeconomy').new(limit=None):
        
        if getTime(datetime.fromtimestamp(submission.created_utc)) > 2700: #stop retrieving posts after specified time (in seconds)
            break
        
        if submission.score >= 45: #Checks upvotes
            if submission.id not in posts_checked: #helps prevent showing same post
                secondsSince = getTime(datetime.fromtimestamp(submission.created_utc)) #gets time since post was made in seconds
                posts_checked.append(submission.id) #adds post id to a list to prevent repeats
                reddit.subreddit('insidermemetrading').submit('{} MemeEconomy Investment Oppurtunity '.format(getRise(getUPM(secondsSince, submission.score))) + str(datetime.fromtimestamp(submission.created_utc).strftime('%I:%M %p')) + ' EST', url=submission.shortlink, send_replies=False)
                with open('postids.txt', 'a') as f:
                    f.write(str(submission.id) + '\n')
                time.sleep(10) 
                for post in reddit.redditor('InvestOpportunityBot').submissions.new(limit=1): #adds info about bot post to a dictionary, post id for the post the bot makes, current UPM, a newUPM to compare against the old, timeOne and timeTwo to time 10 minute intervals, and commentUpdate to store the comment ID of market updates
                    bot_diction[submission.id] = {'ID':post.id, 'UPM':getUPM(secondsSince, submission.score), 'newUPM':0.0, 'timeOne':datetime.now(), 'timeTwo':datetime.now(), "commentUpdate":None}
                    post.reply("Market Updates:\n\n%.2f upvotes per minute at %s" % (submission.score/(secondsSince/60), str(datetime.now().strftime("%I:%M %p"))))
                time.sleep(10) #allows time for comment to process so when the bot checks it's new comments it will get the right id
                for comment in reddit.redditor('InvestOpportunityBot').comments.new(limit=1): #get the newly created comment id for fututre updating
                    bot_diction[submission.id]["commentUpdate"] = comment.id
                print('Post Made!')
        else:
            pass
    #upm = upvotes per minute
    if len(bot_diction) > 0: #if there are active posts this loop will run
        for key in bot_diction:  #compared times so every ten minutes the upm will be analyzed and bot will update the comment on it's posts how the post is doing
            secondsUPM = getTime(bot_diction[key]['timeOne']) - getTime(bot_diction[key]['timeTwo']) #handles the time in seconds between checks, runs the if statement if more than 600 seconds(10 minutes)
            #print(secondsUPM) #debug
            if secondsUPM > 600: #if time between updates is greater than ten minutes
                bot_diction[key]['timeOne'] = datetime.now()
                upm = getUPM(getTime(datetime.fromtimestamp(reddit.submission(id=key).created_utc)), reddit.submission(id=key).score) #calculates a new upm
                for comment in reddit.redditor('InvestOpportunityBot').comments.new(limit=None):
                    if comment.id == bot_diction[key]["commentUpdate"]:
                        if getTime(datetime.fromtimestamp(reddit.submission(id=key).created_utc)) > 5400 and upm >= 3.0: #if after 2 hours the post is still getting 3 upm, it is probably going to the front page
                            comment.edit(comment.body + '\n\nPost is possibly front page bound with %.2f upvotes per minute. %s' % (upm, str(datetime.now().strftime("%I:%M %p"))))
                            bot_diction[key]['UPM'] = upm
                            print('Front page')
                        elif upm <= 0.9: #below this upm the meme isn't really going anywhere
                            comment.edit(comment.body + '\n\nThe market is slowing down with %.2f upvotes per minute. %s' % (upm, str(datetime.now().strftime("%I:%M %p"))))
                            bot_diction[key]['UPM'] = upm
                            print('Dying out')
                        elif upm < bot_diction[key]['UPM'] - 0.2: #if upms have dropped this much its popularity is dying
                            comment.edit(comment.body + '\n\nDownward trend with %.2f upvotes per minute. %s' % (upm, str(datetime.now().strftime("%I:%M %p"))))
                            bot_diction[key]['UPM'] = upm
                            print('Downward Trend')
                        elif upm > bot_diction[key]['UPM'] + 0.2: #if upms have risen this much it's gaining popularity
                            comment.edit(comment.body + '\n\nUpward trend with %.2f upvotes per minute. %s' % (upm, str(datetime.now().strftime("%I:%M %p"))))
                            bot_diction[key]['UPM'] = upm
                            print('Upward Trend')
                        else: #if upms haven't changed much, it's staying steady
                            comment.edit(comment.body + '\n\nMarket is steady with %.2f upvotes per minute. %s' % (upm, str(datetime.now().strftime("%I:%M %p"))))
                            print('Market is steady')
            else:
                bot_diction[key]['timeTwo'] = datetime.now()
            #print(bot_diction) #debug
            for post in reddit.redditor('InvestOpportunityBot').new(limit=None): #if the posts is older than 1 hour 15 minutes it is deleted
                if getTime(datetime.fromtimestamp(post.created_utc)) > 4500: #4500 seconds / 1hr 15 minutes
                    if bot_diction[key]['ID'] == post.id:
                        bot_diction.pop(key, None)
                        post.delete()
                        break
            break
    else:
        print('No active threads')
        
    print('Restarting loop...')
    time.sleep(60) #time between loops, can be changed, used to help with rate limit
