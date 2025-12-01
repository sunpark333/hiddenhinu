import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from config import TELEGRAM_BOT_TOKEN, ADMIN_IDS
from twitter_bot import TwitterBot

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, twitter_bot: TwitterBot):
        self.twitter_bot = twitter_bot
        self.bot_app = None
        self._polling_started = False

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
        
        await update.message.reply_text(
            "🤖 **Twitter Video Bot Started!**\n\n"
            "📤 **Send any Twitter/X link to download and forward videos.**\n\n"
            "📋 **Available Scheduling Modes:**\n"
            "• **1 hour** - Daily at 7 AM with 1-hour intervals\n"
            "• **now send** - Incremental scheduling (2h, 3h, 4h...)\n"
            "• **2 hour** - Fixed 2-hour intervals starting from 7 AM\n\n"
            "🎯 **Select a scheduling mode or send link directly:**",
            reply_markup=reply_markup
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

    async def start_task_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Start scheduled posting mode from callback"""
        self.twitter_bot.scheduled_mode = True
        self.twitter_bot.incremental_schedule_mode = False
        self.twitter_bot.fixed_interval_mode = False
        self.twitter_bot.scheduled_counter = 0
        self.twitter_bot.scheduled_messages = []

        from datetime import datetime, timedelta
        from config import TIMEZONE
        
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

        await query.edit_message_text(response_text)

    async def start_task2_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Start incremental scheduled posting mode from callback"""
        self.twitter_bot.incremental_schedule_mode = True
        self.twitter_bot.scheduled_mode = False
        self.twitter_bot.fixed_interval_mode = False
        self.twitter_bot.scheduled_counter = 0
        self.twitter_bot.scheduled_messages = []

        from datetime import datetime, timedelta
        from config import TIMEZONE
        
        now = datetime.now(TIMEZONE)
        first_schedule_time = now + timedelta(hours=2)

        response_text = (
            "⏱️ **Now Send Mode Activated!**\n\n"
            f"⏰ First video: {first_schedule_time.strftime('%Y-%m-%d %H:%M')} IST\n"
            f"🕐 Next intervals: +2h, +3h, +4h...\n\n"
            "❌ Use /endtask to stop scheduled posting."
        )

        await query.edit_message_text(response_text)

    async def start_task3_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Start fixed 2-hour interval scheduling mode from callback"""
        self.twitter_bot.fixed_interval_mode = True
        self.twitter_bot.scheduled_mode = False
        self.twitter_bot.incremental_schedule_mode = False
        self.twitter_bot.scheduled_counter = 0
        self.twitter_bot.scheduled_messages = []

        from datetime import datetime, timedelta
        from config import TIMEZONE
        
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

        await query.edit_message_text(response_text)

    async def process_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process Twitter links"""
        try:
            if not await self.admin_only(update, context):
                return

            if not update or not update.message or not update.message.text:
                await update.message.reply_text("⚠️ Please provide a valid Twitter link.")
                return

            message = update.message
            text = message.text.strip()

            if not any(domain in text for domain in ['twitter.com', 'x.com']):
                await message.reply_text("⚠️ Please provide a valid Twitter/X link.")
                return

            text = self.twitter_bot.clean_text(text)

            self.twitter_bot.current_update = update

            await message.reply_text("⏳ Processing link and downloading video...")

            success = await self.twitter_bot.process_link(text)

            if not success:
                await message.reply_text("⚠️ Timeout waiting for video processing. Please try again.")

        except Exception as e:
            error_msg = f"❌ Error processing link: {str(e)}"
            logger.error(error_msg)
            if update and update.message:
                await update.message.reply_text(error_msg)
            self.twitter_bot._reset_flags()

    async def end_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """End scheduled posting mode"""
        if not await self.admin_only(update, context):
            return

        self.twitter_bot.scheduled_mode = False
        self.twitter_bot.incremental_schedule_mode = False
        self.twitter_bot.fixed_interval_mode = False

        await update.message.reply_text(
            "🚫 **Scheduled Mode Deactivated!**\n\n"
            "✅ Videos will now be posted immediately.\n"
            f"📊 Total {self.twitter_bot.scheduled_counter} videos were scheduled.\n\n"
            "🎯 Use commands to start scheduling again:"
        )

        self.twitter_bot.scheduled_counter = 0
        self.twitter_bot.scheduled_messages = []

    async def start_polling(self):
        """Start bot polling"""
        try:
            if self._polling_started:
                logger.warning("Polling already started, skipping...")
                return
                
            logger.info("Starting Telegram Bot...")
            self.bot_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

            # Add handlers
            self.bot_app.add_handler(CommandHandler("start", self.start_command))
            self.bot_app.add_handler(CommandHandler("endtask", self.end_task))
            self.bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_link))
            self.bot_app.add_handler(CallbackQueryHandler(self.button_handler))

            logger.info("Bot started successfully! Waiting for messages...")
            
            # Stop any existing webhook first
            await self.bot_app.bot.delete_webhook(drop_pending_updates=True)
            await asyncio.sleep(2)
            
            await self.bot_app.initialize()
            await self.bot_app.start()
            await self.bot_app.updater.start_polling()
            
            self._polling_started = True
            
            # Keep the polling running
            while self._polling_started:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in polling: {e}")
            self._polling_started = False
            raise

    async def shutdown(self):
        """Shutdown telegram bot"""
        self._polling_started = False
        if self.bot_app:
            logger.info("Stopping bot application...")
            try:
                await self.bot_app.updater.stop()
                await self.bot_app.stop()
                await self.bot_app.shutdown()
            except Exception as e:
                logger.error(f"Error stopping bot app: {e}")
