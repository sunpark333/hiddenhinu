"""
Twitter Video Bot - Main Entry Point
Entry point for starting the bot
"""

import logging
import asyncio
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Import config and bot
from config import TELEGRAM_BOT_TOKEN, API_ID, API_HASH, TELEGRAM_SESSION_STRING, TWITTER_VID_BOT, YOUR_CHANNEL_ID, YOUR_SECOND_CHANNEL_ID, TIMEZONE
from twitter_bot.core import TwitterBot

def main():
    """Main entry point"""
    logger.info("Starting Twitter Bot on Koyeb...")
    
    try:
        bot = TwitterBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
