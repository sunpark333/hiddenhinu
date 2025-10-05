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
        Create prompt for AI enhancement with separate paragraphs and natural Hindi
        """
        prompt = f"""
        Original text: "{original_text}"

        Create an engaging social media post with these requirements:

        ENGLISH SECTION (2-3 separate paragraphs):
        - First paragraph: Main news/announcement (attention-grabbing)
        - Second paragraph: Additional context/details
        - Third paragraph: Impact/importance (optional)
        - Use natural, human-like language (not AI-generated)
        - Add 2-3 relevant emojis naturally
        - Each paragraph should be separate

        HINDI SECTION (completely different approach):
        - Don't do direct translation from English
        - Create separate Hindi content with different phrasing
        - Use natural Hindi conversational style
        - Focus on emotional appeal and local context
        - Add 1-2 Hindi-appropriate emojis
        - Make it sound like human-written, not translated

        FORMAT:
        [English Paragraph 1]

        [English Paragraph 2]

        [English Paragraph 3]

        🌐 हिंदी संस्करण:
        [Completely different Hindi content with unique perspective]

        Important: 
        - Avoid AI-generated sounding language
        - Use casual, natural tone in both languages
        - Hindi content should stand on its own, not be a translation
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
                    "content": "You are a bilingual social media manager who creates engaging posts in both English and Hindi. You write in natural, human-like language that doesn't sound AI-generated. You create separate, unique content for Hindi that is not a direct translation but has its own perspective and emotional appeal."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 350,  # Increased for longer content
            "temperature": 0.8  # Slightly higher for more creativity
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, headers=headers, json=payload, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data['choices'][0]['message']['content'].strip()
                        
                        # Clean the response but preserve paragraph structure
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
        Clean AI response but preserve paragraph structure and natural flow
        """
        if not text:
            return text
            
        # Remove quotes if present
        text = text.strip('"\'')
        
        # Remove common AI prefixes but keep the content structure
        prefixes_to_remove = [
            "Here's the enhanced post:",
            "Enhanced post:",
            "Social media post:",
            "Here is the post:",
            "Created post:",
            "Post content:"
        ]
        
        for prefix in prefixes_to_remove:
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix):].strip()
                
        # Remove markdown formatting but preserve paragraphs
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Remove bold
        text = re.sub(r'\*(.*?)\*', r'\1', text)      # Remove italic
        
        # Ensure proper paragraph spacing
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
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
