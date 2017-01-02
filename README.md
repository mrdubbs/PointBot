# PointBot
Loyalty Tracking Bot for Twitch by MrDubbs

1. Awards points based on active viewing, following status, and subscriber status
2. Does not need authorization from host channel as it learns subscriber data from IRC chat tags
3. Pulls follower and viewer data from Twitch API
4. Multithreading allows for bot to be in multiple channels at once
5. User can request bot to join their channel by typing '!join' on my channel
6. Gamble points with !gamble <amount> command

TODO:

1. Join all requesting channels upon startup (store channels on file) (ADDED)
2. Monitor online/offline status of serviced channels (ADDED)
3. Add SQL functionality instead of reading from file (ADDED)
4. Host bot on server so that always active
5. Add moderator functionality (bans, timeouts, custom commands) (CUSTOM COMMANDS ADDED)
6. Limit command usage to prevent spam (ADDED)
7. Add additional cool features
