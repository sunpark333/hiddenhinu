import logging
import asyncio
import os
import sys
from config import TELEGRAM_BOT_TOKEN, API_ID, API_HASH, TELEGRAM_SESSION_STRING, TWITTER_VID_BOT, YOUR_CHANNEL_ID, YOUR_SECOND_CHANNEL_ID, TIMEZONE, ADMIN_IDS, TWITTER_BEARER_TOKEN, TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
from telegram_handler import TelegramHandler
from userbot_manager import UserBotManager
from twitter_poster import TwitterPoster
from scheduler import Scheduler

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
        self.logger = logger
        self.scheduler = Scheduler()
        self.twitter_poster = TwitterPoster()
        self.userbot_manager = UserBotManager(self)
        self.telegram_handler = TelegramHandler(self)
        self._shutdown_flag = False

    async def initialize_services(self):
        """Initialize all services"""
        try:
            self.logger.info("Initializing Twitter Poster...")
            await self.twitter_poster.initialize()
            
            self.logger.info("Initializing UserBot...")
            await self.userbot_manager.initialize()
            
            self.logger.info("Initializing Telegram Bot...")
            await self.telegram_handler.initialize()
            
            self.logger.info("All services initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize services: {str(e)}")
            return False

    async def run_async(self):
        """Async main function"""
        try:
            self.logger.info("Starting bot services...")
            success = await self.initialize_services()
            
            if not success:
                raise Exception("Failed to initialize services")
            
            self.logger.info("✅ Bot started successfully!")
            self.logger.info("🤖 Waiting for commands...")
            
            # Keep running until shutdown
            while not self._shutdown_flag:
                await asyncio.sleep(1)
                
        except Exception as e:
            self.logger.error(f"Error in run_async: {e}")
            raise

    async def shutdown(self):
        """Shutdown all services properly"""
        self.logger.info("Shutting down services...")
        self._shutdown_flag = True
        
        try:
            await self.telegram_handler.shutdown()
            await self.userbot_manager.shutdown()
            await self.twitter_poster.shutdown()
                
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
        
        self.logger.info("All services safely shut down")

    def run(self):
        """Main function to run the bot"""
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries and not self._shutdown_flag:
            try:
                # Create new event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                self.logger.info(f"Starting bot... (Attempt {retry_count + 1})")
                loop.run_until_complete(self.run_async())
                
            except KeyboardInterrupt:
                self.logger.info("Received keyboard interrupt, shutting down...")
                break
                
            except Exception as e:
                retry_count += 1
                self.logger.error(f"Critical error (attempt {retry_count}/{max_retries}): {str(e)}")
                
                if retry_count < max_retries:
                    self.logger.info(f"Retrying in 10 seconds...")
                    try:
                        loop.run_until_complete(self.shutdown())
                    except Exception as shutdown_error:
                        self.logger.error(f"Error during shutdown: {shutdown_error}")
                    
                    import time
                    time.sleep(10)
                else:
                    self.logger.error("Maximum retries reached. Exiting...")
                    break
            finally:
                if loop and not loop.is_closed():
                    try:
                        loop.run_until_complete(self.shutdown())
                    except Exception as e:
                        self.logger.error(f"Error in final shutdown: {e}")
                    loop.close()

if __name__ == "__main__":
    bot = TwitterBot()
    bot.run()
