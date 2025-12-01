import logging
import os
import re
from tweepy import Client as TwitterClient, OAuth1UserHandler, API
from tweepy.errors import TweepyException
from config import TWITTER_BEARER_TOKEN, TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET

logger = logging.getLogger(__name__)

class TwitterPoster:
    def __init__(self):
        self.twitter_poster_enabled = True
        self.twitter_client = None

    async def initialize_twitter_client(self):
        """Initialize Twitter client"""
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
                logger.info("Twitter client initialized successfully")
                return True
            else:
                logger.warning("Twitter credentials not complete, Twitter posting disabled")
                return False
        except Exception as e:
            logger.error(f"Failed to initialize Twitter client: {str(e)}")
            return False

    def process_text_for_twitter(self, text):
        """Process text for Twitter posting"""
        if not text:
            return ""
            
        processed_text = text
        
        # Remove URLs
        processed_text = re.sub(r'http\S+|www\S+|https\S+', '', processed_text, flags=re.MULTILINE)
        
        # Remove hashtags and mentions if needed
        processed_text = re.sub(r'#\w+', '', processed_text)
        processed_text = re.sub(r'@\w+', '', processed_text)
        
        # Trim extra spaces
        processed_text = re.sub(r'\s+', ' ', processed_text).strip()
        
        return processed_text

    async def post_to_twitter(self, text, media_path=None):
        """Post content to Twitter"""
        try:
            if not self.twitter_client or not self.twitter_poster_enabled:
                return False

            processed_text = self.process_text_for_twitter(text)
            
            # Check length (280 characters for Twitter)
            if len(processed_text) > 280:
                logger.warning(f"Message too long for Twitter ({len(processed_text)} chars), trimming")
                processed_text = processed_text[:277] + "..."
            
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
                    
                    # Check file size
                    file_size = os.path.getsize(media_path) / (1024 * 1024)
                    if file_size > 50:
                        logger.warning(f"Media file too large ({file_size:.2f}MB)")
                        return False
                    
                    media = legacy_api.media_upload(media_path)
                    media_ids = [media.media_id]
                    logger.info(f"Media uploaded to Twitter, ID: {media.media_id}")
                except Exception as e:
                    logger.error(f"Error uploading media to Twitter: {str(e)}")
                    return False

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
