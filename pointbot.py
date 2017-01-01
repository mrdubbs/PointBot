import mysql.connector as sql
import json
import urllib as urllib2 # for compatibility reasons when moving between IDEs. Can just import urllib2.
import threading
import socket
import re
from cfg import *
from time import sleep

class PointsBot(threading.Thread):
    def __init__(self, channelName, mySocket = None):
        threading.Thread.__init__(self)
        self.channelName = channelName
        self.mySocket = joinChannel(channelName)

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
        chatters = [elem.encode('utf-8') for sublist in data['chatters'].values() for elem in sublist]
        if not executeSQL('show tables like "{}"'.format(self.channelName)):
            executeSQL('create table {}('
                        'id varchar(255) not null primary key,'
                        'isActive bool default True,'
                        'isFollowing bool default false,'
                        'isSubbed bool default false,'
                        'points int default 0);'.format(self.channelName))
            executeSQL('create table {}('
                        'cmd varchar(255) primary key,'
                        'message varchar(255));'.format(self.channelName + 'cmd'))
        saved = executeSQL('select id from {}'.format(self.channelName))
        saved = [d['id'] for d in saved]
        newusers = [user for user in chatters if user not in saved]
        executeSQL('update {} set isActive = id in ({})'.format(self.channelName, str(chatters).strip('[]')))
        print('{} new users to add'.format(len(newusers)))
        starttime = time()
        for user in newusers:
            values = [user, self.isFollowing(user)]
            executeSQL('insert into {} (id, isFollowing) values("{}", {})'.format(self.channelName, *values))
        print(self.channelName + ': Complete. Took %s seconds' % (time() - starttime))

    def isFollowing(self, user): # approx. 6 requests per second == not too fast
        try:
            query = urllib2.urlopen(TWITCH + '/users/' + user + '/follows/channels/' + self.channelName + CLIENT_ID)
            return True
        except urllib2.error.HTTPError:
            return False

    def addPoints(self): # add points every minute
        while True:
            executeSQL('update {} set points = points +'
                       'if(isActive, 1, 0)*'
                       'if(isFollowing, 2, 1)*'
                       'if(isSubbed, 5, 1)'.format(self.channelName))
            print(self.channelName + ': Points added')
            sleep(60)

    def readChat(self):
        sublist = set()
        msgreg = re.compile('#'+self.channelName+' :(.*)')
        while True:
            response = self.mySocket.recv(1024).decode('utf-8')
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
                    print(user + ': ' + message)
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
        if cmdlist[0] == '!join' and self.channelName == HOME:
            if executeSQL('show tables like "{}"'.format(self.channelName)):
                self.sendMessage('I appreciate another invite, but I\'m already in your channel, @' + user)
                return
            newBot = PointsBot(user)
            newBot.start()
            self.sendMessage('Thanks for the invite, @' + user + '! Heading over to your channel right now')
        elif cmdlist[0] == '!gamble' and self.channelName == HOME:
            if executeSQL('show tables like "{}"'.format(self.channelName)):
                amount = int(cmdlist[1])
                if amount < getPoints(user, self.channelName):
                    executeSQL('set @rnum = floor(1 + rand()*100);')
                    executeSQL('update {} set points = points + {}*'
                               '(case when @rnum > 90 then 2 '
                               'when @rnum > 60 then 1 '
                               'else -1 end) '
                               'where id = "{}"'.format(self.channelName, amount, user))
                    vals = executeSQL('select @rnum, points from {} where id = "{}"'.format(self.channelName, user))
                    rnum = int(vals[0]['@rnum'])
                    points = int(vals[0]['points'])
                    self.sendMessage('@{} rolled a {} and now has {} points'.format(user, rnum, points))
        elif cmdlist[0] == '!points' and self.channelName == HOME:
            current = getPoints(user, self.channelName)
            self.sendMessage('@{}, you have {} points'.format(user, current))
        elif cmdlist[0] == '!addcom' and self.channelName == HOME:
            if len(cmdlist) < 3 or cmdlist[1][0] != '!':
                self.sendMessage('@{}, the format for adding commands is !addcom !<commandname> <message>'.format(user))
                return
            if executeSQL('show tables like "{}"'.format(self.channelName)):
                newcom = cmdlist[1]
                message = str(' '.join(cmdlist[2:])).strip('[]')
                executeSQL('insert into {} values("{}", "{}")'.format(self.channelName + 'cmd', newcom, message))
                self.sendMessage('@{}, {} was succesfully added!'.format(user, newcom))
        elif cmdlist[0] == '!delcom' and self.channelName == HOME:
            if len(cmdlist) < 2 or cmdlist[1][0] != '!':
                self.sendMessage('@{}, the format for deleting commands is !delcom !<commandname>'.format(user))
                return
            if executeSQL('show tables like "{}"'.format(self.channelName)):
                delcom = cmdlist[1]
                executeSQL('delete from {} where cmd = "{}"'.format(self.channelName + 'cmd', delcom))
            self.sendMessage('{} was successfully removed'.format(delcom))
        elif cmdlist[0] == '!editcom' and self.channelName == HOME:
            if len(cmdlist) < 3 or cmdlist[1][0] != '!':
                self.sendMessage('@{}, the format for editing commands is !editcom !<commandname> <newmessage>'.format(user))
                return
            if executeSQL('show tables like "{}"'.format(self.channelName)):
                newcom = cmdlist[1]
                message = str(' '.join(cmdlist[2:])).strip('[]')
                executeSQL('update {} set message = "{}" where cmd = "{}"'.format(self.channelName + 'cmd', message, newcom))
                self.sendMessage('@{}, {} was succesfully edited!'.format(user, newcom))
        else:
            if executeSQL('show tables like "{}"'.format(self.channelName)):
                cmd = cmdlist[0]
                message = executeSQL('select message from {} where cmd = "{}"'.format(self.channelName + 'cmd', cmd))
                self.sendMessage(message[0]['message'])

    def updateSubs(self, sublist):
        executeSQL('update {} set isSubbed = True where id in ({});'.format(self.channelName, str(sublist).strip('[]')))
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

    def sendMessage(self, message):
        self.mySocket.send('PRIVMSG #{} :{}\r\n'.format(self.channelName, message).encode('utf-8'))

def executeSQL(command):
    try:
        CURSOR.execute(command)
    except sql.ProgrammingError as e:
        print 'here'
        print(e)
    if CURSOR.description:
        print CURSOR.description
        return CURSOR.fetchall()
    CONN.commit()

def getPoints(user, channelName):
    points = executeSQL('select points from {} where id = "{}"'.format(channelName, user))
    return points[0]['points']

def joinChannel(channelName):
    s = socket.socket()
    s.connect((HOST, PORT))
    s.send('CAP REQ :twitch.tv/tags\r\n')
    s.send('PASS {}\r\n'.format(PASS).encode('utf-8'))
    s.send('NICK {}\r\n'.format(NICK).encode('utf-8'))
    s.send('JOIN #{}\r\n'.format(channelName).encode('utf-8'))
    return s


