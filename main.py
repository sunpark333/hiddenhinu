import logging
import asyncio
import os
import sys
from aiohttp import web
from config import TELEGRAM_BOT_TOKEN, API_ID, API_HASH, TELEGRAM_SESSION_STRING, TWITTER_VID_BOT, YOUR_CHANNEL_ID, TIMEZONE, PERPLEXITY_API_KEY
from task import TwitterBot

# Koyeb के लिए logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logger.info("Starting Twitter Bot with AI Enhancement on Koyeb...")
    
    # Check if AI features are available
    if PERPLEXITY_API_KEY:
        logger.info("🤖 AI Caption Enhancement: ENABLED")
    else:
        logger.warning("🤖 AI Caption Enhancement: DISABLED (No API key)")
        
    bot = TwitterBot()
    bot.run()
