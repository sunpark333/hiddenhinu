import logging
import re
import asyncio
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telethon import events

from config import TWITTER_VID_BOT, YOUR_CHANNEL_ID, YOUR_SECOND_CHANNEL_ID, TIMEZONE, ADMIN_IDS
from bot.utils import is_admin, clean_text
from bot.ai_caption_enhancer import AICaptionEnhancer

logger = logging.getLogger(__name__)

def setup_handlers(bot_app: Application, twitter_bot):
    """Setup all bot handlers"""
    
    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler with buttons"""
        if not await is_admin(update, context, ADMIN_IDS):
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

        twitter_status = "✅ ENABLED" if twitter_bot.twitter_manager.twitter_poster_enabled and twitter_bot.twitter_manager.twitter_client else "❌ DISABLED"
        
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

    async def twitter_poster_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Twitter poster को enable/disable करें"""
        if not await is_admin(update, context, ADMIN_IDS):
            return

        if context.args and context.args[0].lower() in ['on', 'enable', 'start']:
            twitter_bot.twitter_manager.twitter_poster_enabled = True
            await update.message.reply_text("✅ Twitter poster enabled! Second channel posts will be auto-posted to Twitter.")
        elif context.args and context.args[0].lower() in ['off', 'disable', 'stop']:
            twitter_bot.twitter_manager.twitter_poster_enabled = False
            await update.message.reply_text("❌ Twitter poster disabled!")
        else:
            status = "enabled" if twitter_bot.twitter_manager.twitter_poster_enabled else "disabled"
            twitter_client_status = "available" if twitter_bot.twitter_manager.twitter_client else "not available"
            await update.message.reply_text(
                f"📊 **Twitter Poster Status:** **{status.upper()}**\n"
                f"🔧 **Twitter Client:** **{twitter_client_status}**\n\n"
                "Use `/twitter_poster on` to enable\n"
                "Use `/twitter_poster off` to disable"
            )

    async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()

        if not await is_admin(update, context, ADMIN_IDS):
            return

        try:
            if query.data == "task_1hour":
                await start_task_callback(query, context)
            elif query.data == "task2_nowsend":
                await start_task2_callback(query, context)
            elif query.data == "task3_2hour":
                await start_task3_callback(query, context)
        except Exception as e:
            logger.error(f"Error in button handler: {e}")
            await query.edit_message_text("❌ Error processing your request. Please try again.")

    async def start_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start scheduled posting mode"""
        if not await is_admin(update, context, ADMIN_IDS):
            return

        await _start_task_common(update, context)

    async def start_task_callback(query, context: ContextTypes.DEFAULT_TYPE):
        """Start scheduled posting mode from callback"""
        await _start_task_common(query, context, is_callback=True)

    async def start_task2(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start incremental scheduled posting mode"""
        if not await is_admin(update, context, ADMIN_IDS):
            return

        await _start_task2_common(update, context)

    async def start_task2_callback(query, context: ContextTypes.DEFAULT_TYPE):
        """Start incremental scheduled posting mode from callback"""
        await _start_task2_common(query, context, is_callback=True)

    async def start_task3(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start fixed 2-hour interval scheduling mode starting from 7 AM"""
        if not await is_admin(update, context, ADMIN_IDS):
            return

        await _start_task3_common(update, context)

    async def start_task3_callback(query, context: ContextTypes.DEFAULT_TYPE):
        """Start fixed 2-hour interval scheduling mode from callback"""
        await _start_task3_common(query, context, is_callback=True)

    async def _start_task_common(update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
        """Common function for starting task mode"""
        twitter_bot.scheduler.scheduled_mode = True
        twitter_bot.scheduler.incremental_schedule_mode = False
        twitter_bot.scheduler.fixed_interval_mode = False
        twitter_bot.scheduler.scheduled_counter = 0
        twitter_bot.scheduler.scheduled_messages = []

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

    async def _start_task2_common(update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
        """Common function for starting task2 mode"""
        twitter_bot.scheduler.incremental_schedule_mode = True
        twitter_bot.scheduler.scheduled_mode = False
        twitter_bot.scheduler.fixed_interval_mode = False
        twitter_bot.scheduler.scheduled_counter = 0
        twitter_bot.scheduler.scheduled_messages = []

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

    async def _start_task3_common(update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
        """Common function for starting task3 mode"""
        twitter_bot.scheduler.fixed_interval_mode = True
        twitter_bot.scheduler.scheduled_mode = False
        twitter_bot.scheduler.incremental_schedule_mode = False
        twitter_bot.scheduler.scheduled_counter = 0
        twitter_bot.scheduler.scheduled_messages = []

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

    async def end_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """End scheduled posting mode"""
        if not await is_admin(update, context, ADMIN_IDS):
            return

        twitter_bot.scheduler.scheduled_mode = False
        twitter_bot.scheduler.incremental_schedule_mode = False
        twitter_bot.scheduler.fixed_interval_mode = False

        await update.message.reply_text(
            "🚫 **Scheduled Mode Deactivated!**\n\n"
            "✅ Videos will now be posted immediately.\n"
            f"📊 Total {twitter_bot.scheduler.scheduled_counter} videos were scheduled.\n\n"
            "🎯 Use commands to start scheduling again:"
        )

        twitter_bot.scheduler.scheduled_counter = 0
        twitter_bot.scheduler.scheduled_messages = []

    async def process_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process Twitter links"""
        try:
            if not await is_admin(update, context, ADMIN_IDS):
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

            text = clean_text(text)

            twitter_bot.current_update = update
            twitter_bot.waiting_for_video = True
            twitter_bot.quality_selected = False
            twitter_bot.video_received = False

            await message.reply_text(
                "⏳ Processing link and downloading video..."
            )

            await twitter_bot.userbot.send_message(TWITTER_VID_BOT, text)
            logger.info(f"Link sent to twittervid_bot: {text}")

            start_time = datetime.now()
            while (datetime.now() - start_time).seconds < 60:
                if twitter_bot.quality_selected or twitter_bot.video_received:
                    break
                await asyncio.sleep(2)

            if not twitter_bot.quality_selected and not twitter_bot.video_received:
                await message.reply_text(
                    "⚠️ Timeout waiting for video processing. Please try again."
                )
                twitter_bot._reset_flags()

        except Exception as e:
            error_msg = f"❌ Error processing link: {str(e)}"
            logger.error(error_msg)
            if update and update.message:
                await update.message.reply_text(
                    error_msg
                )
            twitter_bot._reset_flags()

    # Setup event handlers for userbot
    @twitter_bot.userbot.on(events.NewMessage(from_users=TWITTER_VID_BOT))
    async def handle_twittervid_message(event):
        await twitter_bot._handle_twittervid_response(event)

    # Add handler for second channel (Twitter posting)
    if twitter_bot.twitter_manager.twitter_poster_enabled:
        @twitter_bot.userbot.on(events.NewMessage(chats=YOUR_SECOND_CHANNEL_ID))
        async def handle_second_channel_message(event):
            await twitter_bot.twitter_manager.handle_second_channel_message(event, twitter_bot.userbot)
        logger.info("Second channel handler added for Twitter posting")

    # Add handlers to bot application
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("task", start_task))
    bot_app.add_handler(CommandHandler("task2", start_task2))
    bot_app.add_handler(CommandHandler("task3", start_task3))
    bot_app.add_handler(CommandHandler("endtask", end_task))
    bot_app.add_handler(CommandHandler("twitter_poster", twitter_poster_command))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_link))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
