import logging
import asyncio  # ADD THIS IMPORT
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import TIMEZONE, ADMIN_IDS

logger = logging.getLogger(__name__)

class BotHandlers:
    def __init__(self, twitter_bot):
        self.bot = twitter_bot

    # ... (all your existing methods remain same until process_link) ...

    async def process_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process Twitter links"""
        try:
            if not await self.admin_only(update, context):
                return

            if not update or not update.message or not update.message.text:
                await update.message.reply_text(
                    "⚠️ Please provide a valid Twitter link."
                )
                return

            message = update.message
            text = message.text.strip()

            if not any(domain in text for domain in ['twitter.com', 'x.com']):
                await message.reply_text(
                    "⚠️ Please provide a valid Twitter/X link."
                )
                return

            text = self.bot.clean_text(text)

            self.bot.current_update = update
            self.bot.waiting_for_video = True
            self.bot.quality_selected = False
            self.bot.video_received = False

            await message.reply_text(
                "⏳ Processing link and downloading video..."
            )

            await self.bot.userbot.send_message(self.bot.TWITTER_VID_BOT, text)
            logger.info(f"Link sent to twittervid_bot: {text}")

            start_time = datetime.now()
            while (datetime.now() - start_time).seconds < self.bot.quality_selection_timeout:
                if self.bot.quality_selected or self.bot.video_received:
                    break
                await asyncio.sleep(2)  # FIXED: asyncio imported now

            if not self.bot.quality_selected and not self.bot.video_received:
                await message.reply_text(
                    "⚠️ Timeout waiting for video processing. Please try again."
                )
                self.bot._reset_flags()

        except Exception as e:
            error_msg = f"❌ Error processing link: {str(e)}"
            logger.error(error_msg)
            if update and update.message:
                await update.message.reply_text(
                    error_msg
                )
            self.bot._reset_flags()
