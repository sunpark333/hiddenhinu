"""
Quiz Generator - PERPLEXITY API INTEGRATION
Generates properly formatted quiz questions using Perplexity
"""

import logging
import asyncio
import json
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import httpx
from config import YOUR_CHANNEL_ID, TIMEZONE, ADMIN_IDS

logger = logging.getLogger(__name__)

# Perplexity API Configuration
PERPLEXITY_API_KEY = "pplx-2e3e31ceb78547ba97df4a68e07e7db0"  # Your API key
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"


class QuizGenerator:
    """Generate and post quizzes to Telegram channels as polls"""

    def __init__(self, bot, ai_enhancer):
        """
        Initialize quiz generator
        Args:
            bot: TwitterBot instance
            ai_enhancer: AI caption enhancer instance (not used, using Perplexity directly)
        """
        self.bot = bot
        self.ai_enhancer = ai_enhancer
        self.quiz_mode = False
        self.quiz_topic = None
        self.current_question = None
        self.quiz_scheduled = False
        self.http_client = httpx.AsyncClient()

    async def quiz_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /quiz command - Start quiz generation
        Usage: /quiz
        Examples: /quiz ramayan, /quiz mahabharata
        """
        if not await self.bot.handlers.admin_only(update, context):
            return

        # Show topic selection if no args
        if not context.args or len(context.args) == 0:
            keyboard = [
                [
                    InlineKeyboardButton("🏹 Ramayan", callback_data="quiz_ramayan"),
                    InlineKeyboardButton("⚔️ Mahabharata", callback_data="quiz_mahabharata")
                ],
                [
                    InlineKeyboardButton("🕉️ Hindu Mythology", callback_data="quiz_mythology"),
                    InlineKeyboardButton("📚 Vedas", callback_data="quiz_vedas")
                ]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "🎯 **Quiz Generator**\n\n"
                "📖 Select a topic to generate AI-powered quiz question:\n\n"
                "• **Ramayan** - भगवान राम की गाथा\n"
                "• **Mahabharata** - महाकाव्य की कहानियाँ\n"
                "• **Hindu Mythology** - हिंदू पौराणिक कथाएं\n"
                "• **Vedas** - वेदों का ज्ञान\n\n"
                "📋 या command से use करो: `/quiz ramayan`",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            return

        # If topic provided in command
        topic = ' '.join(context.args).lower()
        await self._start_quiz_generation(update, context, topic)

    async def quiz_button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle quiz topic selection buttons"""
        query = update.callback_query
        await query.answer()

        if not await self.bot.handlers.admin_only_callback(update, context):
            return

        # Extract topic from callback data
        callback_data = query.data
        if callback_data.startswith("quiz_"):
            topic = callback_data.replace("quiz_", "").replace("_", " ")
            await self._start_quiz_generation(query, context, topic)

    async def _start_quiz_generation(self, update, context: ContextTypes.DEFAULT_TYPE, topic: str):
        """Start quiz generation process"""
        try:
            # Acknowledge the action
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.edit_message_text(
                    f"🎯 **Quiz Generator Started**\n\n"
                    f"📖 Topic: **{topic.title()}**\n"
                    f"🤖 Generating question with Perplexity AI...\n\n"
                    f"⏳ Please wait...",
                    parse_mode="Markdown"
                )
                message_obj = update
            else:
                await update.message.reply_text(
                    f"🎯 **Quiz Generator Started**\n\n"
                    f"📖 Topic: **{topic.title()}**\n"
                    f"🤖 Generating question with Perplexity AI...\n\n"
                    f"⏳ Please wait...",
                    parse_mode="Markdown"
                )
                message_obj = update.message

            self.quiz_topic = topic
            self.quiz_mode = True

            # Generate single question using Perplexity API
            question_data = await self._generate_quiz_question(topic)

            if not question_data:
                error_msg = "❌ Failed to generate question. Please try again later."
                if hasattr(message_obj, 'edit_text'):
                    await message_obj.edit_text(error_msg)
                elif hasattr(message_obj, 'reply_text'):
                    await message_obj.reply_text(error_msg)
                return

            self.current_question = question_data

            # Show posting options
            keyboard = [
                [
                    InlineKeyboardButton("📤 Post Now", callback_data="quiz_post_now"),
                    InlineKeyboardButton("⏰ Schedule", callback_data="quiz_schedule")
                ],
                [
                    InlineKeyboardButton("❌ Cancel", callback_data="quiz_cancel")
                ]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            question_preview = self._format_question_preview(question_data)

            if hasattr(message_obj, 'edit_text'):
                await message_obj.edit_text(
                    f"✅ **Question Generated!**\n\n"
                    f"{question_preview}\n\n"
                    f"🎯 Select action:",
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            elif hasattr(message_obj, 'reply_text'):
                await message_obj.reply_text(
                    f"✅ **Question Generated!**\n\n"
                    f"{question_preview}\n\n"
                    f"🎯 Select action:",
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )

        except Exception as e:
            logger.error(f"Error in quiz generation: {str(e)}")
            error_msg = f"❌ Error generating question: {str(e)}"
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
            elif hasattr(update, 'message') and update.message:
                await update.message.reply_text(error_msg)

    async def _generate_quiz_question(self, topic: str) -> dict:
        """
        Generate single quiz question using Perplexity API
        Args:
            topic: Topic for quiz (ramayan, mahabharata, etc)
        Returns:
            Dictionary with question data or None if failed
        """
        try:
            prompt = self._create_quiz_prompt(topic)

            logger.info(f"Calling Perplexity API for topic: {topic}")

            # Call Perplexity API
            headers = {
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": "sonar",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 500,
                "temperature": 0.7
            }

            response = await self.http_client.post(
                PERPLEXITY_API_URL,
                headers=headers,
                json=payload,
                timeout=30.0
            )

            response.raise_for_status()
            result = response.json()

            if "choices" not in result or not result["choices"]:
                logger.error("No choices in API response")
                return None

            question_content = result["choices"][0]["message"]["content"]
            logger.info(f"Perplexity Response: {question_content[:300]}...")

            # Parse question from API response
            question_data = self._parse_question_response(question_content, topic)

            if not question_data:
                logger.error("Failed to parse question")
                return None

            logger.info(f"Generated question successfully for topic: {topic}")
            return question_data

        except Exception as e:
            logger.error(f"Error generating question from Perplexity: {str(e)}")
            return None

    def _create_quiz_prompt(self, topic: str) -> str:
        """Create Perplexity prompt for question generation"""
        prompts = {
            "ramayan": (
                "Generate 1 interesting quiz question about Ramayan in this exact JSON format:\n"
                "{\n"
                '  "question": "Your detailed question here (in Hindi and English)",\n'
                '  "options": ["Option A", "Option B", "Option C", "Option D"],\n'
                '  "correct_index": 0\n'
                "}\n\n"
                "IMPORTANT:\n"
                "1. Question MUST be in both Hindi and English\n"
                "2. Question should be detailed and interesting\n"
                "3. Exactly 4 options\n"
                "4. correct_index should be 0, 1, 2, or 3 (position of correct answer)\n"
                "5. Return ONLY valid JSON, no other text\n\n"
                "Topics to cover: राम की यात्रा, सीता, लंका विजय, नैतिक संदेश"
            ),

            "mahabharata": (
                "Generate 1 interesting quiz question about Mahabharata in this exact JSON format:\n"
                "{\n"
                '  "question": "Your detailed question here (in Hindi and English)",\n'
                '  "options": ["Option A", "Option B", "Option C", "Option D"],\n'
                '  "correct_index": 0\n'
                "}\n\n"
                "IMPORTANT:\n"
                "1. Question MUST be in both Hindi and English\n"
                "2. Question should be detailed and interesting\n"
                "3. Exactly 4 options\n"
                "4. correct_index should be 0, 1, 2, or 3 (position of correct answer)\n"
                "5. Return ONLY valid JSON, no other text\n\n"
                "Topics to cover: पांडव-कौरव, कुरुक्षेत्र, कृष्ण, धर्मशास्त्र"
            ),

            "mythology": (
                "Generate 1 interesting quiz question about Hindu Mythology in this exact JSON format:\n"
                "{\n"
                '  "question": "Your detailed question here (in Hindi and English)",\n'
                '  "options": ["Option A", "Option B", "Option C", "Option D"],\n'
                '  "correct_index": 0\n'
                "}\n\n"
                "IMPORTANT:\n"
                "1. Question MUST be in both Hindi and English\n"
                "2. Question should be detailed and interesting\n"
                "3. Exactly 4 options\n"
                "4. correct_index should be 0, 1, 2, or 3 (position of correct answer)\n"
                "5. Return ONLY valid JSON, no other text\n\n"
                "Topics to cover: देवता, असुर, देवी, कथाएं"
            ),

            "vedas": (
                "Generate 1 interesting quiz question about Vedas in this exact JSON format:\n"
                "{\n"
                '  "question": "Your detailed question here (in Hindi and English)",\n'
                '  "options": ["Option A", "Option B", "Option C", "Option D"],\n'
                '  "correct_index": 0\n'
                "}\n\n"
                "IMPORTANT:\n"
                "1. Question MUST be in both Hindi and English\n"
                "2. Question should be detailed and interesting\n"
                "3. Exactly 4 options\n"
                "4. correct_index should be 0, 1, 2, or 3 (position of correct answer)\n"
                "5. Return ONLY valid JSON, no other text\n\n"
                "Topics to cover: चार वेद, उपनिषद, ऋषि, दर्शन"
            )
        }

        return prompts.get(topic, prompts["mythology"])

    def _parse_question_response(self, response: str, topic: str) -> dict:
        """
        Parse Perplexity API response into structured format
        Args:
            response: API response text (should be JSON)
            topic: Quiz topic
        Returns:
            Dictionary with question data
        """
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                logger.error("No JSON found in response")
                return None

            json_str = json_match.group(0)
            data = json.loads(json_str)

            logger.info(f"Parsed JSON: {data}")

            # Validate structure
            if "question" not in data or "options" not in data or "correct_index" not in data:
                logger.error("Missing required fields in JSON")
                return None

            question_text = data["question"]
            options = data["options"]
            correct_index = data["correct_index"]

            # Validate question
            if not question_text or len(question_text.strip()) < 10:
                logger.error("Question text too short or empty")
                return None

            # Validate options
            if not isinstance(options, list) or len(options) != 4:
                logger.error(f"Invalid options: expected list of 4, got {len(options)}")
                return None

            for i, opt in enumerate(options):
                if not opt or len(str(opt).strip()) < 2:
                    logger.error(f"Option {i} is invalid")
                    return None

            # Validate correct_index
            if not isinstance(correct_index, int) or correct_index < 0 or correct_index > 3:
                logger.error(f"Invalid correct_index: {correct_index}")
                return None

            # Convert index to letter (0->A, 1->B, etc)
            correct_letter = chr(65 + correct_index)

            result = {
                'topic': topic,
                'question': question_text,
                'options': options,
                'correct': correct_letter,
                'created_at': datetime.now(TIMEZONE),
                'posted': False
            }

            logger.info(f"Successfully parsed question: {result}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error parsing question: {str(e)}")
            return None

    def _format_question_preview(self, question_data: dict) -> str:
        """Format question for preview display"""
        preview = f"📚 **{question_data['topic'].title()} Quiz**\n\n"
        preview += f"❓ {question_data['question']}\n\n"

        for i, opt in enumerate(question_data['options']):
            preview += f"{chr(65+i)}) {opt}\n"

        preview += f"\n💡 सही उत्तर: {question_data['correct']}"

        return preview

    async def quiz_post_now_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Post question to channel immediately"""
        query = update.callback_query
        await query.answer()

        if not self.current_question:
            await query.edit_message_text("❌ No question data found.")
            return

        try:
            await query.edit_message_text(
                "📤 Posting question to channel...\n⏳ Please wait...",
                parse_mode="Markdown"
            )

            await self._post_question_as_poll(self.current_question)

            await query.edit_message_text(
                "✅ **Question Posted Successfully!**\n\n"
                f"📚 Topic: {self.current_question['topic'].title()}\n"
                f"✨ Posted to channel!",
                parse_mode="Markdown"
            )

            self.quiz_mode = False

        except Exception as e:
            logger.error(f"Error posting question: {str(e)}")
            await query.edit_message_text(f"❌ Error: {str(e)}")

    async def quiz_schedule_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Schedule question posting"""
        query = update.callback_query
        await query.answer()

        if not self.current_question:
            await query.edit_message_text("❌ No question data found.")
            return

        keyboard = [
            [InlineKeyboardButton("⏰ 30 minutes", callback_data="quiz_delay_30")],
            [InlineKeyboardButton("⏰ 1 hour", callback_data="quiz_delay_60")],
            [InlineKeyboardButton("⏰ 2 hours", callback_data="quiz_delay_120")],
            [InlineKeyboardButton("❌ Cancel", callback_data="quiz_cancel")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "⏰ **Schedule Question Posting**\n\n"
            "Select delay:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    async def quiz_delay_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE, delay_minutes: int):
        """Schedule question with delay"""
        query = update.callback_query
        await query.answer()

        try:
            await query.edit_message_text(
                f"⏰ Scheduling for {delay_minutes} minutes...",
                parse_mode="Markdown"
            )

            await asyncio.sleep(delay_minutes * 60)
            await self._post_question_as_poll(self.current_question)

            await query.edit_message_text(
                f"✅ **Posted!**",
                parse_mode="Markdown"
            )

            self.quiz_mode = False

        except Exception as e:
            logger.error(f"Error: {str(e)}")

    async def _post_question_as_poll(self, question_data: dict):
        """Post question to Telegram channel"""
        try:
            if not self.bot.userbot or not self.bot.userbot.is_connected():
                logger.error("Userbot not connected")
                return

            channel = await self.bot.userbot.get_entity(int(YOUR_CHANNEL_ID))

            poll_message = (
                f"🎯 **{question_data['topic'].title()} Question**\n\n"
                f"❓ {question_data['question']}\n\n"
                f"A) {question_data['options'][0]}\n"
                f"B) {question_data['options'][1]}\n"
                f"C) {question_data['options'][2]}\n"
                f"D) {question_data['options'][3]}\n\n"
                f"💡 सही उत्तर: {question_data['correct']}"
            )

            await self.bot.userbot.send_message(channel, poll_message)

            logger.info(f"Posted question to channel: {question_data['topic']}")
            question_data['posted'] = True

        except Exception as e:
            logger.error(f"Error posting: {str(e)}")
            raise

    async def quiz_cancel_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel quiz generation"""
        query = update.callback_query
        await query.answer()

        self.quiz_mode = False
        self.current_question = None
        self.quiz_topic = None

        await query.edit_message_text(
            "❌ Cancelled!\n\nUse /quiz to start again.",
            parse_mode="Markdown"
        )
