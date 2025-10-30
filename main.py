import logging
import asyncio
import os
import sys
from aiohttp import web
from task import TwitterBot
from channel_to_twitter import start_channel_to_twitter

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

async def run_all_bots():
    """Run both bots concurrently"""
    try:
        # Start main Twitter bot
        main_bot = TwitterBot()
        
        # Run both bots concurrently
        await asyncio.gather(
            main_bot.run_async(),
            start_channel_to_twitter()
        )
        
    except Exception as e:
        logger.error(f"Error running bots: {e}")

if __name__ == '__main__':
    logger.info("Starting both Twitter Bot and Channel-to-Twitter Bot...")
    
    # Run both bots
    asyncio.run(run_all_bots())
