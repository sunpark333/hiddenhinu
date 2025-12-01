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
        Enhance caption using Perplexity AI to make it more engaging and natural
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
        Create prompt for AI enhancement - more natural and human-like
        """
        prompt = f"""
        Rewrite this Twitter text to make it more engaging and natural for social media: "{original_text}"
        
        IMPORTANT RULES:
        - Make it sound completely human-written, not AI-generated
        - Keep the original meaning and context
        - Use natural, conversational language
        - Avoid starting with words like "Breaking", "Alert", "News", etc.
        - Use minimal punctuation - avoid excessive commas, exclamations
        - write 1-2 Paragraph with and space between Paragraphs
        - Keep it concise and impactful
        - Make it look like a normal social media post
        - Return ONLY the rewritten text, no explanations
        - DO NOT use hashtags like #AIEnhanced #Viral etc.
        - DO NOT mention it's enhanced or rewritten
        - Make it flow naturally like human speech and use easy english 
        """
        
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
            "model": "sonar",
            "messages": [
                {
                    "role": "system", 
                    "content": "You are a social media user who writes engaging, natural posts. You rewrite text to make it more conversational and human-like. You never sound like AI. You avoid formal language and excessive punctuation. You return only the rewritten text without any explanations or labels."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 120,
            "temperature": 0.8  # Slightly higher temperature for more creative/natural output
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, headers=headers, json=payload, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data['choices'][0]['message']['content'].strip()
                        
                        # Clean the response to make it more natural
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
        Clean AI response to make it more natural and human-like
        """
        if not text:
            return text
            
        # Remove quotes if present
        text = text.strip('"\'')
        
        # Remove common AI prefixes and labels
        prefixes_to_remove = [
            "Enhanced caption:",
            "Here's the enhanced caption:",
            "Caption:",
            "Enhanced:",
            "News-style caption:",
            "Here is the enhanced caption:",
            "Viral caption:",
            "Rewritten text:",
            "Here's the rewritten version:",
            "Social media version:",
            "Breaking:",
            "Alert:",
            "News:",
            "Update:",
            "#AIEnhanced",
            "#AI",
            "#Enhanced",
            "#Viral",
            "#Breaking"
        ]
        
        for prefix in prefixes_to_remove:
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix):].strip()
            # Also remove if it appears anywhere in the text
            text = re.sub(re.escape(prefix), '', text, flags=re.IGNORECASE)
        
        # Remove any AI-related hashtags using regex
        ai_hashtags = [
            r'#AIEnhanced\b', 
            r'#AIGenerated\b', 
            r'#AI\b', 
            r'#EnhancedByAI\b',
            r'#Viral\b',
            r'#Breaking\b',
            r'#News\b'
        ]
        for hashtag in ai_hashtags:
            text = re.sub(hashtag, '', text, flags=re.IGNORECASE)
        
        # Remove any existing markdown formatting
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Remove bold
        text = re.sub(r'\*(.*?)\*', r'\1', text)      # Remove italic
        
        # Reduce excessive punctuation
        text = re.sub(r'\!{2,}', '!', text)  # Multiple ! to single !
        text = re.sub(r'\,{2,}', ',', text)  # Multiple , to single ,
        text = re.sub(r'\.{2,}', '.', text)  # Multiple . to single .
        
        # Clean up extra spaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove leading/trailing punctuation
        text = re.sub(r'^[,\!\."\']+', '', text)
        text = re.sub(r'[,\!\."\']+$', '', text)
        
        # Ensure it doesn't start with formal words
        formal_starts = [
            'breaking', 'alert', 'news', 'update', 'latest', 
            'important', 'urgent', 'attention', 'notice'
        ]
        
        first_word = text.split()[0].lower() if text.split() else ''
        if first_word in formal_starts:
            # Remove the first word if it's too formal
            words = text.split()
            if len(words) > 1:
                text = ' '.join(words[1:])
        
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
        Test API connection
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

    async def enhance_caption_safe(self, original_text, twitter_link=None):
        """
        Safe enhancement with fallback to original text
        """
        try:
            enhanced = await self.enhance_caption(original_text, twitter_link)
            
            # If enhancement failed or returned similar text, use original
            if (not enhanced or 
                enhanced == original_text or 
                len(enhanced) < 15 or
                self._is_too_similar(enhanced, original_text)):
                return original_text
                
            return enhanced
            
        except Exception as e:
            logger.error(f"Safe enhancement failed: {e}")
            return original_text

    def _is_too_similar(self, text1, text2, threshold=0.8):
        """
        Check if two texts are too similar (simple word overlap)
        """
        if not text1 or not text2:
            return False
            
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return False
            
        intersection = words1.intersection(words2)
        similarity = len(intersection) / max(len(words1), len(words2))
        
        return similarity > threshold
