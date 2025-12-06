"""
Utility functions - Text processing and helper functions
"""

import logging
import re

logger = logging.getLogger(__name__)


class TextUtils:
    """Utility class for text processing"""

    @staticmethod
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

    @staticmethod
    def process_text_for_twitter(text):
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

    @staticmethod
    def truncate_text(text, max_length=280, suffix="..."):
        """Truncate text to max length"""
        if len(text) <= max_length:
            return text

        truncated = text[:max_length - len(suffix)]
        return truncated + suffix

    @staticmethod
    def is_valid_twitter_link(text):
        """Check if text contains valid Twitter link"""
        return any(domain in text for domain in ['twitter.com', 'x.com'])

    @staticmethod
    def extract_urls(text):
        """Extract URLs from text"""
        url_pattern = r'https?://[^\s]+'
        return re.findall(url_pattern, text)

    @staticmethod
    def remove_urls(text):
        """Remove all URLs from text"""
        return re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)

    @staticmethod
    def extract_mentions(text):
        """Extract mentions from text"""
        mention_pattern = r'@\w+'
        return re.findall(mention_pattern, text)

    @staticmethod
    def extract_hashtags(text):
        """Extract hashtags from text"""
        hashtag_pattern = r'#\w+'
        return re.findall(hashtag_pattern, text)
