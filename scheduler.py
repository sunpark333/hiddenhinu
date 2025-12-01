import logging
import asyncio
from datetime import datetime, timedelta
from config import TIMEZONE

logger = logging.getLogger(__name__)

class Scheduler:
    """शेड्यूलिंग मैनेजर"""
    
    def __init__(self, twitter_bot):
        self.twitter_bot = twitter_bot
        self.scheduled_mode = False
        self.incremental_schedule_mode = False
        self.fixed_interval_mode = False
        self.scheduled_counter = 0
        self.scheduled_messages = []
    
    def _calculate_schedule_time(self):
        """Calculate schedule time based on mode"""
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
    
    async def start_task_mode(self, is_callback=False):
        """Start 1-hour scheduling mode"""
        self.scheduled_mode = True
        self.incremental_schedule_mode = False
        self.fixed_interval_mode = False
        self.scheduled_counter = 0
        self.scheduled_messages = []

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
        
        return response_text
    
    async def start_task2_mode(self, is_callback=False):
        """Start incremental scheduling mode"""
        self.incremental_schedule_mode = True
        self.scheduled_mode = False
        self.fixed_interval_mode = False
        self.scheduled_counter = 0
        self.scheduled_messages = []

        now = datetime.now(TIMEZONE)
        first_schedule_time = now + timedelta(hours=2)

        response_text = (
            "⏱️ **Now Send Mode Activated!**\n\n"
            f"⏰ First video: {first_schedule_time.strftime('%Y-%m-%d %H:%M')} IST\n"
            f"🕐 Next intervals: +2h, +3h, +4h...\n\n"
            "❌ Use /endtask to stop scheduled posting."
        )
        
        return response_text
    
    async def start_task3_mode(self, is_callback=False):
        """Start 2-hour fixed interval mode"""
        self.fixed_interval_mode = True
        self.scheduled_mode = False
        self.incremental_schedule_mode = False
        self.scheduled_counter = 0
        self.scheduled_messages = []

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
        
        return response_text
    
    async def end_task_mode(self):
        """End all scheduling modes"""
        self.scheduled_mode = False
        self.incremental_schedule_mode = False
        self.fixed_interval_mode = False

        response_text = (
            "🚫 **Scheduled Mode Deactivated!**\n\n"
            "✅ Videos will now be posted immediately.\n"
            f"📊 Total {self.scheduled_counter} videos were scheduled.\n\n"
            "🎯 Use commands to start scheduling again:"
        )

        self.scheduled_counter = 0
        self.scheduled_messages = []
        
        return response_text
    
    def increment_counter(self):
        """Increment schedule counter"""
        self.scheduled_counter += 1
    
    def reset_counter(self):
        """Reset schedule counter"""
        self.scheduled_counter = 0
