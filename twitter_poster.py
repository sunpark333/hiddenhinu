import logging
import os
import re
import asyncio
from tweepy import Client as TwitterClient, OAuth1UserHandler, API
from tweepy.errors import TweepyException
from config import TWITTER_BEARER_TOKEN, TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET

logger = logging.getLogger(__name__)

class SimpleTwitterPoster:
    def __init__(self):
        self.twitter_client = None
        self.is_running = False
        
        # Twitter configuration
        self.config = {
            'MAX_TWITTER_LENGTH': 280,
            'SKIP_LONG_POSTS': True,
            'REMOVE_URLS': True,
            'TRIM_EXTRA_SPACES': True,
        }

    async def initialize(self):
        """Initialize Twitter client only"""
        try:
            logger.info("Initializing Simple Twitter Poster...")
            
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
                self.is_running = True
            else:
                logger.error("Twitter credentials missing, Twitter poster disabled")
                self.is_running = False
                
        except Exception as e:
            logger.error(f"Failed to initialize Twitter poster: {str(e)}")
            self.is_running = False

    def process_text(self, text):
        """Process text for Twitter"""
        if not text:
            return ""
            
        processed_text = text
        
        # Remove URLs
        if self.config['REMOVE_URLS']:
            processed_text = re.sub(r'http\S+|www\S+|https\S+', '', processed_text, flags=re.MULTILINE)
        
        # Trim extra spaces
        if self.config['TRIM_EXTRA_SPACES']:
            processed_text = re.sub(r'\s+', ' ', processed_text).strip()
        
        return processed_text

    async def post_to_twitter(self, text, media_path=None):
        """Post to Twitter"""
        try:
            if not self.twitter_client or not self.is_running:
                logger.warning("Twitter client not available")
                return False

            processed_text = self.process_text(text)
            
            # Check length
            if self.config['SKIP_LONG_POSTS'] and len(processed_text) > self.config['MAX_TWITTER_LENGTH']:
                logger.warning(f"Message too long for Twitter ({len(processed_text)} chars)")
                return False

            media_ids = []
            if media_path and os.path.exists(media_path):
                try:
                    # Upload media using v1.1 API
                    auth = OAuth1UserHandler(
                        TWITTER_CONSUMER_KEY,
                        TWITTER_CONSUMER_SECRET,
                        TWITTER_ACCESS_TOKEN,
                        TWITTER_ACCESS_SECRET
                    )
                    legacy_api = API(auth)
                    media = legacy_api.media_upload(media_path)
                    media_ids = [media.media_id]
                    logger.info(f"Media uploaded to Twitter, ID: {media.media_id}")
                except Exception as e:
                    logger.error(f"Error uploading media: {str(e)}")

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

    async def stop(self):
        """Stop Twitter poster"""
        logger.info("Stopping Simple Twitter Poster...")
        self.is_running = False

# Singleton instance
simple_twitter_poster = SimpleTwitterPoster()

async def initialize_twitter_poster():
    """Initialize Twitter poster"""
    await simple_twitter_poster.initialize()

async def stop_twitter_poster():
    """Stop Twitter poster"""
    await simple_twitter_poster.stop()
