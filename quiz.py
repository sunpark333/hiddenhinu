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
import random

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
                ],
                [
                    InlineKeyboardButton("🕌 Bhagavad Gita", callback_data="quiz_gita"),
                    InlineKeyboardButton("⛰️ Himalayas", callback_data="quiz_himalayas")
                ]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "🎯 **Quiz Generator**\n\n"
                "📖 Select a topic to generate AI-powered quiz:\n\n"
                "• **Ramayan** - भगवान राम की गाथा\n"
                "• **Mahabharata** - महाकाव्य की कहानियाँ\n"
                "• **Hindu Mythology** - हिंदू पौराणिक कथाएं\n"
                "• **Vedas** - वेदों का ज्ञान\n"
                "• **Bhagavad Gita** - भगवद् गीता का ज्ञान\n"
                "• **Himalayas** - हिमालय से जुड़ी कथाएं\n\n"
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
                    f"⏳ Please wait... (This may take 20-30 seconds)"
                )
                message_obj = update
            else:
                await update.message.reply_text(
                    f"🎯 **Quiz Generator Started**\n\n"
                    f"📖 Topic: **{topic.title()}**\n"
                    f"🤖 Generating quiz with AI...\n\n"
                    f"⏳ Please wait... (This may take 20-30 seconds)"
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
                    InlineKeyboardButton("🔄 Generate New", callback_data=f"quiz_regenerate_{topic}"),
                    InlineKeyboardButton("❌ Cancel", callback_data="quiz_cancel")
                ]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)

            quiz_preview = self._format_quiz_preview(quiz_data)

            if hasattr(message_obj, 'edit_text'):
                await message_obj.edit_text(
                    f"✅ **Quiz Generated Successfully!**\n\n"
                    f"{quiz_preview}\n\n"
                    f"🎯 Select action:",
                    reply_markup=reply_markup
                )
            elif hasattr(message_obj, 'reply_text'):
                await message_obj.reply_text(
                    f"✅ **Quiz Generated Successfully!**\n\n"
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
            
            # Use AI enhancer to generate quiz with better parameters
            quiz_content = await self.ai_enhancer.enhance_caption(
                prompt,
                temperature=0.8,  # More creative
                max_tokens=1500    # Longer response for detailed questions
            )
            
            if not quiz_content:
                logger.warning("AI returned empty quiz content")
                return None

            # Parse quiz questions from AI response
            quiz_data = self._parse_quiz_response(quiz_content, topic)
            
            if not quiz_data or len(quiz_data['questions']) == 0:
                logger.warning("No valid questions parsed from AI response")
                return None
            
            logger.info(f"Generated quiz for topic: {topic} with {len(quiz_data['questions'])} questions")
            return quiz_data

        except Exception as e:
            logger.error(f"Error generating quiz questions: {str(e)}")
            return None

    def _create_quiz_prompt(self, topic: str) -> str:
        """Create AI prompt for quiz generation with detailed, interesting questions"""
        
        topic_prompts = {
            "ramayan": (
                "Generate 5 interesting and challenging quiz questions about Ramayan with detailed explanations. "
                "Each question should be in Hindi and English, focusing on less-known facts and deeper meanings. "
                "Format exactly:\n\n"
                "Q1) [Interesting question about Ramayan that tests deeper knowledge]\n"
                "A) [Option 1]\n"
                "B) [Option 2]\n"
                "C) [Option 3]\n"
                "D) [Option 4]\n"
                "Correct: [Letter]\n"
                "Explanation: [Detailed explanation of the answer in Hindi and English]\n\n"
                "Questions should cover:\n"
                "- Symbolism and hidden meanings in Ramayan\n"
                - "Lesser-known characters and their roles\n"
                - "Philosophical teachings and moral lessons\n"
                - "Historical and cultural context\n"
                - "Comparisons with other epics\n"
                "Make questions thought-provoking and educational."
            ),
            "mahabharata": (
                "Generate 5 intriguing and educational quiz questions about Mahabharata that test advanced knowledge. "
                "Each question should be in Hindi and English, exploring complex aspects of the epic. "
                "Format exactly:\n\n"
                "Q1) [Challenging question about Mahabharata]\n"
                "A) [Option 1]\n"
                "B) [Option 2]\n"
                "C) [Option 3]\n"
                "D) [Option 4]\n"
                "Correct: [Letter]\n"
                "Explanation: [Comprehensive explanation in Hindi and English]\n\n"
                "Focus on:\n"
                "- Ethical dilemmas and moral complexities\n"
                "- Strategic aspects of the Kurukshetra war\n"
                "- Psychological profiles of characters\n"
                "- Philosophical teachings beyond Bhagavad Gita\n"
                "- Societal structures and dharma concepts\n"
                "Questions should make people think deeply."
            ),
            "mythology": (
                "Generate 5 fascinating quiz questions about Hindu Mythology covering various traditions and regions. "
                "Each question should be in Hindi and English, exploring diverse mythological narratives. "
                "Format exactly:\n\n"
                "Q1) [Engaging question about Hindu mythology]\n"
                "A) [Option 1]\n"
                "B) [Option 2]\n"
                "C) [Option 3]\n"
                "D) [Option 4]\n"
                "Correct: [Letter]\n"
                "Explanation: [Detailed mythological context in Hindi and English]\n\n"
                "Cover:\n"
                "- Regional variations of mythological stories\n"
                - "Symbolism in temple architecture and iconography\n"
                - "Mythological connections to astronomy and science\n"
                - "Folk traditions and local deities\n"
                - "Mythological basis of festivals and rituals\n"
                "Make questions culturally rich and informative."
            ),
            "vedas": (
                "Generate 5 insightful quiz questions about Vedas and Vedic literature. "
                "Each question should be in Hindi and English, focusing on philosophical depth. "
                "Format exactly:\n\n"
                "Q1) [Deep question about Vedic knowledge]\n"
                "A) [Option 1]\n"
                "B) [Option 2]\n"
                "C) [Option 3]\n"
                "D) [Option 4]\n"
                "Correct: [Letter]\n"
                "Explanation: [Scholarly explanation in Hindi and English]\n\n"
                "Topics:\n"
                "- Vedic cosmology and metaphysics\n"
                - "Ritual symbolism and spiritual significance\n"
                - "Vedic mathematics and astronomy\n"
                - "Philosophical schools emerging from Vedas\n"
                - "Modern scientific correlations with Vedic concepts\n"
                "Questions should be intellectually stimulating."
            ),
            "gita": (
                "Generate 5 profound quiz questions about Bhagavad Gita covering philosophical teachings. "
                "Each question should be in Hindi and English, exploring spiritual concepts. "
                "Format exactly:\n\n"
                "Q1) [Philosophical question from Bhagavad Gita]\n"
                "A) [Option 1]\n"
                "B) [Option 2]\n"
                "C) [Option 3]\n"
                "D) [Option 4]\n"
                "Correct: [Letter]\n"
                "Explanation: [Spiritual interpretation in Hindi and English]\n\n"
                "Focus on:\n"
                "- Concepts of Dharma, Karma, and Moksha\n"
                - "Different yoga paths (Jnana, Karma, Bhakti, Dhyana)\n"
                - "Nature of Self (Atman) and Supreme (Brahman)\n"
                - "Practical applications in modern life\n"
                - "Comparative philosophy with other traditions\n"
                "Questions should inspire self-reflection."
            ),
            "himalayas": (
                "Generate 5 captivating quiz questions about Himalayas in Hindu mythology and spirituality. "
                "Each question should be in Hindi and English, connecting geography with mythology. "
                "Format exactly:\n\n"
                "Q1) [Interesting question about Himalayas]\n"
                "A) [Option 1]\n"
                "B) [Option 2]\n"
                "C) [Option 3]\n"
                "D) [Option 4]\n"
                "Correct: [Letter]\n"
                "Explanation: [Cultural and mythological context in Hindi and English]\n\n"
                "Cover:\n"
                "- Mythological significance of Himalayan peaks\n"
                - "Pilgrimage sites and their stories\n"
                - "Himalayan saints and traditions\n"
                - "Ecological importance in Hindu thought\n"
                - "References in scriptures and epics\n"
                "Questions should be geographically and mythologically rich."
            )
        }

        # Default to mythology if topic not found
        return topic_prompts.get(topic, topic_prompts["mythology"])

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
        
        # Split by question blocks
        blocks = response.split('\n\n')
        current_question = None
        
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            
            # Check if this is a new question
            if block.startswith(('Q', 'Question', 'प्रश्न')):
                if current_question and 'text' in current_question and len(current_question.get('options', [])) == 4:
                    questions.append(current_question)
                
                # Start new question
                current_question = {'text': '', 'options': [], 'correct': '', 'explanation': ''}
                
                # Extract question text
                lines = block.split('\n')
                question_text = ''
                for line in lines:
                    if line.startswith(('Q', 'Question', 'प्रश्न')):
                        # Remove Q1), Q2) etc
                        import re
                        question_text = re.sub(r'^Q\d+\)\s*', '', line)
                        question_text = re.sub(r'^Question \d+:\s*', '', question_text)
                        question_text = re.sub(r'^प्रश्न \d+:\s*', '', question_text)
                        current_question['text'] = question_text.strip()
                    elif line.startswith(('A)', 'B)', 'C)', 'D)')):
                        option_text = line[2:].strip()
                        current_question['options'].append(option_text)
                    elif 'Correct:' in line or 'सही:' in line:
                        correct_part = line.split(':')[1].strip().upper()
                        current_question['correct'] = correct_part[0] if correct_part else 'A'
                    elif 'Explanation:' in line or 'व्याख्या:' in line:
                        if ':' in line:
                            current_question['explanation'] = line.split(':', 1)[1].strip()
            
            elif current_question:
                # Continue parsing current question
                if block.startswith(('A)', 'B)', 'C)', 'D)')):
                    option_text = block[2:].strip()
                    current_question['options'].append(option_text)
                elif 'Correct:' in block or 'सही:' in block:
                    correct_part = block.split(':')[1].strip().upper()
                    current_question['correct'] = correct_part[0] if correct_part else 'A'
                elif 'Explanation:' in block or 'व्याख्या:' in block:
                    if ':' in block:
                        current_question['explanation'] = block.split(':', 1)[1].strip()
                elif len(current_question['options']) < 4 and not block.startswith(('Correct', 'Explanation')):
                    # Might be continuation of option text
                    if current_question['options']:
                        current_question['options'][-1] += " " + block
        
        # Add the last question
        if current_question and 'text' in current_question and len(current_question.get('options', [])) == 4:
            questions.append(current_question)
        
        # Validate questions
        valid_questions = []
        for q in questions:
            if (q.get('text') and 
                len(q.get('options', [])) == 4 and 
                q.get('correct') in ['A', 'B', 'C', 'D']):
                valid_questions.append(q)
        
        if not valid_questions:
            # Try alternative parsing method
            valid_questions = self._alternative_parse(response)
        
        return {
            'topic': topic,
            'questions': valid_questions,
            'created_at': datetime.now(TIMEZONE),
            'posted': False
        }

    def _alternative_parse(self, response: str) -> list:
        """Alternative parsing method for AI response"""
        questions = []
        lines = response.split('\n')
        
        current_q = None
        option_count = 0
        
        for line in lines:
            line = line.strip()
            
            # Detect new question
            if line.lower().startswith(('q1', 'q2', 'q3', 'q4', 'q5', 'question')):
                if current_q and len(current_q.get('options', [])) >= 4:
                    questions.append(current_q)
                
                current_q = {
                    'text': '',
                    'options': [],
                    'correct': 'A',
                    'explanation': ''
                }
                option_count = 0
                
                # Extract question text
                import re
                q_match = re.match(r'Q\d+\)\s*(.+)', line) or re.match(r'Question\s*\d+[:.)]\s*(.+)', line)
                if q_match:
                    current_q['text'] = q_match.group(1)
                else:
                    current_q['text'] = line
            
            elif current_q:
                # Check for options
                option_match = re.match(r'([A-D])[).]\s*(.+)', line)
                if option_match:
                    option_letter = option_match.group(1)
                    option_text = option_match.group(2)
                    current_q['options'].append(option_text)
                    option_count += 1
                
                # Check for correct answer
                elif 'correct' in line.lower() or 'answer:' in line.lower():
                    for letter in ['A', 'B', 'C', 'D']:
                        if f' {letter})' in line.upper() or f': {letter}' in line.upper():
                            current_q['correct'] = letter
                            break
                
                # Check for explanation
                elif 'explanation' in line.lower() or 'व्याख्या' in line.lower():
                    if ':' in line:
                        current_q['explanation'] = line.split(':', 1)[1].strip()
        
        # Add last question
        if current_q and len(current_q.get('options', [])) >= 4:
            questions.append(current_q)
        
        return questions[:5]  # Return max 5 questions

    def _format_quiz_preview(self, quiz_data: dict) -> str:
        """Format quiz for preview display"""
        if not quiz_data or not quiz_data.get('questions'):
            return "❌ No questions generated. Please try again."
        
        preview = f"📚 **{quiz_data['topic'].title()} Quiz**\n\n"
        preview += f"📊 Questions Generated: {len(quiz_data['questions'])}\n"
        preview += f"⏱️ Created: {quiz_data['created_at'].strftime('%Y-%m-%d %H:%M')}\n\n"
        
        preview += "**Sample Question:**\n"
        if quiz_data['questions']:
            q = quiz_data['questions'][0]
            preview += f"\n{q['text']}\n"
            for i, opt in enumerate(q['options'], 1):
                preview += f"\n{chr(64+i)}) {opt}"
            
            if q.get('explanation'):
                preview += f"\n\n💡 **Explanation Preview:**\n{q['explanation'][:150]}..."
        
        return preview

    async def quiz_post_now_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Post quiz to channel immediately"""
        query = update.callback_query
        await query.answer()

        if not self.current_quiz or not self.current_quiz.get('questions'):
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
                f"🤖 AI-Generated Question\n"
                f"📊 Posted as interactive poll\n"
                f"✨ Channel updated!"
            )

            self.quiz_mode = False

        except Exception as e:
            logger.error(f"Error posting quiz: {str(e)}")
            await query.edit_message_text(f"❌ Error posting quiz: {str(e)}")

    async def quiz_regenerate_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE, topic: str):
        """Regenerate quiz for the same topic"""
        query = update.callback_query
        await query.answer()

        await self._start_quiz_generation(query, context, topic)

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
            [InlineKeyboardButton("⏰ 6 hours", callback_data="quiz_delay_360")],
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
                f"✨ Will be posted automatically!"
            )

            # Schedule posting
            await asyncio.sleep(delay_minutes * 60)
            
            if self.current_quiz:
                await self._post_quiz_to_channel(self.current_quiz)
                
                await query.edit_message_text(
                    "✅ **Scheduled Quiz Posted!**\n\n"
                    f"📚 Topic: {self.current_quiz['topic'].title()}\n"
                    f"🤖 AI-Generated Question\n"
                    f"📊 Posted as interactive poll\n"
                    f"⏰ Posted after {delay_minutes} minutes"
                )

            self.quiz_mode = False

        except Exception as e:
            logger.error(f"Error in scheduled quiz posting: {str(e)}")
            await query.edit_message_text(f"❌ Error in scheduled posting: {str(e)}")

    async def _post_quiz_to_channel(self, quiz_data: dict):
        """
        Post quiz to Telegram channel as poll (Only 1 question, poll format only)
        
        Args:
            quiz_data: Dictionary containing quiz questions
        """
        try:
            if not self.bot.userbot or not self.bot.userbot.is_connected():
                logger.error("Userbot not connected")
                return

            if not quiz_data.get('questions'):
                logger.error("No questions in quiz data")
                return

            # Get ONLY ONE random question from the quiz
            question = random.choice(quiz_data['questions'])
            
            # Create poll message with topic context
            poll_question = f"🎯 {quiz_data['topic'].title()} Quiz\n\n{question['text']}"
            
            # Get options for poll (ensure exactly 4)
            poll_options = question['options']
            if len(poll_options) != 4:
                logger.warning(f"Question has {len(poll_options)} options, expected 4")
                # Pad or truncate to 4 options
                if len(poll_options) < 4:
                    poll_options = poll_options + [f"Option {i+1}" for i in range(len(poll_options), 4)]
                else:
                    poll_options = poll_options[:4]
            
            # Determine correct option index (0-3)
            correct_index = ord(question.get('correct', 'A')) - ord('A')
            if correct_index < 0 or correct_index > 3:
                correct_index = 0
            
            # Send poll to channel using telethon
            channel = await self.bot.userbot.get_entity(YOUR_CHANNEL_ID)
            
            # Create poll with correct answer
            poll = await self.bot.userbot.send_message(
                entity=channel,
                message=poll_question,
                silent=None,
                background=None,
                clear_draft=None,
                reply_to=None,
                schedule=None,
                buttons=None,
                link_preview=True,
                file=None,
                formatting_entities=None,
                supports_streaming=True,
                noforwards=False,
                comment_to=None,
                send_as=None,
                poll=dict(
                    question=poll_question[:255],  # Telegram limit
                    answers=[
                        dict(text=opt[:100], option=b'1') for opt in poll_options
                    ],
                    closed=False,
                    multiple_choice=False,
                    public_voters=True,
                    quiz=True,
                    close_date=None,
                    correct_answers=[correct_index] if 0 <= correct_index < 4 else None
                )
            )

            logger.info(f"Single AI-generated quiz question posted as poll to channel: {quiz_data['topic']}")
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
