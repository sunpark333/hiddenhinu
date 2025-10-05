import logging
import asyncio
import pytz
import os
from telethon import TelegramClient, events
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime, timedelta
import re

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Bot configuration settings
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
TWITTER_VID_BOT = os.getenv('TWITTER_VID_BOT', 'twittervid_bot')
YOUR_CHANNEL_ID = int(os.getenv('YOUR_CHANNEL_ID', '-1001737011271'))
TIMEZONE = pytz.timezone(os.getenv('TIMEZONE', 'Asia/Kolkata'))

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

    def clean_text(self, text):
        """Remove last 3 lines and clean text"""
        if not text:
            return text
            
        lines = text.split('\n')
        if len(lines) > 3:
            lines = lines[:-3]
        cleaned_text = '\n'.join(lines)
        
        hidden_link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        cleaned_text = re.sub(hidden_link_pattern, r'\1', cleaned_text)
        
        cleaned_text = cleaned_text.replace('📲 @twittervid_bot', '').strip()
        
        return cleaned_text

    def generate_divider(self):
        """Generate divider line"""
        return ""

    async def initialize_userbot(self):
        """Initialize Telegram userbot"""
        self.userbot = TelegramClient('userbot_session', int(API_ID), API_HASH, loop=self.loop)
        await self.userbot.start(PHONE_NUMBER)
        
        @self.userbot.on(events.NewMessage(from_users=TWITTER_VID_BOT))
        async def handle_twittervid_message(event):
            try:
                if self.last_processed_message_id is not None and event.message.id <= self.last_processed_message_id:
                    return
                    
                self.last_processed_message_id = event.message.id
                
                if self.waiting_for_video and self.current_update:
                    await asyncio.sleep(1)
                    
                    if "Select Video Quality" in event.message.text and not self.quality_selected:
                        buttons = await event.message.get_buttons()
                        if buttons and len(buttons) > 1 and len(buttons[1]) > 0:
                            await buttons[1][0].click()
                            quality = buttons[1][0].text
                            if self.current_update and self.current_update.message:
                                await self.current_update.message.reply_text(
                                    f"✅ Video is being downloaded in {quality} quality..."
                                )
                            self.quality_selected = True
                            return
                    
                    if (event.message.media or event.message.text) and self.quality_selected:
                        try:
                            caption = self.clean_text(event.message.text) if event.message.text else ""
                            divider = self.generate_divider()
                            if caption:
                                caption = f"{divider}\n\n{caption}\n\n{divider}"
                            else:
                                caption = f"{divider}\n\n{divider}"
                            
                            if self.scheduled_mode or self.incremental_schedule_mode:
                                now = datetime.now(TIMEZONE)
                                
                                if self.scheduled_mode:
                                    scheduled_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
                                    if scheduled_time < now:
                                        scheduled_time += timedelta(days=1)
                                    scheduled_time += timedelta(hours=self.scheduled_counter)
                                else:
                                    scheduled_time = now + timedelta(hours=self.scheduled_counter + 2)
                                
                                if event.message.media:
                                    message = await self.userbot.send_file(
                                        YOUR_CHANNEL_ID,
                                        file=event.message.media,
                                        caption=caption,
                                        schedule=scheduled_time,
                                        parse_mode='Markdown'
                                    )
                                else:
                                    message = await self.userbot.send_message(
                                        YOUR_CHANNEL_ID,
                                        caption,
                                        schedule=scheduled_time,
                                        parse_mode='Markdown'
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
                                        caption=caption,
                                        parse_mode='Markdown'
                                    )
                                else:
                                    await self.userbot.send_message(
                                        YOUR_CHANNEL_ID,
                                        caption,
                                        parse_mode='Markdown'
                                    )
                                
                                if self.current_update and self.current_update.message:
                                    await self.current_update.message.reply_text("✅ Video successfully sent to your channel!")
                            
                            logger.info(f"Message sent to channel {YOUR_CHANNEL_ID}")
                            self.video_received = True
                            self.waiting_for_video = False
                            self.current_update = None
                            self.quality_selected = False
                        except Exception as e:
                            error_msg = f"❌ Error sending video to channel: {str(e)}"
                            logger.error(error_msg)
                            if self.current_update and self.current_update.message:
                                await self.current_update.message.reply_text(error_msg)
                            self.waiting_for_video = False
                            self.current_update = None
                            self.quality_selected = False
            except Exception as e:
                logger.error(f"Error in handle_twittervid_message: {str(e)}")
        
        logger.info("UserBot successfully started")
        try:
            me = await self.userbot.get_me()
            test_message = await self.userbot.send_message(YOUR_CHANNEL_ID, "Bot initialized and ready to forward videos")
            await test_message.delete()
            logger.info(f"Verified access to channel {YOUR_CHANNEL_ID}")
        except Exception as e:
            logger.error(f"Failed to access channel: {str(e)}")
            raise

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
            
            text = self.clean_text(text)
            
            if not text:
                await message.reply_text("⚠️ Please provide a valid Twitter link.")
                return
            
            self.current_update = update
            self.waiting_for_video = True
            self.quality_selected = False
            self.video_received = False
            
            await message.reply_text("⏳ Processing link and downloading video...")
            
            await self.userbot.send_message(TWITTER_VID_BOT, text)
            logger.info(f"Link sent: {text}")
            
            start_time = datetime.now()
            while not self.quality_selected:
                await asyncio.sleep(1)
                if (datetime.now() - start_time).seconds > self.quality_selection_timeout:
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
            self.loop.run_until_complete(self.initialize_userbot())
            
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
