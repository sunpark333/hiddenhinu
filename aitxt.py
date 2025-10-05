import logging
import os
import aiohttp
import json
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
        Please enhance this Twitter/X post caption to make it more engaging, professional, and news-style. 
        Keep the core meaning but make it more compelling for a social media audience.
        
        Original caption: "{original_text}"
        
        Guidelines:
        1. Make it more engaging and click-worthy
        2. Use emojis sparingly but effectively
        3. Keep it concise (1-2 lines ideal)
        4. Maintain the original intent
        5. Add relevant hashtags if appropriate
        6. Make it sound like breaking news or important update
        7. Keep the language natural and viral-worthy
        
        Return only the enhanced caption without any explanations or additional text.
        """
        
        if twitter_link:
            prompt += f"\n\nOriginal Twitter link: {twitter_link}"
            
        return prompt

    async def _call_perplexity_api(self, prompt):
        """
        Make API call to Perplexity AI
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "sonar-medium-online",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a social media expert who enhances captions to make them more engaging, viral, and news-style while maintaining original meaning."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 150,
            "temperature": 0.7
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, headers=headers, json=payload, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['choices'][0]['message']['content'].strip()
                    else:
                        error_text = await response.text()
                        logger.error(f"Perplexity API error: {response.status} - {error_text}")
                        return None
        except asyncio.TimeoutError:
            logger.error("Perplexity API request timeout")
            return None
        except Exception as e:
            logger.error(f"Perplexity API request failed: {str(e)}")
            return None

    def is_meaningful_text(self, text):
        """
        Check if text is meaningful enough to enhance
        """
        if not text:
            return False
            
        # Remove URLs and special characters for length check
        import re
        clean_text = re.sub(r'http\S+', '', text)
        clean_text = re.sub(r'[^\w\s]', '', clean_text)
        
        # Check if we have substantial text
        words = clean_text.strip().split()
        return len(words) >= 3 and len(clean_text.strip()) >= 15
