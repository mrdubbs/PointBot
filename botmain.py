from pointbot import *

def main():
    if not executeSQL('show tables like "botjoins"'):
        executeSQL('create table botjoins( channel varchar(255))')
        executeSQL('insert into botjoins values("{}")'.format(HOME))
    channellist = executeSQL('select channel from botjoins')
    channellist = [channel['channel'] for channel in channellist]
    for channel in channellist:
        bot = PointsBot(channel)
        bot.start()
    while True:
        pass

if __name__ == '__main__':
    main()
