import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from config import ADMIN_IDS, TWITTER_VID_BOT

logger = logging.getLogger(__name__)

class TelegramHandlers:
    """Telegram बॉट के हैंडलर्स"""
    
    def __init__(self, bot_app, twitter_bot):
        self.bot_app = bot_app
        self.twitter_bot = twitter_bot
        self.setup_handlers()
    
    def setup_handlers(self):
        """सभी हैंडलर सेटअप करें"""
        # Command handlers
        self.bot_app.add_handler(CommandHandler("start", self.start_command))
        self.bot_app.add_handler(CommandHandler("task", self.start_task))
        self.bot_app.add_handler(CommandHandler("task2", self.start_task2))
        self.bot_app.add_handler(CommandHandler("task3", self.start_task3))
        self.bot_app.add_handler(CommandHandler("endtask", self.end_task))
        self.bot_app.add_handler(CommandHandler("twitter_poster", self.twitter_poster_command))
        
        # Message handler
        self.bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_link))
        
        # Callback handler
        self.bot_app.add_handler(CallbackQueryHandler(self.button_handler))
    
    def is_admin(self, user_id):
        """Check if user is admin"""
        return user_id in ADMIN_IDS

    async def admin_only(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check if user is admin"""
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
        """Admin check for callbacks"""
        user_id = update.callback_query.from_user.id
        if not self.is_admin(user_id):
            await update.callback_query.answer(
                "🚫 Access Denied! You are not authorized to use this bot.",
                show_alert=True
            )
            return False
        return True
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
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

        twitter_status = "✅ ENABLED" if self.twitter_bot.twitter_poster.twitter_poster_enabled and self.twitter_bot.twitter_poster.twitter_client else "❌ DISABLED"
        
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
        """Twitter poster enable/disable"""
        if not await self.admin_only(update, context):
            return

        if context.args and context.args[0].lower() in ['on', 'enable', 'start']:
            self.twitter_bot.twitter_poster.twitter_poster_enabled = True
            await update.message.reply_text("✅ Twitter poster enabled! Second channel posts will be auto-posted to Twitter.")
        elif context.args and context.args[0].lower() in ['off', 'disable', 'stop']:
            self.twitter_bot.twitter_poster.twitter_poster_enabled = False
            await update.message.reply_text("❌ Twitter poster disabled!")
        else:
            status = "enabled" if self.twitter_bot.twitter_poster.twitter_poster_enabled else "disabled"
            twitter_client_status = "available" if self.twitter_bot.twitter_poster.twitter_client else "not available"
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
        await self.twitter_bot.scheduler.start_task_mode()

    async def start_task_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Start scheduled posting mode from callback"""
        await self.twitter_bot.scheduler.start_task_mode(is_callback=True)

    async def start_task2(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start incremental scheduled posting mode"""
        if not await self.admin_only(update, context):
            return
        await self.twitter_bot.scheduler.start_task2_mode()

    async def start_task2_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Start incremental scheduled posting mode from callback"""
        await self.twitter_bot.scheduler.start_task2_mode(is_callback=True)

    async def start_task3(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start fixed 2-hour interval scheduling mode"""
        if not await self.admin_only(update, context):
            return
        await self.twitter_bot.scheduler.start_task3_mode()

    async def start_task3_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Start fixed 2-hour interval scheduling mode from callback"""
        await self.twitter_bot.scheduler.start_task3_mode(is_callback=True)

    async def end_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """End scheduled posting mode"""
        if not await self.admin_only(update, context):
            return
        await self.twitter_bot.scheduler.end_task_mode()

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

            # Process the link
            await self.twitter_bot.video_processor.process_twitter_link(update, text)
                    
        except Exception as e:
            error_msg = f"❌ Error processing link: {str(e)}"
            logger.error(error_msg)
            if update and update.message:
                await update.message.reply_text(error_msg)
