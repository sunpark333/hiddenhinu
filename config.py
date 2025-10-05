import os
from dotenv import load_dotenv

load_dotenv()

# Bot configuration settings
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
TELEGRAM_SESSION_STRING = os.getenv('TELEGRAM_SESSION_STRING')
TWITTER_VID_BOT = os.getenv('TWITTER_VID_BOT', 'twittervid_bot')
YOUR_CHANNEL_ID = int(os.getenv('YOUR_CHANNEL_ID', '-1001737011271'))
TIMEZONE = os.getenv('TIMEZONE', 'Asia/Kolkata')
