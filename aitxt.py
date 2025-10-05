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
        self.available_models = [
            "llama-3.1-sonar-small-128k-online",
            "llama-3.1-sonar-large-128k-online", 
            "sonar-small-online",
            "sonar-medium-online",
            "sonar-large-online",
            "llama-3.1-8b-instruct",
            "llama-3.1-70b-instruct"
        ]
        self.current_model_index = 0
        
    async def enhance_caption(self, original_text, twitter_link=None):
        """
        Enhance caption using Perplexity AI to make it more engaging and news-style
        """
        if not self.api_key:
            logger.warning("Perplexity API key not found. Returning original caption.")
            return original_text
            
        if not original_text or len(original_text.strip()) < 10:
            return original_text

        # Try all available models
        for attempt in range(len(self.available_models)):
            try:
                model = self.available_models[self.current_model_index]
                logger.info(f"Trying AI model: {model}")
                
                prompt = self._create_enhancement_prompt(original_text, twitter_link)
                enhanced_text = await self._call_perplexity_api(prompt, model)
                
                if enhanced_text and len(enhanced_text.strip()) > 20:
                    logger.info(f"Successfully enhanced caption using {model}")
                    return enhanced_text.strip()
                else:
                    logger.warning(f"AI returned empty response with model {model}")
                    
            except Exception as e:
                logger.error(f"Error with model {self.available_models[self.current_model_index]}: {str(e)}")
            
            # Try next model
            self.current_model_index = (self.current_model_index + 1) % len(self.available_models)
            
            # Don't wait between attempts for the same request
            if attempt < len(self.available_models) - 1:
                logger.info(f"Trying next model...")

        logger.error("All AI models failed, returning original caption")
        return original_text

    def _create_enhancement_prompt(self, original_text, twitter_link=None):
        """
        Create prompt for AI enhancement
        """
        prompt = f"""
        ENHANCE THIS TWITTER CAPTION: "{original_text}"
        
        Make it more engaging, viral, and news-style. Follow these rules:
        
        1. Keep it short (1-2 lines max)
        2. Make it attention-grabbing
        3. Use 1-2 relevant emojis if appropriate
        4. Add 1-2 relevant hashtags
        5. Keep the original meaning
        6. Make it sound like breaking news
        7. No URLs or links
        8. No AI mentions
        
        Return ONLY the enhanced caption, nothing else.
        """
        
        return prompt

    async def _call_perplexity_api(self, prompt, model):
        """
        Make API call to Perplexity AI
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You enhance social media captions to be more engaging and viral. Always return only the enhanced caption without any explanations."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 100,
            "temperature": 0.8,
            "top_p": 0.9
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
                        logger.error(f"Perplexity API error ({response.status}) with model {model}: {error_text}")
                        
                        # If model not found error, try next model immediately
                        if "invalid_model" in error_text or "not found" in error_text:
                            raise Exception(f"Invalid model: {model}")
                            
                        return None
                        
        except aiohttp.ClientError as e:
            logger.error(f"Perplexity API request failed for model {model}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in Perplexity API call for model {model}: {str(e)}")
            return None

    def _clean_ai_response(self, text):
        """
        Clean AI response from unwanted formatting
        """
        if not text:
            return text
            
        # Remove quotes if present
        text = text.strip('"\'')
        
        # Remove common AI prefixes
        prefixes_to_remove = [
            "Enhanced caption:",
            "Here's the enhanced caption:",
            "Caption:",
            "Enhanced:",
            "News-style caption:",
            "Here is the enhanced caption:",
            "Viral caption:"
        ]
        
        for prefix in prefixes_to_remove:
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix):].strip()
                
        # Remove any markdown formatting
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Remove bold
        text = re.sub(r'\*(.*?)\*', r'\1', text)      # Remove italic
        
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
        Test API connection and available models
        """
        if not self.api_key:
            return False, "No API key provided"
            
        test_prompt = "Hello, please respond with 'OK' if you can see this message."
        
        working_models = []
        
        for model in self.available_models:
            try:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": test_prompt}],
                    "max_tokens": 10
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(self.base_url, headers=headers, json=payload, timeout=10) as response:
                        if response.status == 200:
                            working_models.append(model)
                            
            except Exception as e:
                continue
                
        if working_models:
            return True, f"Working models: {', '.join(working_models[:2])}"
        else:
            return False, "No working models found. Check API key and models."import logging
import aiohttp
import json
import re
from config import PERPLEXITY_API_KEY

logger = logging.getLogger(__name__)

