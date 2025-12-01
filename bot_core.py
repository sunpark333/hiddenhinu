
import logging
import asyncio
import pytz
import os
import sys
import re
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from datetime import datetime, timedelta
from config import TELEGRAM_BOT_TOKEN, API_ID, API_HASH, TELEGRAM_SESSION_STRING, TWITTER_VID_BOT, YOUR_CHANNEL_ID, YOUR_SECOND_CHANNEL_ID, TIMEZONE, ADMIN_IDS, TWITTER_BEARER_TOKEN, TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
from ai_caption_enhancer import AICaptionEnhancer

logger = logging.getLogger(__name__)

class TwitterBotCore:
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
        self.ai_enhancer = AICaptionEnhancer()
        self.twitter_poster_enabled = True
        self.twitter_client = None

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
        """Process received video and send to both channels"""
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

    def is_admin(self, user_id):
        """Check if user is admin"""
        return user_id in ADMIN_IDS

    async def start_polling(self):
        """Start bot polling in a separate task"""
        try:
            if self._polling_started:
                logger.warning("Polling already started, skipping...")
                return
                
            logger.info("Starting Telegram Bot...")
            self.bot_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

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
