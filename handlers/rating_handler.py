from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from keyboards import (
    RATING_CALLBACKS, RATING_MOD_CALLBACKS,
    get_gender_keyboard, get_moderation_keyboard, get_voting_keyboard,
    get_rating_cancel_keyboard
)
from services.cooldown import cooldown_service, CooldownType
from services.db import db
from models import RatingPost
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)

COOLDOWN_HOURS = 24
MIN_AGE = 18
MAX_AGE = 70
MAX_ABOUT_WORDS = 3
MAX_WORD_LENGTH = 7

def safe_markdown(text: str) -> str:
    if not text:
        return ""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    result = str(text)
    for char in special_chars:
        result = result.replace(char, f'\\{char}')
    return result

def validate_instagram_url(url: str) -> tuple:
    if not url:
        return False, ""
    url = url.strip()
    instagram_patterns = [
        r'(?:https?://)?(?:www\.)?instagram\.com/([a-zA-Z0-9._]+)',
        r'(?:https?://)?(?:www\.)?instagram\.com/p/([a-zA-Z0-9_-]+)',
        r'(?:https?://)?(?:www\.)?instagr\.am/([a-zA-Z0-9._]+)',
        r'@([a-zA-Z0-9._]+)'
    ]
    for pattern in instagram_patterns:
        match = re.search(pattern, url)
        if match:
            username = match.group(1)
            if username and len(username) <= 30:
                return True, f"https://instagram.com/{username}"
    return False, ""

def validate_age(age_str: str) -> tuple:
    try:
        age = int(age_str)
        if MIN_AGE <= age <= MAX_AGE:
            return True, age
        return False, f"Возраст должен быть от {MIN_AGE} до {MAX_AGE}"
    except ValueError:
        return False, "Введите число"

def validate_about(text: str) -> tuple:
    if not text or len(text) > 100:
        return False, "Максимум 100 символов"
    words = text.split()
    if len(words) > MAX_ABOUT_WORDS:
        return False, f"Максимум {MAX_ABOUT_WORDS} слова"
    for word in words:
        if len(word) > MAX_WORD_LENGTH:
            return False, f"Слова до {MAX_WORD_LENGTH} букв"
    return True, text

async def itsme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    can_use, remaining = await cooldown_service.check_cooldown(
        user_id=user_id,
        command='rating',
        duration=COOLDOWN_HOURS * 3600,
        cooldown_type=CooldownType.NORMAL
    )
    if not can_use:
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        await update.message.reply_text(
            f"Следующая анкета через:\n{hours}ч {minutes}м"
        )
        return
    context.user_data['rating_form'] = {'step': 'gender'}
    await update.message.reply_text(
        "Создание анкеты\n\nВыберите пол:",
        reply_markup=get_gender_keyboard()
    )

async def handle_rate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    
    if data == RATING_CALLBACKS['cancel']:
        context.user_data.pop('rating_form', None)
        await query.edit_message_text("Создание анкеты отменено")
        return
    
    if data == RATING_CALLBACKS['noop']:
        return
    
    if data.startswith(RATING_CALLBACKS['gender']):
        gender = data.split(':')[1]
        context.user_data['rating_form'] = {
            'step': 'age',
            'gender': gender
        }
        gender_text = "Девушка" if gender == 'girl' else "Парень"
        await query.edit_message_text(
            f"{gender_text}\n\nВведите возраст ({MIN_AGE}-{MAX_AGE}):"
        )
        return
    
    if data.startswith(RATING_CALLBACKS['vote']):
        parts = data.split(':')
        if len(parts) != 3:
            await query.answer("Ошибка данных")
            return
        
        post_id = int(parts[1])
        vote_value = int(parts[2])
        
        async with db.session_maker() as session:
            try:
                post = await session.get(RatingPost, post_id)
                if not post:
                    await query.answer("Анкета не найдена", show_alert=True)
                    return
                
                if post.user_id == user_id:
                    await query.answer("Нельзя голосовать за себя", show_alert=True)
                    return
                
                if not post.user_votes:
                    post.user_votes = {}
                
                if str(user_id) in post.user_votes:
                    await query.answer("Вы уже голосовали", show_alert=True)
                    return
                
                post.user_votes[str(user_id)] = vote_value
                
                if not post.vote_counts:
                    post.vote_counts = {-2: 0, -1: 0, 0: 0, 1: 0, 2: 0}
                
                post.vote_counts[vote_value] = post.vote_counts.get(vote_value, 0) + 1
                post.total_score = (post.total_score or 0) + vote_value
                post.vote_count = (post.vote_count or 0) + 1
                
                await session.commit()
                
                vote_text = {-2: "-2", -1: "-1", 0: "0", 1: "+1", 2: "+2"}
                await query.answer(f"Голос учтён: {vote_text[vote_value]}")
                
                await query.edit_message_reply_markup(
                    reply_markup=get_voting_keyboard(
                        post_id, 
                        post.vote_counts, 
                        post.total_score, 
                        post.vote_count
                    )
                )
                
            except Exception as e:
                logger.error(f"Vote error: {e}")
                await query.answer("Ошибка голосования", show_alert=True)
        return

