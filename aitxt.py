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
        Enhance caption using Perplexity AI
        """
        if not self.api_key:
            logger.warning("No Perplexity API key found")
            return original_text
            
        if not original_text or len(original_text.strip()) < 10:
            return original_text

        try:
            prompt = f"""Make this Twitter caption more engaging and viral: "{original_text}"
            
            Rules:
            - Keep it short (1-2 lines)
            - Make it attention-grabbing  
            - Use 1-2 emojis if relevant
            - Add 1-2 hashtags
            - Keep original meaning
            - Return only the enhanced caption"""
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Try different models
            models_to_try = [
                "llama-3.1-sonar-small-128k-online",
                "sonar-small-online", 
                "llama-3.1-8b-instruct"
            ]
            
            for model in models_to_try:
                try:
                    payload = {
                        "model": model,
                        "messages": [
                            {
                                "role": "system", 
                                "content": "You enhance social media captions. Return only the enhanced caption."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "max_tokens": 100,
                        "temperature": 0.7
                    }
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.post(self.base_url, headers=headers, json=payload, timeout=15) as response:
                            if response.status == 200:
                                data = await response.json()
                                enhanced = data['choices'][0]['message']['content'].strip()
                                
                                # Clean response
                                enhanced = re.sub(r'^["\']|["\']$', '', enhanced)  # Remove quotes
                                enhanced = re.sub(r'^(Enhanced|Caption):\s*', '', enhanced, flags=re.IGNORECASE)
                                
                                if enhanced and len(enhanced) > 20 and enhanced != original_text:
                                    logger.info(f"Successfully enhanced with {model}")
                                    return enhanced
                                    
                except Exception as e:
                    logger.warning(f"Model {model} failed: {e}")
                    continue
                    
            return original_text
            
        except Exception as e:
            logger.error(f"AI enhancement error: {e}")
            return original_text

    def is_meaningful_text(self, text):
        """Check if text is meaningful enough to enhance"""
        if not text:
            return False
        words = text.strip().split()
        return len(words) >= 3 and len(text.strip()) >= 15

    async def test_connection(self):
        """Test API connection"""
        if not self.api_key:
            return False, "No API key provided"
            
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "llama-3.1-sonar-small-128k-online",
                "messages": [{"role": "user", "content": "Say 'OK'"}],
                "max_tokens": 5
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, headers=headers, json=payload, timeout=10) as response:
                    if response.status == 200:
                        return True, "API connection successful"
                    else:
                        return False, f"API error: {response.status}"
                        
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
