import logging
import re
import os
from aiohttp import web
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

async def health_check(request):
    """Health check endpoint for Koyeb"""
    return web.Response(text="Bot is running!")

async def start_http_server(health_check_func):
    """Start HTTP server for health checks"""
    http_app = web.Application()
    http_app.router.add_get('/', health_check_func)
    http_app.router.add_get('/health', health_check_func)
    
    runner = web.AppRunner(http_app)
    await runner.setup()
    
    port = int(os.environ.get('PORT', 8000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logger.info(f"HTTP server started on port {port}")
    return runner, site

def is_admin_user(user_id, admin_ids):
    """Check if user is admin"""
    return user_id in admin_ids

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_ids):
    """Check if user is admin and send access denied message if not"""
    try:
        if hasattr(update, 'effective_user'):
            user_id = update.effective_user.id
        elif hasattr(update, 'message') and update.message:
            user_id = update.message.from_user.id
        elif hasattr(update, 'callback_query') and update.callback_query:
            user_id = update.callback_query.from_user.id
        else:
            user_id = update.from_user.id if hasattr(update, 'from_user') else None
        
        if not user_id or not is_admin_user(user_id, admin_ids):
            if hasattr(update, 'message') and update.message:
                await update.message.reply_text(
                    "🚫 **Access Denied!**\n\n"
                    "You are not authorized to use this bot.\n"
                    "This bot is restricted to administrators only."
                )
            elif hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.message.reply_text(
                    "🚫 **Access Denied!**\n\n"
                    "You are not authorized to use this bot.\n"
                    "This bot is restricted to administrators only."
                )
            return False
        return True
    except Exception as e:
        logger.error(f"Error in admin check: {e}")
        return False

def clean_text(text):
    """Remove last 3 lines and clean text"""
    if not text:
        return text

    lines = text.split('\n')
    if len(lines) > 3:
        lines = lines[:-3]

    cleaned_text = '\n'.join(lines)
    hidden_link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    cleaned_text = re.sub(hidden_link_pattern, r'\1', cleaned_text)
    cleaned_text = cleaned_text.replace('📲 @twittervid_bot', '').strip()

    return cleaned_text