async def handle_rate_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    form_data = context.user_data.get('rating_form')
    if not form_data or form_data.get('step') != 'age':
        return
    
    is_valid, result = validate_age(update.message.text)
    if not is_valid:
        await update.message.reply_text(f"{result}\n\nВведите возраст снова:")
        return
    
    form_data['age'] = result
    form_data['step'] = 'name'
    await update.message.reply_text("Введите имя (макс 20 символов):")

async def handle_rate_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    form_data = context.user_data.get('rating_form')
    if not form_data or form_data.get('step') != 'name':
        return
    
    name = update.message.text.strip()
    if not name or len(name) > 20:
        await update.message.reply_text("Имя до 20 символов\n\nВведите имя снова:")
        return
    
    form_data['name'] = name
    form_data['step'] = 'about'
    await update.message.reply_text(
        f"О себе (макс {MAX_ABOUT_WORDS} слова, каждое до {MAX_WORD_LENGTH} букв):"
    )

async def handle_rate_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    form_data = context.user_data.get('rating_form')
    if not form_data or form_data.get('step') != 'about':
        return
    
    is_valid, result = validate_about(update.message.text)
    if not is_valid:
        await update.message.reply_text(f"{result}\n\nВведите снова:")
        return
    
    form_data['about'] = result
    form_data['step'] = 'profile'
    await update.message.reply_text("Отправьте ссылку на профиль Instagram:")

async def handle_rate_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    form_data = context.user_data.get('rating_form')
    if not form_data or form_data.get('step') != 'profile':
        return
    
    is_valid, profile_url = validate_instagram_url(update.message.text)
    if not is_valid:
        await update.message.reply_text("Неверная ссылка Instagram\n\nОтправьте снова:")
        return
    
    form_data['profile_url'] = profile_url
    form_data['step'] = 'photo'
    await update.message.reply_text("Отправьте своё фото:")

async def handle_rate_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    form_data = context.user_data.get('rating_form')
    if not form_data or form_data.get('step') != 'photo':
        return
    
    if not update.message.photo:
        await update.message.reply_text("Отправьте фото")
        return
    
    photo_file_id = update.message.photo[-1].file_id
    user_id = update.effective_user.id
    
    async with db.session_maker() as session:
        try:
            new_post = RatingPost(
                user_id=user_id,
                gender=form_data['gender'],
                age=form_data['age'],
                name=form_data['name'],
                about=form_data['about'],
                profile_url=form_data['profile_url'],
                photo_file_id=photo_file_id,
                total_score=0,
                vote_count=0,
                vote_counts={-2: 0, -1: 0, 0: 0, 1: 0, 2: 0},
                user_votes={},
                status='pending',
                created_at=datetime.utcnow()
            )
            
            session.add(new_post)
            await session.commit()
            await session.refresh(new_post)
            
            gender_emoji = "" if form_data['gender'] == 'girl' else ""
            caption = (
                f"{gender_emoji} {safe_markdown(form_data['name'])}, {form_data['age']}\n"
                f"{safe_markdown(form_data['about'])}\n"
                f"[Instagram]({form_data['profile_url']})"
            )
            
            msg = await context.bot.send_photo(
                chat_id=Config.MODERATION_GROUP_ID,
                photo=photo_file_id,
                caption=caption,
                parse_mode='Markdown',
                reply_markup=get_moderation_keyboard(new_post.id)
            )
            
            new_post.moderation_message_id = msg.message_id
            await session.commit()
            
            await update.message.reply_text("Анкета отправлена на модерацию!")
            context.user_data.pop('rating_form', None)
            
        except Exception as e:
            logger.error(f"Rating post creation error: {e}")
            await update.message.reply_text("Ошибка создания анкеты")

