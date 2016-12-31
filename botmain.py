import threading
from time import *
from pointbot import *

def main():
    with open(IO + 'botjoins.txt', 'r') as f:
        channels = f.read().split()
        for channel in channels:
            bot = PointsBot(channel)
            bot.start()
    while True:
        pass

if __name__ == '__main__':
    main()
