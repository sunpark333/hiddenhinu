# file name: task(2).py
# file content begin
import logging
import asyncio
import pytz
import os
import sys
import re
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from datetime import datetime, timedelta
from tweepy import Client as TwitterClient, OAuth1UserHandler, API
from tweepy.errors import TweepyException
from config import TELEGRAM_BOT_TOKEN, API_ID, API_HASH, TELEGRAM_SESSION_STRING, TWITTER_VID_BOT, YOUR_CHANNEL_ID, YOUR_SECOND_CHANNEL_ID, TIMEZONE, ADMIN_IDS, TWITTER_BEARER_TOKEN, TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
from ai_caption_enhancer import AICaptionEnhancer
from video_watermark import VideoWatermark, check_ffmpeg_available

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
        self.ai_enhancer = AICaptionEnhancer()
        
        # Twitter posting feature
        self.twitter_poster_enabled = True
        self.twitter_client = None
        
        # Video watermark feature
        self.watermark_enabled = True
        self.watermark_position = "bottom-right"
        self.watermark_opacity = 0.7
        self.watermark_processor = None
        self.ffmpeg_available = check_ffmpeg_available()
        
        self._initialize_watermark_processor()

    def _initialize_watermark_processor(self):
        """Initialize video watermark processor"""
        try:
            if self.watermark_enabled:
                self.watermark_processor = VideoWatermark(
                    logo_path="channel_logo.png",
                    position=self.watermark_position,
                    opacity=self.watermark_opacity
                )
                
                if not self.ffmpeg_available:
                    logger.warning("FFmpeg not available! Video watermarking may not work properly.")
                    logger.info("Install FFmpeg with: sudo apt-get install ffmpeg")
                else:
                    logger.info("Video watermark processor initialized successfully")
            else:
                logger.info("Video watermarking is disabled")
        except Exception as e:
            logger.error(f"Failed to initialize watermark processor: {str(e)}")
            self.watermark_enabled = False

    async def _add_watermark_to_media(self, media_path):
        """
        Add watermark to media file (video or image)
        
        Args:
            media_path: Path to media file
            
        Returns:
            Path to watermarked media file
        """
        if not self.watermark_enabled or not self.watermark_processor:
            return media_path
        
        if not os.path.exists(media_path):
            logger.error(f"Media file not found: {media_path}")
            return media_path
        
        try:
            # Check file extension
            file_ext = os.path.splitext(media_path)[1].lower()
            
            if file_ext in ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm']:
                # Video file
                if self.ffmpeg_available:
                    logger.info(f"Adding watermark to video: {media_path}")
                    watermarked_path = self.watermark_processor.add_watermark_to_video(media_path)
                    return watermarked_path
                else:
                    logger.warning("FFmpeg not available, skipping video watermark")
                    return media_path
                    
            elif file_ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif']:
                # Image file
                logger.info(f"Adding watermark to image: {media_path}")
                watermarked_path = self.watermark_processor.add_watermark_to_image(media_path)
                return watermarked_path
                
            else:
                logger.warning(f"Unsupported file format for watermarking: {file_ext}")
                return media_path
                
        except Exception as e:
            logger.error(f"Error adding watermark: {str(e)}")
            return media_path

    async def initialize_twitter_client(self):
        """Initialize Twitter client"""
        try:
            if all([TWITTER_BEARER_TOKEN, TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET, 
                   TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
                self.twitter_client = TwitterClient(
                    bearer_token=TWITTER_BEARER_TOKEN,
                    consumer_key=TWITTER_CONSUMER_KEY,
                    consumer_secret=TWITTER_CONSUMER_SECRET,
                    access_token=TWITTER_ACCESS_TOKEN,
                    access_token_secret=TWITTER_ACCESS_SECRET
                )
                logger.info("Twitter client initialized successfully")
                return True
            else:
                logger.warning("Twitter credentials not complete, Twitter posting disabled")
                return False
        except Exception as e:
            logger.error(f"Failed to initialize Twitter client: {str(e)}")
            return False

    def process_text_for_twitter(self, text):
        """Process text for Twitter posting"""
        if not text:
            return ""
            
        processed_text = text
        
        # Remove URLs
        processed_text = re.sub(r'http\S+|www\S+|https\S+', '', processed_text, flags=re.MULTILINE)
        
        # Remove hashtags and mentions if needed
        processed_text = re.sub(r'#\w+', '', processed_text)
        processed_text = re.sub(r'@\w+', '', processed_text)
        
        # Trim extra spaces
        processed_text = re.sub(r'\s+', ' ', processed_text).strip()
        
        # Add prefix
        # processed_text = f" {processed_text}"
        
        return processed_text

    async def post_to_twitter(self, text, media_path=None):
        """Post content to Twitter"""
        try:
            if not self.twitter_client or not self.twitter_poster_enabled:
                return False

            processed_text = self.process_text_for_twitter(text)
            
            # Check length (280 characters for Twitter)
            if len(processed_text) > 280:
                logger.warning(f"Message too long for Twitter ({len(processed_text)} chars), trimming")
                processed_text = processed_text[:277] + "..."
            
            media_ids = []
            if media_path and os.path.exists(media_path):
                try:
                    # Add watermark before uploading to Twitter
                    if self.watermark_enabled:
                        logger.info("Adding watermark for Twitter post")
                        media_path = await self._add_watermark_to_media(media_path)
                    
                    # Upload media using v1.1 API
                    auth = OAuth1UserHandler(
                        TWITTER_CONSUMER_KEY,
                        TWITTER_CONSUMER_SECRET,
                        TWITTER_ACCESS_TOKEN,
                        TWITTER_ACCESS_SECRET
                    )
                    legacy_api = API(auth)
                    
                    # Check file size
                    file_size = os.path.getsize(media_path) / (1024 * 1024)
                    if file_size > 50:
                        logger.warning(f"Media file too large ({file_size:.2f}MB)")
                        return False
                    
                    media = legacy_api.media_upload(media_path)
                    media_ids = [media.media_id]
                    logger.info(f"Media uploaded to Twitter, ID: {media.media_id}")
                except Exception as e:
                    logger.error(f"Error uploading media to Twitter: {str(e)}")
                    return False

            # Post to Twitter
            if media_ids:
                response = self.twitter_client.create_tweet(
                    text=processed_text,
                    media_ids=media_ids
                )
            else:
                response = self.twitter_client.create_tweet(text=processed_text)
            
            logger.info(f"Tweet posted successfully! ID: {response.data['id']}")
            return True
            
        except TweepyException as e:
            logger.error(f"Twitter API error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error posting to Twitter: {str(e)}")
            return False

    async def handle_second_channel_message(self, event):
        """Handle messages from second channel for Twitter posting"""
        try:
            if not self.twitter_poster_enabled or not self.twitter_client:
                return

            message = event.message
            logger.info(f"New message from second channel (ID: {message.id}) for Twitter posting")
            
            # Get message text
            original_text = message.text or message.caption or ""
            
            # Download media if present
            media_path = None
            if message.media:
                media_path = await self.userbot.download_media(
                    message,
                    file=f"temp_twitter_media_{message.id}"
                )
            
            # Post to Twitter
            success = await self.post_to_twitter(original_text, media_path)
            
            if success:
                logger.info("Successfully posted to Twitter from second channel")
            else:
                logger.warning("Failed to post to Twitter from second channel")
                
            # Clean up temporary file
            if media_path and os.path.exists(media_path):
                try:
                    os.remove(media_path)
                except Exception as e:
                    logger.warning(f"Could not delete temp file: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error handling second channel message for Twitter: {str(e)}")

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

    async def health_check(self, request):
        """Health check endpoint for Koyeb"""
        watermark_status = "✅ ENABLED" if self.watermark_enabled and self.ffmpeg_available else "❌ DISABLED"
        return web.Response(
            text=f"Bot is running!\n"
                 f"Watermark Status: {watermark_status}\n"
                 f"FFmpeg Available: {'✅ YES' if self.ffmpeg_available else '❌ NO'}"
        )

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

            # Add handler for twittervid_bot responses
            @self.userbot.on(events.NewMessage(from_users=TWITTER_VID_BOT))
            async def handle_twittervid_message(event):
                await self._handle_twittervid_response(event)

            # Add handler for second channel (Twitter posting)
            if self.twitter_poster_enabled:
                @self.userbot.on(events.NewMessage(chats=YOUR_SECOND_CHANNEL_ID))
                async def handle_second_channel_message(event):
                    await self.handle_second_channel_message(event)
                logger.info("Second channel handler added for Twitter posting")

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
        """Process received video and send to both channels with AI-enhanced caption and watermark for second channel"""
        try:
            original_caption = self.clean_text(event.message.text) if event.message.text else ""

            # Prepare captions for both channels
            first_channel_caption = f"\n\n{original_caption}\n\n" if original_caption else ""
            
            # Enhance caption for second channel using AI
            second_channel_caption = await self._get_enhanced_caption(original_caption)

            # Function to send to a channel
            async def send_to_channel(channel_id, caption_text, add_watermark=False):
                if event.message.media:
                    # Download media first
                    temp_media_path = await self.userbot.download_media(
                        event.message,
                        file=f"temp_media_{event.message.id}"
                    )
                    
                    # Add watermark if needed
                    final_media_path = temp_media_path
                    if add_watermark and self.watermark_enabled:
                        logger.info(f"Adding watermark for channel: {channel_id}")
                        final_media_path = await self._add_watermark_to_media(temp_media_path)
                    
                    # Send to channel
                    sent_message = await self.userbot.send_file(
                        channel_id,
                        file=final_media_path,
                        caption=caption_text,
                        schedule=scheduled_time if self.scheduled_mode or self.incremental_schedule_mode or self.fixed_interval_mode else None
                    )
                    
                    # Clean up temp files
                    for temp_path in [temp_media_path, final_media_path]:
                        if temp_path and os.path.exists(temp_path) and temp_path != event.message.media:
                            try:
                                os.remove(temp_path)
                            except Exception as e:
                                logger.warning(f"Could not delete temp file {temp_path}: {str(e)}")
                    
                    return sent_message
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

            # Send to first channel (original caption, no watermark)
            message1 = await send_to_channel(YOUR_CHANNEL_ID, first_channel_caption, add_watermark=False)
            
            # Send to second channel (AI-enhanced caption, with watermark)
            message2 = await send_to_channel(YOUR_SECOND_CHANNEL_ID, second_channel_caption, add_watermark=True)

            # Update counters and send success message
            watermark_status = " with channel logo" if self.watermark_enabled else ""
            if self.scheduled_mode or self.incremental_schedule_mode or self.fixed_interval_mode:
                self.scheduled_counter += 1
                self.scheduled_messages.extend([message1.id, message2.id])

                if self.current_update and self.current_update.message:
                    await self.current_update.message.reply_text(
                        f"✅ Video successfully scheduled for {scheduled_time.strftime('%Y-%m-%d %H:%M')} IST in both channels!\n"
                        f"📝 Second channel caption enhanced with AI.\n"
                        f"🖼️ Watermark added to second channel video{watermark_status}."
                    )
            else:
                if self.current_update and self.current_update.message:
                    await self.current_update.message.reply_text(
                        f"✅ Video successfully sent to both channels!\n"
                        f"📝 Second channel caption enhanced with AI.\n"
                        f"🖼️ Watermark added to second channel video{watermark_status}."
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

        twitter_status = "✅ ENABLED" if self.twitter_poster_enabled and self.twitter_client else "❌ DISABLED"
        watermark_status = "✅ ENABLED" if self.watermark_enabled else "❌ DISABLED"
        ffmpeg_status = "✅ AVAILABLE" if self.ffmpeg_available else "❌ NOT AVAILABLE"
        
        await update.message.reply_text(
            "🤖 **Twitter Video Bot Started!**\n\n"
            "📤 **Send any Twitter/X link to download and forward videos.**\n\n"
            "📋 **Available Scheduling Modes:**\n"
            "• **1 hour** - Daily at 7 AM with 1-hour intervals\n"
            "• **now send** - Incremental scheduling (2h, 3h, 4h...)\n"
            "• **2 hour** - Fixed 2-hour intervals starting from 7 AM\n\n"
            f"🐦 **Twitter Auto-Poster:** {twitter_status}\n"
            f"🖼️ **Video Watermark:** {watermark_status}\n"
            f"🔧 **FFmpeg Status:** {ffmpeg_status}\n\n"
            "🎯 **Select a scheduling mode or send link directly:**",
            reply_markup=reply_markup
        )

    async def watermark_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Watermark settings command"""
        if not await self.admin_only(update, context):
            return

        if context.args:
            action = context.args[0].lower()
            
            if action == 'on':
                self.watermark_enabled = True
                await update.message.reply_text("✅ Watermark enabled! Videos in second channel will have channel logo.")
            elif action == 'off':
                self.watermark_enabled = False
                await update.message.reply_text("❌ Watermark disabled!")
            elif action == 'position':
                if len(context.args) > 1:
                    position = context.args[1].lower()
                    valid_positions = ['bottom-right', 'bottom-left', 'top-right', 'top-left']
                    
                    if position in valid_positions:
                        self.watermark_position = position
                        if self.watermark_processor:
                            self.watermark_processor.position = position
                        await update.message.reply_text(f"✅ Watermark position set to: {position}")
                    else:
                        await update.message.reply_text(
                            "⚠️ Invalid position. Use one of:\n"
                            "• bottom-right\n• bottom-left\n• top-right\n• top-left"
                        )
                else:
                    await update.message.reply_text("Please specify position: /watermark position bottom-right")
            elif action == 'opacity':
                if len(context.args) > 1:
                    try:
                        opacity = float(context.args[1])
                        if 0.0 <= opacity <= 1.0:
                            self.watermark_opacity = opacity
                            if self.watermark_processor:
                                self.watermark_processor.opacity = opacity
                            await update.message.reply_text(f"✅ Watermark opacity set to: {opacity}")
                        else:
                            await update.message.reply_text("⚠️ Opacity must be between 0.0 and 1.0")
                    except ValueError:
                        await update.message.reply_text("⚠️ Please provide a valid number for opacity (0.0 to 1.0)")
                else:
                    await update.message.reply_text("Please specify opacity: /watermark opacity 0.7")
            else:
                await update.message.reply_text(
                    "❓ Unknown command. Available options:\n"
                    "• /watermark on - Enable watermark\n"
                    "• /watermark off - Disable watermark\n"
                    "• /watermark position [pos] - Set position\n"
                    "• /watermark opacity [value] - Set opacity (0.0-1.0)\n"
                    "• /watermark status - Show current settings"
                )
        else:
            # Show current status
            status_text = (
                f"🖼️ **Watermark Settings:**\n\n"
                f"• **Status:** {'✅ ENABLED' if self.watermark_enabled else '❌ DISABLED'}\n"
                f"• **Position:** {self.watermark_position}\n"
                f"• **Opacity:** {self.watermark_opacity}\n"
                f"• **FFmpeg:** {'✅ AVAILABLE' if self.ffmpeg_available else '❌ NOT AVAILABLE'}\n\n"
                "Use commands:\n"
                "• /watermark on/off\n"
                "• /watermark position [bottom-right|bottom-left|top-right|top-left]\n"
                "• /watermark opacity [0.0-1.0]"
            )
            await update.message.reply_text(status_text)

    async def twitter_poster_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Twitter poster को enable/disable करें"""
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
            twitter_client_status = "available" if self.twitter_client else "not available"
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
        self.scheduled_mode = True
        self.incremental_schedule_mode = False
        self.fixed_interval_mode = False
        self.scheduled_counter = 0
        self.scheduled_messages = []

        now = datetime.now(TIMEZONE)
        first_schedule_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
        if first_schedule_time < now:
            first_schedule_time += timedelta(days=1)

        watermark_status = "with channel logo " if self.watermark_enabled else ""
        response_text = (
            "📅 **1 Hour Mode Activated!**\n\n"
            f"⏰ First video: {first_schedule_time.strftime('%Y-%m-%d %H:%M')} IST\n"
            f"🕐 Each new video: +1 hour interval\n"
            f"🖼️ Second channel videos: AI caption + {watermark_status}\n\n"
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

        watermark_status = "with channel logo " if self.watermark_enabled else ""
        response_text = (
            "⏱️ **Now Send Mode Activated!**\n\n"
            f"⏰ First video: {first_schedule_time.strftime('%Y-%m-%d %H:%M')} IST\n"
            f"🕐 Next intervals: +2h, +3h, +4h...\n"
            f"🖼️ Second channel videos: AI caption + {watermark_status}\n\n"
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

        watermark_status = "with channel logo " if self.watermark_enabled else ""
        response_text = (
            "🕑 **2 Hour Mode Activated!**\n\n"
            f"⏰ Schedule starts at: 7:00 AM IST\n"
            f"🕐 Fixed interval: Every 2 hours\n"
            f"🖼️ Second channel videos: AI caption + {watermark_status}\n\n"
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

            watermark_status = " with channel logo" if self.watermark_enabled else ""
            await message.reply_text(
                f"⏳ Processing link and downloading video...\n"
                f"🖼️ Watermark{watermark_status} will be added to second channel."
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
            self.bot_app.add_handler(CommandHandler("watermark", self.watermark_command))
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
            
            logger.info("Initializing Twitter client...")
            await self.initialize_twitter_client()
            
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
# file content end
