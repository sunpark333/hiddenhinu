import logging
import aiohttp
import json
import re
from config import PERPLEXITY_API_KEY

logger = logging.getLogger(__name__)

class AICaptionEnhancer:
    def __init__(self):
        self.api_key = PERPLEXITY_API_KEY
        self.base_url = "https://api.perplexity.ai/chat/completions"
        
    async def enhance_caption(self, original_text, twitter_link=None):
        """
        Enhance caption using Perplexity AI to make it more engaging and news-style
        """
        if not self.api_key:
            logger.warning("Perplexity API key not found. Returning original caption.")
            return original_text
            
        if not original_text or len(original_text.strip()) < 10:
            return original_text

        try:
            prompt = self._create_enhancement_prompt(original_text, twitter_link)
            enhanced_text = await self._call_perplexity_api(prompt)
            
            if enhanced_text and len(enhanced_text.strip()) > 20:
                # Trim to Telegram limit (1024 characters)
                trimmed_text = self._trim_to_telegram_limit(enhanced_text.strip())
                return trimmed_text
            else:
                return original_text
                
        except Exception as e:
            logger.error(f"Error enhancing caption with AI: {str(e)}")
            return original_text

    def _create_enhancement_prompt(self, original_text, twitter_link=None):
        """
        Create prompt for AI enhancement with shorter content
        """
        prompt = f"""
        Original text: "{original_text}"

        Create a SHORT and ENGAGING social media post for Telegram:

        REQUIREMENTS:
        - MAX 3-4 lines total (including both English and Hindi)
        - English: 1-2 short lines only
        - Hindi: 1 short line only  
        - Total character count MUST be under 900 characters
        - Use simple, concise language
        - Add 1-2 emojis max
        - Hindi should be brief and different from English
        - Sound natural and human-written

        FORMAT:
        [1-2 short English lines]

        🌐 [One very short Hindi line]

        Keep it VERY SHORT and impactful!
        """
        
        return prompt

    async def _call_perplexity_api(self, prompt):
        """
        Make API call to Perplexity AI using the working "sonar" model
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "sonar",
            "messages": [
                {
                    "role": "system", 
                    "content": "You create very short, concise social media posts that are under 900 characters. You write in a natural, human-like tone. Keep English content to 1-2 lines and Hindi to just 1 line. Always stay within character limits."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 150,  # Reduced tokens for shorter output
            "temperature": 0.7
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, headers=headers, json=payload, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data['choices'][0]['message']['content'].strip()
                        
                        # Clean the response
                        content = self._clean_ai_response(content)
                        return content
                        
                    else:
                        error_text = await response.text()
                        logger.error(f"Perplexity API error: {response.status} - {error_text}")
                        return None
                        
        except aiohttp.ClientError as e:
            logger.error(f"Perplexity API request failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in Perplexity API call: {str(e)}")
            return None

    def _clean_ai_response(self, text):
        """
        Clean AI response and ensure short length
        """
        if not text:
            return text
            
        # Remove quotes if present
        text = text.strip('"\'')
        
        # Remove common AI prefixes
        prefixes_to_remove = [
            "Here's the short post:",
            "Short post:",
            "Social media post:",
            "Here is the post:",
            "Created post:",
            "Post content:",
            "Here's the concise post:"
        ]
        
        for prefix in prefixes_to_remove:
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix):].strip()
                
        # Remove markdown formatting
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        
        # Ensure proper spacing but keep it compact
        text = re.sub(r'\n\s*\n', '\n', text)
        
        return text.strip()

    def _trim_to_telegram_limit(self, text):
        """
        Trim text to Telegram's caption limit (1024 characters)
        """
        TELEGRAM_MAX_LENGTH = 1024
        
        if len(text) <= TELEGRAM_MAX_LENGTH:
            return text
            
        # Trim to maximum length
        trimmed = text[:TELEGRAM_MAX_LENGTH - 3] + "..."
        
        # Try to trim at sentence end if possible
        last_period = trimmed.rfind('.')
        last_newline = trimmed.rfind('\n')
        
        if last_period > TELEGRAM_MAX_LENGTH * 0.7:  # If we have a period in last 30%
            trimmed = trimmed[:last_period + 1]
        elif last_newline > TELEGRAM_MAX_LENGTH * 0.7:
            trimmed = trimmed[:last_newline]
            
        logger.warning(f"Caption trimmed from {len(text)} to {len(trimmed)} characters")
        return trimmed

    def is_meaningful_text(self, text):
        """
        Check if text is meaningful enough to enhance
        """
        if not text:
            return False
            
        # Remove URLs and special characters for length check
        clean_text = re.sub(r'http\S+', '', text)
        clean_text = re.sub(r'[^\w\s]', '', clean_text)
        
        # Check if we have substantial text
        words = clean_text.strip().split()
        return len(words) >= 3 and len(clean_text.strip()) >= 15

    async def test_connection(self):
        """
        Test API connection using the working "sonar" model
        """
        if not self.api_key:
            return False, "No API key provided"
            
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "sonar",
                "messages": [{"role": "user", "content": "Say 'OK' if you can see this message."}],
                "max_tokens": 10
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, headers=headers, json=payload, timeout=10) as response:
                    if response.status == 200:
                        return True, "API connection successful with 'sonar' model"
                    else:
                        error_text = await response.text()
                        return False, f"API error: {response.status} - {error_text}"
                        
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
