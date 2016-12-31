import MySQLdb
import json
import urllib2
import threading
from cfg import *
import socket
import re
import random
import os.path
from time import *

HOST = 'irc.chat.twitch.tv'
PORT = 6667
NICK = 'dubbsbot'
PASS = '***'
TWITCH = 'https://api.twitch.tv/kraken'
HOME = 'mrdubbs'
CLIENT_ID = '***'
IO = 'iofiles/'

class PointsBot(threading.Thread):
    def __init__(self, channelName, mySocket = None):
        threading.Thread.__init__(self)
        self.channelName = channelName
        self.mySocket = joinChannel(channelName)

    def run(self):
        #while not self.isOnline():
          #  sleep(60)
        self.getChatters()
        modChatThread = threading.Thread(target = self.readChat)
        getChattersThread = threading.Timer(300, self.getChatters)
        addPointsThread = threading.Thread(target = self.addPoints)
        modChatThread.start()
        getChattersThread.start()
        addPointsThread.start()

    def getChatters(self): # API refreshes every 5 miuntes, so should be enough to check status of all viewers per cycle
        try:
            query = urllib2.urlopen('https://tmi.twitch.tv/group/user/'+ self.channelName + '/chatters')
        except (urllib2.HTTPError):
            return
        data = json.load(query)
        chatters = [elem for sublist in data['chatters'].values() for elem in sublist]
        starttime = '1'
        print self.channelName + '| Loading chatters...'
        with open(IO + self.channelName + '.txt', 'a+') as f:
            data = f.read()
            newusers = [user for user in chatters if user not in data]
            print '{} new users to add'.format(len(newusers))
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
                f.write(user + '\t1\t' + str('1' if self.isFollowing(user) else '0') + '\t0\t0\n')
        print self.channelName + ': Complete. Took %s seconds' % (time() - starttime)

    def isFollowing(self, user): # approx. 6 requests per second == not too fast
        try:
            query = urllib2.urlopen(TWITCH + '/users/' + user + '/follows/channels/' + self.channelName + CLIENT_ID)
            return True
        except (urllib2.HTTPError):
            return False

    def addPoints(self): # add points every minute
        while True:
            with open(IO + self.channelName+'.txt', 'a+') as f:
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
                print f.read()
            print self.channelName + ': Points added'
            sleep(60)

    def readChat(self):
        sublist = set()
        count = 0
        msgreg = re.compile('#'+self.channelName+' :(.*)')
        while True:
            response = self.mySocket.recv(1024).decode('utf-8')
            if response == 'PING :tmi.twitch.tv\r\n':
                self.mySocket.send('PONG :tmi.twitch.tv\r\n'.encode('utf-8'))
            else:
                subbed = 'subscriber=1' in response
                user = re.search('\w+!\w+@(.+?)\.tmi\.twitch\.tv', response)
                user = user.group(1) if user else ''
                if subbed:
                    sublist.add(user)
                try:
                    message = re.search(msgreg, response).group(1)
                    print user + ': ' + message
                    if message.split()[0][0] == '!':
                        self.botChatResponse(user, message)
                except:
                    pass
            if len(sublist) > 3:
                self.updateSubs(sublist)
                sublist = set()
            sleep(0.1)

    def botChatResponse(self, user, command):
        cmdlist = command.split()
        if cmdlist[0] == '!join' and self.channelName == HOME:
            with open(IO + 'botjoins.txt', 'a+') as f:
                if user not in f.read():
                    f.write(user + '\n')
                    newBot = PointsBot(user)
                    newBot.start()
                    self.sendMessage('Thanks for the invite, @'+user+'! Heading over to your channel right now')
                else:
                    self.sendMessage('I appreciate another invite, but I\'m already in your channel, @'+user)
        if cmdlist[0] == '!gamble' and channelName == HOME:
            with open(IO + channelName+'.txt', 'r+') as f:
                current = getPoints(user, self.channelName)
                amount = int(cmdlist[1])
                data = f.read()
                if amount > current:
                    self.sendMessage('@{}, you only have {} points'.format(user, current))
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
                pointpattern = re.compile('('+user+'\t\d\t\d\t\d\t)(\d+)(.*)')
                self.sendMessage('@{} rolled a {}. You now have {} points'.format(user, roll, current))
                data = re.sub(pointpattern, '\g<1>'+str(current)+'\g<3>', data)
                f.seek(0)
                f.write(data)
                f.truncate()
        if cmdlist[0] == '!points' and self.channelName == HOME:
            current = getPoints(user, self.channelName)
            self.sendMessage('@{}, you have {} points'.format(user, current))
        if cmdlist[0] == '!addcom' and self.channelName == HOME:
            if len(cmdlist) < 3 or cmdlist[1][0] != '!':
                self.sendMessage('@{}, the format for adding commands is !addcom !<commandname> <message>'.format(user))
                return
            newcom = cmdlist[1]
            message = cmdlist[2:]
            with open(IO + self.channelName + 'cmd.txt', 'a+') as f:
                if newcom in f.read():
                    return
                f.write(newcom + '\t' + ' '.join(message) + '\n')
            self.sendMessage('@{}, {} was succesfully added!'.format(user, newcom))
        if cmdlist[0] == '!delcom' and channelName == HOME:
            if len(cmdlist) < 2 or cmdlist[1][0] != '!':
                self.sendMessage('@{}, the format for deleting commands is !delcom !<commandname>'.format(user))
                return
            delcom = cmdlist[1]
            with open(IO + self.channelName + 'cmd.txt', 'a+') as f:
                data = f.read()
                if delcom not in data:
                    self.sendMessage('@{}, {} was not found'.format(user, delcom))
                    return
                data = data.splitlines()
                f.seek(0)
                for cmd in data:
                    if delcom not in cmd:
                        f.write(cmd + '\n')
                f.truncate()
            self.sendMessage('{} was successfully removed'.format(delcom))

        else:
            with open(IO + self.channelName + 'cmd.txt', 'a+') as f:
                com = cmdlist[0]
                cmdsearch = re.compile(com + '\t(.*)')
                cmdmatch = re.search(cmdsearch, f.read())
                if cmdmatch:
                    self.sendMessage(cmdmatch.group(1))

    def updateSubs(self, sublist):
        with open(IO + self.channelName+'.txt', 'r+') as f:
            data = f.read()
            f.seek(0)
            for sub in sublist:
                if sub in data:
                    pattern = re.compile('(' + sub + '\t\d\t\d\t)(\d)(.*)')
                    data = re.sub(pattern, r'\g<1>1\g<3>', data)
            f.write(data)
            f.truncate()
        print self.channelName + ': Subs updated'

    def isOnline(self):
        try:
            query = urllib2.urlopen(TWITCH + '/streams/'+ self.channelName + CLIENT_ID)
        except (urllib2.HTTPError):
            return False
        data = json.load(query)
        if data['stream']:
            return True
        return False

    def sendMessage(self, message):
        self.mySocket.send('PRIVMSG #{} :{}\r\n'.format(self.channelName, message).encode('utf-8'))

def getPoints(user, channelName):
    with open(IO + channelName+'.txt', 'r') as f:
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


