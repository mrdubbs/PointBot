import MySQLdb
import json
import urllib2
import threading
from cfg import *
import socket
import re
import random
from time import *

HOST = 'irc.chat.twitch.tv'
PORT = 6667
NICK = 'dubbsbot'
PASS = 'oauth:nywwhny3tnm4z0yqiy51n0gb38jyac'
TWITCH = 'https://api.twitch.tv/kraken'
HOME = 'mrdubbs'
CLIENT_ID = '?client_id=bs6lblxhqd8k6qiniysylxewehd3oi'

class PointsBot(threading.Thread):
    def __init__(self, channelName, mySocket = None):
        threading.Thread.__init__(self)
        self.channelName = channelName
        self.mySocket = joinChannel(channelName)

    def run(self):
        self.getChatters(self.channelName)
        modChatThread = threading.Thread(target = self.readChat, args = [self.mySocket, self.channelName])
        getChattersThread = threading.Timer(300, self.getChatters, [self.channelName])
        addPointsThread = threading.Thread(target = self.addPoints, args = [self.channelName])
        modChatThread.start()
        getChattersThread.start()
        addPointsThread.start()

    def getChatters(self, channelName): # API refreshes every 5 miuntes, so should be enough to check status of all viewers per cycle
        try:
            query = urllib2.urlopen('https://tmi.twitch.tv/group/user/'+ channelName + '/chatters')
        except (urllib2.HTTPError):
            return
        data = json.load(query)
        chatters = [elem for sublist in data['chatters'].values() for elem in sublist]
        starttime = '1'
        print 'Loading chatters...'
        with open(channelName+'.txt', 'a+') as f:
            data = f.read()
            newusers = [user for user in chatters if user not in data]
            print '%d new users to add' % len(newusers)
            data = data.splitlines()
            starttime = time()
            for i, userdata in enumerate(data):
                userdata = userdata.split()
                userdata[1] = '1' if userdata[0] in chatters else '0'
                data[i] = '\t'.join(userdata)
            f.seek(0)
            f.write('\n'.join(data))
            f.write('\n') if data else ''
            f.truncate()
            for user in newusers:
                f.write(user + '\t1\t' + str(1 if self.isFollowing(user, channelName) else 0) + '\t0\t0\n')
        print 'Complete. Took %s seconds' % (time() - starttime)

    def isFollowing(self, user, target): # approx. 6 requests per second == not too fast
        try:
            query = urllib2.urlopen(TWITCH + '/users/' + user + '/follows/channels/' + target + CLIENT_ID)
            return True
        except (urllib2.HTTPError):
            return False

    def addPoints(self, channelName): # add points every minute
        while True:
            with open(channelName+'.txt', 'r+') as f:
                data = f.read().splitlines()
                for i, userdata in enumerate(data):
                    userdata = userdata.split()
                    multiplier = 1
                    multiplier *= 0 if not int(userdata[1]) else 1
                    multiplier *= 2 if int(userdata[2]) else 1
                    multiplier *= 5 if int(userdata[3]) else 1
                    newtotal = str(int(userdata[4]) + PPM*multiplier)
                    userdata[4] = newtotal
                    data[i] = '\t'.join(userdata)
                f.seek(0)
                f.write('\n'.join(data))
                f.write('\n') if data else ''
                f.truncate()
            print channelName + ': Points added'
            sleep(60)

    def readChat(self, s, channelName):
        sublist = set()
        count = 0
        msgreg = re.compile('#'+channelName+' :(.*)')
        while True:
            response = s.recv(1024).decode('utf-8')
            if response == 'PING :tmi.twitch.tv\r\n':
                s.send('PONG :tmi.twitch.tv\r\n'.encode('utf-8'))
            else:
                subbed = 'subscriber=1' in response
                user = re.search('\w+!\w+@(.+?)\.tmi\.twitch\.tv', response)
                user = user.group(1) if user else ''
                if subbed:
                    sublist.add(user)
                try:
                    message = re.search(msgreg, response).group(1)
                    print channelName + ' | ' + user + ': ' + message
                    if message.split()[0][0] == '!':
                        self.botChatResponse(user, channelName, message, s)
                except:
                    pass
            if len(sublist) > 3:
                self.updateSubs(channelName, sublist)
                sublist = set()
            sleep(0.1)

    def botChatResponse(self, user, channelName, command, s):
        cmdlist = command.split()
        if cmdlist[0] == '!join' and channelName == HOME:
            with open('botjoins.txt', 'a+') as f:
                if user not in f.read():
                    f.write(user + '\n')
            print 'Joining '+user+'\'s channel'
        if cmdlist[0] == '!gamble' and channelName == HOME:
            with open(channelName+'.txt', 'r+') as f:
                current = getPoints(user, channelName)
                amount = int(cmdlist[1])
                if amount > current:
                    sendMessage(s, channelName, '@{}, you only have {} points'.format(user, current))
                    return
                current -= amount
                roll = random.randint(1, 100)
                if roll > 90:
                    amount *= 3
                elif roll > 60:
                    amount *= 2
                else:
                    amount *= 0
                current += amount
                sendMessage(s, channelName, '@{} rolled a {}. You now have {} points'.format(user, roll, current))
                data = re.sub(pointpattern, '\g<1>'+str(current)+'\g<3>', f.read())
                f.seek(0)
                f.write(data)
                f.truncate()
        if cmdlist[0] == '!points' and channelName == HOME:
            current = getPoints(user, channelName)
            sendMessage(s, channelName, '@{}, you have {} points'.format(user, current))

    def updateSubs(self, channelName, sublist):
        with open(channelName+'.txt', 'r+') as f:
            data = f.read()
            f.seek(0)
            for sub in sublist:
                if sub in data:
                    pattern = re.compile('(' + sub + '\t\d\t\d\t)(\d)(.*)')
                    data = re.sub(pattern, r'\g<1>1\g<3>', data)
            f.write(data)
            f.truncate()
        print channelName + ': Subs updated'

def sendMessage(s, channelName, message):
    s.send('PRIVMSG #{} :{}\r\n'.format(channelName, message).encode('utf-8'))

def getPoints(user, channelName):
    with open(channelName+'.txt', 'r+') as f:
        data = f.read()
        pointpattern = re.compile('('+user+'\t\d\t\d\t\d\t)(\d+)(.*)')
        current = re.search(pointpattern, data)
        return int(current.group(2)) if current else 0

def joinChannel(channelName):
    s = socket.socket()
    s.connect((HOST, PORT))
    s.send('CAP REQ :twitch.tv/tags\r\n')
    s.send('PASS {}\r\n'.format(PASS).encode('utf-8'))
    s.send('NICK {}\r\n'.format(NICK).encode('utf-8'))
    s.send('JOIN #{}\r\n'.format(channelName).encode('utf-8'))
    return s


