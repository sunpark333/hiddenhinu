"""
Twitter Video Bot - Main Entry Point (Updated with Quiz)
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
from quiz import QuizGenerator


def main():
    """Main entry point"""
    logger.info("Starting Twitter Bot with Quiz Generator on Koyeb...")
    
    try:
        bot = TwitterBot()
        
        # Initialize quiz generator
        quiz_generator = QuizGenerator(bot, bot.ai_enhancer)
        bot.quiz_generator = quiz_generator
        
        # Add quiz handlers to handlers module
        bot.handlers.quiz_generator = quiz_generator
        
        logger.info("Quiz Generator initialized successfully")
        
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
