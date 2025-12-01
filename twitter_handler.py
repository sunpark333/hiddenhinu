import logging
import os
import re
from tweepy import Client as TwitterClient, OAuth1UserHandler, API
from tweepy.errors import TweepyException
from config import (TWITTER_BEARER_TOKEN, TWITTER_CONSUMER_KEY, 
                   TWITTER_CONSUMER_SECRET, TWITTER_ACCESS_TOKEN, 
                   TWITTER_ACCESS_SECRET, YOUR_SECOND_CHANNEL_ID)

logger = logging.getLogger(__name__)

class TwitterHandler:
    def __init__(self):
        self.twitter_client = None
        self.twitter_poster_enabled = True

    async def initialize(self):
        """Twitter client initialize करें"""
        try:
            if all([TWITTER_BEARER_TOKEN, TWITTER_CONSUMER_KEY, 
                   TWITTER_CONSUMER_SECRET, TWITTER_ACCESS_TOKEN, 
                   TWITTER_ACCESS_SECRET]):
                self.twitter_client = TwitterClient(
                    bearer_token=TWITTER_BEARER_TOKEN,
                    consumer_key=TWITTER_CONSUMER_KEY,
                    consumer_secret=TWITTER_CONSUMER_SECRET,
                    access_token=TWITTER_ACCESS_TOKEN,
                    access_token_secret=TWITTER_ACCESS_SECRET
                )
                logger.info("✅ Twitter client initialized")
                return True
            else:
                logger.warning("❌ Twitter credentials incomplete")
                return False
        except Exception as e:
            logger.error(f"Twitter init failed: {e}")
            return False

    def process_text_for_twitter(self, text):
        """Twitter के लिए text clean करें"""
        if not text:
            return ""
        processed = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)
        processed = re.sub(r'#\w+|@\w+', '', processed)
        return re.sub(r'\s+', ' ', processed).strip()[:277] + "..." if len(processed) > 280 else processed

    async def post_to_twitter(self, text, media_path=None):
        """Twitter पर post करें"""
        try:
            if not self.twitter_client or not self.twitter_poster_enabled:
                return False
            
            processed_text = self.process_text_for_twitter(text)
            media_ids = []
            
            if media_path and os.path.exists(media_path):
                try:
                    auth = OAuth1UserHandler(TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET,
                                           TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)
                    legacy_api = API(auth)
                    if os.path.getsize(media_path) > 50 * 1024 * 1024:
                        logger.warning("Media too large")
                        return False
                    media = legacy_api.media_upload(media_path)
                    media_ids = [media.media_id]
                except Exception as e:
                    logger.error(f"Media upload failed: {e}")
                    return False
            
            if media_ids:
                response = self.twitter_client.create_tweet(text=processed_text, media_ids=media_ids)
            else:
                response = self.twitter_client.create_tweet(text=processed_text)
            
            logger.info(f"✅ Tweet posted: {response.data['id']}")
            return True
        except Exception as e:
            logger.error(f"Twitter post failed: {e}")
            return False

    async def handle_second_channel(self, bot_instance, event):
        """Second channel से Twitter post करें"""
        try:
            if not self.twitter_poster_enabled or not self.twitter_client:
                return
            
            message = event.message
            original_text = message.text or message.caption or ""
            media_path = None
            
            if message.media:
                media_path = await bot_instance.userbot.download_media(
                    message, file=f"temp_twitter_{message.id}"
                )
            
            success = await self.post_to_twitter(original_text, media_path)
            logger.info("✅/❌ Twitter post from 2nd channel")
            
            if media_path and os.path.exists(media_path):
                os.remove(media_path)
        except Exception as e:
            logger.error(f"2nd channel Twitter error: {e}")
