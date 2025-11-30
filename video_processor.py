import logging
import asyncio
import re
import os
from datetime import datetime, timedelta
from config import YOUR_CHANNEL_ID, YOUR_SECOND_CHANNEL_ID, TIMEZONE, TWITTER_VID_BOT, WATERMARK_ENABLED, WATERMARK_LOGO_PATH, WATERMARK_POSITION, WATERMARK_OPACITY
from ai_caption_enhancer import AICaptionEnhancer

logger = logging.getLogger(__name__)

class WatermarkProcessor:
    def __init__(self):
        self.logo_path = WATERMARK_LOGO_PATH
        self.position = WATERMARK_POSITION
        self.opacity = WATERMARK_OPACITY
        
    async def add_watermark_to_image(self, image_path):
        """Add watermark to image"""
        try:
            if not os.path.exists(self.logo_path):
                logger.warning("Watermark logo not found, skipping watermark")
                return image_path
                
            from PIL import Image
            
            # Open the original image
            original_image = Image.open(image_path)
            watermark = Image.open(self.logo_path)
            
            # Calculate position
            position = self._calculate_position(original_image.size, watermark.size)
            
            # Convert watermark to RGBA if not already
            if watermark.mode != 'RGBA':
                watermark = watermark.convert('RGBA')
                
            # Set opacity
            watermark = self._set_opacity(watermark, self.opacity)
            
            # Create a copy of original image
            watermarked_image = original_image.copy().convert('RGBA')
            
            # Paste watermark
            watermarked_image.paste(watermark, position, watermark)
            
            # Convert back to RGB if needed
            if original_image.mode == 'RGB':
                watermarked_image = watermarked_image.convert('RGB')
            
            # Save watermarked image
            output_path = image_path.replace('.', '_watermarked.')
            watermarked_image.save(output_path, quality=95)
            
            logger.info(f"Watermark added to image: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error adding watermark to image: {str(e)}")
            return image_path
            
    async def add_watermark_to_video(self, video_path):
        """Add watermark to video - Simplified version without OpenCV"""
        try:
            if not os.path.exists(self.logo_path):
                logger.warning("Watermark logo not found, skipping video watermark")
                return video_path
                
            # For now, return original video (advanced video watermarking requires FFmpeg/OpenCV)
            logger.info("Video watermarking requires additional setup. Using original video.")
            return video_path
            
        except Exception as e:
            logger.error(f"Error in video watermarking: {str(e)}")
            return video_path
            
    def _calculate_position(self, image_size, watermark_size):
        """Calculate watermark position based on configuration"""
        img_width, img_height = image_size
        wm_width, wm_height = watermark_size
        
        margin = 20  # pixels from edge
        
        if self.position == 'top-left':
            return (margin, margin)
        elif self.position == 'top-right':
            return (img_width - wm_width - margin, margin)
        elif self.position == 'bottom-left':
            return (margin, img_height - wm_height - margin)
        elif self.position == 'bottom-right':
            return (img_width - wm_width - margin, img_height - wm_height - margin)
        elif self.position == 'center':
            return ((img_width - wm_width) // 2, (img_height - wm_height) // 2)
        else:  # default to bottom-right
            return (img_width - wm_width - margin, img_height - wm_height - margin)
            
    def _set_opacity(self, image, opacity):
        """Set opacity of watermark"""
        if image.mode != 'RGBA':
            return image
            
        # Create a new image with adjusted alpha
        alpha = image.split()[3]
        alpha = alpha.point(lambda p: p * opacity // 255)
        image.putalpha(alpha)
        return image
        
    def cleanup_temp_files(self, *file_paths):
        """Clean up temporary watermarked files"""
        for file_path in file_paths:
            if file_path and os.path.exists(file_path) and 'watermarked' in file_path:
                try:
                    os.remove(file_path)
                    logger.info(f"Cleaned up temporary file: {file_path}")
                except Exception as e:
                    logger.warning(f"Could not delete temp file {file_path}: {str(e)}")

class VideoProcessor:
    def __init__(self, twitter_bot):
        self.bot = twitter_bot
        self.ai_enhancer = AICaptionEnhancer()
        self.watermark_processor = WatermarkProcessor() if WATERMARK_ENABLED else None

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

            # Download media if present and add watermark if enabled
            media_file = None
            temp_files_to_cleanup = []
            
            if event.message.media:
                # Download the media
                media_file = await self.bot.userbot.download_media(
                    event.message,
                    file=f"temp_media_{event.message.id}"
                )
                
                # Add watermark if enabled and file exists
                if WATERMARK_ENABLED and media_file and os.path.exists(media_file) and self.watermark_processor:
                    try:
                        if media_file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp')):
                            # Process image watermark
                            logger.info("Adding watermark to image...")
                            watermarked_file = await self.watermark_processor.add_watermark_to_image(media_file)
                            if watermarked_file != media_file:
                                # Use watermarked file for sending
                                media_file_to_send = watermarked_file
                                temp_files_to_cleanup.append(watermarked_file)
                                logger.info("✅ Watermark added to image")
                            else:
                                media_file_to_send = media_file
                        else:
                            # For videos, use original file (video watermarking requires advanced setup)
                            media_file_to_send = media_file
                            logger.info("📹 Video file - watermarking skipped (requires FFmpeg setup)")
                    except Exception as e:
                        logger.error(f"Error applying watermark: {str(e)}")
                        media_file_to_send = media_file
                else:
                    media_file_to_send = media_file
            else:
                media_file_to_send = None

            # Function to send to a channel
            async def send_to_channel(channel_id, caption_text):
                if media_file_to_send and os.path.exists(media_file_to_send):
                    # Determine if it's video or image
                    if media_file_to_send.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
                        # Send as video
                        return await self.bot.userbot.send_file(
                            channel_id,
                            file=media_file_to_send,
                            caption=caption_text,
                            supports_streaming=True,
                            schedule=scheduled_time if self.bot.scheduled_mode or self.bot.incremental_schedule_mode or self.bot.fixed_interval_mode else None
                        )
                    else:
                        # Send as photo
                        return await self.bot.userbot.send_file(
                            channel_id,
                            file=media_file_to_send,
                            caption=caption_text,
                            schedule=scheduled_time if self.bot.scheduled_mode or self.bot.incremental_schedule_mode or self.bot.fixed_interval_mode else None
                        )
                else:
                    # Send as text message if no media
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
            watermark_status = " + 🎯 Watermark" if WATERMARK_ENABLED and media_file and media_file_to_send and media_file_to_send != media_file else ""
            
            if self.bot.scheduled_mode or self.bot.incremental_schedule_mode or self.bot.fixed_interval_mode:
                self.bot.scheduled_counter += 1
                self.bot.scheduled_messages.extend([message1.id, message2.id])

                if self.bot.current_update and self.bot.current_update.message:
                    await self.bot.current_update.message.reply_text(
                        f"✅ Video successfully scheduled for {scheduled_time.strftime('%Y-%m-%d %H:%M')} IST in both channels!\n"
                        f"📝 Second channel caption enhanced with AI{watermark_status}"
                    )
            else:
                if self.bot.current_update and self.bot.current_update.message:
                    await self.bot.current_update.message.reply_text(
                        f"✅ Video successfully sent to both channels!\n"
                        f"📝 Second channel caption enhanced with AI{watermark_status}"
                    )

            logger.info(f"Message sent to both channels: {YOUR_CHANNEL_ID} and {YOUR_SECOND_CHANNEL_ID}")

            # Clean up temporary files
            try:
                # Clean original downloaded file
                if media_file and os.path.exists(media_file) and 'temp_media' in media_file:
                    os.remove(media_file)
                
                # Clean watermarked files
                for temp_file in temp_files_to_cleanup:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
            except Exception as e:
                logger.warning(f"Could not delete temp files: {str(e)}")
                
            self.bot._reset_flags()

        except Exception as e:
            error_msg = f"❌ Error sending video to channels: {str(e)}"
            logger.error(error_msg)
            
            # Clean up files even if error occurs
            try:
                if 'media_file' in locals() and media_file and os.path.exists(media_file):
                    os.remove(media_file)
                if 'temp_files_to_cleanup' in locals():
                    for temp_file in temp_files_to_cleanup:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
            except Exception as cleanup_error:
                logger.warning(f"Cleanup error: {cleanup_error}")
                
            if self.bot.current_update and self.bot.current_update.message:
                await self.bot.current_update.message.reply_text(error_msg)
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
