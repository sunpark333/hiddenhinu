import logging
import asyncio
import os
import re
from datetime import datetime
from config import TWITTER_VID_BOT, YOUR_CHANNEL_ID, YOUR_SECOND_CHANNEL_ID, TIMEZONE

logger = logging.getLogger(__name__)

class VideoProcessor:
    """वीडियो डाउनलोड और प्रोसेसिंग"""
    
    def __init__(self, twitter_bot):
        self.twitter_bot = twitter_bot
        self.waiting_for_video = False
        self.quality_selected = False
        self.video_received = False
        self.current_update = None
        self.last_processed_message_id = None
        self.quality_selection_timeout = 60
    
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
    
    async def process_twitter_link(self, update, text):
        """Process Twitter link"""
        text = self.clean_text(text)

        self.current_update = update
        self.waiting_for_video = True
        self.quality_selected = False
        self.video_received = False

        await update.message.reply_text("⏳ Processing link and downloading video...")

        await self.twitter_bot.userbot.send_message(TWITTER_VID_BOT, text)
        logger.info(f"Link sent to twittervid_bot: {text}")

        # Wait for video
        await self._wait_for_video_response()
    
    async def _wait_for_video_response(self):
        """Wait for video response from twittervid_bot"""
        start_time = datetime.now()
        while (datetime.now() - start_time).seconds < self.quality_selection_timeout:
            if self.quality_selected or self.video_received:
                break
            await asyncio.sleep(2)

        if not self.quality_selected and not self.video_received:
            if self.current_update and self.current_update.message:
                await self.current_update.message.reply_text(
                    "⚠️ Timeout waiting for video processing. Please try again."
                )
            self._reset_flags()
    
    async def handle_twittervid_response(self, event):
        """Handle responses from twittervid_bot"""
        try:
            if self.last_processed_message_id is not None and event.message.id <= self.last_processed_message_id:
                return

            self.last_processed_message_id = event.message.id

            if self.waiting_for_video and self.current_update:
                await asyncio.sleep(3)
                
                message_text = event.message.text or ""
                logger.info(f"Received message from twittervid_bot: {message_text[:100]}...")

                # Delete previous messages
                await self._cleanup_old_messages(event)

                if "Select Video Quality" in message_text and not self.quality_selected:
                    await self._handle_quality_selection(event, message_text)
                    return

                has_media = bool(event.message.media)
                is_final_message = any(word in message_text for word in ['Download', 'Ready', 'Here', 'Quality'])

                if (has_media or is_final_message) and self.quality_selected:
                    await self._process_received_video(event)

        except Exception as e:
            logger.error(f"Error in handle_twittervid_message: {str(e)}")
    
    async def _cleanup_old_messages(self, event):
        """Clean up old messages"""
        try:
            async for old_msg in self.twitter_bot.userbot.iter_messages(TWITTER_VID_BOT, limit=5):
                if old_msg.id < event.message.id:
                    await old_msg.delete()
                    await asyncio.sleep(1)
        except Exception as e:
            logger.warning(f"Could not delete old messages: {str(e)}")
    
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
        """Process received video"""
        try:
            original_caption = self.clean_text(event.message.text) if event.message.text else ""

            # Prepare captions
            first_channel_caption = f"\n\n{original_caption}\n\n" if original_caption else ""
            second_channel_caption = await self._get_enhanced_caption(original_caption)

            # Send to channels
            scheduled_time = self.twitter_bot.scheduler._calculate_schedule_time()
            
            message1 = await self._send_to_channel(
                YOUR_CHANNEL_ID, event, first_channel_caption, scheduled_time
            )
            
            message2 = await self._send_to_channel(
                YOUR_SECOND_CHANNEL_ID, event, second_channel_caption, scheduled_time
            )

            # Handle success response
            await self._handle_success_response(message1, message2, scheduled_time)

            logger.info(f"Message sent to both channels: {YOUR_CHANNEL_ID} and {YOUR_SECOND_CHANNEL_ID}")
            self._reset_flags()

        except Exception as e:
            error_msg = f"❌ Error sending video to channels: {str(e)}"
            logger.error(error_msg)
            if self.current_update and self.current_update.message:
                await self.current_update.message.reply_text(error_msg)
            self._reset_flags()
    
    async def _send_to_channel(self, channel_id, event, caption_text, scheduled_time):
        """Send message to channel"""
        if event.message.media:
            return await self.twitter_bot.userbot.send_file(
                channel_id,
                file=event.message.media,
                caption=caption_text,
                schedule=scheduled_time if any([
                    self.twitter_bot.scheduler.scheduled_mode,
                    self.twitter_bot.scheduler.incremental_schedule_mode,
                    self.twitter_bot.scheduler.fixed_interval_mode
                ]) else None
            )
        else:
            return await self.twitter_bot.userbot.send_message(
                channel_id,
                caption_text or "📹 Video Content",
                schedule=scheduled_time if any([
                    self.twitter_bot.scheduler.scheduled_mode,
                    self.twitter_bot.scheduler.incremental_schedule_mode,
                    self.twitter_bot.scheduler.fixed_interval_mode
                ]) else None
            )
    
    async def _get_enhanced_caption(self, original_caption):
        """Get AI-enhanced caption"""
        try:
            if not original_caption or len(original_caption.strip()) < 10:
                return f"\n\n{original_caption}\n\n" if original_caption else ""
            
            logger.info("Enhancing caption for second channel using AI...")
            enhanced_caption = await self.twitter_bot.ai_enhancer.enhance_caption(original_caption)
            
            if enhanced_caption and enhanced_caption != original_caption:
                logger.info("Caption successfully enhanced with AI")
                return f"\n\n{enhanced_caption}\n\n"
            else:
                logger.info("Using original caption (AI enhancement failed or not available)")
                return f"\n\n{original_caption}\n\n"
                
        except Exception as e:
            logger.error(f"Error in AI caption enhancement: {str(e)}")
            return f"\n\n{original_caption}\n\n"
    
    async def _handle_success_response(self, message1, message2, scheduled_time):
        """Handle success response to user"""
        if any([
            self.twitter_bot.scheduler.scheduled_mode,
            self.twitter_bot.scheduler.incremental_schedule_mode,
            self.twitter_bot.scheduler.fixed_interval_mode
        ]):
            self.twitter_bot.scheduler.increment_counter()
            self.twitter_bot.scheduler.scheduled_messages.extend([message1.id, message2.id])

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
    
    def _reset_flags(self):
        """Reset processing flags"""
        self.video_received = True
        self.waiting_for_video = False
        self.current_update = None
        self.quality_selected = False
    
    async def handle_second_channel_for_twitter(self, event):
        """Handle second channel messages for Twitter posting"""
        try:
            if not self.twitter_bot.twitter_poster.twitter_poster_enabled or not self.twitter_bot.twitter_poster.twitter_client:
                return

            message = event.message
            logger.info(f"New message from second channel (ID: {message.id}) for Twitter posting")
            
            # Get message text
            original_text = message.text or message.caption or ""
            
            # Download media if present
            media_path = None
            if message.media:
                media_path = await self.twitter_bot.userbot.download_media(
                    message,
                    file=f"temp_twitter_media_{message.id}"
                )
            
            # Post to Twitter
            success = await self.twitter_bot.twitter_poster.post_to_twitter(original_text, media_path)
            
            if success:
                logger.info("Successfully posted to Twitter from second channel")
            else:
                logger.warning("Failed to post to Twitter from second channel")
                
            # Clean up
            if media_path and os.path.exists(media_path):
                try:
                    os.remove(media_path)
                except Exception as e:
                    logger.warning(f"Could not delete temp file: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error handling second channel message for Twitter: {str(e)}")
