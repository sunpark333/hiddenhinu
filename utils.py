import logging
import asyncio
import os
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telegram.ext import Application
from config import (
    TELEGRAM_BOT_TOKEN, API_ID, API_HASH, 
    TELEGRAM_SESSION_STRING, YOUR_CHANNEL_ID,
    YOUR_SECOND_CHANNEL_ID
)

logger = logging.getLogger(__name__)

class BotUtils:
    """सहायक utilities"""
    
    def __init__(self, twitter_bot):
        self.twitter_bot = twitter_bot
        self.http_app = None
        self.runner = None
        self.site = None
    
    async def health_check(self, request):
        """Health check endpoint"""
        return web.Response(text="Bot is running!")
    
    async def start_http_server(self):
        """Start HTTP server"""
        self.http_app = web.Application()
        self.http_app.router.add_get('/', self.health_check)
        self.http_app.router.add_get('/health', self.health_check)
        
        self.runner = web.AppRunner(self.http_app)
        await self.runner.setup()
        
        port = int(os.environ.get('PORT', 8000))
        self.site = web.TCPSite(self.runner, '0.0.0.0', port)
        await self.site.start()
        
        logger.info(f"HTTP server started on port {port}")
        return self.runner, self.site
    
    async def initialize_userbot(self):
        """Initialize Telegram userbot"""
        try:
            logger.info("Starting UserBot initialization...")
            
            session = StringSession(TELEGRAM_SESSION_STRING)
            self.twitter_bot.userbot = TelegramClient(
                session=session,
                api_id=int(API_ID),
                api_hash=API_HASH
            )

            await self.twitter_bot.userbot.start()
            logger.info("UserBot successfully started")

            # Add handlers
            self._setup_userbot_handlers()

            me = await self.twitter_bot.userbot.get_me()
            logger.info(f"UserBot started as: {me.username} (ID: {me.id})")

            # Verify channel access
            await self._verify_channel_access()
            
        except Exception as e:
            logger.error(f"Failed to initialize userbot: {str(e)}")
            raise
    
    def _setup_userbot_handlers(self):
        """Setup userbot event handlers"""
        
        @self.twitter_bot.userbot.on(events.NewMessage(from_users=self.twitter_bot.config.TWITTER_VID_BOT))
        async def handle_twittervid_message(event):
            await self.twitter_bot.video_processor.handle_twittervid_response(event)

        if self.twitter_bot.twitter_poster.twitter_poster_enabled:
            @self.twitter_bot.userbot.on(events.NewMessage(chats=YOUR_SECOND_CHANNEL_ID))
            async def handle_second_channel_message(event):
                await self.twitter_bot.video_processor.handle_second_channel_for_twitter(event)
            logger.info("Second channel handler added for Twitter posting")
    
    async def _verify_channel_access(self):
        """Verify access to channels"""
        try:
            channel = await self.twitter_bot.userbot.get_entity(YOUR_CHANNEL_ID)
            logger.info(f"Verified access to channel: {channel.title}")
            
            second_channel = await self.twitter_bot.userbot.get_entity(YOUR_SECOND_CHANNEL_ID)
            logger.info(f"Verified access to second channel: {second_channel.title}")
        except Exception as e:
            logger.error(f"Channel access failed: {str(e)}")
            raise
    
    async def start_polling(self):
        """Start bot polling"""
        try:
            if self.twitter_bot._polling_started:
                logger.warning("Polling already started, skipping...")
                return
                
            logger.info("Starting Telegram Bot...")
            self.twitter_bot.bot_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

            # Setup handlers
            self.twitter_bot.telegram_handlers = TelegramHandlers(
                self.twitter_bot.bot_app, 
                self.twitter_bot
            )

            logger.info("Bot started successfully! Waiting for messages...")
            
            # Stop any existing webhook first
            await self.twitter_bot.bot_app.bot.delete_webhook(drop_pending_updates=True)
            await asyncio.sleep(2)
            
            await self.twitter_bot.bot_app.initialize()
            await self.twitter_bot.bot_app.start()
            await self.twitter_bot.bot_app.updater.start_polling()
            
            self.twitter_bot._polling_started = True
            
            # Keep the polling running
            while not self.twitter_bot._shutdown_flag:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in polling: {e}")
            self.twitter_bot._polling_started = False
            raise
