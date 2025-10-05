import logging
import aiohttp
import json
import re
import requests
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
        - Keep it short (1-2 lines)
        - Make it attention-grabbing  
        - Use 1-2 emojis if relevant
        - Add 1-2 hashtags
        - Keep original meaning
        - Make it sound like breaking news
        - Return only the enhanced caption
        """
        
        return prompt

    async def _call_perplexity_api(self, prompt):
        """
        Make API call to Perplexity AI using the working model from group.py
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
                    "content": "You are a social media expert who enhances captions to make them more engaging and viral. Always return only the enhanced caption without any explanations."
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
        Test API connection using the working model
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

    def generate_quiz_with_perplexity(self, subject: str, difficulty: str, num_questions: int = 20):
        """
        Generate quiz questions using Perplexity AI API - same as in group.py
        """
        try:
            # Perplexity API endpoint
            url = "https://api.perplexity.ai/chat/completions"
            
            # Prepare the prompt
            prompt = f"""
            Create a {num_questions}-question multiple choice quiz on {subject} for 12th grade Commerce students.
            Difficulty level: {difficulty}.
            For each question, provide:
            1. The question text
            2. Four options (labeled a, b, c, d)
            3. The correct answer (0-indexed, e.g., 0 for first option)
            4. A brief explanation of the correct answer
            
            Return the response as a JSON array with the following structure:
            [
              {{
                "question": "question text",
                "options": ["option1", "option2", "option3", "option4"],
                "correct_answer": 0,
                "explanation": "brief explanation"
              }}
            ]
            """
            
            # Headers for the API request
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Payload for the API request
            payload = {
                "model": "sonar",
                "messages": [
                    {"role": "system", "content": "You are a helpful educational assistant that creates quiz questions for 12th grade Commerce students."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 4000,
                "temperature": 0.7
            }
            
            # Make the API request
            response = requests.post(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                # Parse the response
                response_data = response.json()
                content = response_data['choices'][0]['message']['content']
                
                # Extract JSON from the response
                try:
                    # Try to find JSON array in the response
                    start_idx = content.find('[')
                    end_idx = content.rfind(']') + 1
                    json_str = content[start_idx:end_idx]
                    quiz_data = json.loads(json_str)
                    return quiz_data
                except (json.JSONDecodeError, KeyError, IndexError):
                    logger.error("Failed to parse JSON from Perplexity response")
                    return None
            else:
                logger.error(f"Perplexity API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating quiz with Perplexity: {e}")
            return None
