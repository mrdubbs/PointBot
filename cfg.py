import mysql.connector as sql

# macros used in pointbot/botmain
HOST = 'irc.chat.twitch.tv'
PORT = 6667
NICK = 'dubbsbot'
PASS = '***'
TWITCH = 'https://api.twitch.tv/kraken'
HOME = 'mrdubbs'
CLIENT_ID = '***'
IO = 'iofiles/'
CONN = sql.connect(host='localhost', database = 'sys', user='root', password='***')
CURSOR = CONN.cursor(dictionary=True)
