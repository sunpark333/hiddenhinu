import logging
import aiohttp
import asyncio
import json
import re
from typing import Optional, Tuple
from config import PERPLEXITY_API_KEY

logger = logging.getLogger(__name__)

class AICaptionEnhancer:
    """
    Twitter/X caption enhancement service using Perplexity API.
    - Default: tries best-quality model first, then fallbacks.
    - Optional: strict_mode to disable fallback.
    - Robust cleaning and error handling.
    """

    def __init__(
        self,
        preferred_model: Optional[str] = None,
        strict_mode: bool = False,
        request_timeout: int = 30,
        temperature: float = 0.8,
        top_p: float = 0.9,
        max_tokens: int = 100
    ):
        self.api_key = PERPLEXITY_API_KEY
        self.base_url = "https://api.perplexity.ai/chat/completions"

        # Best to least preference
        self.available_models = [
            "llama-3.1-sonar-huge-128k-online",   # Best quality & reasoning
            "llama-3.1-sonar-large-128k-online",  # Balance of quality/speed
            "llama-3.1-sonar-small-128k-online",  # Fastest among sonar
            "llama-3.1-70b-instruct",             # Strong instruct
            "llama-3.1-8b-instruct"               # Budget/fast
        ]

        # If user prefers a specific model and it exists, prioritize it first
        if preferred_model and preferred_model in self.available_models:
            # Move preferred to index 0 for first attempt
            self.available_models.remove(preferred_model)
            self.available_models.insert(0, preferred_model)

        self.strict_mode = strict_mode
        self.request_timeout = request_timeout
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens

    async def enhance_caption(self, original_text: str, twitter_link: Optional[str] = None) -> str:
        """
        Enhance caption using Perplexity AI to make it more engaging and news-style.
        Tries the best model first, with fallbacks unless strict_mode is True.
        """
        if not self.api_key:
            logger.warning("Perplexity API key not found. Returning original caption.")
            return original_text

        if not self.is_meaningful_text(original_text):
            logger.info("Original text not meaningful enough to enhance; returning original.")
            return original_text

        prompt = self._create_enhancement_prompt(original_text, twitter_link)

        # Strict mode: call only the top model and return
        if self.strict_mode:
            top_model = self.available_models[0]
            logger.info(f"Strict mode: trying only model {top_model}")
            try:
                enhanced_text = await self._call_perplexity_api(prompt, top_model)
                if self._is_valid_output(enhanced_text):
                    return enhanced_text.strip()
            except Exception as e:
                logger.error(f"Strict mode call failed for {top_model}: {e}")
            return original_text

        # Non-strict: iterate through models with smart fallback
        for idx, model in enumerate(self.available_models):
            try:
                logger.info(f"Trying AI model: {model}")
                enhanced_text = await self._call_perplexity_api(prompt, model)
                if self._is_valid_output(enhanced_text):
                    logger.info(f"Successfully enhanced caption using {model}")
                    return enhanced_text.strip()
                else:
                    logger.warning(f"AI returned empty/invalid response with model {model}")
            except Exception as e:
                logger.error(f"Error with model {model}: {str(e)}")

            if idx < len(self.available_models) - 1:
                logger.info("Trying next model...")
                # Small jitter to avoid hitting same rate limits across retries
                await asyncio.sleep(0.2)

        logger.error("All AI models failed, returning original caption.")
        return original_text

    def _create_enhancement_prompt(self, original_text: str, twitter_link: Optional[str] = None) -> str:
        """
        Create prompt for AI enhancement with strict output instruction.
        """
        prompt = f"""
You are a social media expert. Enhance this Twitter/X post caption to make it more engaging, professional, and news-style.
Keep the core meaning but make it more compelling for a social media audience.

Original caption: "{original_text}"

Enhancement Guidelines:
1) Make it engaging and click-worthy
2) Use 1-2 relevant emojis if appropriate
3) Keep it concise (1-2 lines maximum)
4) Maintain the original intent and facts
5) Add 1-2 relevant hashtags if they fit naturally
6) Make it sound like breaking news or important update
7) Keep the language natural and viral-worthy
8) Do not add URLs or links
9) Do not mention that it's enhanced by AI
10) Focus on the key message only

Return ONLY the enhanced caption without any explanations, quotes, or additional text.
""".strip()

        if twitter_link:
            prompt += f"\n\nOriginal Twitter link: {twitter_link}"

        return prompt

    async def _call_perplexity_api(self, prompt: str, model: str) -> Optional[str]:
        """
        Make API call to Perplexity AI and clean the response.
        Raises exceptions for transport errors; returns None for handled API errors.
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
                    "content": (
                        "You are a social media expert who enhances captions to make them more engaging, "
                        "viral, and news-style while maintaining original meaning. Always return only the "
                        "enhanced caption without any additional text."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p
        }

        try:
            timeout = aiohttp.ClientTimeout(total=self.request_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.base_url, headers=headers, json=payload) as response:
                    text_body = await self._safe_read_text(response)
                    if response.status == 200:
                        try:
                            data = json.loads(text_body)
                            content = data["choices"][0]["message"]["content"]
                            content = self._clean_ai_response(content)
                            return content
                        except Exception as parse_err:
                            logger.error(f"Parse error for model {model}: {parse_err} | body: {text_body[:500]}")
                            return None
                    else:
                        # Handle common error scenarios
                        logger.error(f"Perplexity API error ({response.status}) with model {model}: {text_body}")

                        # Immediate switch if invalid model
                        if "invalid_model" in text_body.lower():
                            raise ValueError(f"Invalid model: {model}")

                        # Basic rate limit/backoff hint — let caller decide next step
                        if response.status in (429, 503):
                            await asyncio.sleep(0.5)

                        return None

        except aiohttp.ClientError as e:
            logger.error(f"Perplexity API request failed for model {model}: {str(e)}")
            # Let caller try next model
            return None
        except asyncio.TimeoutError:
            logger.error(f"Perplexity API request timed out for model {model}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in Perplexity API call for model {model}: {str(e)}")
            return None

    async def _safe_read_text(self, response: aiohttp.ClientResponse) -> str:
        """
        Safely read response body as text; avoid unhandled exceptions in error paths.
        """
        try:
            return await response.text()
        except Exception:
            return ""

    def _clean_ai_response(self, text: Optional[str]) -> str:
        """
        Clean AI response from unwanted formatting:
        - Remove quotes/prefixes
        - Remove basic markdown bold/italic
        - Trim spaces and ensure single-line or short lines
        """
        if not text:
            return ""

        cleaned = text.strip().strip('"\'`')

        # Remove common AI prefixes (case-insensitive)
        prefixes_to_remove = [
            "enhanced caption:",
            "here's the enhanced caption:",
            "caption:",
            "enhanced:",
            "news-style caption:"
        ]
        low = cleaned.lower()
        for prefix in prefixes_to_remove:
            if low.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
                break  # remove only first matching prefix

        # Remove markdown bold/italic safely
        # Bold: **text** -> text
        cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
        # Italic: *text* or _text_ -> text
        cleaned = re.sub(r"\*(.*?)\*", r"\1", cleaned)
        cleaned = re.sub(r"_(.*?)_", r"\1", cleaned)

        # Strip extraneous quotes again
        cleaned = cleaned.strip().strip('"\'`')

        # Enforce 1-2 line max (hard trim extra newlines)
        lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
        if len(lines) > 2:
            lines = lines[:2]
        cleaned = " ".join(lines) if len(lines) <= 1 else "\n".join(lines)

        return cleaned.strip()

    def is_meaningful_text(self, text: Optional[str]) -> bool:
        """
        Check if text is meaningful enough to enhance:
        - At least 3 words and >= 15 non-URL chars after cleaning.
        """
        if not text:
            return False

        # Remove URLs
        clean_text = re.sub(r"http\S+", "", text)
        # Remove special characters except spaces and alphanumerics
        clean_text = re.sub(r"[^\w\s#@]", "", clean_text, flags=re.UNICODE)

        words = clean_text.strip().split()
        return len(words) >= 3 and len(clean_text.strip()) >= 15

    def _is_valid_output(self, text: Optional[str]) -> bool:
        """
        Validate output length and ensure it isn't boilerplate.
        """
        if not text:
            return False
        t = text.strip()
        if len(t) < 20:
            return False
        # Reject if it contains obvious instruction echoes
        bad_patterns = [
            r"return only the enhanced caption",
            r"do not add urls",
            r"do not mention that it's enhanced by ai",
        ]
        for bp in bad_patterns:
            if re.search(bp, t, re.IGNORECASE):
                return False
        return True

    async def test_connection(self) -> Tuple[bool, str]:
        """
        Test API connection and available models (quick ping).
        Returns (status, message)
        """
        if not self.api_key:
            return False, "No API key provided"

        test_prompt = "Respond with only: OK"

        for model in self.available_models:
            try:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }

                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": test_prompt}],
                    "max_tokens": 5
                }

                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(self.base_url, headers=headers, json=payload) as response:
                        if response.status == 200:
                            body = await self._safe_read_text(response)
                            try:
                                data = json.loads(body)
                                content = data["choices"][0]["message"]["content"].strip()
                                if content.upper() == "OK":
                                    return True, f"Model {model} is working"
                            except Exception:
                                pass
                        # continue to next model
            except Exception:
                continue

        return False, "No working models found"
