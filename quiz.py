"""
Quiz Generator - AI-powered quiz creation and posting
Generates quizzes on topics like Ramayan and Mahabharata
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
    """Generate and post quizzes to Telegram channels"""
    
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
        self.current_quiz = None
        self.quiz_scheduled = False

    async def quiz_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /quiz command - Start quiz generation
        Usage: /quiz <topic>
        Examples: /quiz ramayan, /quiz mahabharata
        """
        if not await self.bot.handlers.admin_only(update, context):
            return

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
                "📖 Select a topic to generate AI-powered quiz:\n\n"
                "• **Ramayan** - भगवान राम की गाथा\n"
                "• **Mahabharata** - महाकाव्य की कहानियाँ\n"
                "• **Hindu Mythology** - हिंदू पौराणिक कथाएं\n"
                "• **Vedas** - वेदों का ज्ञान\n\n"
                "📋 या command से use करो: `/quiz <topic>`",
                reply_markup=reply_markup
            )
            return

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
                    f"🤖 Generating quiz with AI...\n\n"
                    f"⏳ Please wait..."
                )
                message_obj = update
            else:
                await update.message.reply_text(
                    f"🎯 **Quiz Generator Started**\n\n"
                    f"📖 Topic: **{topic.title()}**\n"
                    f"🤖 Generating quiz with AI...\n\n"
                    f"⏳ Please wait..."
                )
                message_obj = update.message

            self.quiz_topic = topic
            self.quiz_mode = True

            # Generate quiz questions using AI
            quiz_data = await self._generate_quiz_questions(topic)

            if not quiz_data:
                error_msg = "❌ Failed to generate quiz. Please try again."
                if hasattr(message_obj, 'edit_text'):
                    await message_obj.edit_text(error_msg)
                elif hasattr(message_obj, 'reply_text'):
                    await message_obj.reply_text(error_msg)
                return

            self.current_quiz = quiz_data

            # Show scheduling options
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

            quiz_preview = self._format_quiz_preview(quiz_data)

            if hasattr(message_obj, 'edit_text'):
                await message_obj.edit_text(
                    f"✅ **Quiz Generated!**\n\n"
                    f"{quiz_preview}\n\n"
                    f"🎯 Select action:",
                    reply_markup=reply_markup
                )
            elif hasattr(message_obj, 'reply_text'):
                await message_obj.reply_text(
                    f"✅ **Quiz Generated!**\n\n"
                    f"{quiz_preview}\n\n"
                    f"🎯 Select action:",
                    reply_markup=reply_markup
                )

        except Exception as e:
            logger.error(f"Error in quiz generation: {str(e)}")
            error_msg = f"❌ Error generating quiz: {str(e)}"
            
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
            elif hasattr(update, 'message') and update.message:
                await update.message.reply_text(error_msg)

    async def _generate_quiz_questions(self, topic: str) -> dict:
        """
        Generate quiz questions using AI
        
        Args:
            topic: Topic for quiz (ramayan, mahabharata, etc)
            
        Returns:
            Dictionary with quiz data or None if failed
        """
        try:
            prompt = self._create_quiz_prompt(topic)
            
            # Use AI enhancer to generate quiz
            quiz_content = await self.ai_enhancer.enhance_caption(prompt)
            
            if not quiz_content:
                logger.warning("AI returned empty quiz content")
                return None

            # Parse quiz questions from AI response
            quiz_data = self._parse_quiz_response(quiz_content, topic)
            
            logger.info(f"Generated quiz for topic: {topic}")
            return quiz_data

        except Exception as e:
            logger.error(f"Error generating quiz questions: {str(e)}")
            return None

    def _create_quiz_prompt(self, topic: str) -> str:
        """Create AI prompt for quiz generation"""
        
        prompts = {
            "ramayan": (
                "Generate a fun and educational quiz about Ramayan with 5 questions. "
                "Each question should be in Hindi and English with 4 options (A, B, C, D). "
                "Format: Q1) Question text\nA) Option1\nB) Option2\nC) Option3\nD) Option4\nCorrect: A\n\n"
                "Questions should be about:\n"
                "- राम की कहानी / Rama's story\n"
                "- सीता का परिचय / Sita's story\n"
                "- लंका विजय / Lanka conquest\n"
                "- नैतिक पाठ / Moral lessons\n"
                "- महत्वपूर्ण घटनाएं / Important events"
            ),
            "mahabharata": (
                "Generate a fun and educational quiz about Mahabharata with 5 questions. "
                "Each question should be in Hindi and English with 4 options (A, B, C, D). "
                "Format: Q1) Question text\nA) Option1\nB) Option2\nC) Option3\nD) Option4\nCorrect: A\n\n"
                "Questions should be about:\n"
                "- पांडव और कौरव / Pandavas and Kauravas\n"
                "- भीष्म की कहानी / Bhishma's role\n"
                "- कुरुक्षेत्र युद्ध / Kurukshetra war\n"
                "- कृष्ण की शिक्षा / Krishna's teachings\n"
                "- युद्ध की कहानियाँ / Battle stories"
            ),
            "mythology": (
                "Generate a fun and educational quiz about Hindu Mythology with 5 questions. "
                "Each question should be in Hindi and English with 4 options (A, B, C, D). "
                "Format: Q1) Question text\nA) Option1\nB) Option2\nC) Option3\nD) Option4\nCorrect: A\n\n"
                "Questions should be about:\n"
                "- देवता और असुर / Gods and demons\n"
                "- पौराणिक कथाएं / Mythological tales\n"
                "- देवताओं के नाम / Names of deities\n"
                "- त्रिमूर्ति / Trinity\n"
                "- शास्त्रों का ज्ञान / Scriptural knowledge"
            ),
            "vedas": (
                "Generate a fun and educational quiz about Vedas with 5 questions. "
                "Each question should be in Hindi and English with 4 options (A, B, C, D). "
                "Format: Q1) Question text\nA) Option1\nB) Option2\nC) Option3\nD) Option4\nCorrect: A\n\n"
                "Questions should be about:\n"
                "- चार वेद / Four Vedas\n"
                "- वेदों का महत्व / Vedas' significance\n"
                "- उपनिषद / Upanishads\n"
                "- योग और दर्शन / Philosophy\n"
                "- प्राचीन ज्ञान / Ancient wisdom"
            )
        }

        # Default prompt if topic not found
        default_prompt = prompts.get(topic, prompts["mythology"])
        
        return default_prompt

    def _parse_quiz_response(self, response: str, topic: str) -> dict:
        """
        Parse AI-generated quiz response into structured format
        
        Args:
            response: AI-generated quiz text
            topic: Quiz topic
            
        Returns:
            Dictionary with quiz questions
        """
        questions = []
        
        # Split by question markers
        q_blocks = response.split('\n\n')
        
        for block in q_blocks:
            if not block.strip() or 'Q' not in block[:5]:
                continue
                
            lines = block.strip().split('\n')
            if len(lines) < 5:
                continue
            
            try:
                # Extract question text
                question_line = lines[0]
                question_text = question_line.replace('Q', '').replace(')', '').strip()
                
                # Extract options
                options = []
                correct_answer = None
                
                for line in lines[1:]:
                    line = line.strip()
                    
                    if line.startswith(('A)', 'B)', 'C)', 'D)')):
                        option_text = line[2:].strip()
                        options.append(option_text)
                    
                    if 'Correct' in line or 'सही' in line:
                        # Extract correct answer
                        if ':' in line:
                            correct_answer = line.split(':')[1].strip().upper()
                
                if len(options) == 4 and question_text:
                    questions.append({
                        'text': question_text,
                        'options': options,
                        'correct': correct_answer or 'A'
                    })
            
            except Exception as e:
                logger.warning(f"Error parsing question block: {str(e)}")
                continue
        
        return {
            'topic': topic,
            'questions': questions if questions else self._get_default_quiz(topic),
            'created_at': datetime.now(TIMEZONE),
            'posted': False
        }

    def _get_default_quiz(self, topic: str) -> list:
        """Get default quiz questions if AI generation fails"""
        
        default_quizzes = {
            "ramayan": [
                {
                    "text": "राम के पिता का नाम क्या था? / Who was Rama's father?",
                    "options": ["दशरथ / Dasharatha", "विश्वामित्र / Vishwamitra", "अग्नि / Agni", "इंद्र / Indra"],
                    "correct": "A"
                },
                {
                    "text": "सीता किस राज्य की राजकुमारी थीं? / Which kingdom's princess was Sita?",
                    "options": ["मिथिला / Mithila", "अयोध्या / Ayodhya", "लंका / Lanka", "विदेह / Videha"],
                    "correct": "A"
                },
                {
                    "text": "राम का वनवास कितने वर्ष का था? / How many years was Rama's exile?",
                    "options": ["5 वर्ष / years", "10 वर्ष / years", "14 वर्ष / years", "7 वर्ष / years"],
                    "correct": "C"
                },
                {
                    "text": "लंका के राजा का नाम क्या था? / What was the name of Lanka's king?",
                    "options": ["कुंभकरण / Kumbhakarna", "रावण / Ravana", "मेघनाद / Meghnath", "विभीषण / Vibhishan"],
                    "correct": "B"
                },
                {
                    "text": "हनुमान किस देवता के अवतार माने जाते हैं? / Hanuman is considered an avatar of?",
                    "options": ["वायु / Vayu", "शिव / Shiva", "विष्णु / Vishnu", "ब्रह्मा / Brahma"],
                    "correct": "A"
                }
            ],
            "mahabharata": [
                {
                    "text": "महाभारत का लेखक कौन था? / Who wrote the Mahabharata?",
                    "options": ["वेदव्यास / Vedvyas", "कालिदास / Kalidasa", "तुलसीदास / Tulsidas", "भवभूति / Bhavabhuti"],
                    "correct": "A"
                },
                {
                    "text": "कुरुक्षेत्र युद्ध कितने दिन चला? / How many days did Kurukshetra war last?",
                    "options": ["7 दिन / days", "14 दिन / days", "18 दिन / days", "21 दिन / days"],
                    "correct": "C"
                },
                {
                    "text": "पांडवों की संख्या कितनी थी? / How many Pandavas were there?",
                    "options": ["3", "5", "7", "10"],
                    "correct": "B"
                },
                {
                    "text": "युधिष्ठिर के अन्य भाइयों के नाम बताइए। / Yudhishthira's brothers were:",
                    "options": ["भीम और अर्जुन / Bhima and Arjun", "भीम, अर्जुन, नकुल, सहदेव / All of these", "नकुल और सहदेव / Nakul and Sahadev", "सिर्फ अर्जुन / Only Arjun"],
                    "correct": "B"
                },
                {
                    "text": "गीता किसने किसको सुनाई? / Who told Gita to whom?",
                    "options": ["शिव ने पार्वती को / Shiva to Parvati", "कृष्ण ने अर्जुन को / Krishna to Arjun", "व्यास ने युधिष्ठिर को / Vyasa to Yudhisthira", "ब्रह्मा ने देवताओं को / Brahma to deities"],
                    "correct": "B"
                }
            ]
        }
        
        return default_quizzes.get(topic, default_quizzes["ramayan"])

    def _format_quiz_preview(self, quiz_data: dict) -> str:
        """Format quiz for preview display"""
        preview = f"📚 **{quiz_data['topic'].title()} Quiz**\n\n"
        preview += f"📊 Questions: {len(quiz_data['questions'])}\n"
        preview += f"⏱️ Created: {quiz_data['created_at'].strftime('%Y-%m-%d %H:%M')}\n\n"
        
        preview += "**Sample Questions:**\n"
        for i, q in enumerate(quiz_data['questions'][:2], 1):
            preview += f"\n{i}. {q['text']}\n"
            for j, opt in enumerate(q['options'], 1):
                preview += f"   {chr(64+j)}) {opt}\n"
        
        if len(quiz_data['questions']) > 2:
            preview += f"\n... और {len(quiz_data['questions']) - 2} और प्रश्न"
        
        return preview

    async def quiz_post_now_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Post quiz to channel immediately"""
        query = update.callback_query
        await query.answer()

        if not self.current_quiz:
            await query.edit_message_text("❌ No quiz data found. Please generate a quiz first.")
            return

        try:
            await query.edit_message_text(
                "📤 Posting quiz to channel...\n⏳ Please wait..."
            )

            # Post quiz to channel
            await self._post_quiz_to_channel(self.current_quiz)

            await query.edit_message_text(
                "✅ **Quiz Posted Successfully!**\n\n"
                f"📚 Topic: {self.current_quiz['topic'].title()}\n"
                f"📊 Questions: {len(self.current_quiz['questions'])}\n"
                f"✨ Posted to channel!"
            )

            self.quiz_mode = False

        except Exception as e:
            logger.error(f"Error posting quiz: {str(e)}")
            await query.edit_message_text(f"❌ Error posting quiz: {str(e)}")

    async def quiz_schedule_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Schedule quiz posting"""
        query = update.callback_query
        await query.answer()

        if not self.current_quiz:
            await query.edit_message_text("❌ No quiz data found.")
            return

        keyboard = [
            [InlineKeyboardButton("⏰ 30 minutes", callback_data="quiz_delay_30")],
            [InlineKeyboardButton("⏰ 1 hour", callback_data="quiz_delay_60")],
            [InlineKeyboardButton("⏰ 2 hours", callback_data="quiz_delay_120")],
            [InlineKeyboardButton("❌ Cancel", callback_data="quiz_cancel")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "⏰ **Schedule Quiz Posting**\n\n"
            "Select delay before posting:",
            reply_markup=reply_markup
        )

    async def quiz_delay_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE, delay_minutes: int):
        """Schedule quiz with delay"""
        query = update.callback_query
        await query.answer()

        try:
            await query.edit_message_text(
                f"⏰ Quiz scheduled to post in {delay_minutes} minutes...\n"
                f"✨ Please wait!"
            )

            # Schedule posting
            await asyncio.sleep(delay_minutes * 60)
            await self._post_quiz_to_channel(self.current_quiz)

            await query.edit_message_text(
                "✅ **Scheduled Quiz Posted!**\n\n"
                f"📚 Topic: {self.current_quiz['topic'].title()}\n"
                f"📊 Questions: {len(self.current_quiz['questions'])}\n"
                f"✨ Posted to channel!"
            )

            self.quiz_mode = False

        except Exception as e:
            logger.error(f"Error in scheduled quiz posting: {str(e)}")

    async def _post_quiz_to_channel(self, quiz_data: dict):
        """
        Post quiz to Telegram channel as poll
        
        Args:
            quiz_data: Dictionary containing quiz questions
        """
        try:
            if not self.bot.userbot or not self.bot.userbot.is_connected():
                logger.error("Userbot not connected")
                return

            # Get first question for poll
            first_question = quiz_data['questions'][0]
            
            # Create poll message
            poll_message = (
                f"🎯 **{quiz_data['topic'].title()} Quiz**\n\n"
                f"{first_question['text']}\n\n"
                f"📊 Total Questions: {len(quiz_data['questions'])}"
            )

            # Send poll to channel
            channel = await self.bot.userbot.get_entity(YOUR_CHANNEL_ID)
            
            # Send as message with options
            await self.bot.userbot.send_message(
                channel,
                poll_message
            )

            # Send each question as separate message
            for i, question in enumerate(quiz_data['questions'], 1):
                question_text = (
                    f"**प्रश्न {i}/{len(quiz_data['questions'])}**\n\n"
                    f"{question['text']}\n\n"
                    f"A) {question['options'][0]}\n"
                    f"B) {question['options'][1]}\n"
                    f"C) {question['options'][2]}\n"
                    f"D) {question['options'][3]}\n\n"
                    f"💡 सही उत्तर: {question['correct']}"
                )
                
                await self.bot.userbot.send_message(
                    channel,
                    question_text
                )
                
                await asyncio.sleep(1)  # Delay between posts

            logger.info(f"Quiz posted to channel: {quiz_data['topic']}")
            quiz_data['posted'] = True

        except Exception as e:
            logger.error(f"Error posting quiz to channel: {str(e)}")
            raise

    async def quiz_cancel_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel quiz generation"""
        query = update.callback_query
        await query.answer()

        self.quiz_mode = False
        self.current_quiz = None
        self.quiz_topic = None

        await query.edit_message_text(
            "❌ Quiz generation cancelled.\n\n"
            "Use /quiz to start a new quiz!"
        )
