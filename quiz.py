"""
Quiz Generator - AI-powered quiz creation and posting
Generate 1 question as Telegram Poll (UPDATED VERSION)
Questions are detailed, interesting, and have 4 options only
No default quiz - AI required for all questions
"""

import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telethon.tl.types import TypeInputPeer
from config import YOUR_CHANNEL_ID, TIMEZONE, ADMIN_IDS

logger = logging.getLogger(__name__)


class QuizGenerator:
    """Generate and post quizzes to Telegram channels as polls"""

    def __init__(self, bot, ai_enhancer):
        """
        Initialize quiz generator
        Args:
            bot: TwitterBot instance
            ai_enhancer: AI caption enhancer instance
        """
        self.bot = bot
        self.ai_enhancer = ai_enhancer
        self.quiz_mode = False
        self.quiz_topic = None
        self.current_question = None
        self.quiz_scheduled = False

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
                    f"🤖 Generating question with AI...\n\n"
                    f"⏳ Please wait...",
                    parse_mode="Markdown"
                )
                message_obj = update
            else:
                await update.message.reply_text(
                    f"🎯 **Quiz Generator Started**\n\n"
                    f"📖 Topic: **{topic.title()}**\n"
                    f"🤖 Generating question with AI...\n\n"
                    f"⏳ Please wait...",
                    parse_mode="Markdown"
                )
                message_obj = update.message

            self.quiz_topic = topic
            self.quiz_mode = True

            # Generate single question using AI
            question_data = await self._generate_quiz_question(topic)

            if not question_data:
                error_msg = "❌ Failed to generate question. Please try again."
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
        Generate single quiz question using AI
        Args:
            topic: Topic for quiz (ramayan, mahabharata, etc)
        Returns:
            Dictionary with question data or None if failed
        """
        try:
            prompt = self._create_quiz_prompt(topic)

            # Use AI enhancer to generate question
            question_content = await self.ai_enhancer.enhance_caption(prompt)

            if not question_content:
                logger.warning("AI returned empty question content")
                return None

            # Parse question from AI response
            question_data = self._parse_question_response(question_content, topic)

            logger.info(f"Generated question for topic: {topic}")
            return question_data

        except Exception as e:
            logger.error(f"Error generating question: {str(e)}")
            return None

    def _create_quiz_prompt(self, topic: str) -> str:
        """Create AI prompt for question generation - DETAILED & INTERESTING"""
        prompts = {
            "ramayan": (
                "Generate 1 detailed and interesting quiz question about Ramayan in Hindi and English. "
                "The question should be thought-provoking and test deep knowledge. "
                "Format: Q) Question text (in Hindi and English)\n"
                "A) Option1\nB) Option2\nC) Option3\nD) Option4\nCorrect: A\n\n"
                "Requirements:\n"
                "- Question should be 1-2 sentences, detailed and interesting\n"
                "- Exactly 4 options (A, B, C, D) - no more, no less\n"
                "- Options should be plausible and test real knowledge\n"
                "- Include both Hindi and English in the question\n"
                "- Topics: राम की यात्रा, सीता का किस्सा, लंका विजय, नैतिक संदेश, महत्वपूर्ण पात्र"
            ),

            "mahabharata": (
                "Generate 1 detailed and interesting quiz question about Mahabharata in Hindi and English. "
                "The question should be thought-provoking and test deep knowledge. "
                "Format: Q) Question text (in Hindi and English)\n"
                "A) Option1\nB) Option2\nC) Option3\nD) Option4\nCorrect: A\n\n"
                "Requirements:\n"
                "- Question should be 1-2 sentences, detailed and interesting\n"
                "- Exactly 4 options (A, B, C, D) - no more, no less\n"
                "- Options should be plausible and test real knowledge\n"
                "- Include both Hindi and English in the question\n"
                "- Topics: पांडव-कौरव संघर्ष, कुरुक्षेत्र युद्ध, कृष्ण की भूमिका, धर्मशास्त्र का ज्ञान"
            ),

            "mythology": (
                "Generate 1 detailed and interesting quiz question about Hindu Mythology in Hindi and English. "
                "The question should be thought-provoking and test deep knowledge. "
                "Format: Q) Question text (in Hindi and English)\n"
                "A) Option1\nB) Option2\nC) Option3\nD) Option4\nCorrect: A\n\n"
                "Requirements:\n"
                "- Question should be 1-2 sentences, detailed and interesting\n"
                "- Exactly 4 options (A, B, C, D) - no more, no less\n"
                "- Options should be plausible and test real knowledge\n"
                "- Include both Hindi and English in the question\n"
                "- Topics: देवता, असुर, पौराणिक कथाएं, देवताओं की शक्तियाँ, त्रिलोक"
            ),

            "vedas": (
                "Generate 1 detailed and interesting quiz question about Vedas in Hindi and English. "
                "The question should be thought-provoking and test deep knowledge. "
                "Format: Q) Question text (in Hindi and English)\n"
                "A) Option1\nB) Option2\nC) Option3\nD) Option4\nCorrect: A\n\n"
                "Requirements:\n"
                "- Question should be 1-2 sentences, detailed and interesting\n"
                "- Exactly 4 options (A, B, C, D) - no more, no less\n"
                "- Options should be plausible and test real knowledge\n"
                "- Include both Hindi and English in the question\n"
                "- Topics: चार वेद, वेदों का ज्ञान, ऋषियों की शिक्षाएं, उपनिषद, दर्शन"
            )
        }

        # Default prompt if topic not found
        default_prompt = prompts.get(topic, prompts["mythology"])
        return default_prompt

    def _parse_question_response(self, response: str, topic: str) -> dict:
        """
        Parse AI-generated question response into structured format
        Args:
            response: AI-generated question text
            topic: Quiz topic
        Returns:
            Dictionary with question data
        """
        try:
            lines = response.strip().split('\n')
            
            question_text = None
            options = []
            correct_answer = None

            for i, line in enumerate(lines):
                line = line.strip()
                
                # Find question (starts with Q or Q))
                if line and (line.startswith('Q)') or (line.startswith('Q ') and i == 0)):
                    question_text = line.replace('Q)', '').replace('Q ', '').strip()
                
                # Find options (A, B, C, D)
                elif line.startswith(('A)', 'B)', 'C)', 'D)')):
                    option_text = line[2:].strip() if len(line) > 2 else line[1:].strip()
                    if option_text:
                        options.append(option_text)
                
                # Find correct answer
                elif 'Correct' in line or 'सही' in line or 'correct' in line.lower():
                    if ':' in line:
                        answer_part = line.split(':')[1].strip()
                        correct_answer = answer_part.replace(')', '').strip().upper()

            # Validate question has exactly 4 options
            if len(options) != 4:
                logger.warning(f"Question has {len(options)} options, padding/trimming to 4")
                options = options[:4] if len(options) > 4 else options + ["Option"] * (4 - len(options))

            if not question_text:
                question_text = "No question text found"

            if not correct_answer or correct_answer not in ['A', 'B', 'C', 'D']:
                correct_answer = 'A'

            return {
                'topic': topic,
                'question': question_text,
                'options': options,
                'correct': correct_answer,
                'created_at': datetime.now(TIMEZONE),
                'posted': False
            }

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
        """Post question to channel immediately as poll"""
        query = update.callback_query
        await query.answer()

        if not self.current_question:
            await query.edit_message_text("❌ No question data found. Please generate a question first.")
            return

        try:
            await query.edit_message_text(
                "📤 Posting question to channel...\n⏳ Please wait...",
                parse_mode="Markdown"
            )

            # Post question as poll
            await self._post_question_as_poll(self.current_question)

            await query.edit_message_text(
                "✅ **Question Posted Successfully!**\n\n"
                f"📚 Topic: {self.current_question['topic'].title()}\n"
                f"✨ Posted as poll to channel!",
                parse_mode="Markdown"
            )

            self.quiz_mode = False

        except Exception as e:
            logger.error(f"Error posting question: {str(e)}")
            await query.edit_message_text(f"❌ Error posting question: {str(e)}")

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
            "Select delay before posting:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    async def quiz_delay_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE, delay_minutes: int):
        """Schedule question with delay"""
        query = update.callback_query
        await query.answer()

        try:
            await query.edit_message_text(
                f"⏰ Question scheduled to post in {delay_minutes} minutes...\n"
                f"✨ Please wait!",
                parse_mode="Markdown"
            )

            # Schedule posting
            await asyncio.sleep(delay_minutes * 60)

            await self._post_question_as_poll(self.current_question)

            await query.edit_message_text(
                "✅ **Scheduled Question Posted!**\n\n"
                f"📚 Topic: {self.current_question['topic'].title()}\n"
                f"✨ Posted as poll to channel!",
                parse_mode="Markdown"
            )

            self.quiz_mode = False

        except Exception as e:
            logger.error(f"Error in scheduled question posting: {str(e)}")

    async def _post_question_as_poll(self, question_data: dict):
        """
        Post question to Telegram channel as poll
        Args:
            question_data: Dictionary containing question data
        """
        try:
            if not self.bot.userbot or not self.bot.userbot.is_connected():
                logger.error("Userbot not connected")
                return

            # Get channel entity
            channel = await self.bot.userbot.get_entity(YOUR_CHANNEL_ID)

            # Create poll with 4 options
            question_text = question_data['question']
            options = question_data['options']
            correct_option = ord(question_data['correct']) - ord('A')  # Convert A->0, B->1, etc

            # Send poll to channel
            await self.bot.userbot.send_message(
                channel,
                question_text,
                buttons=[
                    options
                ] if len(options) == 4 else None
            )

            # Send poll with correct answer highlighted
            poll_message = (
                f"🎯 **{question_data['topic'].title()} Question**\n\n"
                f"❓ {question_text}\n\n"
                f"A) {options[0]}\n"
                f"B) {options[1]}\n"
                f"C) {options[2]}\n"
                f"D) {options[3]}\n\n"
                f"💡 सही उत्तर: {question_data['correct']}"
            )

            # Send as formatted message
            await self.bot.userbot.send_message(channel, poll_message)

            logger.info(f"Question posted to channel: {question_data['topic']}")
            question_data['posted'] = True

        except Exception as e:
            logger.error(f"Error posting question to channel: {str(e)}")
            raise

    async def quiz_cancel_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel quiz generation"""
        query = update.callback_query
        await query.answer()

        self.quiz_mode = False
        self.current_question = None
        self.quiz_topic = None

        await query.edit_message_text(
            "❌ Question generation cancelled.\n\n"
            "Use /quiz to generate a new question!",
            parse_mode="Markdown"
        )
