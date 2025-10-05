import os
import logging
import aiohttp
import json
from config import PERPLEXITY_API_KEY

logger = logging.getLogger(__name__)

class TextEnhancer:
    def __init__(self):
        self.api_key = PERPLEXITY_API_KEY
        self.base_url = "https://api.perplexity.ai/chat/completions"
        
    async def enhance_caption(self, original_text, tweet_url=None):
        """
        Enhance caption using Perplexity AI to make it more engaging and news-like
        
        Args:
            original_text (str): Original caption text from tweet
            tweet_url (str): Twitter URL for context (optional)
            
        Returns:
            str: Enhanced caption or original if enhancement fails
        """
        if not self.api_key or self.api_key == "YOUR_PERPLEXITY_API_KEY":
            logger.warning("Perplexity API key not configured. Returning original text.")
            return original_text
            
        if not original_text or len(original_text.strip()) < 10:
            return original_text
            
        try:
            # Prepare the prompt for enhancement
            prompt = self._create_enhancement_prompt(original_text, tweet_url)
            
            # Call Perplexity API
            enhanced_text = await self._call_perplexity_api(prompt)
            
            if enhanced_text and len(enhanced_text.strip()) > 20:
                logger.info("Caption successfully enhanced using Perplexity AI")
                return enhanced_text
            else:
                logger.warning("Enhanced text too short, returning original")
                return original_text
                
        except Exception as e:
            logger.error(f"Error enhancing caption: {str(e)}")
            return original_text
            
    def _create_enhancement_prompt(self, original_text, tweet_url=None):
        """Create enhancement prompt for Perplexity AI"""
        
        base_prompt = f"""
        Please enhance the following social media text to make it more engaging, informative, and professional for a news-style format. Follow these guidelines:

        1. **Keep it concise** (120-250 characters)
        2. **Make it engaging** - use compelling language
        3. **Add context** if needed for better understanding
        4. **Use emojis sparingly** (max 2-3 relevant emojis)
        5. **Maintain the core message** and key information
        6. **Write in a neutral, news-style tone**
        7. **Highlight the main point** clearly
        8. **Make it easily understandable**

        Original text: "{original_text}"

        Enhanced version should be ready to use as a social media post caption. Return ONLY the enhanced text without any explanations or additional text.
        """
        
        if tweet_url:
            base_prompt += f"\nSource context: {tweet_url}"
            
        return base_prompt
        
    async def _call_perplexity_api(self, prompt):
        """Make API call to Perplexity AI"""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "llama-3.1-sonar-small-128k-online",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a social media content enhancer. Your task is to rewrite text to make it more engaging, concise, and suitable for news-style social media posts. Always return only the enhanced text without any additional explanations."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 300,
            "temperature": 0.7,
            "top_p": 0.9
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, headers=headers, json=payload, timeout=30) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        enhanced_text = data['choices'][0]['message']['content'].strip()
                        
                        # Clean up the response
                        enhanced_text = self._clean_enhanced_text(enhanced_text)
                        return enhanced_text
                        
                    else:
                        error_text = await response.text()
                        logger.error(f"Perplexity API error: {response.status} - {error_text}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error("Perplexity API request timeout")
            return None
        except Exception as e:
            logger.error(f"Perplexity API call failed: {str(e)}")
            return None
            
    def _clean_enhanced_text(self, text):
        """Clean and format the enhanced text"""
        if not text:
            return text
            
        # Remove quotation marks if present
        text = text.strip('"\'')
        
        # Remove any introductory phrases
        remove_phrases = [
            "Enhanced text:",
            "Here's the enhanced version:",
            "Enhanced version:",
            "News-style caption:",
            "Social media post:"
        ]
        
        for phrase in remove_phrases:
            if text.startswith(phrase):
                text = text[len(phrase):].strip()
                
        # Ensure proper formatting
        text = ' '.join(text.split())  # Remove extra whitespace
        
        return text
        
    async def create_news_summary(self, tweet_text, tweet_url=None):
        """
        Create a comprehensive news summary from tweet content
        
        Args:
            tweet_text (str): Original tweet text
            tweet_url (str): Tweet URL for context
            
        Returns:
            str: News-style summary
        """
        if not self.api_key or self.api_key == "YOUR_PERPLEXITY_API_KEY":
            return tweet_text
            
        try:
            prompt = f"""
            Create a comprehensive news-style summary from this social media content:
            
            "{tweet_text}"
            
            Guidelines:
            - Write in formal news style
            - Maximum 2-3 sentences
            - Include key facts and context
            - Maintain objectivity
            - Use proper news terminology
            - Highlight the main news value
            
            Return ONLY the news summary without any additional text or explanations.
            """
            
            if tweet_url:
                prompt += f"\nSource: {tweet_url}"
                
            summary = await self._call_perplexity_api(prompt)
            return summary if summary else tweet_text
            
        except Exception as e:
            logger.error(f"Error creating news summary: {str(e)}")
            return tweet_text

# Global instance
text_enhancer = TextEnhancer()
