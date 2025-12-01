import logging
import asyncio
import sys
from bot_manager import BotManager
from config import TELEGRAM_BOT_TOKEN

# Koyeb logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logger.info("🚀 Twitter Bot Starting...")
    bot = BotManager()
    bot.run()
