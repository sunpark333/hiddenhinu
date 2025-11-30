import logging
import asyncio
import signal
import sys
import os
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

        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        try:
            if sys.platform != 'win32':
                signal.signal(signal.SIGTERM, self._signal_handler)
                signal.signal(signal.SIGINT, self._signal_handler)
                logger.info("Signal handlers setup completed")
        except Exception as e:
            logger.warning(f"Could not setup signal handlers: {e}")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received shutdown signal {signum}, initiating graceful shutdown...")
        self._shutdown_flag = True

    def _reset_flags(self):
        """Reset processing flags"""
        self.video_received = True
        self.waiting_for_video = False
        self.current_update = None
        self.quality_selected = False
        logger.debug("Bot flags reset successfully")

    def clean_text(self, text):
        """Delegate to video processor"""
        return self.video_processor.clean_text(text)

    async def initialize_twitter_client(self):
        """Initialize Twitter client"""
        try:
            success = await self.twitter_poster.initialize_twitter_client()
            if success:
                logger.info("✅ Twitter client initialized successfully")
            else:
                logger.warning("❌ Twitter client initialization failed")
            return success
        except Exception as e:
            logger.error(f"❌ Error initializing Twitter client: {e}")
            return False

    async def handle_second_channel_message(self, event):
        """Handle messages from second channel for Twitter posting"""
        try:
            await self.twitter_poster.handle_second_channel_message(
                self.telegram_client.userbot, event, self.YOUR_SECOND_CHANNEL_ID
            )
        except Exception as e:
            logger.error(f"Error handling second channel message: {e}")

    async def run_async(self):
        """Async main function"""
        try:
            # Koyeb fix: Add delay to prevent multiple instances conflict
            logger.info("⏳ Waiting 5 seconds to prevent multiple instances conflict...")
            await asyncio.sleep(5)
            
            logger.info("🚀 Starting bot initialization...")
            
            # Step 1: Start HTTP server for health checks
            logger.info("🌐 Starting HTTP server for health checks...")
            await self.http_server.start_http_server()
            
            # Step 2: Initialize Telegram UserBot
            logger.info("🔧 Initializing UserBot...")
            await self.telegram_client.initialize_userbot()
            self.userbot = self.telegram_client.userbot
            
            # Step 3: Initialize Twitter client
            logger.info("🐦 Initializing Twitter client...")
            await self.initialize_twitter_client()
            
            # Step 4: Start bot polling
            logger.info("🤖 Starting Telegram bot polling...")
            await self.bot_runner.start_polling()
            
            logger.info("✅ All services started successfully! Bot is now running...")
            
        except Exception as e:
            logger.error(f"❌ Error in run_async: {e}")
            raise

    async def shutdown(self):
        """Shutdown all services properly"""
        logger.info("🛑 Shutting down services...")
        self._shutdown_flag = True
        
        shutdown_tasks = []
        
        try:
            # Shutdown bot runner
            if hasattr(self, 'bot_runner'):
                shutdown_tasks.append(self.bot_runner.shutdown_bot())
            
            # Disconnect Telegram client
            if hasattr(self, 'telegram_client'):
                shutdown_tasks.append(self.telegram_client.disconnect_userbot())
            
            # Shutdown HTTP server
            if hasattr(self, 'http_server'):
                shutdown_tasks.append(self.http_server.shutdown_server())
            
            # Wait for all shutdown tasks to complete
            if shutdown_tasks:
                await asyncio.gather(*shutdown_tasks, return_exceptions=True)
                
        except Exception as e:
            logger.error(f"❌ Error during shutdown: {e}")
        
        logger.info("✅ All services safely shut down")

    def run(self):
        """Main function to run the bot"""
        retry_count = 0
        max_retries = 3
        
        logger.info(f"🤖 Starting Twitter Video Bot (Max retries: {max_retries})...")
        
        while retry_count < max_retries and not self._shutdown_flag:
            try:
                # Create new event loop for each retry
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                
                logger.info(f"🔄 Starting bot... (Attempt {retry_count + 1}/{max_retries})")
                
                # Run the main async function
                self.loop.run_until_complete(self.run_async())
                
                # If we reach here, the bot is running successfully
                logger.info("✅ Bot is running successfully!")
                
                # Keep the bot running until shutdown signal
                try:
                    while not self._shutdown_flag:
                        self.loop.run_until_complete(asyncio.sleep(1))
                except KeyboardInterrupt:
                    logger.info("Received keyboard interrupt, shutting down...")
                    break
                    
            except KeyboardInterrupt:
                logger.info("⌨️ Received keyboard interrupt, shutting down...")
                break
                
            except Exception as e:
                retry_count += 1
                logger.error(f"❌ Critical error (attempt {retry_count}/{max_retries}): {str(e)}")
                
                if retry_count < max_retries:
                    logger.info(f"⏳ Retrying in 10 seconds...")
                    try:
                        # Shutdown properly before retry
                        if self.loop and not self.loop.is_closed():
                            self.loop.run_until_complete(self.shutdown())
                    except Exception as shutdown_error:
                        logger.error(f"❌ Error during shutdown: {shutdown_error}")
                    
                    # Wait before retry
                    import time
                    time.sleep(10)
                else:
                    logger.error("🚫 Maximum retries reached. Exiting...")
                    break
                    
            finally:
                # Always cleanup the event loop
                if hasattr(self, 'loop') and self.loop and not self.loop.is_closed():
                    try:
                        logger.info("🧹 Cleaning up event loop...")
                        self.loop.run_until_complete(self.shutdown())
                        self.loop.close()
                    except Exception as e:
                        logger.error(f"❌ Error in final shutdown: {e}")
        
        logger.info("👋 Bot shutdown completed. Goodbye!")

def main():
    """Main entry point with proper error handling"""
    try:
        # Setup basic logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Create and run bot
        bot = TwitterBot()
        bot.run()
        
    except Exception as e:
        logger.error(f"❌ Fatal error in main: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
