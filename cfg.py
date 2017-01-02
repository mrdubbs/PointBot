import mysql.connector as sql

# globals used in bot main program

HOST = 'irc.chat.twitch.tv'
PORT = 6667
NICK = 'dubbsbot'
PASS = '***'
TWITCH = 'https://api.twitch.tv/kraken'
HOME = 'mrdubbs'
CLIENT_ID = '***'
IO = 'iofiles/'
GAMBLECOOLDOWN = 10 # in minutes
PPM = 1 # points per minute
CONN = sql.connect(host='localhost', database = 'sys', user='root', password='pass')



