import os
import pytz
from dotenv import load_dotenv

load_dotenv()

# Bot configuration settings
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
TELEGRAM_SESSION_STRING = os.getenv('TELEGRAM_SESSION_STRING')
TWITTER_VID_BOT = os.getenv('TWITTER_VID_BOT', 'twittervid_bot')
YOUR_CHANNEL_ID = int(os.getenv('YOUR_CHANNEL_ID', ''))
YOUR_SECOND_CHANNEL_ID = int(os.getenv('YOUR_SECOND_CHANNEL_ID', ''))
TIMEZONE = pytz.timezone(os.getenv('TIMEZONE', 'Asia/Kolkata'))
ADMIN_IDS = [int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]
PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY', '')

# Twitter Configuration
TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN', '')
TWITTER_CONSUMER_KEY = os.getenv('TWITTER_CONSUMER_KEY', '')
TWITTER_CONSUMER_SECRET = os.getenv('TWITTER_CONSUMER_SECRET', '')
TWITTER_ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN', '')
TWITTER_ACCESS_SECRET = os.getenv('TWITTER_ACCESS_SECRET', '')

# Watermark Configuration
WATERMARK_LOGO_PATH = "assets/watermark.png"  # Path to your logo file
WATERMARK_POSITION = "top-left"  # top-left, top-right, bottom-left, bottom-right, center
WATERMARK_OPACITY = 180  # 0-255 (0=transparent, 255=opaque)
WATERMARK_ENABLED = True  # Set to False to disable watermark
