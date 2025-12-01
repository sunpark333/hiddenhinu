import logging
import asyncio
import os
import sys
from config import TELEGRAM_BOT_TOKEN, API_ID, API_HASH, TELEGRAM_SESSION_STRING, TWITTER_VID_BOT, YOUR_CHANNEL_ID, YOUR_SECOND_CHANNEL_ID, TIMEZONE
from twitter_bot import TwitterBot
from telegram_bot import TelegramBot
from twitter_poster import TwitterPoster
from http_server import HTTPServer

# Koyeb के लिए logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class MainBot:
    def __init__(self):
        self.twitter_bot = TwitterBot()
        self.telegram_bot = TelegramBot(self.twitter_bot)
        self.twitter_poster = TwitterPoster()
        self.http_server = HTTPServer()
        self._shutdown_flag = False

    async def run_async(self):
        """Async main function"""
        try:
            logger.info("Starting HTTP server for health checks...")
            await self.http_server.start_http_server()
            
            logger.info("Initializing UserBot...")
            await self.twitter_bot.initialize_userbot()
            
            logger.info("Initializing Twitter client...")
            await self.twitter_poster.initialize_twitter_client()
            
            logger.info("Starting Telegram bot polling...")
            await self.telegram_bot.start_polling()
            
            # Keep the application running
            while not self._shutdown_flag:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in run_async: {e}")
            raise

    async def shutdown(self):
        """Shutdown all services properly"""
        logger.info("Shutting down services...")
        self._shutdown_flag = True
        
        try:
            await self.telegram_bot.shutdown()
            await self.twitter_bot.shutdown()
            await self.http_server.shutdown()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        
        logger.info("All services safely shut down")

    def run(self):
        """Main function to run the bot"""
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries and not self._shutdown_flag:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                logger.info(f"Starting bot... (Attempt {retry_count + 1})")
                loop.run_until_complete(self.run_async())
                
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, shutting down...")
                break
                
            except Exception as e:
                retry_count += 1
                logger.error(f"Critical error (attempt {retry_count}/{max_retries}): {str(e)}")
                
                if retry_count < max_retries:
                    logger.info(f"Retrying in 10 seconds...")
                    try:
                        loop.run_until_complete(self.shutdown())
                    except Exception as shutdown_error:
                        logger.error(f"Error during shutdown: {shutdown_error}")
                    import time
                    time.sleep(10)
                else:
                    logger.error("Maximum retries reached. Exiting...")
                    break
            finally:
                try:
                    loop.run_until_complete(self.shutdown())
                except Exception as e:
                    logger.error(f"Error in final shutdown: {e}")
                loop.close()

if __name__ == '__main__':
    logger.info("Starting Twitter Bot on Koyeb...")
    bot = MainBot()
    bot.run()
