import threading
from time import *
from pointbot import *

def main():
    bot1 = PointsBot(CHANNEL)
    bot2 = PointsBot('mrdubbs')
    bot1.start()
    bot2.start()
    while True:
        pass

if __name__ == '__main__':
    main()
