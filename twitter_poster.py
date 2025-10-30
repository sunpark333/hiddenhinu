import logging
import os
import re
import asyncio
from urllib.request import urlretrieve
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from tweepy import Client as TwitterClient
from tweepy.errors import TweepyException
from config import TELEGRAM_SESSION_STRING, API_ID, API_HASH, YOUR_SECOND_CHANNEL_ID, TWITTER_BEARER_TOKEN, TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET

logger = logging.getLogger(__name__)

class TwitterPoster:
    def __init__(self):
        self.telegram_client = None
        self.twitter_client = None
        self.is_running = False
        
        # Twitter पोस्टिंग कॉन्फ़िगरेशन
        self.config = {
            'MAX_TWITTER_LENGTH': 280,
            'SKIP_LONG_POSTS': True,
            'REMOVE_URLS': True,
            'REMOVE_HASHTAGS': False,
            'REMOVE_MENTIONS': False,
            'ADD_PREFIX': '📢 ',
            'ADD_SUFFIX': '',
            'REMOVE_EMOJIS': False,
            'TRIM_EXTRA_SPACES': True,
            'DOWNLOAD_MEDIA': True,
            'MAX_MEDIA_SIZE_MB': 50
        }

    async def initialize(self):
        """Telegram और Twitter क्लाइंट को इनिशियलाइज़ करें"""
        try:
            logger.info("Initializing Twitter Poster...")
            
            # Telegram क्लाइंट इनिशियलाइज़ करें
            session = StringSession(TELEGRAM_SESSION_STRING)
            self.telegram_client = TelegramClient(
                session=session,
                api_id=int(API_ID),
                api_hash=API_HASH
            )
            
            await self.telegram_client.start()
            logger.info("Telegram client started for Twitter poster")
            
            # Twitter क्लाइंट इनिशियलाइज़ करें
            self.twitter_client = TwitterClient(
                bearer_token=TWITTER_BEARER_TOKEN,
                consumer_key=TWITTER_CONSUMER_KEY,
                consumer_secret=TWITTER_CONSUMER_SECRET,
                access_token=TWITTER_ACCESS_TOKEN,
                access_token_secret=TWITTER_ACCESS_SECRET
            )
            
            logger.info("Twitter client initialized successfully")
            
            # इवेंट हैंडलर रजिस्टर करें
            self.telegram_client.add_event_handler(
                self.handle_second_channel_message,
                events.NewMessage(chats=YOUR_SECOND_CHANNEL_ID)
            )
            
            self.is_running = True
            logger.info(f"Twitter poster started monitoring channel: {YOUR_SECOND_CHANNEL_ID}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Twitter poster: {str(e)}")
            raise

    def process_text(self, text):
        """Twitter के लिए टेक्स्ट को प्रोसेस करें"""
        if not text:
            return ""
            
        processed_text = text
        
        # URLs हटाएं
        if self.config['REMOVE_URLS']:
            processed_text = re.sub(r'http\S+|www\S+|https\S+', '', processed_text, flags=re.MULTILINE)
        
        # हैशटैग हटाएं
        if self.config['REMOVE_HASHTAGS']:
            processed_text = re.sub(r'#\w+', '', processed_text)
        
        # मेंशन हटाएं
        if self.config['REMOVE_MENTIONS']:
            processed_text = re.sub(r'@\w+', '', processed_text)
        
        # इमोजी हटाएं
        if self.config['REMOVE_EMOJIS']:
            emoji_pattern = re.compile("["
                u"\U0001F600-\U0001F64F"  # emoticons
                u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                u"\U0001F680-\U0001F6FF"  # transport & map symbols
                u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                u"\U00002702-\U000027B0"
                u"\U000024C2-\U0001F251"
                "]+", flags=re.UNICODE)
            processed_text = emoji_pattern.sub(r'', processed_text)
        
        # एक्स्ट्रा स्पेस ट्रिम करें
        if self.config['TRIM_EXTRA_SPACES']:
            processed_text = re.sub(r'\s+', ' ', processed_text).strip()
        
        # प्रीफिक्स जोड़ें
        if self.config['ADD_PREFIX']:
            processed_text = f"{self.config['ADD_PREFIX']}{processed_text}"
        
        # सफिक्स जोड़ें
        if self.config['ADD_SUFFIX']:
            processed_text = f"{processed_text}{self.config['ADD_SUFFIX']}"
        
        return processed_text.strip()

    async def handle_second_channel_message(self, event):
        """दूसरे चैनल की नई मैसेज को हैंडल करें"""
        try:
            message = event.message
            logger.info(f"New message from second channel (ID: {message.id})")
            
            # मैसेज टेक्स्ट प्रोसेस करें
            original_text = message.text or message.caption or ""
            processed_text = self.process_text(original_text)
            
            # Twitter पोस्टिंग के लिए चेक करें
            should_post_to_twitter = True
            
            if self.config['SKIP_LONG_POSTS'] and len(processed_text) > self.config['MAX_TWITTER_LENGTH']:
                logger.warning(f"Message too long for Twitter ({len(processed_text)} chars), skipping")
                should_post_to_twitter = False
            
            # Twitter पर पोस्ट करें
            if should_post_to_twitter:
                await self.post_to_twitter(message, processed_text)
            else:
                logger.info("Skipped Twitter posting due to length restrictions")
                
        except Exception as e:
            logger.error(f"Error handling second channel message: {str(e)}")

    async def post_to_twitter(self, message, processed_text):
        """Twitter पर पोस्ट करें"""
        media_path = None
        try:
            # मीडिया डाउनलोड करें (अगर है)
            media_ids = []
            if message.media and self.config['DOWNLOAD_MEDIA']:
                logger.info("Downloading media for Twitter...")
                media_path = await self.download_media(message)
                if media_path:
                    media_ids = await self.upload_media_to_twitter(media_path)
            
            # Twitter पर पोस्ट करें
            if media_ids:
                response = self.twitter_client.create_tweet(
                    text=processed_text,
                    media_ids=media_ids
                )
                logger.info(f"Tweet with media posted successfully! ID: {response.data['id']}")
            else:
                response = self.twitter_client.create_tweet(text=processed_text)
                logger.info(f"Text tweet posted successfully! ID: {response.data['id']}")
                
        except TweepyException as e:
            logger.error(f"Twitter API error: {str(e)}")
        except Exception as e:
            logger.error(f"Error posting to Twitter: {str(e)}")
        finally:
            # टेम्पोररी फाइल्स क्लीन अप करें
            if media_path and os.path.exists(media_path):
                try:
                    os.remove(media_path)
                    logger.info("Temporary media file cleaned up")
                except Exception as e:
                    logger.warning(f"Could not delete temp file: {str(e)}")

    async def download_media(self, message):
        """मीडिया को डाउनलोड करें"""
        try:
            media_path = await self.telegram_client.download_media(
                message,
                file=f"temp_twitter_media_{message.id}"
            )
            
            # फाइल साइज चेक करें
            if media_path and os.path.exists(media_path):
                file_size = os.path.getsize(media_path) / (1024 * 1024)  # MB में
                if file_size > self.config['MAX_MEDIA_SIZE_MB']:
                    logger.warning(f"Media file too large ({file_size:.2f}MB), skipping")
                    os.remove(media_path)
                    return None
            
            return media_path
            
        except Exception as e:
            logger.error(f"Error downloading media: {str(e)}")
            return None

    async def upload_media_to_twitter(self, media_path):
        """मीडिया को Twitter पर अपलोड करें"""
        try:
            # v1.1 API का उपयोग करके मीडिया अपलोड करें
            from tweepy import OAuth1UserHandler, API
            
            auth = OAuth1UserHandler(
                TWITTER_CONSUMER_KEY,
                TWITTER_CONSUMER_SECRET,
                TWITTER_ACCESS_TOKEN,
                TWITTER_ACCESS_SECRET
            )
            legacy_api = API(auth)
            
            media = legacy_api.media_upload(media_path)
            logger.info(f"Media uploaded to Twitter, ID: {media.media_id}")
            
            return [media.media_id]
            
        except Exception as e:
            logger.error(f"Error uploading media to Twitter: {str(e)}")
            return []

    async def start(self):
        """Twitter पोस्टर शुरू करें"""
        try:
            await self.initialize()
            
            # बैकग्राउंड में चलते रहें
            while self.is_running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in Twitter poster: {str(e)}")
            self.is_running = False

    async def stop(self):
        """Twitter पोस्टर बंद करें"""
        logger.info("Stopping Twitter poster...")
        self.is_running = False
        
        if self.telegram_client and self.telegram_client.is_connected():
            await self.telegram_client.disconnect()
            logger.info("Telegram client disconnected for Twitter poster")

# सिंगलटॉन इंस्टेंस
twitter_poster = TwitterPoster()

async def start_twitter_poster():
    """Twitter पोस्टर शुरू करें (मुख्य बॉट से कॉल करें)"""
    await twitter_poster.start()

async def stop_twitter_poster():
    """Twitter पोस्टर बंद करें"""
    await twitter_poster.stop()
