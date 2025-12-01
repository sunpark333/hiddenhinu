import logging
import asyncio
import os
import sys

# Import configuration
# Note: You might need to update config.py to include new variables
from config import (
    TELEGRAM_BOT_TOKEN, API_ID, API_HASH, 
    TELEGRAM_SESSION_STRING, TWITTER_VID_BOT, 
    YOUR_CHANNEL_ID, YOUR_SECOND_CHANNEL_ID, TIMEZONE
)

# Import the main bot class
from twitter_client import TwitterBot

# Koyeb के लिए logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

async def shutdown_signal_handler(bot):
    """Signal handler for graceful shutdown"""
    logger.info("Shutdown signal received...")
    await bot.shutdown()

if __name__ == '__main__':
    logger.info("Starting Twitter Bot on Koyeb...")
    
    # Create and run the bot
    bot = TwitterBot()
    
    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)
