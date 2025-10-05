import logging
import asyncio
import pytz
import os
from telethon import TelegramClient, events
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime, timedelta
import re
from config import TELEGRAM_BOT_TOKEN, API_ID, API_HASH, TELEGRAM_SESSION_STRING, TWITTER_VID_BOT, YOUR_CHANNEL_ID, TIMEZONE

# Set timezone
TIMEZONE = pytz.timezone(TIMEZONE)

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TwitterBot:
    def __init__(self):
        self.userbot = None
        self.bot_app = None
        self.loop = asyncio.new_event_loop()
        self.waiting_for_video = False
        self.current_update = None
        self.quality_selected = False
        self.video_received = False
        self.scheduled_mode = False
        self.scheduled_counter = 0
        self.scheduled_messages = []
        self.last_processed_message_id = None
        self.incremental_schedule_mode = False
        self.quality_selection_timeout = 30

    async def initialize_userbot(self):
        """Initialize Telegram userbot with string session"""
        try:
            # String session se initialize karein
            self.userbot = TelegramClient(
                session=TELEGRAM_SESSION_STRING,
                api_id=int(API_ID),
                api_hash=API_HASH,
                loop=self.loop
            )
            
            await self.userbot.start()
            
            logger.info("UserBot successfully started with string session")
            
            # Event handler for twittervid_bot
            @self.userbot.on(events.NewMessage(from_users=TWITTER_VID_BOT))
            async def handle_twittervid_message(event):
                await self._handle_twittervid_response(event)
                
            # Test connection
            me = await self.userbot.get_me()
            logger.info(f"Bot started as: {me.username}")
            
            # Channel access test
            try:
                test_message = await self.userbot.send_message(YOUR_CHANNEL_ID, "🤖 Bot initialized and ready!")
                await test_message.delete()
                logger.info(f"Verified access to channel {YOUR_CHANNEL_ID}")
            except Exception as e:
                logger.error(f"Channel access failed: {str(e)}")
                raise
                
        except Exception as e:
            logger.error(f"Failed to initialize userbot: {str(e)}")
            raise

    async def _handle_twittervid_response(self, event):
        """Handle responses from twittervid_bot"""
        try:
            if self.last_processed_message_id is not None and event.message.id <= self.last_processed_message_id:
                return
                
            self.last_processed_message_id = event.message.id
            
            if self.waiting_for_video and self.current_update:
                await asyncio.sleep(2)  # Increased delay for stability
                
                # Handle quality selection
                if "Select Video Quality" in event.message.text and not self.quality_selected:
                    logger.info("Quality selection detected")
                    try:
                        buttons = await event.message.get_buttons()
                        if buttons:
                            # First row ke buttons check karein
                            if len(buttons) > 0 and len(buttons[0]) > 0:
                                await buttons[0][0].click()  # First button click karein
                                quality = buttons[0][0].text
                                logger.info(f"Selected quality: {quality}")
                                
                                if self.current_update and self.current_update.message:
                                    await self.current_update.message.reply_text(
                                        f"✅ Video is being downloaded in {quality} quality..."
                                    )
                                self.quality_selected = True
                                return
                    except Exception as e:
                        logger.error(f"Error in quality selection: {str(e)}")
                
                # Handle received video/media
                if (event.message.media or event.message.text) and self.quality_selected:
                    await self._process_received_video(event)
                    
        except Exception as e:
            logger.error(f"Error in handle_twittervid_message: {str(e)}")

    async def _process_received_video(self, event):
        """Process received video and send to channel"""
        try:
            caption = self.clean_text(event.message.text) if event.message.text else ""
            
            if caption:
                caption = f"\n\n{caption}\n\n"
            else:
                caption = "\n\n"
            
            if self.scheduled_mode or self.incremental_schedule_mode:
                scheduled_time = self._calculate_schedule_time()
                
                if event.message.media:
                    message = await self.userbot.send_file(
                        YOUR_CHANNEL_ID,
                        file=event.message.media,
                        caption=caption,
                        schedule=scheduled_time
                    )
                else:
                    message = await self.userbot.send_message(
                        YOUR_CHANNEL_ID,
                        caption,
                        schedule=scheduled_time
                    )
                
                self.scheduled_counter += 1
                self.scheduled_messages.append(message.id)
                
                if self.current_update and self.current_update.message:
                    await self.current_update.message.reply_text(
                        f"✅ Video successfully scheduled for {scheduled_time.strftime('%Y-%m-%d %H:%M')} IST!"
                    )
            else:
                if event.message.media:
                    await self.userbot.send_file(
                        YOUR_CHANNEL_ID,
                        file=event.message.media,
                        caption=caption
                    )
                else:
                    await self.userbot.send_message(
                        YOUR_CHANNEL_ID,
                        caption
                    )
                
                if self.current_update and self.current_update.message:
                    await self.current_update.message.reply_text("✅ Video successfully sent to your channel!")
            
            logger.info(f"Message sent to channel {YOUR_CHANNEL_ID}")
            self._reset_flags()
            
        except Exception as e:
            error_msg = f"❌ Error sending video to channel: {str(e)}"
            logger.error(error_msg)
            if self.current_update and self.current_update.message:
                await self.current_update.message.reply_text(error_msg)
            self._reset_flags()

    def _calculate_schedule_time(self):
        """Calculate schedule time based on mode"""
        now = datetime.now(TIMEZONE)
        
        if self.scheduled_mode:
            scheduled_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
            if scheduled_time < now:
                scheduled_time += timedelta(days=1)
            scheduled_time += timedelta(hours=self.scheduled_counter)
        else:
            scheduled_time = now + timedelta(hours=self.scheduled_counter + 2)
        
        return scheduled_time

    def _reset_flags(self):
        """Reset processing flags"""
        self.video_received = True
        self.waiting_for_video = False
        self.current_update = None
        self.quality_selected = False

    def clean_text(self, text):
        """Remove last 3 lines and clean text"""
        if not text:
            return text
            
        lines = text.split('\n')
        if len(lines) > 3:
            lines = lines[:-3]
        cleaned_text = '\n'.join(lines)
        
        # Remove hidden links if any
        hidden_link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        cleaned_text = re.sub(hidden_link_pattern, r'\1', cleaned_text)
        
        # Remove banned text pattern
        cleaned_text = cleaned_text.replace('📲 @twittervid_bot', '').strip()
        
        return cleaned_text

    async def start_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start scheduled posting mode"""
        self.scheduled_mode = True
        self.incremental_schedule_mode = False
        self.scheduled_counter = 0
        self.scheduled_messages = []
        
        now = datetime.now(TIMEZONE)
        first_schedule_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
        if first_schedule_time < now:
            first_schedule_time += timedelta(days=1)
        
        await update.message.reply_text(
            "📅 Scheduled mode activated!\n"
            f"First video will be scheduled at {first_schedule_time.strftime('%Y-%m-%d %H:%M')} IST\n"
            "Each new video will be scheduled 1 hour after the previous one.\n"
            "Use /endtask to stop scheduled posting."
        )

    async def start_task2(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start incremental scheduled posting mode"""
        self.incremental_schedule_mode = True
        self.scheduled_mode = False
        self.scheduled_counter = 0
        self.scheduled_messages = []
        
        now = datetime.now(TIMEZONE)
        first_schedule_time = now + timedelta(hours=2)
        
        await update.message.reply_text(
            "⏱️ Incremental Scheduled mode activated!\n"
            f"First video will be scheduled at {first_schedule_time.strftime('%Y-%m-%d %H:%M')} IST\n"
            "Next video will be scheduled 2 hours after, then 3 hours, and so on.\n"
            "Use /endtask to stop scheduled posting."
        )

    async def end_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """End scheduled posting mode"""
        self.scheduled_mode = False
        self.incremental_schedule_mode = False
        await update.message.reply_text(
            "🚫 Scheduled mode deactivated!\n"
            "Videos will now be posted immediately.\n"
            f"Total {self.scheduled_counter} videos were scheduled."
        )
        self.scheduled_counter = 0
        self.scheduled_messages = []

    async def process_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process Twitter links"""
        try:
            if not update or not update.message or not update.message.text:
                await update.message.reply_text("⚠️ Please provide a valid Twitter link.")
                return

            message = update.message
            text = message.text
            
            # Clean the text (removes last 3 lines and other unwanted content)
            text = self.clean_text(text)
            
            if not text:
                await message.reply_text("⚠️ Please provide a valid Twitter link.")
                return
            
            self.current_update = update
            self.waiting_for_video = True
            self.quality_selected = False
            self.video_received = False
            
            await message.reply_text("⏳ Processing link and downloading video...")
            
            # Send the link to twittervid_bot
            await self.userbot.send_message(TWITTER_VID_BOT, text)
            logger.info(f"Link sent to twittervid_bot: {text}")
            
            # Wait for quality selection response
            start_time = datetime.now()
            while not self.quality_selected and (datetime.now() - start_time).seconds < self.quality_selection_timeout:
                await asyncio.sleep(1)
                
            if not self.quality_selected:
                await message.reply_text("⚠️ Timeout waiting for quality selection. Please try again.")
                self.waiting_for_video = False
                self.current_update = None
                return

        except Exception as e:
            error_msg = f"❌ Error processing link: {str(e)}"
            logger.error(error_msg)
            if update and update.message:
                await update.message.reply_text(error_msg)
            self.waiting_for_video = False
            self.current_update = None
            self.quality_selected = False

    def run(self):
        """Main function to run the bot"""
        asyncio.set_event_loop(self.loop)
        
        try:
            # First userbot initialize karein
            self.loop.run_until_complete(self.initialize_userbot())
            
            # Phir bot app start karein
            self.bot_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
            self.bot_app.add_handler(CommandHandler("task", self.start_task))
            self.bot_app.add_handler(CommandHandler("task2", self.start_task2))
            self.bot_app.add_handler(CommandHandler("endtask", self.end_task))
            self.bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_link))
            
            logger.info("Telegram Bot starting...")
            self.loop.run_until_complete(self.bot_app.run_polling())
            
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Critical error: {str(e)}")
        finally:
            self.loop.run_until_complete(self.shutdown())
            self.loop.close()

    async def shutdown(self):
        """Shutdown all services"""
        logger.info("Shutting down services...")
        if self.bot_app:
            await self.bot_app.shutdown()
        if self.userbot and self.userbot.is_connected():
            await self.userbot.disconnect()
        logger.info("All services safely shut down")

if __name__ == '__main__':
    bot = TwitterBot()
    bot.run()