class AICaptionEnhancer:
    def __init__(self):
        self.api_key = PERPLEXITY_API_KEY
        self.base_url = "https://api.perplexity.ai/chat/completions"
        self.available_models = [
            "llama-3.1-sonar-small-128k-online",
            "llama-3.1-sonar-large-128k-online", 
            "sonar-small-online",
            "sonar-medium-online",
            "sonar-large-online",
            "llama-3.1-8b-instruct",
            "llama-3.1-70b-instruct"
        ]
        self.current_model_index = 0
        
    async def enhance_caption(self, original_text, twitter_link=None):
        """
        Enhance caption using Perplexity AI to make it more engaging and news-style
        """
        if not self.api_key:
            logger.warning("Perplexity API key not found. Returning original caption.")
            return original_text
            
        if not original_text or len(original_text.strip()) < 10:
            return original_text

        # Try all available models
        for attempt in range(len(self.available_models)):
            try:
                model = self.available_models[self.current_model_index]
                logger.info(f"Trying AI model: {model}")
                
                prompt = self._create_enhancement_prompt(original_text, twitter_link)
                enhanced_text = await self._call_perplexity_api(prompt, model)
                
                if enhanced_text and len(enhanced_text.strip()) > 20:
                    logger.info(f"Successfully enhanced caption using {model}")
                    return enhanced_text.strip()
                else:
                    logger.warning(f"AI returned empty response with model {model}")
                    
            except Exception as e:
                logger.error(f"Error with model {self.available_models[self.current_model_index]}: {str(e)}")
            
            # Try next model
            self.current_model_index = (self.current_model_index + 1) % len(self.available_models)
            
            # Don't wait between attempts for the same request
            if attempt < len(self.available_models) - 1:
                logger.info(f"Trying next model...")

        logger.error("All AI models failed, returning original caption")
        return original_text

    def _create_enhancement_prompt(self, original_text, twitter_link=None):
        """
        Create prompt for AI enhancement
        """
        prompt = f"""
        ENHANCE THIS TWITTER CAPTION: "{original_text}"
        
        Make it more engaging, viral, and news-style. Follow these rules:
        
        1. Keep it short (1-2 lines max)
        2. Make it attention-grabbing
        3. Use 1-2 relevant emojis if appropriate
        4. Add 1-2 relevant hashtags
        5. Keep the original meaning
        6. Make it sound like breaking news
        7. No URLs or links
        8. No AI mentions
        
        Return ONLY the enhanced caption, nothing else.
        """
        
        return prompt

    async def _call_perplexity_api(self, prompt, model):
        """
        Make API call to Perplexity AI
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You enhance social media captions to be more engaging and viral. Always return only the enhanced caption without any explanations."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 100,
            "temperature": 0.8,
            "top_p": 0.9
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
                        logger.error(f"Perplexity API error ({response.status}) with model {model}: {error_text}")
                        
                        # If model not found error, try next model immediately
                        if "invalid_model" in error_text or "not found" in error_text:
                            raise Exception(f"Invalid model: {model}")
                            
                        return None
                        
        except aiohttp.ClientError as e:
            logger.error(f"Perplexity API request failed for model {model}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in Perplexity API call for model {model}: {str(e)}")
            return None

    def _clean_ai_response(self, text):
        """
        Clean AI response from unwanted formatting
        """
        if not text:
            return text
            
        # Remove quotes if present
        text = text.strip('"\'')
        
        # Remove common AI prefixes
        prefixes_to_remove = [
            "Enhanced caption:",
            "Here's the enhanced caption:",
            "Caption:",
            "Enhanced:",
            "News-style caption:",
            "Here is the enhanced caption:",
            "Viral caption:"
        ]
        
        for prefix in prefixes_to_remove:
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix):].strip()
                
        # Remove any markdown formatting
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Remove bold
        text = re.sub(r'\*(.*?)\*', r'\1', text)      # Remove italic
        
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
        Test API connection and available models
        """
        if not self.api_key:
            return False, "No API key provided"
            
        test_prompt = "Hello, please respond with 'OK' if you can see this message."
        
        working_models = []
        
        for model in self.available_models:
            try:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": test_prompt}],
                    "max_tokens": 10
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(self.base_url, headers=headers, json=payload, timeout=10) as response:
                        if response.status == 200:
                            working_models.append(model)
                            
            except Exception as e:
                continue
                
        if working_models:
            return True, f"Working models: {', '.join(working_models[:2])}"
        else:
            return False, "No working models found. Check API key and models."
