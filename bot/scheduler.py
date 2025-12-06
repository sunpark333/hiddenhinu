"""
Scheduler - Task scheduling functionality
"""

import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes

from config import TIMEZONE

logger = logging.getLogger(__name__)


class ScheduleManager:
    def __init__(self, bot):
        self.bot = bot

    def _calculate_schedule_time(self):
        """Calculate schedule time based on mode"""
        now = datetime.now(TIMEZONE)

        if self.bot.scheduled_mode:
            scheduled_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
            if scheduled_time < now:
                scheduled_time += timedelta(days=1)
            scheduled_time += timedelta(hours=self.bot.scheduled_counter)

        elif self.bot.incremental_schedule_mode:
            scheduled_time = now + timedelta(hours=self.bot.scheduled_counter + 2)

        elif self.bot.fixed_interval_mode:
            scheduled_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
            if scheduled_time < now:
                scheduled_time += timedelta(days=1)
            scheduled_time += timedelta(hours=2 * self.bot.scheduled_counter)

        else:
            scheduled_time = now

        return scheduled_time

    async def start_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start scheduled posting mode"""
        if not await self.bot.handlers.admin_only(update, context):
            return

        await self._start_task_common(update, context)

    async def start_task_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Start scheduled posting mode from callback"""
        await self._start_task_common(query, context, is_callback=True)

    async def start_task2(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start incremental scheduled posting mode"""
        if not await self.bot.handlers.admin_only(update, context):
            return

        await self._start_task2_common(update, context)

    async def start_task2_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Start incremental scheduled posting mode from callback"""
        await self._start_task2_common(query, context, is_callback=True)

    async def start_task3(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start fixed 2-hour interval scheduling mode"""
        if not await self.bot.handlers.admin_only(update, context):
            return

        await self._start_task3_common(update, context)

    async def start_task3_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Start fixed 2-hour interval scheduling mode from callback"""
        await self._start_task3_common(query, context, is_callback=True)

    async def _start_task_common(self, update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
        """Common function for starting task mode"""
        self.bot.scheduled_mode = True
        self.bot.incremental_schedule_mode = False
        self.bot.fixed_interval_mode = False
        self.bot.scheduled_counter = 0
        self.bot.scheduled_messages = []

        now = datetime.now(TIMEZONE)
        first_schedule_time = now.replace(hour=7, minute=0, second=0, microsecond=0)

        if first_schedule_time < now:
            first_schedule_time += timedelta(days=1)

        response_text = (
            "📅 **1 Hour Mode Activated!**\n\n"
            f"⏰ First video: {first_schedule_time.strftime('%Y-%m-%d %H:%M')} IST\n"
            f"🕐 Each new video: +1 hour interval\n\n"
            "❌ Use /endtask to stop scheduled posting."
        )

        if is_callback:
            await update.edit_message_text(response_text)
        else:
            await update.message.reply_text(response_text)

    async def _start_task2_common(self, update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
        """Common function for starting task2 mode"""
        self.bot.incremental_schedule_mode = True
        self.bot.scheduled_mode = False
        self.bot.fixed_interval_mode = False
        self.bot.scheduled_counter = 0
        self.bot.scheduled_messages = []

        now = datetime.now(TIMEZONE)
        first_schedule_time = now + timedelta(hours=2)

        response_text = (
            "⏱️ **Now Send Mode Activated!**\n\n"
            f"⏰ First video: {first_schedule_time.strftime('%Y-%m-%d %H:%M')} IST\n"
            f"🕐 Next intervals: +2h, +3h, +4h...\n\n"
            "❌ Use /endtask to stop scheduled posting."
        )

        if is_callback:
            await update.edit_message_text(response_text)
        else:
            await update.message.reply_text(response_text)

    async def _start_task3_common(self, update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
        """Common function for starting task3 mode"""
        self.bot.fixed_interval_mode = True
        self.bot.scheduled_mode = False
        self.bot.incremental_schedule_mode = False
        self.bot.scheduled_counter = 0
        self.bot.scheduled_messages = []

        now = datetime.now(TIMEZONE)
        first_schedule_time = now.replace(hour=7, minute=0, second=0, microsecond=0)

        if first_schedule_time < now:
            first_schedule_time += timedelta(days=1)

        second_schedule_time = first_schedule_time + timedelta(hours=2)
        third_schedule_time = first_schedule_time + timedelta(hours=4)

        response_text = (
            "🕑 **2 Hour Mode Activated!**\n\n"
            f"⏰ Schedule starts at: 7:00 AM IST\n"
            f"🕐 Fixed interval: Every 2 hours\n\n"
            f"📅 Example schedule:\n"
            f"• 1st post: {first_schedule_time.strftime('%H:%M')} IST\n"
            f"• 2nd post: {second_schedule_time.strftime('%H:%M')} IST\n"
            f"• 3rd post: {third_schedule_time.strftime('%H:%M')} IST\n\n"
            "❌ Use /endtask to stop scheduled posting."
        )

        if is_callback:
            await update.edit_message_text(response_text)
        else:
            await update.message.reply_text(response_text)

    async def end_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """End scheduled posting mode"""
        if not await self.bot.handlers.admin_only(update, context):
            return

        self.bot.scheduled_mode = False
        self.bot.incremental_schedule_mode = False
        self.bot.fixed_interval_mode = False

        await update.message.reply_text(
            "🚫 **Scheduled Mode Deactivated!**\n\n"
            "✅ Videos will now be posted immediately.\n"
            f"📊 Total {self.bot.scheduled_counter} videos were scheduled.\n\n"
            "🎯 Use commands to start scheduling again:"
        )

        self.bot.scheduled_counter = 0
        self.bot.scheduled_messages = []
