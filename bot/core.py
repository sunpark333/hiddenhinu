"""
Core functionality - Bot initialization and main logic
"""

import logging
import asyncio
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.sessions import StringSession
from telegram.ext import Application

from config import (
    TELEGRAM_BOT_TOKEN, API_ID, API_HASH, TELEGRAM_SESSION_STRING,
    TWITTER_VID_BOT, YOUR_CHANNEL_ID, YOUR_SECOND_CHANNEL_ID, TIMEZONE,
    ADMIN_IDS
)
from ai_caption_enhancer import AICaptionEnhancer
from .handlers import MessageHandlers
from .twitter import TwitterPoster
from .scheduler import ScheduleManager
from .utils import TextUtils

logger = logging.getLogger(__name__)


class TwitterBot:
    def __init__(self):
        self.userbot = None
        self.bot_app = None
        self.loop = None
        self.waiting_for_video = False
        self.current_update = None
        self.quality_selected = False
        self.video_received = False
        
        # Scheduling related
        self.scheduled_mode = False
        self.scheduled_counter = 0
        self.scheduled_messages = []
        self.last_processed_message_id = None
        self.incremental_schedule_mode = False
        self.fixed_interval_mode = False
        
        # Server and shutdown
        self.quality_selection_timeout = 60
        self._shutdown_flag = False
        self.http_app = None
        self.runner = None
        self.site = None
        self.polling_task = None
        self._polling_started = False
        
        # Initialize components
        self.ai_enhancer = AICaptionEnhancer()
        self.twitter_poster = TwitterPoster()
        self.handlers = MessageHandlers(self)
        self.scheduler = ScheduleManager(self)
        self.text_utils = TextUtils()
        
        # Twitter posting feature
        self.twitter_poster_enabled = True

    async def initialize_userbot(self):
        """Initialize Telegram userbot with string session"""
        try:
            logger.info("Starting UserBot initialization...")
            session = StringSession(TELEGRAM_SESSION_STRING)
            self.userbot = TelegramClient(
                session=session,
                api_id=int(API_ID),
                api_hash=API_HASH
            )

            await self.userbot.start()
            logger.info("UserBot successfully started")

            me = await self.userbot.get_me()
            logger.info(f"UserBot started as: {me.username} (ID: {me.id})")

            try:
                channel = await self.userbot.get_entity(YOUR_CHANNEL_ID)
                logger.info(f"Verified access to channel: {channel.title}")
                second_channel = await self.userbot.get_entity(YOUR_SECOND_CHANNEL_ID)
                logger.info(f"Verified access to second channel: {second_channel.title}")
            except Exception as e:
                logger.error(f"Channel access failed: {str(e)}")
                raise

            # Setup handlers
            await self.handlers.setup_handlers()

        except Exception as e:
            logger.error(f"Failed to initialize userbot: {str(e)}")
            raise

    async def start_http_server(self):
        """Start HTTP server for health checks"""
        from aiohttp import web
        
        self.http_app = web.Application()
        self.http_app.router.add_get('/', self.handlers.health_check)
        self.http_app.router.add_get('/health', self.handlers.health_check)

        runner = web.AppRunner(self.http_app)
        await runner.setup()

        import os
        port = int(os.environ.get('PORT', 8000))
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()

        logger.info(f"HTTP server started on port {port}")
        return runner, site

    async def start_polling(self):
        """Start bot polling in a separate task"""
        try:
            if self._polling_started:
                logger.warning("Polling already started, skipping...")
                return

            logger.info("Starting Telegram Bot...")
            self.bot_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

            # Add all handlers
            await self.handlers.add_all_handlers(self.bot_app)

            logger.info("Bot started successfully! Waiting for messages...")

            await self.bot_app.bot.delete_webhook(drop_pending_updates=True)
            await asyncio.sleep(2)

            await self.bot_app.initialize()
            await self.bot_app.start()
            await self.bot_app.updater.start_polling()

            self._polling_started = True

            while not self._shutdown_flag:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error in polling: {e}")
            self._polling_started = False
            raise

        finally:
            if self.bot_app:
                await self.bot_app.updater.stop()
                await self.bot_app.stop()
                await self.bot_app.shutdown()
            self._polling_started = False

    async def shutdown(self):
        """Shutdown all services properly"""
        logger.info("Shutting down services...")
        self._shutdown_flag = True

        try:
            if self.bot_app and self.bot_app.running:
                logger.info("Stopping bot application...")
                await self.bot_app.updater.stop()
                await self.bot_app.stop()
                await self.bot_app.shutdown()

            if self.userbot and self.userbot.is_connected():
                logger.info("Disconnecting userbot...")
                await self.userbot.disconnect()

            if self.runner:
                logger.info("Stopping HTTP server...")
                await self.runner.cleanup()

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

        logger.info("All services safely shut down")

    async def run_async(self):
        """Async main function"""
        try:
            logger.info("Starting HTTP server for health checks...")
            self.runner, self.site = await self.start_http_server()

            logger.info("Initializing UserBot...")
            await self.initialize_userbot()

            logger.info("Initializing Twitter client...")
            await self.twitter_poster.initialize_twitter_client()

            await self.start_polling()

        except Exception as e:
            logger.error(f"Error in run_async: {e}")
            raise

    def run(self):
        """Main function to run the bot"""
        import time
        
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
