import logging
import asyncio
import re
from telethon import TelegramClient, events
from telethon.sessions import StringSession
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
        self.quality_selection_timeout = 60
        self.last_processed_message_id = None
        self.ai_enhancer = AICaptionEnhancer()

    async def initialize(self):
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

            clean_text = self.clean_text(link_text)
            
            await update.message.reply_text("⏳ Processing link and downloading video...")
            
            await self.userbot.send_message(TWITTER_VID_BOT, clean_text)
            logger.info(f"Link sent to twittervid_bot: {clean_text}")

            start_time = asyncio.get_event_loop().time()
            while (asyncio.get_event_loop().time() - start_time) < self.quality_selection_timeout:
                if self.quality_selected or self.video_received:
                    break
                await asyncio.sleep(2)

            if not self.quality_selected and not self.video_received:
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
                    await self._handle_quality_selection(event, message_text)

                has_media = bool(event.message.media)
                is_final_message = any(word in message_text for word in ['Download', 'Ready', 'Here', 'Quality'])

                if (has_media or is_final_message) and self.quality_selected:
                    await self._process_received_video(event)

        except Exception as e:
            logger.error(f"Error in handle_twittervid_message: {str(e)}")

    async def _handle_quality_selection(self, event, message_text):
        """Handle video quality selection"""
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

    async def _process_received_video(self, event):
        """Process received video and send to both channels"""
        try:
            original_caption = self.clean_text(event.message.text) if event.message.text else ""

            # Prepare captions for both channels
            first_channel_caption = f"\n\n{original_caption}\n\n" if original_caption else ""
            
            # Enhance caption for second channel using AI
            second_channel_caption = await self._get_enhanced_caption(original_caption)

            # Calculate schedule time if in scheduled mode
            scheduled_time = await self.bot.scheduler.get_next_schedule_time()

            # Send to first channel
            message1 = await self._send_to_channel(YOUR_CHANNEL_ID, event.message, first_channel_caption, scheduled_time)
            
            # Send to second channel
            message2 = await self._send_to_channel(YOUR_SECOND_CHANNEL_ID, event.message, second_channel_caption, scheduled_time)

            # Update scheduler counter
            if scheduled_time:
                await self.bot.scheduler.increment_counter()

            # Send success message
            await self._send_success_message(scheduled_time)

            logger.info(f"Message sent to both channels: {YOUR_CHANNEL_ID} and {YOUR_SECOND_CHANNEL_ID}")
            self._reset_flags()

        except Exception as e:
            error_msg = f"❌ Error sending video to channels: {str(e)}"
            logger.error(error_msg)
            if self.current_update and self.current_update.message:
                await self.current_update.message.reply_text(error_msg)
            self._reset_flags()

    async def _send_to_channel(self, channel_id, message, caption, scheduled_time):
        """Send message to channel"""
        if message.media:
            return await self.userbot.send_file(
                channel_id,
                file=message.media,
                caption=caption,
                schedule=scheduled_time if scheduled_time else None
            )
        else:
            return await self.userbot.send_message(
                channel_id,
                caption or "📹 Video Content",
                schedule=scheduled_time if scheduled_time else None
            )

    async def _send_success_message(self, scheduled_time):
        """Send success message to user"""
        if self.current_update and self.current_update.message:
            if scheduled_time:
                await self.current_update.message.reply_text(
                    f"✅ Video successfully scheduled for {scheduled_time.strftime('%Y-%m-%d %H:%M')} IST in both channels!\n"
                    f"📝 Second channel caption enhanced with AI."
                )
            else:
                await self.current_update.message.reply_text(
                    "✅ Video successfully sent to both channels!\n"
                    "📝 Second channel caption enhanced with AI."
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
            
            # Download media if present
            media_path = None
            if message.media:
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
            if media_path:
                import os
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

    async def shutdown(self):
        """Shutdown userbot"""
        if self.userbot and self.userbot.is_connected():
            logger.info("Disconnecting userbot...")
            await self.userbot.disconnect()
            logger.info("UserBot disconnected")
