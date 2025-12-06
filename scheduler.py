import logging
from datetime import datetime, timedelta
from config import TIMEZONE
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

class Scheduler:
    def __init__(self):
        self.scheduled_mode = False
        self.incremental_schedule_mode = False
        self.fixed_interval_mode = False
        self.scheduled_counter = 0
        self.scheduled_messages = []

    async def get_next_schedule_time(self):
        """Calculate schedule time based on mode"""
        if not (self.scheduled_mode or self.incremental_schedule_mode or self.fixed_interval_mode):
            return None

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

    async def start_scheduled_mode(self):
        """Start scheduled posting mode"""
        self.scheduled_mode = True
        self.incremental_schedule_mode = False
        self.fixed_interval_mode = False
        self.scheduled_counter = 0
        self.scheduled_messages = []
        logger.info("1 Hour Mode Activated")

    async def start_incremental_mode(self):
        """Start incremental scheduled posting mode"""
        self.incremental_schedule_mode = True
        self.scheduled_mode = False
        self.fixed_interval_mode = False
        self.scheduled_counter = 0
        self.scheduled_messages = []
        logger.info("Now Send Mode Activated")

    async def start_fixed_interval_mode(self):
        """Start fixed 2-hour interval scheduling mode"""
        self.fixed_interval_mode = True
        self.scheduled_mode = False
        self.incremental_schedule_mode = False
        self.scheduled_counter = 0
        self.scheduled_messages = []
        logger.info("2 Hour Mode Activated")

    async def end_scheduling(self):
        """End all scheduling modes"""
        count = self.scheduled_counter
        self.scheduled_mode = False
        self.incremental_schedule_mode = False
        self.fixed_interval_mode = False
        self.scheduled_counter = 0
        self.scheduled_messages = []
        logger.info("Scheduling mode deactivated")
        return count

    async def increment_counter(self):
        """Increment scheduled counter"""
        self.scheduled_counter += 1
        logger.info(f"Scheduled counter incremented to: {self.scheduled_counter}")

    # Handler methods for Telegram commands
    async def start_scheduled_mode_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Telegram command handler for starting scheduled mode"""
        await self.start_scheduled_mode()
        await update.message.reply_text(
            "📅 **1 Hour Mode Activated!**\n\n"
            f"⏰ First video: 7:00 AM IST (next day if past 7 AM)\n"
            f"🕐 Each new video: +1 hour interval\n\n"
            "❌ Use /endtask to stop scheduled posting."
        )

    async def start_incremental_mode_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Telegram command handler for starting incremental mode"""
        await self.start_incremental_mode()
        await update.message.reply_text(
            "⏱️ **Now Send Mode Activated!**\n\n"
            f"⏰ First video: +2 hours from now\n"
            f"🕐 Next intervals: +3h, +4h, +5h...\n\n"
            "❌ Use /endtask to stop scheduled posting."
        )

    async def start_fixed_interval_mode_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Telegram command handler for starting fixed interval mode"""
        await self.start_fixed_interval_mode()
        await update.message.reply_text(
            "🕑 **2 Hour Mode Activated!**\n\n"
            f"⏰ Schedule starts at: 7:00 AM IST\n"
            f"🕐 Fixed interval: Every 2 hours\n\n"
            "❌ Use /endtask to stop scheduled posting."
        )
