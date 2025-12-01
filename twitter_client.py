import logging
import asyncio
import sys
from ai_caption_enhancer import AICaptionEnhancer
from twitter_poster import TwitterPoster
from telegram_handlers import TelegramHandlers
from scheduler import Scheduler
from video_processor import VideoProcessor
from utils import BotUtils
from config import (
    TELEGRAM_BOT_TOKEN, API_ID, API_HASH, 
    TELEGRAM_SESSION_STRING, TWITTER_VID_BOT, 
    YOUR_CHANNEL_ID, YOUR_SECOND_CHANNEL_ID, TIMEZONE
)

logger = logging.getLogger(__name__)

class TwitterBot:
    """मुख्य Twitter Bot क्लास"""
    
    def __init__(self):
        self.userbot = None
        self.bot_app = None
        self._shutdown_flag = False
        self._polling_started = False
        
        # Initialize components
        self.config = self._get_config()
        self.twitter_poster = TwitterPoster()
        self.scheduler = Scheduler(self)
        self.video_processor = VideoProcessor(self)
        self.utils = BotUtils(self)
        self.ai_enhancer = AICaptionEnhancer()
        self.telegram_handlers = None
    
    def _get_config(self):
        """Get configuration"""
        class Config:
            TWITTER_VID_BOT = TWITTER_VID_BOT
        return Config()
    
    async def run_async(self):
        """Async main function"""
        try:
            logger.info("Starting bot components...")
            
            # Start HTTP server
            await self.utils.start_http_server()
            
            # Initialize UserBot
            await self.utils.initialize_userbot()
            
            # Initialize Twitter client
            if not self.twitter_poster.initialize_twitter_client():
                logger.warning("Twitter client initialization failed, continuing without Twitter posting")
            
            # Start polling
            await self.utils.start_polling()
            
        except Exception as e:
            logger.error(f"Error in run_async: {e}")
            raise
    
    async def shutdown(self):
        """Shutdown all services"""
        logger.info("Shutting down services...")
        self._shutdown_flag = True
        
        try:
            if self.bot_app and hasattr(self.bot_app, 'running') and self.bot_app.running:
                logger.info("Stopping bot application...")
                await self.bot_app.updater.stop()
                await self.bot_app.stop()
                await self.bot_app.shutdown()
                
            if self.userbot and self.userbot.is_connected():
                logger.info("Disconnecting userbot...")
                await self.userbot.disconnect()
                
            if self.utils.runner:
                logger.info("Stopping HTTP server...")
                await self.utils.runner.cleanup()
                
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        
        logger.info("All services safely shut down")
    
    def run(self):
        """Main function to run the bot"""
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries and not self._shutdown_flag:
            try:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                
                logger.info(f"Starting bot... (Attempt {retry_count + 1})")
                self.loop.run_until_complete(self.run_async())
                
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, shutting down...")
                break
                
            except Exception as e:
                retry_count += 1
                logger.error(f"Critical error (attempt {retry_count}/{max_retries}): {str(e)}")
                
                if retry_count < max_retries:
                    logger.info(f"Retrying in 10 seconds...")
                    try:
                        if self.loop and not self.loop.is_closed():
                            self.loop.run_until_complete(self.shutdown())
                    except Exception as shutdown_error:
                        logger.error(f"Error during shutdown: {shutdown_error}")
                    import time
                    time.sleep(10)
                else:
                    logger.error("Maximum retries reached. Exiting...")
                    break
            finally:
                if self.loop and not self.loop.is_closed():
                    try:
                        self.loop.run_until_complete(self.shutdown())
                    except Exception as e:
                        logger.error(f"Error in final shutdown: {e}")
                    self.loop.close()

# Import the old task.py functions for compatibility
from video_processor import VideoProcessor as OldVideoProcessor
from scheduler import Scheduler as OldScheduler
from twitter_poster import TwitterPoster as OldTwitterPoster

# Create aliases for backward compatibility
TwitterBot.VideoProcessor = VideoProcessor
TwitterBot.Scheduler = Scheduler
TwitterBot.TwitterPoster = TwitterPoster

if __name__ == "__main__":
    bot = TwitterBot()
    bot.run()
