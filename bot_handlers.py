import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import TIMEZONE, ADMIN_IDS

logger = logging.getLogger(__name__)

class BotHandlers:
    def __init__(self, twitter_bot):
        self.bot = twitter_bot

    def is_admin(self, user_id):
        """Check if user is admin"""
        return user_id in ADMIN_IDS

    async def admin_only(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check if user is admin and send access denied message if not"""
        try:
            if hasattr(update, 'effective_user'):
                user_id = update.effective_user.id
            elif hasattr(update, 'message') and update.message:
                user_id = update.message.from_user.id
            elif hasattr(update, 'callback_query') and update.callback_query:
                user_id = update.callback_query.from_user.id
            else:
                user_id = update.from_user.id if hasattr(update, 'from_user') else None
            
            if not user_id or not self.is_admin(user_id):
                if hasattr(update, 'message') and update.message:
                    await update.message.reply_text(
                        "🚫 **Access Denied!**\n\n"
                        "You are not authorized to use this bot.\n"
                        "This bot is restricted to administrators only."
                    )
                elif hasattr(update, 'callback_query') and update.callback_query:
                    await update.callback_query.message.reply_text(
                        "🚫 **Access Denied!**\n\n"
                        "You are not authorized to use this bot.\n"
                        "This bot is restricted to administrators only."
                    )
                return False
            return True
        except Exception as e:
            logger.error(f"Error in admin check: {e}")
            return False

    async def admin_only_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin check specifically for callback queries"""
        user_id = update.callback_query.from_user.id
        if not self.is_admin(user_id):
            await update.callback_query.answer(
                "🚫 Access Denied! You are not authorized to use this bot.",
                show_alert=True
            )
            return False
        return True

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler with buttons"""
        if not await self.admin_only(update, context):
            return

        keyboard = [
            [
                InlineKeyboardButton("1 hour", callback_data="task_1hour"),
                InlineKeyboardButton("now send", callback_data="task2_nowsend")
            ],
            [
                InlineKeyboardButton("2 hour", callback_data="task3_2hour")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        twitter_status = "✅ ENABLED" if self.bot.twitter_poster.twitter_poster_enabled and self.bot.twitter_poster.twitter_client else "❌ DISABLED"
        
        await update.message.reply_text(
            "🤖 **Twitter Video Bot Started!**\n\n"
            "📤 **Send any Twitter/X link to download and forward videos.**\n\n"
            "📋 **Available Scheduling Modes:**\n"
            "• **1 hour** - Daily at 7 AM with 1-hour intervals\n"
            "• **now send** - Incremental scheduling (2h, 3h, 4h...)\n"
            "• **2 hour** - Fixed 2-hour intervals starting from 7 AM\n\n"
            f"🐦 **Twitter Auto-Poster:** {twitter_status}\n\n"
            "🎯 **Select a scheduling mode or send link directly:**",
            reply_markup=reply_markup
        )

    async def twitter_poster_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Twitter poster को enable/disable करें"""
        if not await self.admin_only(update, context):
            return

        if context.args and context.args[0].lower() in ['on', 'enable', 'start']:
            self.bot.twitter_poster.twitter_poster_enabled = True
            await update.message.reply_text("✅ Twitter poster enabled! Second channel posts will be auto-posted to Twitter.")
        elif context.args and context.args[0].lower() in ['off', 'disable', 'stop']:
            self.bot.twitter_poster.twitter_poster_enabled = False
            await update.message.reply_text("❌ Twitter poster disabled!")
        else:
            status = "enabled" if self.bot.twitter_poster.twitter_poster_enabled else "disabled"
            twitter_client_status = "available" if self.bot.twitter_poster.twitter_client else "not available"
            await update.message.reply_text(
                f"📊 **Twitter Poster Status:** **{status.upper()}**\n"
                f"🔧 **Twitter Client:** **{twitter_client_status}**\n\n"
                "Use `/twitter_poster on` to enable\n"
                "Use `/twitter_poster off` to disable"
            )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()

        if not await self.admin_only_callback(update, context):
            return

        try:
            if query.data == "task_1hour":
                await self.start_task_callback(query, context)
            elif query.data == "task2_nowsend":
                await self.start_task2_callback(query, context)
            elif query.data == "task3_2hour":
                await self.start_task3_callback(query, context)
        except Exception as e:
            logger.error(f"Error in button handler: {e}")
            await query.edit_message_text("❌ Error processing your request. Please try again.")

    async def start_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start scheduled posting mode"""
        if not await self.admin_only(update, context):
            return

        await self._start_task_common(update, context)

    async def start_task_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Start scheduled posting mode from callback"""
        await self._start_task_common(query, context, is_callback=True)

    async def start_task2(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start incremental scheduled posting mode"""
        if not await self.admin_only(update, context):
            return

        await self._start_task2_common(update, context)

    async def start_task2_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Start incremental scheduled posting mode from callback"""
        await self._start_task2_common(query, context, is_callback=True)

    async def start_task3(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start fixed 2-hour interval scheduling mode starting from 7 AM"""
        if not await self.admin_only(update, context):
            return

        await self._start_task3_common(update, context)

    async def start_task3_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Start fixed 2-hour interval scheduling mode from callback"""
        await self._start_task3_common(query, context, is_callback=True)

    async def _start_task_common(self, update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
        """Common function for starting task mode"""
        self.bot.scheduled_mode = True
        self.bot.incremental_schedule_mode = False
        self.bot.fixed_interval_mode = False
        self.bot.scheduled_counter = 0
        self.bot.scheduled_messages = []

        now = datetime.now(TIMEZONE)
        first_schedule_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
        if first_schedule_time < now:
            first_schedule_time += timedelta(days=1)

        response_text = (
            "📅 **1 Hour Mode Activated!**\n\n"
            f"⏰ First video: {first_schedule_time.strftime('%Y-%m-%d %H:%M')} IST\n"
            f"🕐 Each new video: +1 hour interval\n\n"
            "❌ Use /endtask to stop scheduled posting."
        )

        if is_callback:
            await update.edit_message_text(response_text)
        else:
            await update.message.reply_text(response_text)

    async def _start_task2_common(self, update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
        """Common function for starting task2 mode"""
        self.bot.incremental_schedule_mode = True
        self.bot.scheduled_mode = False
        self.bot.fixed_interval_mode = False
        self.bot.scheduled_counter = 0
        self.bot.scheduled_messages = []

        now = datetime.now(TIMEZONE)
        first_schedule_time = now + timedelta(hours=2)

        response_text = (
            "⏱️ **Now Send Mode Activated!**\n\n"
            f"⏰ First video: {first_schedule_time.strftime('%Y-%m-%d %H:%M')} IST\n"
            f"🕐 Next intervals: +2h, +3h, +4h...\n\n"
            "❌ Use /endtask to stop scheduled posting."
        )

        if is_callback:
            await update.edit_message_text(response_text)
        else:
            await update.message.reply_text(response_text)

    async def _start_task3_common(self, update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
        """Common function for starting task3 mode"""
        self.bot.fixed_interval_mode = True
        self.bot.scheduled_mode = False
        self.bot.incremental_schedule_mode = False
        self.bot.scheduled_counter = 0
        self.bot.scheduled_messages = []

        now = datetime.now(TIMEZONE)
        first_schedule_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
        if first_schedule_time < now:
            first_schedule_time += timedelta(days=1)

        second_schedule_time = first_schedule_time + timedelta(hours=2)
        third_schedule_time = first_schedule_time + timedelta(hours=4)

        response_text = (
            "🕑 **2 Hour Mode Activated!**\n\n"
            f"⏰ Schedule starts at: 7:00 AM IST\n"
            f"🕐 Fixed interval: Every 2 hours\n\n"
            f"📅 Example schedule:\n"
            f"• 1st post: {first_schedule_time.strftime('%H:%M')} IST\n"
            f"• 2nd post: {second_schedule_time.strftime('%H:%M')} IST\n"
            f"• 3rd post: {third_schedule_time.strftime('%H:%M')} IST\n\n"
            "❌ Use /endtask to stop scheduled posting."
        )

        if is_callback:
            await update.edit_message_text(response_text)
        else:
            await update.message.reply_text(response_text)

    async def end_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """End scheduled posting mode"""
        if not await self.admin_only(update, context):
            return

        self.bot.scheduled_mode = False
        self.bot.incremental_schedule_mode = False
        self.bot.fixed_interval_mode = False

        await update.message.reply_text(
            "🚫 **Scheduled Mode Deactivated!**\n\n"
            "✅ Videos will now be posted immediately.\n"
            f"📊 Total {self.bot.scheduled_counter} videos were scheduled.\n\n"
            "🎯 Use commands to start scheduling again:"
        )

        self.bot.scheduled_counter = 0
        self.bot.scheduled_messages = []

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
                await asyncio.sleep(2)

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
