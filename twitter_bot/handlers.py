"""
Message handlers - Telegram bot command and message handlers
Updated with Quiz Generator integration
"""

import logging
import asyncio
from datetime import datetime
from aiohttp import web
from telethon import events
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

from config import TELEGRAM_BOT_TOKEN, TWITTER_VID_BOT, YOUR_CHANNEL_ID, YOUR_SECOND_CHANNEL_ID, ADMIN_IDS
from .utils import TextUtils

logger = logging.getLogger(__name__)


class MessageHandlers:
    def __init__(self, bot):
        self.bot = bot
        self.text_utils = TextUtils()
        self.quiz_generator = None  # Will be set by main.py

    async def health_check(self, request):
        """Health check endpoint for Koyeb"""
        return web.Response(text="Bot is running!")

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

    async def handle_twittervid_message(self, event):
        """Handle responses from twittervid_bot"""
        try:
            if self.bot.last_processed_message_id is not None and event.message.id <= self.bot.last_processed_message_id:
                return

            self.bot.last_processed_message_id = event.message.id

            if self.bot.waiting_for_video and self.bot.current_update:
                await asyncio.sleep(3)

                message_text = event.message.text or ""
                logger.info(f"Received message from twittervid_bot: {message_text[:100]}...")

                # Delete previous messages
                try:
                    async for old_msg in self.bot.userbot.iter_messages(TWITTER_VID_BOT, limit=5):
                        if old_msg.id < event.message.id:
                            await old_msg.delete()
                            await asyncio.sleep(1)
                except Exception as e:
                    logger.warning(f"Could not delete old messages: {str(e)}")

                if "Select Video Quality" in message_text and not self.bot.quality_selected:
                    logger.info("Quality selection detected")
                    try:
                        buttons = await event.message.get_buttons()
                        if buttons:
                            for row in buttons:
                                for button in row:
                                    if any(q in button.text for q in ['720', 'HD', 'High', '1080']):
                                        await button.click()
                                        quality = button.text
                                        logger.info(f"Selected quality: {quality}")
                                        if self.bot.current_update and self.bot.current_update.message:
                                            await self.bot.current_update.message.reply_text(
                                                f"✅ Video is being downloaded in {quality} quality..."
                                            )
                                        self.bot.quality_selected = True
                                        return

                            if buttons[0]:
                                await buttons[0][0].click()
                                quality = buttons[0][0].text
                                logger.info(f"Selected first available quality: {quality}")
                                if self.bot.current_update and self.bot.current_update.message:
                                    await self.bot.current_update.message.reply_text(
                                        f"✅ Video is being downloaded in {quality} quality..."
                                    )
                                self.bot.quality_selected = True
                                return

                    except Exception as e:
                        logger.error(f"Error in quality selection: {str(e)}")
                        self.bot.quality_selected = True

                has_media = bool(event.message.media)
                is_final_message = any(word in message_text for word in ['Download', 'Ready', 'Here', 'Quality'])

                if (has_media or is_final_message) and self.bot.quality_selected:
                    await self._process_received_video(event)

        except Exception as e:
            logger.error(f"Error in handle_twittervid_message: {str(e)}")

    async def handle_second_channel_message(self, event):
        """Handle messages from second channel for Twitter posting"""
        try:
            if not self.bot.twitter_poster_enabled or not self.bot.twitter_poster.twitter_client:
                return

            message = event.message
            logger.info(f"New message from second channel (ID: {message.id}) for Twitter posting")

            original_text = message.text or message.caption or ""

            media_path = None
            if message.media:
                media_path = await self.bot.userbot.download_media(
                    message,
                    file=f"temp_twitter_media_{message.id}"
                )

            success = await self.bot.twitter_poster.post_to_twitter(original_text, media_path)

            if success:
                logger.info("Successfully posted to Twitter from second channel")
            else:
                logger.warning("Failed to post to Twitter from second channel")

            if media_path:
                import os
                try:
                    if os.path.exists(media_path):
                        os.remove(media_path)
                except Exception as e:
                    logger.warning(f"Could not delete temp file: {str(e)}")

        except Exception as e:
            logger.error(f"Error handling second channel message for Twitter: {str(e)}")

    async def _process_received_video(self, event):
        """Process received video and send to both channels"""
        try:
            original_caption = self.text_utils.clean_text(event.message.text) if event.message.text else ""
            
            first_channel_caption = f"\n\n{original_caption}\n\n" if original_caption else ""
            second_channel_caption = await self._get_enhanced_caption(original_caption)

            async def send_to_channel(channel_id, caption_text):
                scheduled_time = None
                if self.bot.scheduled_mode or self.bot.incremental_schedule_mode or self.bot.fixed_interval_mode:
                    scheduled_time = self.bot.scheduler._calculate_schedule_time()

                if event.message.media:
                    return await self.bot.userbot.send_file(
                        channel_id,
                        file=event.message.media,
                        caption=caption_text,
                        schedule=scheduled_time
                    )
                else:
                    return await self.bot.userbot.send_message(
                        channel_id,
                        caption_text or "📹 Video Content",
                        schedule=scheduled_time
                    )

            message1 = await send_to_channel(YOUR_CHANNEL_ID, first_channel_caption)
            message2 = await send_to_channel(YOUR_SECOND_CHANNEL_ID, second_channel_caption)

            scheduled_time = None
            if self.bot.scheduled_mode or self.bot.incremental_schedule_mode or self.bot.fixed_interval_mode:
                scheduled_time = self.bot.scheduler._calculate_schedule_time()
                self.bot.scheduled_counter += 1
                self.bot.scheduled_messages.extend([message1.id, message2.id])

                if self.bot.current_update and self.bot.current_update.message:
                    await self.bot.current_update.message.reply_text(
                        f"✅ Video successfully scheduled for {scheduled_time.strftime('%Y-%m-%d %H:%M')} IST in both channels!\n"
                        f"📝 Second channel caption enhanced with AI."
                    )
            else:
                if self.bot.current_update and self.bot.current_update.message:
                    await self.bot.current_update.message.reply_text(
                        "✅ Video successfully sent to both channels!\n"
                        "📝 Second channel caption enhanced with AI."
                    )

            logger.info(f"Message sent to both channels: {YOUR_CHANNEL_ID} and {YOUR_SECOND_CHANNEL_ID}")
            self._reset_flags()

        except Exception as e:
            error_msg = f"❌ Error sending video to channels: {str(e)}"
            logger.error(error_msg)
            if self.bot.current_update and self.bot.current_update.message:
                await self.bot.current_update.message.reply_text(error_msg)
            self._reset_flags()

    async def _get_enhanced_caption(self, original_caption):
        """Get AI-enhanced caption for second channel"""
        try:
            if not original_caption or len(original_caption.strip()) < 10:
                return f"\n\n{original_caption}\n\n" if original_caption else ""

            logger.info("Enhancing caption for second channel using AI...")
            enhanced_caption = await self.bot.ai_enhancer.enhance_caption(original_caption)

            if enhanced_caption and enhanced_caption != original_caption:
                logger.info("Caption successfully enhanced with AI")
                return f"\n\n{enhanced_caption}\n\n"
            else:
                logger.info("Using original caption (AI enhancement failed or not available)")
                return f"\n\n{original_caption}\n\n"

        except Exception as e:
            logger.error(f"Error in AI caption enhancement: {str(e)}")
            return f"\n\n{original_caption}\n\n"

    def _reset_flags(self):
        """Reset processing flags"""
        self.bot.video_received = True
        self.bot.waiting_for_video = False
        self.bot.current_update = None
        self.bot.quality_selected = False

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
            ],
            [
                InlineKeyboardButton("🎯 Quiz", callback_data="quiz_show_topics")
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        twitter_status = "✅ ENABLED" if self.bot.twitter_poster_enabled and self.bot.twitter_poster.twitter_client else "❌ DISABLED"

        await update.message.reply_text(
            "🤖 **Twitter Video Bot Started!**\n\n"
            "📤 **Send any Twitter/X link to download and forward videos.**\n\n"
            "📋 **Available Scheduling Modes:**\n"
            "• **1 hour** - Daily at 7 AM with 1-hour intervals\n"
            "• **now send** - Incremental scheduling (2h, 3h, 4h...)\n"
            "• **2 hour** - Fixed 2-hour intervals starting from 7 AM\n\n"
            "🎯 **Quiz Generator** - AI-powered quizzes on Ramayan & Mahabharata\n\n"
            f"🐦 **Twitter Auto-Poster:** {twitter_status}\n\n"
            "🎯 **Select a scheduling mode, start a quiz, or send link directly:**",
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
                await self.bot.scheduler.start_task_callback(query, context)
            elif query.data == "task2_nowsend":
                await self.bot.scheduler.start_task2_callback(query, context)
            elif query.data == "task3_2hour":
                await self.bot.scheduler.start_task3_callback(query, context)
        except Exception as e:
            logger.error(f"Error in button handler: {e}")
            await query.edit_message_text("❌ Error processing your request. Please try again.")

    async def quiz_callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all quiz-related callback queries"""
        query = update.callback_query
        callback_data = query.data

        if not hasattr(self, 'quiz_generator') or not self.quiz_generator:
            await query.answer("Quiz generator not initialized")
            return

        try:
            # Topic selection
            if callback_data == "quiz_show_topics":
                await self.quiz_generator.quiz_command(update, context)
            
            elif callback_data.startswith("quiz_") and any(x in callback_data for x in ["ramayan", "mahabharata", "mythology", "vedas"]):
                await self.quiz_generator.quiz_button_handler(update, context)
            
            # Post options
            elif callback_data == "quiz_post_now":
                await self.quiz_generator.quiz_post_now_handler(update, context)
            
            elif callback_data == "quiz_schedule":
                await self.quiz_generator.quiz_schedule_handler(update, context)
            
            # Schedule delay
            elif callback_data.startswith("quiz_delay_"):
                delay_str = callback_data.replace("quiz_delay_", "")
                try:
                    delay_minutes = int(delay_str)
                    await self.quiz_generator.quiz_delay_handler(update, context, delay_minutes)
                except ValueError:
                    await query.answer("Invalid delay value")
            
            # Cancel
            elif callback_data == "quiz_cancel":
                await self.quiz_generator.quiz_cancel_handler(update, context)

        except Exception as e:
            logger.error(f"Error in quiz callback handler: {e}")
            await query.answer("Error processing your request", show_alert=True)

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

            text = self.text_utils.clean_text(text)

            self.bot.current_update = update
            self.bot.waiting_for_video = True
            self.bot.quality_selected = False
            self.bot.video_received = False

            await message.reply_text("⏳ Processing link and downloading video...")
            await self.bot.userbot.send_message(TWITTER_VID_BOT, text)

            logger.info(f"Link sent to twittervid_bot: {text}")

            start_time = datetime.now()
            while (datetime.now() - start_time).seconds < self.bot.quality_selection_timeout:
                if self.bot.quality_selected or self.bot.video_received:
                    break
                await asyncio.sleep(2)

            if not self.bot.quality_selected and not self.bot.video_received:
                await message.reply_text("⚠️ Timeout waiting for video processing. Please try again.")
                self._reset_flags()

        except Exception as e:
            error_msg = f"❌ Error processing link: {str(e)}"
            logger.error(error_msg)
            if update and update.message:
                await update.message.reply_text(error_msg)
            self._reset_flags()

    async def setup_handlers(self):
        """Setup event handlers for userbot"""
        @self.bot.userbot.on(events.NewMessage(from_users=TWITTER_VID_BOT))
        async def on_twittervid_message(event):
            await self.handle_twittervid_message(event)

        if self.bot.twitter_poster_enabled:
            @self.bot.userbot.on(events.NewMessage(chats=YOUR_SECOND_CHANNEL_ID))
            async def on_second_channel_message(event):
                await self.handle_second_channel_message(event)

            logger.info("Second channel handler added for Twitter posting")

    async def add_all_handlers(self, bot_app):
        """Add all command and message handlers to bot - UPDATED WITH QUIZ"""
        # Original handlers
        bot_app.add_handler(CommandHandler("start", self.start_command))
        bot_app.add_handler(CommandHandler("task", self.bot.scheduler.start_task))
        bot_app.add_handler(CommandHandler("task2", self.bot.scheduler.start_task2))
        bot_app.add_handler(CommandHandler("task3", self.bot.scheduler.start_task3))
        bot_app.add_handler(CommandHandler("endtask", self.bot.scheduler.end_task))
        bot_app.add_handler(CommandHandler("twitter_poster", self.bot.twitter_poster.twitter_poster_command))
        
        # ✨ QUIZ HANDLERS - NEW
        if hasattr(self, 'quiz_generator') and self.quiz_generator:
            bot_app.add_handler(CommandHandler("quiz", self.quiz_generator.quiz_command))
        
        # Message and callback handlers
        bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_link))
        
        # Callback query handlers with patterns
        bot_app.add_handler(CallbackQueryHandler(self.quiz_callback_handler, pattern="^quiz_"))
        bot_app.add_handler(CallbackQueryHandler(self.button_handler, pattern="^(task|timer)"))
