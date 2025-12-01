import logging
import asyncio
import os
import sys
from config import TELEGRAM_BOT_TOKEN, API_ID, API_HASH, TELEGRAM_SESSION_STRING, TWITTER_VID_BOT, YOUR_CHANNEL_ID, YOUR_SECOND_CHANNEL_ID, TIMEZONE, ADMIN_IDS, TWITTER_BEARER_TOKEN, TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
from bot_core import TwitterBotCore
from handlers import BotHandlers
from twitter_poster import TwitterPoster

# Koyeb के लिए logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class TwitterBot:
    def __init__(self):
        self.core = TwitterBotCore()
        self.handlers = BotHandlers(self.core)
        self.twitter_poster = TwitterPoster(self.core)
        
    def run(self):
        logger.info("Starting Twitter Bot on Koyeb...")
        self.core.run()

if __name__ == '__main__':
    bot = TwitterBot()
    bot.run()
