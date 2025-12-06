import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from config import TELEGRAM_BOT_TOKEN, ADMIN_IDS

logger = logging.getLogger(__name__)

class TelegramHandler:
    def __init__(self, bot_instance):
        self.bot = bot_instance
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
            self.bot.twitter_poster.enable_poster(True)
            await update.message.reply_text("✅ Twitter poster enabled! Second channel posts will be auto-posted to Twitter.")
        elif context.args and context.args[0].lower() in ['off', 'disable', 'stop']:
            self.bot.twitter_poster.enable_poster(False)
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
                await self.bot.scheduler.start_scheduled_mode()
                response_text = (
                    "📅 **1 Hour Mode Activated!**\n\n"
                    f"⏰ First video: 7:00 AM IST (next day if past 7 AM)\n"
                    f"🕐 Each new video: +1 hour interval\n\n"
                    "❌ Use /endtask to stop scheduled posting."
                )
                await query.edit_message_text(response_text)
                
            elif query.data == "task2_nowsend":
                await self.bot.scheduler.start_incremental_mode()
                response_text = (
                    "⏱️ **Now Send Mode Activated!**\n\n"
                    f"⏰ First video: +2 hours from now\n"
                    f"🕐 Next intervals: +3h, +4h, +5h...\n\n"
                    "❌ Use /endtask to stop scheduled posting."
                )
                await query.edit_message_text(response_text)
                
            elif query.data == "task3_2hour":
                await self.bot.scheduler.start_fixed_interval_mode()
                response_text = (
                    "🕑 **2 Hour Mode Activated!**\n\n"
                    f"⏰ Schedule starts at: 7:00 AM IST\n"
                    f"🕐 Fixed interval: Every 2 hours\n\n"
                    "❌ Use /endtask to stop scheduled posting."
                )
                await query.edit_message_text(response_text)
                
        except Exception as e:
            logger.error(f"Error in button handler: {e}")
            await query.edit_message_text("❌ Error processing your request. Please try again.")

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

            # Process link through userbot manager
            success = await self.bot.userbot_manager.process_twitter_link(update, text)
            
            if not success:
                await message.reply_text("❌ Error processing link. Please try again.")

        except Exception as e:
            error_msg = f"❌ Error processing link: {str(e)}"
            logger.error(error_msg)
            if update and update.message:
                await update.message.reply_text(error_msg)

    async def end_task_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """End scheduled posting mode"""
        if not await self.admin_only(update, context):
            return

        count = await self.bot.scheduler.end_scheduling()
        await update.message.reply_text(
            f"🚫 **Scheduled Mode Deactivated!**\n\n"
            f"✅ Videos will now be posted immediately.\n"
            f"📊 Total {count} videos were scheduled.\n\n"
            "🎯 Use buttons to start scheduling again:"
        )

    async def initialize(self):
        """Initialize Telegram bot"""
        try:
            logger.info("Starting Telegram Bot...")
            self.bot_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

            # Add handlers
            self.bot_app.add_handler(CommandHandler("start", self.start_command))
            self.bot_app.add_handler(CommandHandler("task", self.bot.scheduler.start_scheduled_mode_handler))
            self.bot_app.add_handler(CommandHandler("task2", self.bot.scheduler.start_incremental_mode_handler))
            self.bot_app.add_handler(CommandHandler("task3", self.bot.scheduler.start_fixed_interval_mode_handler))
            self.bot_app.add_handler(CommandHandler("endtask", self.end_task_command))
            self.bot_app.add_handler(CommandHandler("twitter_poster", self.twitter_poster_command))
            self.bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_link))
            self.bot_app.add_handler(CallbackQueryHandler(self.button_handler))

            # Stop any existing webhook first
            await self.bot_app.bot.delete_webhook(drop_pending_updates=True)
            await asyncio.sleep(2)
            
            await self.bot_app.initialize()
            await self.bot_app.start()
            await self.bot_app.updater.start_polling()
            
            self._polling_started = True
            logger.info("Bot started successfully! Waiting for messages...")
            
        except Exception as e:
            logger.error(f"Error initializing Telegram bot: {e}")
            raise

    async def shutdown(self):
        """Shutdown Telegram bot"""
        if self.bot_app:
            logger.info("Stopping bot application...")
            try:
                if self.bot_app.running:
                    await self.bot_app.updater.stop()
                    await self.bot_app.stop()
                    await self.bot_app.shutdown()
            except Exception as e:
                logger.error(f"Error stopping bot app: {e}")
            self.bot_app = None
            self._polling_started = False
            logger.info("Telegram bot shutdown complete")
