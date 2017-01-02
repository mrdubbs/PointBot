import json
import urllib as urllib2
import threading
import socket
import re
from cfg import *
from math import ceil
from time import sleep, time


class PointsBot(threading.Thread):
    def __init__(self, channelName):
        threading.Thread.__init__(self)
        self.channelName = channelName
        self.mySocket = joinChannel(channelName)
        self.usedGambles = dict()
        self.cursor = CONN.cursor(dictionary=True)

    def run(self):
        while not self.isOnline():
            sleep(60)
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
        except urllib2.error.HTTPError:
            return
        data = json.load(query)
        print(self.channelName + '| Loading chatters...')
        try:
            chatters = [elem.encode('utf-8') for sublist in data['chatters'].values() for elem in sublist]
        except TypeError: # bug when retrieving data from API makes dictionary unable to be read
            chatters = []
        if not executeSQL(self.cursor, 'show tables like "{}"'.format(self.channelName)):
            executeSQL(self.cursor, 'create table {}('
                                    'id varchar(255) not null primary key,'
                                    'isActive bool default True,'
                                    'isFollowing bool default false,'
                                    'isSubbed bool default false,'
                                    'points int default 0);'.format(self.channelName))
        if not executeSQL(self.cursor, 'show tables like "{}cmd"'.format(self.channelName)):
            executeSQL(self.cursor, 'create table {}cmd('
                                    'cmd varchar(255) primary key,'
                                    'message varchar(255));'.format(self.channelName))
        saved = executeSQL(self.cursor, 'select id from {}'.format(self.channelName))
        saved = [d['id'] for d in saved]
        newusers = [user for user in chatters if user not in saved]
        if chatters:
            executeSQL(self.cursor, 'update {} set isActive = id in ({})'.format(self.channelName, str(chatters).strip('[]')))
        print('{} new users to add'.format(len(newusers)))
        starttime = time()
        followlist = list()
        if newusers:
            # multithreading gives 25x speedup for running isFollowing queries
            def threadFollowHelper(followlist, newusers):
                threadlock1.acquire()
                if not newusers:
                    return
                user = newusers.pop()
                threadlock1.release()
                followlist.append([user, self.isFollowing(user)])
            threadlock1 = threading.Lock()
            threadList = list()
            while newusers:
                newthread = threading.Thread(target = threadFollowHelper, args = [followlist, newusers])
                newthread.start()
                threadList.append(newthread)
            for thread in threadList:
                thread.join()
            # executemany gives 5x speedup over multiple execute statements
            self.cursor.executemany('insert into ' + self.channelName + ' (id, isFollowing) values(%s, %s)', followlist)
        print(self.channelName + ': Complete. Took %s seconds' % (time() - starttime))

    def addPoints(self): # add points every minute
        while True:
            executeSQL(self.cursor, 'update {} set points = points + {}*'
                                       'if(isActive, 1, 0)*'
                                       'if(isFollowing, 2, 1)*'
                                       'if(isSubbed, 5, 1)'.format(self.channelName, PPM))
            print(self.channelName + ': Points added')
            sleep(60)

    def readChat(self):
        sublist = set()
        msgreg = re.compile('#'+self.channelName+' :(.*)')
        while True:
            try:
                response = self.mySocket.recv(1024).decode('utf-8')
            except UnicodeDecodeError:
                continue
            if response == 'PING :tmi.twitch.tv\r\n':
                self.mySocket.send('PONG :tmi.twitch.tv\r\n'.encode('utf-8'))
            else:
                subbed = 'subscriber=1' in response
                user = re.search('\w+!\w+@(.+?)\.tmi\.twitch\.tv', response)
                user = user.group(1).encode('utf-8') if user else ''
                if subbed:
                    sublist.add(user)
                try:
                    message = re.search(msgreg, response).group(1).encode('utf-8')
                    print(self.channelName + '| ' + user + ': ' + message)
                    if message.split()[0][0] == '!':
                        self.botChatResponse(user, message)
                except:
                    pass
            if len(sublist) > 3:
                self.updateSubs(list(sublist))
                sublist = set()
            sleep(0.1)

    def botChatResponse(self, user, command):
        cmdlist = command.split()
        if cmdlist[0] == '!join' and self.channelName == HOME: # HOME conditional so that I can test in my channel only
            if executeSQL(self.cursor, 'show tables like "{}"'.format(self.channelName)):
                self.sendMessage('I appreciate another invite, but I\'m already in your channel, ' + user)
                return
            newBot = PointsBot(user)
            newBot.start()
            self.sendMessage('Thanks for the invite, ' + user + '! Heading over to your channel right now')
        elif cmdlist[0] == '!gamble' and self.channelName == HOME:
            waittime = ceil((time() - self.usedGambles[user])/60) if user in self.usedGambles.keys() else GAMBLECOOLDOWN
            if waittime < GAMBLECOOLDOWN:
                self.sendMessage('Please wait {} more minutes to gamble again'.format(int(GAMBLECOOLDOWN - waittime)))
                return
            if executeSQL(self.cursor, 'show tables like "{}"'.format(self.channelName)):
                amount = int(cmdlist[1])
                if amount < self.getPoints(user, self.channelName):
                    executeSQL(self.cursor, 'set @rnum = floor(1 + rand()*100);')
                    executeSQL(self.cursor, 'update {} set points = points + {}*'
                                               '(case when @rnum > 90 then 2 '
                                               'when @rnum > 60 then 1 '
                                               'else -1 end) '
                                               'where id = "{}"'.format(self.channelName, amount, user))
                    vals = executeSQL(self.cursor, 'select @rnum, points from {} where id = "{}"'.format(self.channelName, user))
                    rnum = int(vals[0]['@rnum'])
                    points = int(vals[0]['points'])
                    self.usedGambles[user] = time()
                    self.sendMessage('{} rolled a {} and now has {} points'.format(user, rnum, points))
        elif cmdlist[0] == '!points' and self.channelName == HOME:
            current = self.getPoints(user, self.channelName)
            self.sendMessage('{}, you have {} points'.format(user, current))
        elif cmdlist[0] == '!addcom' and self.channelName == HOME:
            if len(cmdlist) < 3 or cmdlist[1][0] != '!':
                self.sendMessage('{}, the format for adding commands is !addcom !<commandname> <message>'.format(user))
                return
            if executeSQL(self.cursor, 'show tables like "{}"'.format(self.channelName)):
                newcom = cmdlist[1]
                message = str(' '.join(cmdlist[2:])).strip('[]')
                executeSQL(self.cursor, 'insert into {} values("{}", "{}")'.format(self.channelName + 'cmd', newcom, message))
                self.sendMessage('{}, {} was succesfully added!'.format(user, newcom))
        elif cmdlist[0] == '!delcom' and self.channelName == HOME:
            if len(cmdlist) < 2 or cmdlist[1][0] != '!':
                self.sendMessage('{}, the format for deleting commands is !delcom !<commandname>'.format(user))
                return
            if executeSQL(self.cursor, 'show tables like "{}"'.format(self.channelName)):
                delcom = cmdlist[1]
                executeSQL(self.cursor, 'delete from {} where cmd = "{}"'.format(self.channelName + 'cmd', delcom))
                self.sendMessage('{} was successfully removed'.format(delcom))
        elif cmdlist[0] == '!editcom' and self.channelName == HOME:
            if len(cmdlist) < 3 or cmdlist[1][0] != '!':
                self.sendMessage('{}, the format for editing commands is !editcom !<commandname> <newmessage>'.format(user))
                return
            if executeSQL(self.cursor, 'show tables like "{}"'.format(self.channelName)):
                newcom = cmdlist[1]
                message = str(' '.join(cmdlist[2:])).strip('[]')
                executeSQL(self.cursor, 'update {} set message = "{}" where cmd = "{}"'.format(self.channelName + 'cmd', message, newcom))
                self.sendMessage('{}, {} was succesfully edited!'.format(user, newcom))
        elif cmdlist[0] == '!commands' and self.channelName == HOME:
            if executeSQL(self.cursor, 'show tables like "{}"'.format(self.channelName)):
                allcommands = executeSQL(self.cursor, 'select cmd from {}cmd'.format(self.channelName))
                allcommands = [cmd['cmd'].encode('utf-8') for cmd in allcommands]
                self.sendMessage('Commands for {}: '.format(self.channelName) + str(allcommands).strip('[]'))
        else:
            if executeSQL(self.cursor, 'show tables like "{}"'.format(self.channelName)):
                cmd = cmdlist[0]
                message = executeSQL(self.cursor, 'select message from {} where cmd = "{}"'.format(self.channelName + 'cmd', cmd))
                self.sendMessage(message[0]['message'])

    def updateSubs(self, sublist):
        try:
            executeSQL(self.cursor, 'update {} set isSubbed = True where id in ({});'.format(self.channelName, str(sublist).strip('[]')))
        finally:
            print(self.channelName + ': Subs updated')

    def isOnline(self):
        try:
            query = urllib2.urlopen(TWITCH + '/streams/'+ self.channelName + CLIENT_ID)
        except:
            return False
        data = json.load(query)
        if data['stream']:
            return True
        return False

    def getPoints(self, user):
        points = executeSQL(self.cursor, 'select points from {} where id = "{}"'.format(self.channelName, user))
        return points[0]['points']

    def sendMessage(self, message):
        self.mySocket.send('PRIVMSG #{} :{}\r\n'.format(self.channelName, message).encode('utf-8'))

    def isFollowing(self, user): # approx. 6 requests per second == not too fast => multithreaded requests
        try:
            query = urllib2.urlopen(TWITCH + '/users/' + user + '/follows/channels/' + self.channelName + CLIENT_ID)
            data = json.load(query)
        except urllib2.error.HTTPError, ValueError:
            return False
        return 'error' not in data.keys()

threadlock2 = threading.Lock()
def executeSQL(cursor, command):
    threadlock2.acquire()
    try:
        cursor.execute(command)
    except IndexError:  # a bug in the execute command sometimes causes this error to occur
        pass
    data = cursor.fetchall() if cursor.description else CONN.commit()
    threadlock2.release()
    return data

def joinChannel(channelName):
    s = socket.socket()
    s.connect((HOST, PORT))
    s.send('CAP REQ :twitch.tv/tags\r\n')
    s.send('PASS {}\r\n'.format(PASS).encode('utf-8'))
    s.send('NICK {}\r\n'.format(NICK).encode('utf-8'))
    s.send('JOIN #{}\r\n'.format(channelName).encode('utf-8'))
    return s


