import logging
import asyncio
import re
import os
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaWebPage
from config import API_ID, API_HASH, TELEGRAM_SESSION_STRING, TWITTER_VID_BOT, YOUR_CHANNEL_ID, YOUR_SECOND_CHANNEL_ID
from ai_caption_enhancer import AICaptionEnhancer

logger = logging.getLogger(__name__)

class UserBotManager:
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.userbot = None
        self.waiting_for_video = False
        self.current_update = None
        self.quality_selected = False
        self.video_received = False
        self.quality_selection_timeout = 90  # Increased timeout
        self.last_processed_message_id = None
        self.ai_enhancer = AICaptionEnhancer()
        self.video_download_attempts = 0
        self.max_download_attempts = 3

    async def initialize(self):
        """Initialize Telegram userbot with string session"""
        try:
            logger.info("Starting UserBot initialization...")
            
            session = StringSession(TELEGRAM_SESSION_STRING)
            self.userbot = TelegramClient(
                session=session,
                api_id=int(API_ID),
                api_hash=API_HASH,
                connection_retries=5
            )

            await self.userbot.start()
            logger.info("UserBot successfully started")

            # Add handler for twittervid_bot responses
            @self.userbot.on(events.NewMessage(from_users=TWITTER_VID_BOT))
            async def handle_twittervid_message(event):
                await self._handle_twittervid_response(event)

            # Add handler for second channel (Twitter posting)
            @self.userbot.on(events.NewMessage(chats=YOUR_SECOND_CHANNEL_ID))
            async def handle_second_channel_message(event):
                await self._handle_second_channel_for_twitter(event)

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

    async def process_twitter_link(self, update, link_text):
        """Process Twitter link through userbot"""
        try:
            self.current_update = update
            self.waiting_for_video = True
            self.quality_selected = False
            self.video_received = False
            self.video_download_attempts = 0

            clean_text = self.clean_text(link_text)
            
            await update.message.reply_text("⏳ Processing link and downloading video...")
            
            await self.userbot.send_message(TWITTER_VID_BOT, clean_text)
            logger.info(f"Link sent to twittervid_bot: {clean_text}")

            start_time = asyncio.get_event_loop().time()
            while (asyncio.get_event_loop().time() - start_time) < self.quality_selection_timeout:
                if self.video_received:
                    break
                await asyncio.sleep(2)

            if not self.video_received:
                await update.message.reply_text("⚠️ Timeout waiting for video processing. Please try again.")
                self._reset_flags()
                return False

            return True

        except Exception as e:
            logger.error(f"Error processing twitter link: {str(e)}")
            self._reset_flags()
            return False

    async def _handle_twittervid_response(self, event):
        """Handle responses from twittervid_bot"""
        try:
            if self.last_processed_message_id is not None and event.message.id <= self.last_processed_message_id:
                return

            self.last_processed_message_id = event.message.id

            if self.waiting_for_video and self.current_update:
                await asyncio.sleep(2)  # Reduced sleep time
                
                message_text = event.message.text or ""
                logger.info(f"Received message from twittervid_bot: {message_text[:100]}...")

                # Check if message contains video
                has_video = await self._check_if_has_video(event)
                has_media = bool(event.message.media) and not isinstance(event.message.media, MessageMediaWebPage)

                # Delete previous messages from twittervid_bot to keep chat clean
                try:
                    async for old_msg in self.userbot.iter_messages(TWITTER_VID_BOT, limit=5):
                        if old_msg.id < event.message.id:
                            await old_msg.delete()
                            await asyncio.sleep(0.5)
                except Exception as e:
                    logger.warning(f"Could not delete old messages: {str(e)}")

                if "Select Video Quality" in message_text and not self.quality_selected:
                    logger.info("Quality selection detected")
                    await self._handle_quality_selection(event, message_text)
                    return

                # Check if we have actual video (not webpage)
                if has_video or has_media:
                    logger.info(f"Video detected! Type: {type(event.message.media)}")
                    await self._process_received_video(event)
                else:
                    # Wait for video if we have quality selected
                    if self.quality_selected and not self.video_received:
                        self.video_download_attempts += 1
                        logger.info(f"Waiting for video... Attempt {self.video_download_attempts}")
                        
                        if self.video_download_attempts >= self.max_download_attempts:
                            logger.warning("Max download attempts reached, sending text only")
                            await self._send_as_text_only(event)
                            return
                        
                        # Wait and check again
                        await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"Error in handle_twittervid_message: {str(e)}")

    async def _check_if_has_video(self, event):
        """Check if message actually contains video (not webpage)"""
        try:
            if not event.message.media:
                return False
                
            # Check if it's a webpage (which we can't use)
            if isinstance(event.message.media, MessageMediaWebPage):
                logger.warning("Received MessageMediaWebPage instead of video")
                return False
                
            # Check for video attributes
            if hasattr(event.message.media, 'video'):
                return True
            if hasattr(event.message.media, 'document'):
                doc = event.message.media.document
                if hasattr(doc, 'mime_type'):
                    return doc.mime_type.startswith('video/')
                    
            # Try to check by file name
            if hasattr(event.message, 'file') and event.message.file:
                file_name = event.message.file.name or ''
                return any(ext in file_name.lower() for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm'])
                
            return False
        except Exception as e:
            logger.error(f"Error checking for video: {str(e)}")
            return False

    async def _handle_quality_selection(self, event, message_text):
        """Handle video quality selection"""
        try:
            buttons = await event.message.get_buttons()
            if buttons:
                # Try to find HD quality first
                for row in buttons:
                    for button in row:
                        if any(q in button.text.lower() for q in ['1080', '720', 'hd', 'high']):
                            await button.click()
                            quality = button.text
                            logger.info(f"Selected quality: {quality}")
                            if self.current_update and self.current_update.message:
                                await self.current_update.message.reply_text(
                                    f"✅ Video is being downloaded in {quality} quality..."
                                )
                            self.quality_selected = True
                            return

                # If no HD quality found, select first available
                if buttons[0]:
                    await buttons[0][0].click()
                    quality = buttons[0][0].text
                    logger.info(f"Selected first available quality: {quality}")
                    if self.current_update and self.current_update.message:
                        await self.current_update.message.reply_text(
                            f"✅ Video is being downloaded in {quality} quality..."
                        )
                    self.quality_selected = True

        except Exception as e:
            logger.error(f"Error in quality selection: {str(e)}")
            self.quality_selected = True

    async def _process_received_video(self, event):
        """Process received video and send to both channels"""
        try:
            # First check if it's actually a video
            if isinstance(event.message.media, MessageMediaWebPage):
                logger.warning("Cannot process webpage as video")
                await self._send_as_text_only(event)
                return

            original_caption = self.clean_text(event.message.text) if event.message.text else ""

            # Prepare captions for both channels
            first_channel_caption = f"\n\n{original_caption}\n\n" if original_caption else ""
            
            # Enhance caption for second channel using AI
            second_channel_caption = await self._get_enhanced_caption(original_caption)

            # Calculate schedule time if in scheduled mode
            scheduled_time = await self.bot.scheduler.get_next_schedule_time()

            # Try to send video
            try:
                # Send to first channel
                message1 = await self._send_to_channel(YOUR_CHANNEL_ID, event.message, first_channel_caption, scheduled_time)
                
                # Send to second channel
                message2 = await self._send_to_channel(YOUR_SECOND_CHANNEL_ID, event.message, second_channel_caption, scheduled_time)

                # Update scheduler counter
                if scheduled_time:
                    await self.bot.scheduler.increment_counter()

                # Send success message
                await self._send_success_message(scheduled_time, is_video=True)

                logger.info(f"Video sent to both channels: {YOUR_CHANNEL_ID} and {YOUR_SECOND_CHANNEL_ID}")
                self.video_received = True
                
            except Exception as e:
                logger.error(f"Error sending video: {str(e)}")
                # Fallback to text only
                await self._send_as_text_only(event)

        except Exception as e:
            error_msg = f"❌ Error processing video: {str(e)}"
            logger.error(error_msg)
            # Try to send error message
            try:
                if self.current_update and self.current_update.message:
                    await self.current_update.message.reply_text(error_msg)
            except:
                pass
            self._reset_flags()

    async def _send_as_text_only(self, event):
        """Send message as text only (fallback when video not available)"""
        try:
            original_caption = self.clean_text(event.message.text) if event.message.text else "Video content from Twitter"
            
            first_channel_caption = f"📹 Video Content\n\n{original_caption}\n\n"
            second_channel_caption = await self._get_enhanced_caption(original_caption)
            
            scheduled_time = await self.bot.scheduler.get_next_schedule_time()
            
            # Send text only messages
            message1 = await self.userbot.send_message(
                YOUR_CHANNEL_ID,
                first_channel_caption,
                schedule=scheduled_time if scheduled_time else None
            )
            
            message2 = await self.userbot.send_message(
                YOUR_SECOND_CHANNEL_ID,
                second_channel_caption,
                schedule=scheduled_time if scheduled_time else None
            )
            
            if scheduled_time:
                await self.bot.scheduler.increment_counter()
            
            await self._send_success_message(scheduled_time, is_video=False)
            
            logger.info(f"Text-only message sent to both channels")
            self.video_received = True
            
        except Exception as e:
            logger.error(f"Error sending text-only message: {str(e)}")
            if self.current_update and self.current_update.message:
                await self.current_update.message.reply_text("❌ Failed to process video. Please try another link.")
        finally:
            self._reset_flags()

    async def _send_to_channel(self, channel_id, message, caption, scheduled_time):
        """Send message to channel with proper media handling"""
        try:
            # Check if media is actually a video (not webpage)
            if message.media and not isinstance(message.media, MessageMediaWebPage):
                # Download media first to verify it's a video
                try:
                    temp_path = f"temp_video_{message.id}.mp4"
                    downloaded_path = await self.userbot.download_media(
                        message,
                        file=temp_path
                    )
                    
                    if downloaded_path and os.path.exists(downloaded_path):
                        # Send the downloaded file
                        result = await self.userbot.send_file(
                            channel_id,
                            downloaded_path,
                            caption=caption,
                            schedule=scheduled_time if scheduled_time else None
                        )
                        
                        # Clean up temp file
                        try:
                            os.remove(downloaded_path)
                        except:
                            pass
                        
                        return result
                except Exception as e:
                    logger.warning(f"Could not download video: {str(e)}")
                    # Fallback to sending as message
                    return await self.userbot.send_message(
                        channel_id,
                        caption or "📹 Video Content",
                        schedule=scheduled_time if scheduled_time else None
                    )
            else:
                # Send as text message
                return await self.userbot.send_message(
                    channel_id,
                    caption or "📹 Video Content",
                    schedule=scheduled_time if scheduled_time else None
                )
                
        except Exception as e:
            logger.error(f"Error in _send_to_channel: {str(e)}")
            # Ultimate fallback
            return await self.userbot.send_message(
                channel_id,
                caption or "📹 Video Content",
                schedule=scheduled_time if scheduled_time else None
            )

    async def _send_success_message(self, scheduled_time, is_video=True):
        """Send success message to user"""
        if self.current_update and self.current_update.message:
            content_type = "Video" if is_video else "Content"
            
            if scheduled_time:
                await self.current_update.message.reply_text(
                    f"✅ {content_type} successfully scheduled for {scheduled_time.strftime('%Y-%m-%d %H:%M')} IST in both channels!\n"
                    f"📝 Second channel caption enhanced with AI."
                )
            else:
                await self.current_update.message.reply_text(
                    f"✅ {content_type} successfully sent to both channels!\n"
                    f"📝 Second channel caption enhanced with AI."
                )

    async def _get_enhanced_caption(self, original_caption):
        """Get AI-enhanced caption for second channel"""
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

    async def _handle_second_channel_for_twitter(self, event):
        """Handle messages from second channel for Twitter posting"""
        try:
            if not self.bot.twitter_poster.twitter_poster_enabled:
                return

            message = event.message
            logger.info(f"New message from second channel (ID: {message.id}) for Twitter posting")
            
            # Get message text
            original_text = message.text or message.caption or ""
            
            # Download media if present and not webpage
            media_path = None
            if message.media and not isinstance(message.media, MessageMediaWebPage):
                media_path = await self.userbot.download_media(
                    message,
                    file=f"temp_twitter_media_{message.id}"
                )
            
            # Post to Twitter
            success = await self.bot.twitter_poster.post_to_twitter(original_text, media_path)
            
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

    def _reset_flags(self):
        """Reset processing flags"""
        self.video_received = True
        self.waiting_for_video = False
        self.current_update = None
        self.quality_selected = False
        self.video_download_attempts = 0

    async def shutdown(self):
        """Shutdown userbot"""
        if self.userbot and self.userbot.is_connected():
            logger.info("Disconnecting userbot...")
            await self.userbot.disconnect()
            logger.info("UserBot disconnected")
