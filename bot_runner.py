import logging
import asyncio
import os
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from config import TELEGRAM_BOT_TOKEN

logger = logging.getLogger(__name__)

class BotRunner:
    def __init__(self, twitter_bot):
        self.bot = twitter_bot
        self.bot_app = None
        self._polling_started = False
        self._shutdown_flag = False

    async def start_polling(self):
        """Start bot polling with proper webhook cleanup"""
        try:
            if self._polling_started:
                logger.warning("Polling already started, skipping...")
                return
                
            logger.info("Starting Telegram Bot...")
            self.bot_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

            # Add handlers - FIXED: Use proper method references
            self.bot_app.add_handler(CommandHandler("start", self.bot.handlers.start_command))
            self.bot_app.add_handler(CommandHandler("task", self.bot.handlers.start_task))
            self.bot_app.add_handler(CommandHandler("task2", self.bot.handlers.start_task2))
            self.bot_app.add_handler(CommandHandler("task3", self.bot.handlers.start_task3))
            self.bot_app.add_handler(CommandHandler("endtask", self.bot.handlers.end_task))
            self.bot_app.add_handler(CommandHandler("twitter_poster", self.bot.handlers.twitter_poster_command))
            self.bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.bot.handlers.process_link))
            self.bot_app.add_handler(CallbackQueryHandler(self.bot.handlers.button_handler))

            logger.info("Bot handlers registered successfully!")
            
            # IMPORTANT: Delete any existing webhook first
            await self.bot_app.bot.delete_webhook(drop_pending_updates=True)
            logger.info("Webhook deleted, starting polling...")
            
            await asyncio.sleep(2)
            
            # Initialize and start polling
            await self.bot_app.initialize()
            await self.bot_app.start()
            
            # Start polling with specific parameters
            await self.bot_app.updater.start_polling(
                poll_interval=1.0,
                timeout=10,
                drop_pending_updates=True
            )
            
            self._polling_started = True
            logger.info("✅ Bot polling started successfully! Waiting for messages...")
            
            # Keep the polling running
            while not self._shutdown_flag and self._polling_started:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"❌ Error in polling: {e}")
            self._polling_started = False
            raise

    async def shutdown_bot(self):
        """Shutdown bot application properly"""
        if self.bot_app:
            logger.info("Stopping bot application...")
            try:
                if hasattr(self.bot_app, 'updater') and self.bot_app.updater.running:
                    await self.bot_app.updater.stop()
                await self.bot_app.stop()
                await self.bot_app.shutdown()
                self._polling_started = False
                logger.info("✅ Bot application stopped successfully")
            except Exception as e:
                logger.error(f"❌ Error stopping bot: {e}")
