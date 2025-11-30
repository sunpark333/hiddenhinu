import logging
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from config import TELEGRAM_SESSION_STRING, API_ID, API_HASH, TWITTER_VID_BOT, YOUR_CHANNEL_ID, YOUR_SECOND_CHANNEL_ID

logger = logging.getLogger(__name__)

class TelegramClientManager:
    def __init__(self, twitter_bot):
        self.bot = twitter_bot
        self.userbot = None

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
                await self.bot.video_processor._handle_twittervid_response(event)

            # Add handler for second channel (Twitter posting)
            if self.bot.twitter_poster.twitter_poster_enabled:
                @self.userbot.on(events.NewMessage(chats=YOUR_SECOND_CHANNEL_ID))
                async def handle_second_channel_message(event):
                    await self.bot.twitter_poster.handle_second_channel_message(self.userbot, event, YOUR_SECOND_CHANNEL_ID)
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

    async def disconnect_userbot(self):
        """Disconnect userbot"""
        if self.userbot and self.userbot.is_connected():
            logger.info("Disconnecting userbot...")
            await self.userbot.disconnect()
