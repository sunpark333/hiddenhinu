"""
Quiz Generator - AI-powered quiz creation and posting
Generates quizzes on topics like Ramayan and Mahabharata
"""

import logging
import asyncio
import random
import re
from datetime import datetime
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
                reply_markup=reply_markup,
                parse_mode="Markdown"
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
                    f"⏳ Please wait... (This may take 20-30 seconds)",
                    parse_mode="Markdown"
                )
                message_obj = update
            else:
                await update.message.reply_text(
                    f"🎯 **Quiz Generator Started**\n\n"
                    f"📖 Topic: **{topic.title()}**\n"
                    f"🤖 Generating quiz with AI...\n\n"
                    f"⏳ Please wait... (This may take 20-30 seconds)",
                    parse_mode="Markdown"
                )
                message_obj = update.message

            self.quiz_topic = topic
            self.quiz_mode = True

            # Generate quiz questions using AI
            quiz_data = await self._generate_quiz_questions(topic)

            if not quiz_data:
                error_msg = "❌ Failed to generate quiz. Please try again."
                if hasattr(message_obj, 'edit_text'):
                    await message_obj.edit_text(error_msg, parse_mode="Markdown")
                elif hasattr(message_obj, 'reply_text'):
                    await message_obj.reply_text(error_msg, parse_mode="Markdown")
                return

            self.current_quiz = quiz_data

            # Show scheduling options
            keyboard = [
                [
                    InlineKeyboardButton("📤 Post Now", callback_data="quiz_post_now"),
                    InlineKeyboardButton("⏰ Schedule", callback_data="quiz_schedule")
                ],
                [
                    InlineKeyboardButton("🔄 Generate New", callback_data=f"quiz_regenerate_{topic.replace(' ', '_')}"),
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
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            elif hasattr(message_obj, 'reply_text'):
                await message_obj.reply_text(
                    f"✅ **Quiz Generated Successfully!**\n\n"
                    f"{quiz_preview}\n\n"
                    f"🎯 Select action:",
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )

        except Exception as e:
            logger.error(f"Error in quiz generation: {str(e)}")
            error_msg = f"❌ Error generating quiz: {str(e)}"
            
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(error_msg, parse_mode="Markdown")
            elif hasattr(update, 'message') and update.message:
                await update.message.reply_text(error_msg, parse_mode="Markdown")

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
            quiz_content = await self.ai_enhancer.generate_content(
                prompt=prompt,
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
                "Format exactly as follows:\n\n"
                "Q1) [Interesting question about Ramayan that tests deeper knowledge]\n"
                "A) [Option 1]\n"
                "B) [Option 2]\n"
                "C) [Option 3]\n"
                "D) [Option 4]\n"
                "Correct: [Single letter A, B, C, or D]\n"
                "Explanation: [Detailed explanation of the answer in Hindi and English]\n\n"
                "Make questions thought-provoking and educational."
            ),
            "mahabharata": (
                "Generate 5 intriguing and educational quiz questions about Mahabharata that test advanced knowledge. "
                "Each question should be in Hindi and English, exploring complex aspects of the epic. "
                "Format exactly as follows:\n\n"
                "Q1) [Challenging question about Mahabharata]\n"
                "A) [Option 1]\n"
                "B) [Option 2]\n"
                "C) [Option 3]\n"
                "D) [Option 4]\n"
                "Correct: [Single letter A, B, C, or D]\n"
                "Explanation: [Comprehensive explanation in Hindi and English]\n\n"
                "Focus on ethical dilemmas, strategic aspects, and philosophical teachings."
            ),
            "mythology": (
                "Generate 5 fascinating quiz questions about Hindu Mythology covering various traditions and regions. "
                "Each question should be in Hindi and English, exploring diverse mythological narratives. "
                "Format exactly as follows:\n\n"
                "Q1) [Engaging question about Hindu mythology]\n"
                "A) [Option 1]\n"
                "B) [Option 2]\n"
                "C) [Option 3]\n"
                "D) [Option 4]\n"
                "Correct: [Single letter A, B, C, or D]\n"
                "Explanation: [Detailed mythological context in Hindi and English]\n\n"
                "Make questions culturally rich and informative."
            ),
            "vedas": (
                "Generate 5 insightful quiz questions about Vedas and Vedic literature. "
                "Each question should be in Hindi and English, focusing on philosophical depth. "
                "Format exactly as follows:\n\n"
                "Q1) [Deep question about Vedic knowledge]\n"
                "A) [Option 1]\n"
                "B) [Option 2]\n"
                "C) [Option 3]\n"
                "D) [Option 4]\n"
                "Correct: [Single letter A, B, C, or D]\n"
                "Explanation: [Scholarly explanation in Hindi and English]\n\n"
                "Questions should be intellectually stimulating."
            ),
            "gita": (
                "Generate 5 profound quiz questions about Bhagavad Gita covering philosophical teachings. "
                "Each question should be in Hindi and English, exploring spiritual concepts. "
                "Format exactly as follows:\n\n"
                "Q1) [Philosophical question from Bhagavad Gita]\n"
                "A) [Option 1]\n"
                "B) [Option 2]\n"
                "C) [Option 3]\n"
                "D) [Option 4]\n"
                "Correct: [Single letter A, B, C, or D]\n"
                "Explanation: [Spiritual interpretation in Hindi and English]\n\n"
                "Focus on concepts of Dharma, Karma, and different yoga paths."
            ),
            "himalayas": (
                "Generate 5 captivating quiz questions about Himalayas in Hindu mythology and spirituality. "
                "Each question should be in Hindi and English, connecting geography with mythology. "
                "Format exactly as follows:\n\n"
                "Q1) [Interesting question about Himalayas]\n"
                "A) [Option 1]\n"
                "B) [Option 2]\n"
                "C) [Option 3]\n"
                "D) [Option 4]\n"
                "Correct: [Single letter A, B, C, or D]\n"
                "Explanation: [Cultural and mythological context in Hindi and English]\n\n"
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
        
        # Clean the response
        response = response.strip()
        
        # Split into blocks by double newlines
        blocks = [b.strip() for b in response.split('\n\n') if b.strip()]
        
        for block in blocks:
            lines = [line.strip() for line in block.split('\n') if line.strip()]
            if len(lines) < 6:  # Need at least Q, 4 options, and correct
                continue
            
            current_question = {
                'text': '',
                'options': [],
                'correct': 'A',
                'explanation': ''
            }
            
            option_count = 0
            explanation_started = False
            
            for line in lines:
                # Check for question
                if re.match(r'^Q\d+[).]\s*', line) or line.lower().startswith('question'):
                    # Extract question text
                    match = re.match(r'^Q\d+[).]\s*(.+)', line)
                    if match:
                        current_question['text'] = match.group(1)
                    else:
                        # Remove "Question X: " prefix
                        current_question['text'] = re.sub(r'^Question\s*\d+[:.)]\s*', '', line, flags=re.IGNORECASE)
                
                # Check for options A-D
                elif re.match(r'^[A-D][).]\s*.+', line):
                    if option_count < 4:
                        option_text = re.sub(r'^[A-D][).]\s*', '', line)
                        current_question['options'].append(option_text)
                        option_count += 1
                
                # Check for correct answer
                elif 'correct:' in line.lower() or 'answer:' in line.lower():
                    # Extract the letter after "Correct: "
                    match = re.search(r'correct:\s*([A-D])', line, re.IGNORECASE)
                    if match:
                        current_question['correct'] = match.group(1).upper()
                    else:
                        # Try to find A, B, C, D in the line
                        for char in line.upper():
                            if char in ['A', 'B', 'C', 'D']:
                                current_question['correct'] = char
                                break
                
                # Check for explanation
                elif 'explanation:' in line.lower() or 'व्याख्या:' in line:
                    explanation_started = True
                    exp_text = re.split(r'explanation:|व्याख्या:', line, flags=re.IGNORECASE)[-1].strip()
                    current_question['explanation'] = exp_text
                
                # Continue explanation on next lines
                elif explanation_started:
                    current_question['explanation'] += " " + line
            
            # Validate and add the question
            if (current_question['text'] and 
                len(current_question['options']) == 4 and
                current_question['correct'] in ['A', 'B', 'C', 'D']):
                
                # Ensure options are not empty
                valid_options = all(opt.strip() for opt in current_question['options'])
                if valid_options:
                    questions.append(current_question)
        
        # If parsing failed, try alternative method
        if not questions:
            questions = self._alternative_parse(response)
        
        return {
            'topic': topic,
            'questions': questions[:5],  # Limit to 5 questions
            'created_at': datetime.now(TIMEZONE),
            'posted': False
        }

    def _alternative_parse(self, response: str) -> list:
        """Alternative parsing method for AI response"""
        questions = []
        
        # Find all question sections
        question_sections = re.split(r'(?=Q\d+[).]|Question\s*\d+)', response)
        
        for section in question_sections:
            if not section.strip():
                continue
            
            question = {
                'text': '',
                'options': [],
                'correct': 'A',
                'explanation': ''
            }
            
            # Extract question text
            q_match = re.search(r'(?:Q\d+[).]|Question\s*\d+[:.)])\s*(.+)', section, re.DOTALL)
            if q_match:
                question['text'] = q_match.group(1).split('\n')[0].strip()
            
            # Extract options
            options = re.findall(r'^[A-D][).]\s*(.+)$', section, re.MULTILINE)
            if len(options) >= 4:
                question['options'] = options[:4]
            
            # Extract correct answer
            correct_match = re.search(r'Correct:\s*([A-D])', section, re.IGNORECASE)
            if correct_match:
                question['correct'] = correct_match.group(1).upper()
            
            # Only add if valid
            if question['text'] and len(question['options']) == 4:
                questions.append(question)
        
        return questions

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
                preview += f"\n\n💡 **Explanation:**\n{q['explanation'][:150]}..."
            else:
                preview += f"\n\n✅ **Correct Answer:** {q['correct']}"
        
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
                "📤 Posting quiz to channel...\n⏳ Please wait...",
                parse_mode="Markdown"
            )

            # Post quiz to channel
            await self._post_quiz_to_channel(self.current_quiz)

            await query.edit_message_text(
                "✅ **Quiz Posted Successfully!**\n\n"
                f"📚 Topic: {self.current_quiz['topic'].title()}\n"
                f"🤖 AI-Generated Question\n"
                f"📊 Posted as interactive poll\n"
                f"✨ Channel updated!",
                parse_mode="Markdown"
            )

            self.quiz_mode = False

        except Exception as e:
            logger.error(f"Error posting quiz: {str(e)}")
            await query.edit_message_text(f"❌ Error posting quiz: {str(e)}", parse_mode="Markdown")

    async def quiz_regenerate_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Regenerate quiz for the same topic"""
        query = update.callback_query
        await query.answer()

        # Extract topic from callback data
        callback_data = query.data
        if callback_data.startswith("quiz_regenerate_"):
            topic = callback_data.replace("quiz_regenerate_", "").replace("_", " ")
            await self._start_quiz_generation(query, context, topic)

    async def quiz_schedule_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Schedule quiz posting"""
        query = update.callback_query
        await query.answer()

        if not self.current_quiz:
            await query.edit_message_text("❌ No quiz data found.", parse_mode="Markdown")
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
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    async def quiz_delay_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE, delay_minutes: int):
        """Schedule quiz with delay"""
        query = update.callback_query
        await query.answer()

        try:
            await query.edit_message_text(
                f"⏰ Quiz scheduled to post in {delay_minutes} minutes...\n"
                f"✨ Will be posted automatically!",
                parse_mode="Markdown"
            )

            # Schedule posting
            await asyncio.sleep(delay_minutes * 60)
            
            if self.current_quiz and self.current_quiz.get('questions'):
                await self._post_quiz_to_channel(self.current_quiz)
                
                await query.edit_message_text(
                    "✅ **Scheduled Quiz Posted!**\n\n"
                    f"📚 Topic: {self.current_quiz['topic'].title()}\n"
                    f"🤖 AI-Generated Question\n"
                    f"📊 Posted as interactive poll\n"
                    f"⏰ Posted after {delay_minutes} minutes",
                    parse_mode="Markdown"
                )

            self.quiz_mode = False

        except Exception as e:
            logger.error(f"Error in scheduled quiz posting: {str(e)}")
            await query.edit_message_text(f"❌ Error in scheduled posting: {str(e)}", parse_mode="Markdown")

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
            
            # Validate and clean options
            cleaned_options = []
            for opt in poll_options:
                if isinstance(opt, str):
                    # Clean the option text
                    cleaned = opt.strip()
                    if cleaned:
                        cleaned_options.append(cleaned[:100])  # Telegram limit
            
            # Ensure we have exactly 4 options
            if len(cleaned_options) != 4:
                logger.warning(f"Question has {len(cleaned_options)} valid options, expected 4")
                # Create placeholder options if needed
                while len(cleaned_options) < 4:
                    cleaned_options.append(f"Option {len(cleaned_options) + 1}")
                cleaned_options = cleaned_options[:4]
            
            poll_options = cleaned_options
            
            # Determine correct option index (0-3) with better error handling
            correct_answer = question.get('correct', 'A')
            
            # Ensure correct_answer is a single character A-D
            if isinstance(correct_answer, str):
                # Extract first character and convert to uppercase
                correct_answer = correct_answer.strip().upper()
                if correct_answer and correct_answer[0] in ['A', 'B', 'C', 'D']:
                    correct_answer = correct_answer[0]
                else:
                    correct_answer = 'A'
            else:
                correct_answer = 'A'
            
            # Convert to index (0-3)
            try:
                correct_index = ord(correct_answer) - ord('A')
                if correct_index < 0 or correct_index > 3:
                    correct_index = 0
            except:
                correct_index = 0
            
            # Send poll to channel using telethon
            channel = await self.bot.userbot.get_entity(YOUR_CHANNEL_ID)
            
            # Create poll answers list
            poll_answers = []
            for i, opt in enumerate(poll_options):
                poll_answers.append({
                    'text': opt[:100],  # Telegram limit for poll option text
                    'option': bytes([i + 1])  # Option bytes 1, 2, 3, 4
                })
            
            # Send the poll
            await self.bot.userbot.send_message(
                entity=channel,
                message=poll_question,
                silent=None,
                background=None,
                clear_draft=None,
                reply_to=None,
                schedule=None,
                buttons=None,
                link_preview=False,  # Disable link preview for polls
                file=None,
                formatting_entities=None,
                supports_streaming=True,
                noforwards=False,
                comment_to=None,
                send_as=None,
                poll={
                    'question': poll_question[:255],  # Telegram question limit
                    'answers': poll_answers,
                    'closed': False,
                    'multiple_choice': False,
                    'public_voters': True,
                    'quiz': True,
                    'close_date': None,
                    'correct_answers': [correct_index] if 0 <= correct_index < 4 else None
                }
            )

            logger.info(f"Single AI-generated quiz question posted as poll to channel: {quiz_data['topic']}")
            quiz_data['posted'] = True

        except Exception as e:
            logger.error(f"Error posting quiz to channel: {str(e)}", exc_info=True)
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
            "Use /quiz to start a new quiz!",
            parse_mode="Markdown"
        )
