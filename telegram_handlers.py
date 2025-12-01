from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import ADMIN_IDS, TIMEZONE
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class TelegramHandlers:
    def __init__(self, bot_instance):
        self.bot = bot_instance

    def is_admin(self, user_id):
        """Admin check"""
        return user_id in ADMIN_IDS

    async def admin_only(self, update, context):
        """Admin permission check"""
        try:
            if hasattr(update, 'effective_user'):
                user_id = update.effective_user.id
            elif hasattr(update, 'callback_query'):
                user_id = update.callback_query.from_user.id
            else:
                return False

            if not self.is_admin(user_id):
                if hasattr(update, 'message'):
                    await update.message.reply_text("🚫 **Access Denied! Admin only**")
                return False
            return True
        except:
            return False

    async def start_command(self, update, context):
        """Start command with buttons"""
        if not await self.admin_only(update, context):
            return
        
        keyboard = [
            [InlineKeyboardButton("1 hour", callback_data="task_1hour"),
             InlineKeyboardButton("now send", callback_data="task2_nowsend")],
            [InlineKeyboardButton("2 hour", callback_data="task3_2hour")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        twitter_status = "✅ ENABLED" if self.bot.twitter_handler.twitter_poster_enabled else "❌ DISABLED"
        
        await update.message.reply_text(
            f"🤖 **Twitter Video Bot**\n\n"
            f"📤 Send Twitter link to download\n\n"
            f"📋 **Modes:**\n"
            f"• 1 hour - Daily 7AM +1h\n"
            f"• now send - +2h, +3h...\n"
            f"• 2 hour - Every 2h from 7AM\n\n"
            f"🐦 Twitter: {twitter_status}",
            reply_markup=reply_markup
        )

    async def process_link(self, update, context):
        """Twitter link process करें"""
        if not await self.admin_only(update, context):
            return
        
        text = update.message.text.strip()
        if not any(domain in text for domain in ['twitter.com', 'x.com']):
            await update.message.reply_text("⚠️ Valid Twitter/X link भेजें")
            return
        
        self.bot.current_update = update
        self.bot.waiting_for_video = True
        await update.message.reply_text("⏳ Video download हो रही है...")
        await self.bot.userbot.send_message(self.bot.twitter_vid_bot, self.bot.clean_text(text))
