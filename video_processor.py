import logging
import asyncio
import re
from datetime import datetime, timedelta
from config import YOUR_CHANNEL_ID, YOUR_SECOND_CHANNEL_ID, TIMEZONE, TWITTER_VID_BOT
from ai_caption_enhancer import AICaptionEnhancer

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self, twitter_bot):
        self.bot = twitter_bot
        self.ai_enhancer = AICaptionEnhancer()

    async def _handle_twittervid_response(self, event):
        """Handle responses from twittervid_bot"""
        try:
            if self.bot.last_processed_message_id is not None and event.message.id <= self.bot.last_processed_message_id:
                return

            self.bot.last_processed_message_id = event.message.id

            if self.bot.waiting_for_video and self.bot.current_update:
                await asyncio.sleep(3)
                
                message_text = event.message.text or ""
                logger.info(f"Received message from twittervid_bot: {message_text[:100]}...")

                # Delete previous messages from twittervid_bot to keep chat clean
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
                    return await self.bot.userbot.send_file(
                        channel_id,
                        file=event.message.media,
                        caption=caption_text,
                        schedule=scheduled_time if self.bot.scheduled_mode or self.bot.incremental_schedule_mode or self.bot.fixed_interval_mode else None
                    )
                else:
                    return await self.bot.userbot.send_message(
                        channel_id,
                        caption_text or "📹 Video Content",
                        schedule=scheduled_time if self.bot.scheduled_mode or self.bot.incremental_schedule_mode or self.bot.fixed_interval_mode else None
                    )

            # Calculate schedule time if in scheduled mode
            scheduled_time = None
            if self.bot.scheduled_mode or self.bot.incremental_schedule_mode or self.bot.fixed_interval_mode:
                scheduled_time = self._calculate_schedule_time()

            # Send to first channel (original caption)
            message1 = await send_to_channel(YOUR_CHANNEL_ID, first_channel_caption)
            
            # Send to second channel (AI-enhanced caption)
            message2 = await send_to_channel(YOUR_SECOND_CHANNEL_ID, second_channel_caption)

            # Update counters and send success message
            if self.bot.scheduled_mode or self.bot.incremental_schedule_mode or self.bot.fixed_interval_mode:
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
            self.bot._reset_flags()

        except Exception as e:
            error_msg = f"❌ Error sending video to channels: {str(e)}"
            logger.error(error_msg)
            if self.bot.current_update and self.bot.current_update.message:
                await self.bot.current_update.message.reply_text(
                    error_msg
                )
            self.bot._reset_flags()

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

        if self.bot.scheduled_mode:
            scheduled_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
            if scheduled_time < now:
                scheduled_time += timedelta(days=1)
            scheduled_time += timedelta(hours=self.bot.scheduled_counter)
        elif self.bot.incremental_schedule_mode:
            scheduled_time = now + timedelta(hours=self.bot.scheduled_counter + 2)
        elif self.bot.fixed_interval_mode:
            scheduled_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
            if scheduled_time < now:
                scheduled_time += timedelta(days=1)
            scheduled_time += timedelta(hours=2 * self.bot.scheduled_counter)
        else:
            scheduled_time = now

        return scheduled_time

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
