import logging
import asyncio
import re
import os
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from tweepy import Client as TwitterClient
from tweepy.errors import TweepyException
from config import (
    API_ID, API_HASH, TELEGRAM_SESSION_STRING,
    YOUR_SECOND_CHANNEL_ID,
    TWITTER_BEARER_TOKEN, TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET,
    TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SecondChannelToTwitter:
    def __init__(self):
        self.client = None
        self.twitter_client = None
        self.setup_twitter()
        
    def setup_twitter(self):
        """Setup Twitter client"""
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
                logger.info("✅ Twitter client initialized successfully")
            else:
                logger.warning("❌ Twitter credentials missing - Twitter posting disabled")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Twitter client: {e}")

    async def start(self):
        """Start monitoring second channel and posting to Twitter"""
        try:
            # Initialize Telegram client
            session = StringSession(TELEGRAM_SESSION_STRING)
            self.client = TelegramClient(
                session=session,
                api_id=int(API_ID),
                api_hash=API_HASH
            )

            await self.client.start()
            logger.info("🚀 Second Channel to Twitter bot started")

            # Add event handler for second channel
            @self.client.on(events.NewMessage(chats=YOUR_SECOND_CHANNEL_ID))
            async def handle_channel_message(event):
                await self.process_channel_message(event)

            logger.info(f"🔍 Monitoring channel {YOUR_SECOND_CHANNEL_ID} for Twitter posting")
            
            # Keep running
            await self.client.run_until_disconnected()

        except Exception as e:
            logger.error(f"❌ Error in SecondChannelToTwitter: {e}")

    def clean_text_for_twitter(self, text):
        """Clean text for Twitter posting"""
        if not text:
            return ""
            
        # Remove URLs
        cleaned = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)
        
        # Remove extra spaces and trim
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Truncate if too long (280 characters for Twitter)
        if len(cleaned) > 280:
            cleaned = cleaned[:277] + "..."
            
        return cleaned

    async def process_channel_message(self, event):
        """Process channel message and post to Twitter"""
        try:
            message = event.message
            logger.info(f"📥 New message in second channel (ID: {message.id})")

            # Get text content
            text = message.text or message.caption or ""
            cleaned_text = self.clean_text_for_twitter(text)
            
            if not cleaned_text.strip():
                logger.info("📝 No text content for Twitter")
                cleaned_text = "📹 New video posted"  # Default text for media posts

            # Download media if available
            media_path = None
            if message.media:
                media_path = await self.download_media(message)
                
            # Post to Twitter
            success = await self.post_to_twitter(cleaned_text, media_path)
            
            if success:
                logger.info(f"✅ Successfully posted to Twitter from channel message {message.id}")
            else:
                logger.warning(f"❌ Failed to post to Twitter from channel message {message.id}")

        except Exception as e:
            logger.error(f"❌ Error processing channel message: {e}")

    async def download_media(self, message):
        """Download media from message"""
        try:
            media_path = await self.client.download_media(
                message.media,
                file=f"twitter_media_{message.id}"
            )
            logger.info(f"📥 Downloaded media: {media_path}")
            return media_path
        except Exception as e:
            logger.error(f"❌ Error downloading media: {e}")
            return None

    async def post_to_twitter(self, text, media_path=None):
        """Post to Twitter"""
        if not self.twitter_client:
            logger.warning("❌ Twitter client not available")
            return False
            
        try:
            if media_path and os.path.exists(media_path):
                # Check file size
                file_size = os.path.getsize(media_path) / (1024 * 1024)
                if file_size > 50:
                    logger.warning(f"📁 Media file too large ({file_size:.2f}MB), posting text only")
                    return await self.post_text_to_twitter(text)
                
                # Upload media using v1.1 API
                from tweepy import OAuth1UserHandler, API
                auth = OAuth1UserHandler(
                    TWITTER_CONSUMER_KEY,
                    TWITTER_CONSUMER_SECRET,
                    TWITTER_ACCESS_TOKEN,
                    TWITTER_ACCESS_SECRET
                )
                legacy_api = API(auth)
                media = legacy_api.media_upload(media_path)
                
                # Post with media using v2 API
                response = self.twitter_client.create_tweet(
                    text=text,
                    media_ids=[media.media_id]
                )
            else:
                # Text-only tweet
                response = self.twitter_client.create_tweet(text=text)
                
            logger.info(f"🐦 Tweet posted successfully! ID: {response.data['id']}")
            return True
            
        except TweepyException as e:
            logger.error(f"❌ Twitter API error: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error posting to Twitter: {e}")
            return False
        finally:
            # Clean up downloaded media
            if media_path and os.path.exists(media_path):
                try:
                    os.remove(media_path)
                    logger.info("🧹 Cleaned up temporary media file")
                except Exception as e:
                    logger.warning(f"⚠️ Could not delete media file: {e}")

    async def post_text_to_twitter(self, text):
        """Post text-only tweet"""
        try:
            response = self.twitter_client.create_tweet(text=text)
            logger.info(f"📝 Text-only tweet posted! ID: {response.data['id']}")
            return True
        except Exception as e:
            logger.error(f"❌ Error posting text-only tweet: {e}")
            return False

    async def stop(self):
        """Stop the client"""
        if self.client:
            await self.client.disconnect()
            logger.info("🛑 Second Channel to Twitter bot stopped")

async def start_second_channel_to_twitter():
    """Start the second channel to Twitter bot"""
    bot = SecondChannelToTwitter()
    try:
        await bot.start()
    except KeyboardInterrupt:
        await bot.stop()
    except Exception as e:
        logger.error(f"❌ Bot crashed: {e}")
        await bot.stop()

def run_second_channel_to_twitter():
    """Run the second channel to Twitter bot"""
    logger.info("🚀 Starting Second Channel to Twitter Bot...")
    asyncio.run(start_second_channel_to_twitter())

if __name__ == "__main__":
    run_second_channel_to_twitter()