async def handle_rate_moderation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    
    if user_id not in Config.ADMIN_IDS:
        await query.answer("Только для админов", show_alert=True)
        return
    
    await query.answer()
    data = query.data
    
    if data.startswith(RATING_MOD_CALLBACKS['approve']):
        post_id = int(data.split(':')[1])
        
        async with db.session_maker() as session:
            try:
                post = await session.get(RatingPost, post_id)
                if not post:
                    await query.edit_message_caption(
                        caption=query.message.caption + "\n\nАнкета не найдена"
                    )
                    return
                
                post.status = 'approved'
                await session.commit()
                
                gender_emoji = "" if post.gender == 'girl' else ""
                caption = (
                    f"{gender_emoji} {safe_markdown(post.name)}, {post.age}\n"
                    f"{safe_markdown(post.about)}\n"
                    f"[Instagram]({post.profile_url})"
                )
                
                msg = await context.bot.send_photo(
                    chat_id=Config.TARGET_CHANNEL_ID,
                    photo=post.photo_file_id,
                    caption=caption,
                    parse_mode='Markdown',
                    reply_markup=get_voting_keyboard(post.id, post.vote_counts, 0, 0)
                )
                
                post.channel_message_id = msg.message_id
                await session.commit()
                
                await query.edit_message_caption(
                    caption=query.message.caption + "\n\nОдобрено и опубликовано"
                )
                
                try:
                    await context.bot.send_message(
                        chat_id=post.user_id,
                        text="Ваша анкета одобрена и опубликована!"
                    )
                except:
                    pass
                
            except Exception as e:
                logger.error(f"Approve error: {e}")
                await query.edit_message_caption(
                    caption=query.message.caption + "\n\nОшибка публикации"
                )
        return
    
    if data.startswith(RATING_MOD_CALLBACKS['reject']):
        post_id = int(data.split(':')[1])
        
        async with db.session_maker() as session:
            try:
                post = await session.get(RatingPost, post_id)
                if not post:
                    await query.edit_message_caption(
                        caption=query.message.caption + "\n\nАнкета не найдена"
                    )
                    return
                
                post.status = 'rejected'
                await session.commit()
                
                await query.edit_message_caption(
                    caption=query.message.caption + "\n\nОтклонено"
                )
                
                try:
                    await context.bot.send_message(
                        chat_id=post.user_id,
                        text="Ваша анкета отклонена модератором"
                    )
                except:
                    pass
                
            except Exception as e:
                logger.error(f"Reject error: {e}")

async def toppeople_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with db.session_maker() as session:
        try:
            from sqlalchemy import select, desc
            
            stmt = select(RatingPost).where(
                RatingPost.status == 'approved'
            ).order_by(desc(RatingPost.total_score)).limit(10)
            
            result = await session.execute(stmt)
            top_posts = result.scalars().all()
            
            if not top_posts:
                await update.message.reply_text("Рейтинг пока пуст")
                return
            
            text = "ТОП-10 ЛЮДЕЙ\n\n"
            for i, post in enumerate(top_posts, 1):
                emoji = "" if post.gender == 'girl' else ""
                text += f"{i}. {emoji} {post.name} - {post.total_score} ({post.vote_count} голосов)\n"
            
            await update.message.reply_text(text)
            
        except Exception as e:
            logger.error(f"Toppeople error: {e}")
            await update.message.reply_text("Ошибка получения рейтинга")

async def topboys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with db.session_maker() as session:
        try:
            from sqlalchemy import select, desc
            
            stmt = select(RatingPost).where(
                RatingPost.status == 'approved',
                RatingPost.gender == 'boy'
            ).order_by(desc(RatingPost.total_score)).limit(10)
            
            result = await session.execute(stmt)
            top_posts = result.scalars().all()
            
            if not top_posts:
                await update.message.reply_text("Рейтинг парней пуст")
                return
            
            text = "ТОП-10 ПАРНЕЙ\n\n"
            for i, post in enumerate(top_posts, 1):
                text += f"{i}. {post.name} - {post.total_score} ({post.vote_count} голосов)\n"
            
            await update.message.reply_text(text)
            
        except Exception as e:
            logger.error(f"Topboys error: {e}")
            await update.message.reply_text("Ошибка получения рейтинга")

async def topgirls_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with db.session_maker() as session:
        try:
            from sqlalchemy import select, desc
            
            stmt = select(RatingPost).where(
                RatingPost.status == 'approved',
                RatingPost.gender == 'girl'
            ).order_by(desc(RatingPost.total_score)).limit(10)
            
            result = await session.execute(stmt)
            top_posts = result.scalars().all()
            
            if not top_posts:
                await update.message.reply_text("Рейтинг девушек пуст")
                return
            
            text = "ТОП-10 ДЕВУШЕК\n\n"
            for i, post in enumerate(top_posts, 1):
                text += f"{i}. {post.name} - {post.total_score} ({post.vote_count} голосов)\n"
            
            await update.message.reply_text(text)
            
        except Exception as e:
            logger.error(f"Topgirls error: {e}")
            await update.message.reply_text("Ошибка получения рейтинга")

async def toppeoplereset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text("Только для админов")
        return
    
    async with db.session_maker() as session:
        try:
            from sqlalchemy import update as sql_update
            
            stmt = sql_update(RatingPost).values(
                total_score=0,
                vote_count=0,
                vote_counts={-2: 0, -1: 0, 0: 0, 1: 0, 2: 0},
                user_votes={}
            )
            
            await session.execute(stmt)
            await session.commit()
            
            await update.message.reply_text("Рейтинг сброшен")
            
        except Exception as e:
            logger.error(f"Reset error: {e}")
            await update.message.reply_text("Ошибка сброса")

__all__ = [
    'RATING_CALLBACKS',
    'RATING_MOD_CALLBACKS',
    'itsme_command',
    'toppeople_command',
    'topboys_command',
    'topgirls_command',
    'toppeoplereset_command',
    'handle_rate_callback',
    'handle_rate_moderation_callback',
    'handle_rate_photo',
    'handle_rate_age',
    'handle_rate_name',
    'handle_rate_about',
    'handle_rate_profile',
]
