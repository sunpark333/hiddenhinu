"""
PROJECT STRUCTURE DOCUMENTATION
Twitter Video Bot - Modular Architecture
"""

PROJECT STRUCTURE:
==================

twitter_bot/
├── __init__.py              # Package initialization
├── core.py                  # Core bot logic and initialization
├── handlers.py              # Message and command handlers
├── twitter.py               # Twitter API integration
├── scheduler.py             # Task scheduling functionality
├── utils.py                 # Utility functions and helpers
└── main.py                  # Entry point

FILE DESCRIPTIONS:
==================

1. __init__.py
   - Package initialization file
   - Exports TwitterBot class for external imports
   
2. core.py (CORE FUNCTIONALITY)
   - TwitterBot class - Main bot class
   - __init__() - Initialize all components
   - initialize_userbot() - Setup Telegram userbot
   - initialize_twitter_client() - Setup Twitter API client
   - start_http_server() - Start health check server
   - start_polling() - Start bot polling
   - shutdown() - Graceful shutdown
   - run_async() - Async main function
   - run() - Main entry with retry logic

3. handlers.py (MESSAGE HANDLERS)
   - MessageHandlers class
   - admin_only() - Admin authorization
   - start_command() - /start command
   - button_handler() - Button click callbacks
   - process_link() - Process Twitter links
   - handle_twittervid_message() - Handle video bot responses
   - handle_second_channel_message() - Handle second channel posts
   - _process_received_video() - Process and send videos
   - _get_enhanced_caption() - AI caption enhancement
   - setup_handlers() - Setup event listeners
   - add_all_handlers() - Add all command handlers
   - health_check() - HTTP health endpoint

4. twitter.py (TWITTER INTEGRATION)
   - TwitterPoster class
   - initialize_twitter_client() - Setup Twitter client
   - process_text_for_twitter() - Text processing for Twitter
   - post_to_twitter() - Post to Twitter
   - twitter_poster_command() - /twitter_poster command

5. scheduler.py (SCHEDULING)
   - ScheduleManager class
   - _calculate_schedule_time() - Calculate posting time
   - start_task() - /task command (1-hour intervals)
   - start_task2() - /task2 command (incremental)
   - start_task3() - /task3 command (fixed intervals)
   - end_task() - /endtask command
   - *_common() methods - Common scheduling logic
   - *_callback() methods - Handle button callbacks

6. utils.py (UTILITIES)
   - TextUtils class
   - clean_text() - Remove formatting and clean text
   - process_text_for_twitter() - Prepare text for Twitter
   - truncate_text() - Truncate to max length
   - is_valid_twitter_link() - Validate Twitter URLs
   - extract_urls() - Extract URLs from text
   - remove_urls() - Remove all URLs
   - extract_mentions() - Extract @mentions
   - extract_hashtags() - Extract #hashtags

7. main.py (ENTRY POINT)
   - main() - Application entry point
   - Logging configuration
   - Bot initialization and run


COMPONENT RELATIONSHIPS:
========================

TwitterBot (core.py)
    ├── TwitterPoster (twitter.py)
    ├── MessageHandlers (handlers.py)
    ├── ScheduleManager (scheduler.py)
    └── TextUtils (utils.py)


COMMAND FLOW:
=============

1. User sends /start
   → handlers.start_command()
   → Display buttons with scheduling modes

2. User selects scheduling mode (1hour/now send/2hour)
   → handlers.button_handler()
   → scheduler.start_task*_callback()
   → scheduler._start_task*_common()

3. User sends Twitter link
   → handlers.process_link()
   → Send to twittervid_bot
   → Wait for response

4. twittervid_bot responds
   → handlers.handle_twittervid_message()
   → Quality selection
   → Video download

5. Video received
   → handlers._process_received_video()
   → Send to both channels
   → Enhance caption with AI for second channel
   → Post to Twitter if enabled


FEATURES:
=========

✅ Telegram Bot
   - Commands: /start, /task, /task2, /task3, /endtask, /twitter_poster
   - Admin-only access
   - Button callbacks
   - Link processing

✅ Twitter Video Download
   - Integration with @twittervid_bot
   - Quality selection
   - Automatic video processing

✅ Scheduling
   - 1-hour intervals
   - Incremental intervals
   - Fixed 2-hour intervals
   - Channel posting

✅ Twitter Posting
   - Auto-post to Twitter from second channel
   - Media upload
   - Text processing
   - Character limit handling

✅ AI Caption Enhancement
   - Enhance captions for second channel
   - Fallback to original if AI unavailable

✅ Server
   - Health check endpoint
   - Koyeb deployment support
   - Graceful shutdown


USAGE:
======

# Install dependencies
pip install -r requirements.txt

# Setup config.py with your credentials

# Run bot
python main.py

# Or run as module
python -m twitter_bot


IMPORTS IN EACH FILE:
=====================

core.py imports from:
  - handlers (MessageHandlers)
  - twitter (TwitterPoster)
  - scheduler (ScheduleManager)
  - utils (TextUtils)

handlers.py imports from:
  - utils (TextUtils)

twitter.py imports:
  - Re, os modules (no internal imports)

scheduler.py imports:
  - No internal imports

utils.py imports:
  - Re module only (no internal imports)

main.py imports from:
  - twitter_bot (TwitterBot) or core


KEY POINTS:
===========

1. Every file is INDEPENDENT and MODULAR
2. No circular imports
3. All original code is preserved (no modifications)
4. Components communicate through TwitterBot instance
5. Easy to extend or modify individual modules
6. Clean separation of concerns
