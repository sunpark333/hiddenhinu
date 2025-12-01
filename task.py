import logging
import asyncio
import pytz
import os
import sys
from aiohttp import web
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN, API_ID, API_HASH, TELEGRAM_SESSION_STRING, TWITTER_VID_BOT, YOUR_CHANNEL_ID, YOUR_SECOND_CHANNEL_ID, TIMEZONE, ADMIN_IDS
from twitter_poster import TwitterPoster
from bot_handlers import BotHandlers
from video_processor import VideoProcessor
from telegram_client import TelegramClientManager
from bot_runner import BotRunner
from http_server import HTTPServer

logger = logging.getLogger(__name__)

class TwitterBot:
    def __init__(self):
        # Core components
        self.twitter_poster = TwitterPoster()
        self.handlers = BotHandlers(self)
        self.video_processor = VideoProcessor(self)
        self.telegram_client = TelegramClientManager(self)
        self.bot_runner = BotRunner(self)
        self.http_server = HTTPServer(self)
        
        # Bot state variables
        self.userbot = None
        self.waiting_for_video = False
        self.current_update = None
        self.quality_selected = False
        self.video_received = False
        self.scheduled_mode = False
        self.scheduled_counter = 0
        self.scheduled_messages = []
        self.last_processed_message_id = None
        self.incremental_schedule_mode = False
        self.fixed_interval_mode = False
        self.quality_selection_timeout = 60
        self._shutdown_flag = False
        
        # Config constants
        self.TWITTER_VID_BOT = TWITTER_VID_BOT
        self.YOUR_CHANNEL_ID = YOUR_CHANNEL_ID
        self.YOUR_SECOND_CHANNEL_ID = YOUR_SECOND_CHANNEL_ID

    def _reset_flags(self):
        """Reset processing flags"""
        self.video_received = True
        self.waiting_for_video = False
        self.current_update = None
        self.quality_selected = False

    def clean_text(self, text):
        """Delegate to video processor"""
        return self.video_processor.clean_text(text)

    async def initialize_twitter_client(self):
        """Initialize Twitter client"""
        return await self.twitter_poster.initialize_twitter_client()

    async def handle_second_channel_message(self, event):
        """Handle messages from second channel for Twitter posting"""
        await self.twitter_poster.handle_second_channel_message(self.telegram_client.userbot, event, self.YOUR_SECOND_CHANNEL_ID)

    async def run_async(self):
        """Async main function"""
        try:
            logger.info("Starting HTTP server for health checks...")
            await self.http_server.start_http_server()
            
            logger.info("Initializing UserBot...")
            await self.telegram_client.initialize_userbot()
            self.userbot = self.telegram_client.userbot
            
            logger.info("Initializing Twitter client...")
            await self.initialize_twitter_client()
            
            await self.bot_runner.start_polling()
            
        except Exception as e:
            logger.error(f"Error in run_async: {e}")
            raise

    async def shutdown(self):
        """Shutdown all services properly"""
        logger.info("Shutting down services...")
        self._shutdown_flag = True
        
        try:
            await self.bot_runner.shutdown_bot()
            await self.telegram_client.disconnect_userbot()
            await self.http_server.shutdown_server()
                
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

if __name__ == "__main__":
    bot = TwitterBot()
    bot.run()
