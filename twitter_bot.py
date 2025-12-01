import logging
import asyncio
import os
import re
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from datetime import datetime, timedelta
from config import TELEGRAM_BOT_TOKEN, API_ID, API_HASH, TELEGRAM_SESSION_STRING, TWITTER_VID_BOT, YOUR_CHANNEL_ID, YOUR_SECOND_CHANNEL_ID, TIMEZONE, ADMIN_IDS

logger = logging.getLogger(__name__)

class TwitterBot:
    def __init__(self):
        self.userbot = None
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
                    await self._handle_quality_selection(event)

                has_media = bool(event.message.media)
                is_final_message = any(word in message_text for word in ['Download', 'Ready', 'Here', 'Quality'])

                if (has_media or is_final_message) and self.quality_selected:
                    await self._process_received_video(event)

        except Exception as e:
            logger.error(f"Error in handle_twittervid_message: {str(e)}")

    async def _handle_quality_selection(self, event):
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
        """Process received video and send to channels"""
        try:
            original_caption = self.clean_text(event.message.text) if event.message.text else ""

            # Prepare captions for both channels
            first_channel_caption = f"\n\n{original_caption}\n\n" if original_caption else ""
            
            # Calculate schedule time if in scheduled mode
            scheduled_time = None
            if self.scheduled_mode or self.incremental_schedule_mode or self.fixed_interval_mode:
                scheduled_time = self._calculate_schedule_time()

            # Send to first channel
            if event.message.media:
                message1 = await self.userbot.send_file(
                    YOUR_CHANNEL_ID,
                    file=event.message.media,
                    caption=first_channel_caption,
                    schedule=scheduled_time if scheduled_time else None
                )
            else:
                message1 = await self.userbot.send_message(
                    YOUR_CHANNEL_ID,
                    first_channel_caption or "📹 Video Content",
                    schedule=scheduled_time if scheduled_time else None
                )

            # Send to second channel
            if event.message.media:
                message2 = await self.userbot.send_file(
                    YOUR_SECOND_CHANNEL_ID,
                    file=event.message.media,
                    caption=first_channel_caption,
                    schedule=scheduled_time if scheduled_time else None
                )
            else:
                message2 = await self.userbot.send_message(
                    YOUR_SECOND_CHANNEL_ID,
                    first_channel_caption or "📹 Video Content",
                    schedule=scheduled_time if scheduled_time else None
                )

            # Update counters and send success message
            if self.scheduled_mode or self.incremental_schedule_mode or self.fixed_interval_mode:
                self.scheduled_counter += 1
                self.scheduled_messages.extend([message1.id, message2.id])

                if self.current_update and self.current_update.message:
                    await self.current_update.message.reply_text(
                        f"✅ Video successfully scheduled for {scheduled_time.strftime('%Y-%m-%d %H:%M')} IST in both channels!"
                    )
            else:
                if self.current_update and self.current_update.message:
                    await self.current_update.message.reply_text(
                        "✅ Video successfully sent to both channels!"
                    )

            logger.info(f"Message sent to both channels: {YOUR_CHANNEL_ID} and {YOUR_SECOND_CHANNEL_ID}")
            self._reset_flags()

        except Exception as e:
            error_msg = f"❌ Error sending video to channels: {str(e)}"
            logger.error(error_msg)
            if self.current_update and self.current_update.message:
                await self.current_update.message.reply_text(error_msg)
            self._reset_flags()

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

    async def process_link(self, text):
        """Process Twitter link through userbot"""
        try:
            self.waiting_for_video = True
            self.quality_selected = False
            self.video_received = False

            await self.userbot.send_message(TWITTER_VID_BOT, text)
            logger.info(f"Link sent to twittervid_bot: {text}")

            start_time = datetime.now()
            while (datetime.now() - start_time).seconds < self.quality_selection_timeout:
                if self.quality_selected or self.video_received:
                    break
                await asyncio.sleep(2)

            if not self.quality_selected and not self.video_received:
                logger.warning("Timeout waiting for video processing")
                self._reset_flags()
                return False

            return True

        except Exception as e:
            logger.error(f"Error processing link: {str(e)}")
            self._reset_flags()
            return False

    async def shutdown(self):
        """Shutdown userbot"""
        if self.userbot and self.userbot.is_connected():
            logger.info("Disconnecting userbot...")
            await self.userbot.disconnect()
