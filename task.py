import logging
import asyncio
import pytz
import os
import sys
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from datetime import datetime, timedelta
import re
from config import TELEGRAM_BOT_TOKEN, API_ID, API_HASH, TELEGRAM_SESSION_STRING, TWITTER_VID_BOT, YOUR_CHANNEL_ID, YOUR_SECOND_CHANNEL_ID, TIMEZONE, ADMIN_IDS
from ai_caption_enhancer import AICaptionEnhancer  # Import the AI enhancer
from twitter_poster import start_twitter_poster, stop_twitter_poster  # Import Twitter poster

logger = logging.getLogger(__name__)

class TwitterBot:
    def __init__(self):
        self.userbot = None
        self.bot_app = None
        self.loop = None
        self.waiting_for_video = False
        self.current_update = None
        self.quality_selected = False
        self.video_received = False
        self.scheduled_mode = False
        self.scheduled_counter = 0
        self.scheduled_messages = []
        self.last_processed_message_id = None
        self.incremental_schedule_mode = False
        self.fixed_interval_mode = False
        self.quality_selection_timeout = 60
        self._shutdown_flag = False
        self.http_app = None
        self.runner = None
        self.site = None
        self.polling_task = None
        self._polling_started = False
        self.ai_enhancer = AICaptionEnhancer()  # Initialize AI enhancer
        self.twitter_poster_enabled = True  # Twitter poster feature

    def is_admin(self, user_id):
        """Check if user is admin"""
        return user_id in ADMIN_IDS

    async def admin_only(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check if user is admin and send access denied message if not"""
        try:
            # Handle both Message and CallbackQuery updates
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

    async def health_check(self, request):
        """Health check endpoint for Koyeb"""
        return web.Response(text="Bot is running!")

    async def start_http_server(self):
        """Start HTTP server for health checks"""
        self.http_app = web.Application()
        self.http_app.router.add_get('/', self.health_check)
        self.http_app.router.add_get('/health', self.health_check)
        
        runner = web.AppRunner(self.http_app)
        await runner.setup()
        
        port = int(os.environ.get('PORT', 8000))
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        
        logger.info(f"HTTP server started on port {port}")
        return runner, site

    async def initialize_userbot(self):
        """Initialize Telegram userbot with string session"""
        try:
            logger.info("Starting UserBot initialization...")
            
            session = StringSession(TELEGRAM_SESSION_STRING)
            self.userbot = TelegramClient(
                session=session,
                api_id=int(API_ID),
                api_hash=API_HASH
            )

            await self.userbot.start()
            logger.info("UserBot successfully started")

            @self.userbot.on(events.NewMessage(from_users=TWITTER_VID_BOT))
            async def handle_twittervid_message(event):
                await self._handle_twittervid_response(event)

            me = await self.userbot.get_me()
            logger.info(f"UserBot started as: {me.username} (ID: {me.id})")

            try:
                channel = await self.userbot.get_entity(YOUR_CHANNEL_ID)
                logger.info(f"Verified access to channel: {channel.title}")
                
                second_channel = await self.userbot.get_entity(YOUR_SECOND_CHANNEL_ID)
                logger.info(f"Verified access to second channel: {second_channel.title}")
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
                await asyncio.sleep(3)
                
                message_text = event.message.text or ""
                logger.info(f"Received message from twittervid_bot: {message_text[:100]}...")

                # Delete previous messages from twittervid_bot to keep chat clean
                try:
                    async for old_msg in self.userbot.iter_messages(TWITTER_VID_BOT, limit=5):
                        if old_msg.id < event.message.id:
                            await old_msg.delete()
                            await asyncio.sleep(1)
                except Exception as e:
                    logger.warning(f"Could not delete old messages: {str(e)}")

                if "Select Video Quality" in message_text and not self.quality_selected:
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
                                        if self.current_update and self.current_update.message:
                                            await self.current_update.message.reply_text(
                                                f"✅ Video is being downloaded in {quality} quality..."
                                            )
                                        self.quality_selected = True
                                        return

                            if buttons[0]:
                                await buttons[0][0].click()
                                quality = buttons[0][0].text
                                logger.info(f"Selected first available quality: {quality}")
                                if self.current_update and self.current_update.message:
                                    await self.current_update.message.reply_text(
                                        f"✅ Video is being downloaded in {quality} quality..."
                                    )
                                self.quality_selected = True
                                return

                    except Exception as e:
                        logger.error(f"Error in quality selection: {str(e)}")
                        self.quality_selected = True

                has_media = bool(event.message.media)
                is_final_message = any(word in message_text for word in ['Download', 'Ready', 'Here', 'Quality'])

                if (has_media or is_final_message) and self.quality_selected:
                    await self._process_received_video(event)

        except Exception as e:
            logger.error(f"Error in handle_twittervid_message: {str(e)}")

    async def _process_received_video(self, event):
        """Process received video and send to both channels with AI-enhanced caption for second channel"""
        try:
            original_caption = self.clean_text(event.message.text) if event.message.text else ""

            # Prepare captions for both channels
            first_channel_caption = f"\n\n{original_caption}\n\n" if original_caption else ""
            
            # Enhance caption for second channel using AI
            second_channel_caption = await self._get_enhanced_caption(original_caption)

            # Function to send to a channel
            async def send_to_channel(channel_id, caption_text):
                if event.message.media:
                    return await self.userbot.send_file(
                        channel_id,
                        file=event.message.media,
                        caption=caption_text,
                        schedule=scheduled_time if self.scheduled_mode or self.incremental_schedule_mode or self.fixed_interval_mode else None
                    )
                else:
                    return await self.userbot.send_message(
                        channel_id,
                        caption_text or "📹 Video Content",
                        schedule=scheduled_time if self.scheduled_mode or self.incremental_schedule_mode or self.fixed_interval_mode else None
                    )

            # Calculate schedule time if in scheduled mode
            scheduled_time = None
            if self.scheduled_mode or self.incremental_schedule_mode or self.fixed_interval_mode:
                scheduled_time = self._calculate_schedule_time()

            # Send to first channel (original caption)
            message1 = await send_to_channel(YOUR_CHANNEL_ID, first_channel_caption)
            
            # Send to second channel (AI-enhanced caption)
            message2 = await send_to_channel(YOUR_SECOND_CHANNEL_ID, second_channel_caption)

            # Update counters and send success message
            if self.scheduled_mode or self.incremental_schedule_mode or self.fixed_interval_mode:
                self.scheduled_counter += 1
                self.scheduled_messages.extend([message1.id, message2.id])

                if self.current_update and self.current_update.message:
                    await self.current_update.message.reply_text(
                        f"✅ Video successfully scheduled for {scheduled_time.strftime('%Y-%m-%d %H:%M')} IST in both channels!\n"
                        f"📝 Second channel caption enhanced with AI."
                    )
            else:
                if self.current_update and self.current_update.message:
                    await self.current_update.message.reply_text(
                        "✅ Video successfully sent to both channels!\n"
                        "📝 Second channel caption enhanced with AI."
                    )

            logger.info(f"Message sent to both channels: {YOUR_CHANNEL_ID} and {YOUR_SECOND_CHANNEL_ID}")
            self._reset_flags()

        except Exception as e:
            error_msg = f"❌ Error sending video to channels: {str(e)}"
            logger.error(error_msg)
            if self.current_update and self.current_update.message:
                await self.current_update.message.reply_text(
                    error_msg
                )
            self._reset_flags()

    async def _get_enhanced_caption(self, original_caption):
        """
        Get AI-enhanced caption for second channel
        """
        try:
            if not original_caption or len(original_caption.strip()) < 10:
                return f"\n\n{original_caption}\n\n" if original_caption else ""
            
            logger.info("Enhancing caption for second channel using AI...")
            enhanced_caption = await self.ai_enhancer.enhance_caption(original_caption)
            
            if enhanced_caption and enhanced_caption != original_caption:
                logger.info("Caption successfully enhanced with AI")
                return f"\n\n{enhanced_caption}\n\n"
            else:
                logger.info("Using original caption (AI enhancement failed or not available)")
                return f"\n\n{original_caption}\n\n"
                
        except Exception as e:
            logger.error(f"Error in AI caption enhancement: {str(e)}")
            return f"\n\n{original_caption}\n\n"

    def _calculate_schedule_time(self):
        """Calculate schedule time based on mode"""
        now = datetime.now(TIMEZONE)

        if self.scheduled_mode:
            scheduled_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
            if scheduled_time < now:
                scheduled_time += timedelta(days=1)
            scheduled_time += timedelta(hours=self.scheduled_counter)
        elif self.incremental_schedule_mode:
            scheduled_time = now + timedelta(hours=self.scheduled_counter + 2)
        elif self.fixed_interval_mode:
            scheduled_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
            if scheduled_time < now:
                scheduled_time += timedelta(days=1)
            scheduled_time += timedelta(hours=2 * self.scheduled_counter)
        else:
            scheduled_time = now

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
        hidden_link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        cleaned_text = re.sub(hidden_link_pattern, r'\1', cleaned_text)
        cleaned_text = cleaned_text.replace('📲 @twittervid_bot', '').strip()

        return cleaned_text

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
            "🐦 **Twitter Auto-Poster:** " + ("✅ ENABLED" if self.twitter_poster_enabled else "❌ DISABLED") + "\n\n"
            "🎯 **Select a scheduling mode or send link directly:**",
            reply_markup=reply_markup
        )

    async def twitter_poster_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Twitter पोस्टर को enable/disable करें"""
        if not await self.admin_only(update, context):
            return

        if context.args and context.args[0].lower() in ['on', 'enable', 'start']:
            self.twitter_poster_enabled = True
            await update.message.reply_text("✅ Twitter poster enabled! Second channel posts will be auto-posted to Twitter.")
        elif context.args and context.args[0].lower() in ['off', 'disable', 'stop']:
            self.twitter_poster_enabled = False
            await update.message.reply_text("❌ Twitter poster disabled!")
        else:
            status = "enabled" if self.twitter_poster_enabled else "disabled"
            await update.message.reply_text(
                f"📊 **Twitter Poster Status:** **{status.upper()}**\n\n"
                "Use `/twitter_poster on` to enable\n"
                "Use `/twitter_poster off` to disable"
            )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()

        # Admin check for callback
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
        self.scheduled_mode = True
        self.incremental_schedule_mode = False
        self.fixed_interval_mode = False
        self.scheduled_counter = 0
        self.scheduled_messages = []

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
        self.incremental_schedule_mode = True
        self.scheduled_mode = False
        self.fixed_interval_mode = False
        self.scheduled_counter = 0
        self.scheduled_messages = []

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
        self.fixed_interval_mode = True
        self.scheduled_mode = False
        self.incremental_schedule_mode = False
        self.scheduled_counter = 0
        self.scheduled_messages = []

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

        self.scheduled_mode = False
        self.incremental_schedule_mode = False
        self.fixed_interval_mode = False

        await update.message.reply_text(
            "🚫 **Scheduled Mode Deactivated!**\n\n"
            "✅ Videos will now be posted immediately.\n"
            f"📊 Total {self.scheduled_counter} videos were scheduled.\n\n"
            "🎯 Use commands to start scheduling again:"
        )

        self.scheduled_counter = 0
        self.scheduled_messages = []

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

            text = self.clean_text(text)

            self.current_update = update
            self.waiting_for_video = True
            self.quality_selected = False
            self.video_received = False

            await message.reply_text(
                "⏳ Processing link and downloading video..."
            )

            await self.userbot.send_message(TWITTER_VID_BOT, text)
            logger.info(f"Link sent to twittervid_bot: {text}")

            start_time = datetime.now()
            while (datetime.now() - start_time).seconds < self.quality_selection_timeout:
                if self.quality_selected or self.video_received:
                    break
                await asyncio.sleep(2)

            if not self.quality_selected and not self.video_received:
                await message.reply_text(
                    "⚠️ Timeout waiting for video processing. Please try again."
                )
                self._reset_flags()

        except Exception as e:
            error_msg = f"❌ Error processing link: {str(e)}"
            logger.error(error_msg)
            if update and update.message:
                await update.message.reply_text(
                    error_msg
                )
            self._reset_flags()

    async def start_polling(self):
        """Start bot polling in a separate task"""
        try:
            if self._polling_started:
                logger.warning("Polling already started, skipping...")
                return
                
            logger.info("Starting Telegram Bot...")
            self.bot_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

            # Add handlers
            self.bot_app.add_handler(CommandHandler("start", self.start_command))
            self.bot_app.add_handler(CommandHandler("task", self.start_task))
            self.bot_app.add_handler(CommandHandler("task2", self.start_task2))
            self.bot_app.add_handler(CommandHandler("task3", self.start_task3))
            self.bot_app.add_handler(CommandHandler("endtask", self.end_task))
            self.bot_app.add_handler(CommandHandler("twitter_poster", self.twitter_poster_command))
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
            while not self._shutdown_flag:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in polling: {e}")
            self._polling_started = False
            raise
        finally:
            if self.bot_app:
                await self.bot_app.updater.stop()
                await self.bot_app.stop()
                await self.bot_app.shutdown()
                self._polling_started = False

    async def shutdown(self):
        """Shutdown all services properly"""
        logger.info("Shutting down services...")
        self._shutdown_flag = True
        
        try:
            if self.bot_app and self.bot_app.running:
                logger.info("Stopping bot application...")
                await self.bot_app.updater.stop()
                await self.bot_app.stop()
                await self.bot_app.shutdown()
                
            if self.userbot and self.userbot.is_connected():
                logger.info("Disconnecting userbot...")
                await self.userbot.disconnect()
                
            if self.runner:
                logger.info("Stopping HTTP server...")
                await self.runner.cleanup()
                
            # Twitter पोस्टर बंद करें
            if self.twitter_poster_enabled:
                logger.info("Stopping Twitter poster...")
                await stop_twitter_poster()
                
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        
        logger.info("All services safely shut down")

    async def run_async(self):
        """Async main function"""
        try:
            logger.info("Starting HTTP server for health checks...")
            self.runner, self.site = await self.start_http_server()
            
            logger.info("Initializing UserBot...")
            await self.initialize_userbot()
            
            # Twitter पोस्टर शुरू करें (अगर enable है)
            if self.twitter_poster_enabled:
                logger.info("Starting Twitter poster...")
                asyncio.create_task(start_twitter_poster())
            
            await self.start_polling()
            
        except Exception as e:
            logger.error(f"Error in run_async: {e}")
            raise

    def run(self):
        """Main function to run the bot"""
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries and not self._shutdown_flag:
            try:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                
                logger.info(f"Starting bot... (Attempt {retry_count + 1})")
                self.loop.run_until_complete(self.run_async())
                
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, shutting down...")
                break
                
            except Exception as e:
                retry_count += 1
                logger.error(f"Critical error (attempt {retry_count}/{max_retries}): {str(e)}")
                
                if retry_count < max_retries:
                    logger.info(f"Retrying in 10 seconds...")
                    try:
                        if self.loop and not self.loop.is_closed():
                            self.loop.run_until_complete(self.shutdown())
                    except Exception as shutdown_error:
                        logger.error(f"Error during shutdown: {shutdown_error}")
                    import time
                    time.sleep(10)
                else:
                    logger.error("Maximum retries reached. Exiting...")
                    break
            finally:
                if self.loop and not self.loop.is_closed():
                    try:
                        self.loop.run_until_complete(self.shutdown())
                    except Exception as e:
                        logger.error(f"Error in final shutdown: {e}")
                    self.loop.close()

if __name__ == "__main__":
    bot = TwitterBot()
    bot.run()
