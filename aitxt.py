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
                return enhanced_text.strip()
            else:
                return original_text
                
        except Exception as e:
            logger.error(f"Error enhancing caption with AI: {str(e)}")
            return original_text

    def _create_enhancement_prompt(self, original_text, twitter_link=None):
        """
        Create prompt for AI enhancement
        """
        prompt = f"""
        Make this Twitter caption more engaging and viral: "{original_text}"
        
        Rules:
        - Make it attention-grabbing  
        - Use 1-2 emojis if relevant
        - Keep original meaning
        - Make it sound like breaking news
        - Return only the enhanced caption
        - Make it look human-generated, not AI
        - The text should work well in italic format
        - DO NOT include #AIEnhanced or any similar AI-related hashtags
        - DO NOT mention that it's AI generated or enhanced
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
            "model": "sonar",  # Using the working model from group.py
            "messages": [
                {
                    "role": "system", 
                    "content": "You are a social media expert who enhances captions to make them more engaging and viral. Always return only the enhanced caption without any explanations and make sure it looks good in italic formatting. Never include #AIEnhanced or any AI-related hashtags."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 100,
            "temperature": 0.7
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, headers=headers, json=payload, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data['choices'][0]['message']['content'].strip()
                        
                        # Clean the response and apply italic formatting
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
        Clean AI response from unwanted formatting and apply italic style
        """
        if not text:
            return text
            
        # Remove quotes if present
        text = text.strip('"\'')
        
        # Remove common AI prefixes and hashtags
        prefixes_to_remove = [
            "Enhanced caption:",
            "Here's the enhanced caption:",
            "Caption:",
            "Enhanced:",
            "News-style caption:",
            "Here is the enhanced caption:",
            "Viral caption:",
            "#AIEnhanced",
            "#AI",
            "#Enhanced"
        ]
        
        for prefix in prefixes_to_remove:
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix):].strip()
            # Also remove if it appears anywhere in the text
            text = text.replace(prefix, "")
        
        # Remove any AI-related hashtags using regex
        ai_hashtags = [r'#AIEnhanced\b', r'#AIGenerated\b', r'#AI\b', r'#EnhancedByAI\b']
        for hashtag in ai_hashtags:
            text = re.sub(hashtag, '', text, flags=re.IGNORECASE)
        
        # Remove any existing markdown formatting
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Remove bold
        text = re.sub(r'\*(.*?)\*', r'\1', text)      # Remove italic
        
        # Clean up extra spaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Apply italic formatting to the entire text
        text = f"*{text}*"
        
        return text.strip()

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
        if if not self.api_key:
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
