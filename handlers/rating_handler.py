from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from config import Config
from services.cooldown import cooldown_service, CooldownType
from datetime import datetime, timedelta
import logging
import re
import random
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ============= CALLBACK PREFIXES (УНИКАЛЬНЫЕ V8) =============
RATING_CALLBACKS = {
    'gender': 'rtpc_gender',
    'vote': 'rtpc_vote',
    'back': 'rtpc_back',
    'cancel': 'rtpc_cancel',
    'noop': 'rtpc_noop',
}

RATING_MOD_CALLBACKS = {
    'edit': 'rtmc_edit',
    'approve': 'rtmc_approve',
    'reject': 'rtmc_reject',
    'back': 'rtmc_back',
}

# ============= SETTINGS =============
COOLDOWN_HOURS = 24  # 24 часа на создание новой анкеты
MIN_AGE = 18
MAX_AGE = 70
MAX_ABOUT_WORDS = 3
MAX_WORD_LENGTH = 7

# ============= DATA STORAGE =============
rating_data = {
    'posts': {},
    'profiles': {},
    'user_votes': {},  # {user_id: {post_id: vote_value}}
}

# ============= HELPER FUNCTIONS =============

def safe_markdown(text: str) -> str:
    """
    БЕЗОПАСНОЕ форматирование для Markdown
    Решает проблему: Can't parse entities
    """
    if not text:
        return ""
    
    # Экранируем все спецсимволы Markdown
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    result = str(text)
    for char in special_chars:
        result = result.replace(char, f'\\{char}')
    
    return result

def validate_instagram_url(url: str) -> tuple:
    """
    Валидация Instagram URL (включая с UTM-параметрами)
    Returns: (is_valid: bool, cleaned_url: str)
    """
    if not url:
        return False, ""
    
    # Удаляем пробелы
    url = url.strip()
    
    # Паттерны для Instagram
    instagram_patterns = [
        r'(?:https?://)?(?:www\.)?instagram\.com/([a-zA-Z0-9._]+)',
        r'(?:https?://)?(?:www\.)?instagram\.com/p/([a-zA-Z0-9_-]+)',
        r'(?:https?://)?(?:www\.)?instagram\.com/reel/([a-zA-Z0-9_-]+)',
    ]
    
    for pattern in instagram_patterns:
        match = re.search(pattern, url)
        if match:
            # Извлекаем username или post ID
            identifier = match.group(1)
            
            # Формируем чистую ссылку
            if '/p/' in url or '/reel/' in url:
                cleaned_url = f"https://instagram.com/{'p' if '/p/' in url else 'reel'}/{identifier}"
            else:
                cleaned_url = f"https://instagram.com/{identifier}"
            
            return True, cleaned_url
    
    return False, url

def validate_profile_url(url: str) -> Optional[str]:
    """
    Валидация и очистка профиля (Telegram или Instagram)
    Returns: cleaned URL или None если невалидно
    """
    if not url or len(url) < 3:
        return None
    
    url = url.strip()
    
    # Telegram username
    if url.startswith('@'):
        username = url[1:]
        if re.match(r'^[a-zA-Z0-9_]{5,32}$', username):
            return f"@{username}"
        return None
    
    # t.me ссылка
    if 't.me/' in url:
        match = re.search(r't\.me/([a-zA-Z0-9_]{5,32})', url)
        if match:
            return f"@{match.group(1)}"
        return None
    
    # Instagram URL (включая с параметрами)
    is_valid, cleaned = validate_instagram_url(url)
    if is_valid:
        return cleaned
    
    # Обычный username без @
    if re.match(r'^[a-zA-Z0-9_]{3,}$', url):
        return f"@{url}"
    
    return None

async def check_vote_limit(user_id: int, post_id: int) -> bool:
    """Проверка лимита голосования - 1 голос на пост навсегда"""
    if user_id not in rating_data['user_votes']:
        return True
    
    return post_id not in rating_data['user_votes'][user_id]

async def generate_catalog_number() -> int:
    """Генерация уникального номера каталога"""
    from services.catalog_service import catalog_service
    from services.db import db
    from models import CatalogPost
    from sqlalchemy import select
    
    try:
        async with db.get_session() as session:
            for _ in range(100):
                number = random.randint(1, 9999)
                
                result = await session.execute(
                    select(CatalogPost.id).where(CatalogPost.catalog_number == number)
                )
                
                if not result.scalar_one_or_none():
                    used = any(p.get('catalog_number') == number for p in rating_data['posts'].values())
                    if not used:
                        return number
            
            raise Exception("Could not generate number")
    except Exception as e:
        logger.error(f"Error generating number: {e}")
        return random.randint(1000, 9999)

def validate_about(text: str) -> Optional[str]:
    """Валидация поля 'О себе'"""
    words = text.strip().split()
    
    if len(words) > MAX_ABOUT_WORDS:
        return f"❌ Максимум {MAX_ABOUT_WORDS} слова"
    
    for word in words:
        if len(word) > MAX_WORD_LENGTH:
            return f"❌ Слово '{word}' больше {MAX_WORD_LENGTH} символов"
    
    return None

# ============= MAIN COMMAND WITH COOLDOWN =============

async def itsme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать создание анкеты - /itsme с кулдауном 24ч"""
    user_id = update.effective_user.id
    
    # Проверка кулдауна через cooldown_service
    can_use, remaining = await cooldown_service.check_cooldown(
        user_id=user_id,
        command='itsme',
        duration=COOLDOWN_HOURS * 3600,  # 24 часа в секундах
        cooldown_type=CooldownType.NORMAL
    )
    
    if not can_use:
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        await update.message.reply_text(
            f"⏳ Подождите {hours}ч {minutes}мин перед созданием новой анкеты"
        )
        return
    
    context.user_data['rate_step'] = 'name'
    context.user_data['waiting_for'] = 'rate_name'
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=RATING_CALLBACKS['cancel'])]]
    
    await update.message.reply_text(
        "⭐ *TopPeople Budapest*\n\n"
        "🎯 Шаг 1/6: *Ваше имя*\n\n"
        "Как вас представить?\n"
        "Пример: Анна",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============= STEP HANDLERS =============

async def handle_rate_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка имени"""
    name = update.message.text.strip()
    
    if len(name) < 2 or len(name) > 50:
        await update.message.reply_text("❌ Имя: 2-50 символов")
        return
    
    context.user_data['rate_name'] = name
    context.user_data['rate_step'] = 'photo'
    context.user_data['waiting_for'] = 'rate_photo'
    
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data=RATING_CALLBACKS['back'])]]
    
    safe_name = safe_markdown(name)
    await update.message.reply_text(
        f"✅ Имя: *{safe_name}*\n\n"
        f"🎯 Шаг 2/6: *Фото или видео*\n\n"
        f"Отправьте фото или короткое видео",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_rate_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка фото или видео"""
    media_type = None
    file_id = None
    
    # Проверяем фото
    if update.message.photo:
        media_type = 'photo'
        file_id = update.message.photo[-1].file_id
    
    # Проверяем видео
    elif update.message.video:
        media_type = 'video'
        file_id = update.message.video.file_id
        
        # Проверка длительности видео (макс 60 секунд)
        if update.message.video.duration > 60:
            await update.message.reply_text("❌ Видео должно быть не длиннее 60 секунд")
            return
    
    else:
        await update.message.reply_text("❌ Отправьте фото или видео")
        return
    
    context.user_data['rate_media_type'] = media_type
    context.user_data['rate_media_file_id'] = file_id
    context.user_data['rate_step'] = 'age'
    context.user_data['waiting_for'] = 'rate_age'
    
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data=RATING_CALLBACKS['back'])]]
    
    media_text = "Фото" if media_type == 'photo' else "Видео"
    
    await update.message.reply_text(
        f"✅ {media_text} добавлено\n\n"
        f"🎯 Шаг 3/6: *Возраст*\n\n"
        f"Ваш возраст \\({MIN_AGE}\\-{MAX_AGE}\\)",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='MarkdownV2'
    )

async def handle_rate_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка возраста"""
    try:
        age = int(update.message.text.strip())
        if age < MIN_AGE or age > MAX_AGE:
            await update.message.reply_text(f"❌ Возраст: {MIN_AGE}-{MAX_AGE} лет")
            return
    except ValueError:
        await update.message.reply_text("❌ Введите число")
        return
    
    context.user_data['rate_age'] = age
    context.user_data['rate_step'] = 'about'
    context.user_data['waiting_for'] = 'rate_about'
    
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data=RATING_CALLBACKS['back'])]]
    
    await update.message.reply_text(
        f"✅ Возраст: *{age} лет*\n\n"
        f"🎯 Шаг 4/6: *О себе*\n\n"
        f"Опишите себя \\({MAX_ABOUT_WORDS} слова, макс\\. {MAX_WORD_LENGTH} символов\\)\n"
        f"Пример: красотка модель инстаграм",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='MarkdownV2'
    )

async def handle_rate_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка описания"""
    about = update.message.text.strip()
    
    error = validate_about(about)
    if error:
        await update.message.reply_text(error)
        return
    
    context.user_data['rate_about'] = about
    context.user_data['rate_step'] = 'profile'
    context.user_data['waiting_for'] = 'rate_profile'
    
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data=RATING_CALLBACKS['back'])]]
    
    safe_about = safe_markdown(about)
    await update.message.reply_text(
        f"✅ О себе: *{safe_about}*\n\n"
        f"🎯 Шаг 5/6: *Ссылка на профиль*\n\n"
        f"Telegram: @username или t\\.me/username\n"
        f"Instagram: допускаются ссылки с UTM\\-параметрами\n\n"
        f"Примеры:\n"
        f"• @anna\\_budapest\n"
        f"• https://instagram\\.com/anna\n"
        f"• https://www\\.instagram\\.com/anna?igsh=xxx&utm\\_source=qr",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='MarkdownV2'
    )

async def handle_rate_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ссылки на профиль с валидацией Instagram"""
    profile_input = update.message.text.strip()
    
    # Валидация и очистка URL
    cleaned_url = validate_profile_url(profile_input)
    
    if not cleaned_url:
        await update.message.reply_text(
            "❌ Неверная ссылка\n\n"
            "Допустимые форматы:\n"
            "• @username\n"
            "• t.me/username\n"
            "• instagram.com/username\n"
            "• instagram.com/username?параметры"
        )
        return
    
    context.user_data['rate_profile'] = cleaned_url
    context.user_data['rate_step'] = 'gender'
    context.user_data['waiting_for'] = None
    
    keyboard = [
        [
            InlineKeyboardButton("🙋🏼‍♂️ Парень", callback_data=f"{RATING_CALLBACKS['gender']}:boy"),
            InlineKeyboardButton("🙋🏼‍♀️ Девушка", callback_data=f"{RATING_CALLBACKS['gender']}:girl")
        ],
        [InlineKeyboardButton("⬅️ Назад", callback_data=RATING_CALLBACKS['back'])]
    ]
    
    safe_url = safe_markdown(cleaned_url)
    await update.message.reply_text(
        f"✅ Профиль: {safe_url}\n\n"
        f"🎯 Шаг 6/6: *Пол*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='MarkdownV2'
    )

# ============= PUBLISH =============

async def publish_rate_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Публикация в модерацию"""
    media_type = context.user_data.get('rate_media_type', 'photo')
    media_file_id = context.user_data.get('rate_media_file_id')
    name = context.user_data.get('rate_name')
    profile_url = context.user_data.get('rate_profile')
    age = context.user_data.get('rate_age')
    about = context.user_data.get('rate_about')
    gender = context.user_data.get('rate_gender')
    
    user_id = update.effective_user.id
    username = update.effective_user.username or f"ID{user_id}"
    
    if not all([media_file_id, name, profile_url, age, about, gender]):
        await update.callback_query.edit_message_text("❌ Ошибка: не хватает данных")
        return
    
    try:
        post_id = len(rating_data['posts']) + 1
        catalog_number = await generate_catalog_number()
        
        rating_data['posts'][post_id] = {
            'name': name,
            'profile_url': profile_url,
            'age': age,
            'about': about,
            'gender': gender,
            'media_type': media_type,
            'media_file_id': media_file_id,
            'author_user_id': user_id,
            'author_username': username,
            'catalog_number': catalog_number,
            'created_at': datetime.now(),
            'votes': {},
            'status': 'pending'
        }
        
        # УСТАНАВЛИВАЕМ КУЛДАУН через cooldown_service
        await cooldown_service.set_cooldown(
            user_id=user_id,
            command='itsme',
            duration=COOLDOWN_HOURS * 3600,
            cooldown_type=CooldownType.NORMAL
        )
        
        if profile_url not in rating_data['profiles']:
            rating_data['profiles'][profile_url] = {
                'name': name,
                'age': age,
                'about': about,
                'gender': gender,
                'total_score': 0,
                'vote_count': 0,
                'post_ids': []
            }
        
        rating_data['profiles'][profile_url]['post_ids'].append(post_id)
        
        logger.info(f"Rating post {post_id} (#{catalog_number}) created by @{username}")
        
        await send_rating_to_moderation(
            update, context, post_id, media_type, media_file_id,
            name, profile_url, age, about, gender, username, catalog_number
        )
        
        # Clear data
        for key in ['rate_media_type', 'rate_media_file_id', 'rate_name', 'rate_profile', 
                    'rate_age', 'rate_about', 'rate_gender', 'rate_step', 'waiting_for']:
            context.user_data.pop(key, None)
        
        gender_emoji = "🙋🏼‍♂️" if gender == "boy" else "🙋🏼‍♀️"
        media_text = "📹" if media_type == 'video' else "📸"
        
        safe_name = safe_markdown(name)
        safe_about = safe_markdown(about)
        
        await update.callback_query.edit_message_text(
        f"✅ *Заявка отправлена!* \n\n"
        f"{media_text} {media_type.title()}\n"
        f"👤 {safe_name}\n"
        f"{gender_emoji} {age} лет\n"
        f"💬 {safe_about}\n"
        f"🆔 #{catalog_number}\n\n"
        "⏳ Ожидайте проверки",
        parse_mode='MarkdownV2'
    )
        
    except Exception as e:
        logger.error(f"Error publishing: {e}", exc_info=True)
        await update.callback_query.edit_message_text(f"❌ Ошибка: {str(e)[:100]}")

async def send_rating_to_moderation(
    update, context, post_id, media_type, media_file_id,
    name, profile_url, age, about, gender, author_username, catalog_number
):
    """Отправка в модерацию"""
    bot = context.bot
    
    try:
        keyboard = [
            [InlineKeyboardButton("✏️ Редактировать", callback_data=f"{RATING_MOD_CALLBACKS['edit']}:{post_id}")],
            [
                InlineKeyboardButton("✅ Опубликовать", callback_data=f"{RATING_MOD_CALLBACKS['approve']}:{post_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"{RATING_MOD_CALLBACKS['reject']}:{post_id}")
            ]
        ]
        
        gender_text = "Парень" if gender == "boy" else "Девушка"
        gender_emoji = "🙋🏼‍♂️" if gender == "boy" else "🙋🏼‍♀️"
        media_emoji = "📹" if media_type == 'video' else "📸"
        
        # Форматируем ссылку
        if profile_url.startswith('@'):
            if 'instagram' not in profile_url:
                formatted_name = f"[{name}](https://t.me/{profile_url[1:]})"
            else:
                formatted_name = f"[{name}]({profile_url})"
        elif 'instagram.com' in profile_url:
            formatted_name = f"[{name}]({profile_url})"
        else:
            formatted_name = name
        
        safe_name = safe_markdown(name)
        safe_about = safe_markdown(about)
        
        caption = (
            f"🆕 *Новая заявка TopPeople*\n\n"
            f"{media_emoji} Медиа: {media_type}\n"
            f"👤 {formatted_name}\n"
            f"{gender_emoji} {gender_text}, {age} лет\n"
            f"💬 {safe_about}\n"
            f"🆔 \\#{catalog_number}\n"
            f"📤 @{author_username}\n\n"
            f"❓ Ваше действие?"
        )
        
        # Отправляем в зависимости от типа медиа
        if media_type == 'video':
            msg = await bot.send_video(
                chat_id=Config.MODERATION_GROUP_ID,
                video=media_file_id,
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='MarkdownV2'
            )
        else:
            msg = await bot.send_photo(
                chat_id=Config.MODERATION_GROUP_ID,
                photo=media_file_id,
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='MarkdownV2'
            )
        
        rating_data['posts'][post_id]['moderation_message_id'] = msg.message_id
        rating_data['posts'][post_id]['moderation_group_id'] = Config.MODERATION_GROUP_ID
        
        logger.info(f"Rating post {post_id} sent to moderation")
        
    except Exception as e:
        logger.error(f"Error sending to moderation: {e}", exc_info=True)
        raise

# ============= MODERATION =============

async def approve_rating_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Одобрение и публикация"""
    query = update.callback_query
    
    if post_id not in rating_data['posts']:
        await query.answer("❌ Пост не найден", show_alert=True)
        return
    
    post = rating_data['posts'][post_id]
    
    try:
        BUDAPEST_PEOPLE_ID = Config.STATS_CHANNELS.get('budapest_people', -1003088023508)
        
        gender_text = "Парень" if post['gender'] == "boy" else "Девушка"
        profile_url = post['profile_url']
        media_type = post.get('media_type', 'photo')
        
        # Форматируем имя со ссылкой
        if profile_url.startswith('@'):
            if 'instagram' not in profile_url:
                formatted_name = f"[{post['name']}](https://t.me/{profile_url[1:]})"
            else:
                formatted_name = f"[{post['name']}]({profile_url})"
        elif 'instagram.com' in profile_url:
            formatted_name = f"[{post['name']}]({profile_url})"
        else:
            formatted_name = post['name']
        
        keyboard = [
            [
                InlineKeyboardButton("😭 -2 (0)", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:-2"),
                InlineKeyboardButton("👎 -1 (0)", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:-1"),
                InlineKeyboardButton("😐 0 (0)", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:0"),
                InlineKeyboardButton("👍 +1 (0)", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:1"),
                InlineKeyboardButton("🔥 +2 (0)", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:2"),
            ],
            [InlineKeyboardButton(f"⭐ Рейтинг: 0 | Голосов: 0", callback_data=RATING_CALLBACKS['noop'])]
        ]
        
        safe_name = safe_markdown(post['name'])
        safe_about = safe_markdown(post['about'])
        
        caption = (
            f"⭐ *TopPeople Budapest*\n\n"
            f"👤 {formatted_name}\n"
            f"{gender_text}, {post['age']} лет\n"
            f"💬 {safe_about}\n\n"
            f"🆔 \\#{post['catalog_number']}\n\n"
            f"Оцените участника:"
        )
        
        # Публикуем в зависимости от типа медиа
        if media_type == 'video':
            msg = await context.bot.send_video(
                chat_id=BUDAPEST_PEOPLE_ID,
                video=post['media_file_id'],
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='MarkdownV2'
            )
        else:
            msg = await context.bot.send_photo(
                chat_id=BUDAPEST_PEOPLE_ID,
                photo=post['media_file_id'],
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='MarkdownV2'
            )
        
        post['message_id'] = msg.message_id
        post['published_channel_id'] = BUDAPEST_PEOPLE_ID
        post['status'] = 'published'
        post['published_link'] = f"https://t.me/c/{str(BUDAPEST_PEOPLE_ID)[4:]}/{msg.message_id}"
        
        # Добавляем в каталог
        from services.catalog_service import catalog_service
        
        category = '👱🏻‍♀️ TopGirls' if post['gender'] == 'girl' else '🤵🏼‍♂️ TopBoys'
        
        catalog_post_id = await catalog_service.add_post(
            user_id=post['author_user_id'],
            catalog_link=post['published_link'],
            category=category,
            name=post['name'],
            tags=[post['about'], gender_text, f"{post['age']}"],
            media_type=media_type,
            media_file_id=post['media_file_id'],
            media_group_id=None,
            media_json=[post['media_file_id']],
            author_username=post.get('author_username'),
            author_id=post['author_user_id']
        )
        
        if catalog_post_id:
            from services.db import db
            from models import CatalogPost
            from sqlalchemy import update as sql_update
            
            async with db.get_session() as session:
                await session.execute(
                    sql_update(CatalogPost)
                    .where(CatalogPost.id == catalog_post_id)
                    .values(catalog_number=post['catalog_number'])
                )
                await session.commit()
        
        await query.edit_message_reply_markup(reply_markup=None)
        await query.edit_message_caption(
            caption=f"{query.message.caption}\n\n✅ *ОПУБЛИКОВАНО*",
            parse_mode='MarkdownV2'
        )
        
        # Уведомляем автора
        try:
            safe_name_author = safe_markdown(post['name'])
            await context.bot.send_message(
                chat_id=post['author_user_id'],
                text=(
                    f"🎉 *Ваша заявка одобрена\\!*\n\n"
                    f"👤 {safe_name_author}\n"
                    f"🆔 \\#{post['catalog_number']}\n\n"
                    f"🔗 [Ваш пост]({safe_markdown(post['published_link'])})\n\n"
                    f"✅ Теперь вы в TopPeople\\!"
                ),
                parse_mode='MarkdownV2'
            )
        except Exception as e:
            logger.warning(f"Could not notify author: {e}")
        
        await query.answer("✅ Опубликовано", show_alert=False)
        logger.info(f"Rating post {post_id} approved")
        
    except Exception as e:
        logger.error(f"Error approving: {e}", exc_info=True)
        await query.answer(f"❌ Ошибка: {str(e)[:100]}", show_alert=True)

async def reject_rating_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Отклонение поста"""
    query = update.callback_query
    
    if post_id not in rating_data['posts']:
        await query.answer("❌ Пост не найден", show_alert=True)
        return
    
    try:
        post = rating_data['posts'][post_id]
        author_user_id = post.get('author_user_id')
        
        del rating_data['posts'][post_id]
        
        await query.edit_message_reply_markup(reply_markup=None)
        await query.edit_message_caption(
            caption=f"{query.message.caption}\n\n❌ *ОТКЛОНЕНО*",
            parse_mode='MarkdownV2'
        )
        
        if author_user_id:
            try:
                await context.bot.send_message(
                    chat_id=author_user_id,
                    text="❌ Ваша заявка в TopPeople отклонена"
                )
            except:
                pass
        
        await query.answer("❌ Отклонено", show_alert=False)
        logger.info(f"Rating post {post_id} rejected")
        
    except Exception as e:
        logger.error(f"Error rejecting: {e}")
        await query.answer(f"❌ Ошибка: {str(e)[:100]}", show_alert=True)

# ============= VOTING (с лимитом 1 голос навсегда) =============

async def handle_vote(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int, vote_value: int):
    """Обработка голосования с лимитом 1 голос на пост"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    # Проверяем лимит голосования
    can_vote = await check_vote_limit(user_id, post_id)
    
    if not can_vote:
        await query.answer("❌ Вы уже оценили этот пост", show_alert=True)
        return
    
    if post_id not in rating_data['posts']:
        await query.answer("❌ Пост не найден", show_alert=True)
        return
    
    post = rating_data['posts'][post_id]
    
    # Записываем голос
    if user_id not in rating_data['user_votes']:
        rating_data['user_votes'][user_id] = {}
    
    rating_data['user_votes'][user_id][post_id] = vote_value
    
    # Обновляем голоса поста
    if 'votes' not in post:
        post['votes'] = {}
    
    post['votes'][user_id] = vote_value
    
    # Обновляем профиль
    profile_url = post.get('profile_url')
    if profile_url and profile_url in rating_data['profiles']:
        profile = rating_data['profiles'][profile_url]
        
        # Пересчитываем общий рейтинг
        all_votes = []
        for pid in profile.get('post_ids', []):
            if pid in rating_data['posts']:
                all_votes.extend(rating_data['posts'][pid].get('votes', {}).values())
        
        profile['total_score'] = sum(all_votes)
        profile['vote_count'] = len(all_votes)
    
    # Обновляем кнопки
    votes = post.get('votes', {})
    vote_counts = {-2: 0, -1: 0, 0: 0, 1: 0, 2: 0}
    
    for v in votes.values():
        if v in vote_counts:
            vote_counts[v] += 1
    
    total_score = sum(votes.values())
    vote_count = len(votes)
    
    keyboard = [
        [
            InlineKeyboardButton(f"😭 -2 ({vote_counts[-2]})", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:-2"),
            InlineKeyboardButton(f"👎 -1 ({vote_counts[-1]})", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:-1"),
            InlineKeyboardButton(f"😐 0 ({vote_counts[0]})", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:0"),
            InlineKeyboardButton(f"👍 +1 ({vote_counts[1]})", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:1"),
            InlineKeyboardButton(f"🔥 +2 ({vote_counts[2]})", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:2"),
        ],
        [InlineKeyboardButton(f"⭐ Рейтинг: {total_score} | Голосов: {vote_count}", callback_data=RATING_CALLBACKS['noop'])]
    ]
    
    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        await query.answer(f"✅ Ваша оценка: {vote_value:+d}", show_alert=False)
        logger.info(f"User {user_id} voted {vote_value} on post {post_id}")
    except Exception as e:
        logger.error(f"Error updating vote buttons: {e}")
        await query.answer("✅ Голос учтён", show_alert=False)

# ============= CALLBACKS =============

async def handle_rate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка публичных callback"""
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split(":")
    
    if data_parts[0].startswith('rtpc_'):
        action = data_parts[0][5:]
    else:
        action = data_parts[0]
    
    if action == 'gender':
        value = data_parts[1] if len(data_parts) > 1 else None
        context.user_data['rate_gender'] = value
        await publish_rate_post(update, context)
    
    elif action == 'vote':
        post_id = int(data_parts[1]) if len(data_parts) > 1 else None
        vote_value = int(data_parts[2]) if len(data_parts) > 2 else 0
        
        if post_id:
            await handle_vote(update, context, post_id, vote_value)
    
    elif action == 'cancel':
        for key in ['rate_media_type', 'rate_media_file_id', 'rate_name', 'rate_profile', 
                    'rate_age', 'rate_about', 'rate_gender', 'rate_step', 'waiting_for']:
            context.user_data.pop(key, None)
        await query.edit_message_text("❌ Заявка отменена")
    
    elif action == 'noop':
        pass  # Пустое действие для кнопок с рейтингом

async def handle_rate_moderation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка модерационных callback"""
    query = update.callback_query
    
    data_parts = query.data.split(":")
    
    if data_parts[0].startswith('rtmc_'):
        action = data_parts[0][5:]
    else:
        action = data_parts[0]
    
    post_id = int(data_parts[1]) if len(data_parts) > 1 and data_parts[1].isdigit() else None
    
    if not Config.is_moderator(update.effective_user.id):
        await query.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    if action == 'approve':
        await approve_rating_post(update, context, post_id)
    elif action == 'reject':
        await reject_rating_post(update, context, post_id)

# ============= STATS COMMANDS =============

async def toppeople_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Топ-10 в Будапеште"""
    if not rating_data['profiles']:
        await update.message.reply_text("❌ Нет данных")
        return
    
    sorted_profiles = sorted(
        rating_data['profiles'].items(),
        key=lambda x: x[1]['total_score'],
        reverse=True
    )[:10]
    
    text = "⭐ *TOPinBUDAPEST*\n\n"
    
    for i, (profile_url, data) in enumerate(sorted_profiles, 1):
        gender_emoji = "🙋🏼‍♂️" if data['gender'] == 'boy' else "🙋🏼‍♀️"
        safe_name = safe_markdown(data.get('name', ''))
        safe_url = safe_markdown(profile_url)
        
        text += (
            f"{i}\\. {safe_name} \\({safe_url}\\)\n"
            f"   {gender_emoji} {data.get('age')} лет\n"
            f"   ⭐ {data['total_score']} \\| 📊 {data['vote_count']}\n\n"
        )
    
    await update.message.reply_text(text, parse_mode='MarkdownV2')

async def topboys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Топ-10 парней"""
    profiles = {url: data for url, data in rating_data['profiles'].items() if data['gender'] == 'boy'}
    
    if not profiles:
        await update.message.reply_text("❌ Нет данных")
        return
    
    sorted_profiles = sorted(profiles.items(), key=lambda x: x[1]['total_score'], reverse=True)[:10]
    
    text = "🕺 *TOP10 BOYS*\n\n"
    
    for i, (url, data) in enumerate(sorted_profiles, 1):
        safe_name = safe_markdown(data.get('name', ''))
        text += f"{i}\\. {safe_name} — ⭐ {data['total_score']} \\({data['vote_count']}\\)\n"
    
    await update.message.reply_text(text, parse_mode='MarkdownV2')

async def topgirls_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Топ-10 девушек"""
    profiles = {url: data for url, data in rating_data['profiles'].items() if data['gender'] == 'girl'}
    
    if not profiles:
        await update.message.reply_text("❌ Нет данных")
        return
    
    sorted_profiles = sorted(profiles.items(), key=lambda x: x[1]['total_score'], reverse=True)[:10]
    
    text = "👱‍♀️ *TOP10 GIRLS*\n\n"
    
    for i, (url, data) in enumerate(sorted_profiles, 1):
        safe_name = safe_markdown(data.get('name', ''))
        text += f"{i}\\. {safe_name} — 🌟 {data['total_score']} \\({data['vote_count']}\\)\n"
    
    await update.message.reply_text(text, parse_mode='MarkdownV2')

async def toppeoplereset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сброс рейтинга - только админ"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только админы")
        return
    
    await update.message.reply_text(
        "⚠️ *ВНИМАНИЕ: ПОЛНЫЙ СБРОС РЕЙТИНГА*\n\n"
        "Это удалит все очки, голоса и историю\n\n"
        "Подтверждаете?",
        parse_mode='Markdown'
    )

__all__ = [
    'itsme_command',
    'handle_rate_photo',
    'handle_rate_profile',
    'handle_rate_age',
    'handle_rate_name',
    'handle_rate_about',
    'handle_rate_callback',
    'handle_rate_moderation_callback',
    'toppeople_command',
    'topboys_command',
    'topgirls_command',
    'toppeoplereset_command',
    'rating_data',
    'RATING_CALLBACKS',
    'RATING_MOD_CALLBACKS',
]
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from config import Config
from services.cooldown import cooldown_service, CooldownType
from datetime import datetime, timedelta
import logging
import re
import random
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ============= CALLBACK PREFIXES (УНИКАЛЬНЫЕ V8) =============
RATING_CALLBACKS = {
    'gender': 'rtpc_gender',
    'vote': 'rtpc_vote',
    'back': 'rtpc_back',
    'cancel': 'rtpc_cancel',
    'noop': 'rtpc_noop',
}

RATING_MOD_CALLBACKS = {
    'edit': 'rtmc_edit',
    'approve': 'rtmc_approve',
    'reject': 'rtmc_reject',
    'back': 'rtmc_back',
}

# ============= SETTINGS =============
COOLDOWN_HOURS = 24  # 24 часа на создание новой анкеты
MIN_AGE = 18
MAX_AGE = 70
MAX_ABOUT_WORDS = 3
MAX_WORD_LENGTH = 7

# ============= DATA STORAGE =============
rating_data = {
    'posts': {},
    'profiles': {},
    'user_votes': {},  # {user_id: {post_id: vote_value}}
}

# ============= HELPER FUNCTIONS =============

def safe_markdown(text: str) -> str:
    """
    БЕЗОПАСНОЕ форматирование для Markdown
    Решает проблему: Can't parse entities
    """
    if not text:
        return ""
    
    # Экранируем все спецсимволы Markdown
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    result = str(text)
    for char in special_chars:
        result = result.replace(char, f'\\{char}')
    
    return result

def validate_instagram_url(url: str) -> tuple:
    """
    Валидация Instagram URL (включая с UTM-параметрами)
    Returns: (is_valid: bool, cleaned_url: str)
    """
    if not url:
        return False, ""
    
    # Удаляем пробелы
    url = url.strip()
    
    # Паттерны для Instagram
    instagram_patterns = [
        r'(?:https?://)?(?:www\.)?instagram\.com/([a-zA-Z0-9._]+)',
        r'(?:https?://)?(?:www\.)?instagram\.com/p/([a-zA-Z0-9_-]+)',
        r'(?:https?://)?(?:www\.)?instagram\.com/reel/([a-zA-Z0-9_-]+)',
    ]
    
    for pattern in instagram_patterns:
        match = re.search(pattern, url)
        if match:
            # Извлекаем username или post ID
            identifier = match.group(1)
            
            # Формируем чистую ссылку
            if '/p/' in url or '/reel/' in url:
                cleaned_url = f"https://instagram.com/{'p' if '/p/' in url else 'reel'}/{identifier}"
            else:
                cleaned_url = f"https://instagram.com/{identifier}"
            
            return True, cleaned_url
    
    return False, url

def validate_profile_url(url: str) -> Optional[str]:
    """
    Валидация и очистка профиля (Telegram или Instagram)
    Returns: cleaned URL или None если невалидно
    """
    if not url or len(url) < 3:
        return None
    
    url = url.strip()
    
    # Telegram username
    if url.startswith('@'):
        username = url[1:]
        if re.match(r'^[a-zA-Z0-9_]{5,32}$', username):
            return f"@{username}"
        return None
    
    # t.me ссылка
    if 't.me/' in url:
        match = re.search(r't\.me/([a-zA-Z0-9_]{5,32})', url)
        if match:
            return f"@{match.group(1)}"
        return None
    
    # Instagram URL (включая с параметрами)
    is_valid, cleaned = validate_instagram_url(url)
    if is_valid:
        return cleaned
    
    # Обычный username без @
    if re.match(r'^[a-zA-Z0-9_]{3,}$', url):
        return f"@{url}"
    
    return None

async def check_vote_limit(user_id: int, post_id: int) -> bool:
    """Проверка лимита голосования - 1 голос на пост навсегда"""
    if user_id not in rating_data['user_votes']:
        return True
    
    return post_id not in rating_data['user_votes'][user_id]

async def generate_catalog_number() -> int:
    """Генерация уникального номера каталога"""
    from services.catalog_service import catalog_service
    from services.db import db
    from models import CatalogPost
    from sqlalchemy import select
    
    try:
        async with db.get_session() as session:
            for _ in range(100):
                number = random.randint(1, 9999)
                
                result = await session.execute(
                    select(CatalogPost.id).where(CatalogPost.catalog_number == number)
                )
                
                if not result.scalar_one_or_none():
                    used = any(p.get('catalog_number') == number for p in rating_data['posts'].values())
                    if not used:
                        return number
            
            raise Exception("Could not generate number")
    except Exception as e:
        logger.error(f"Error generating number: {e}")
        return random.randint(1000, 9999)

def validate_about(text: str) -> Optional[str]:
    """Валидация поля 'О себе'"""
    words = text.strip().split()
    
    if len(words) > MAX_ABOUT_WORDS:
        return f"❌ Максимум {MAX_ABOUT_WORDS} слова"
    
    for word in words:
        if len(word) > MAX_WORD_LENGTH:
            return f"❌ Слово '{word}' больше {MAX_WORD_LENGTH} символов"
    
    return None

# ============= MAIN COMMAND WITH COOLDOWN =============

async def itsme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать создание анкеты - /itsme с кулдауном 24ч"""
    user_id = update.effective_user.id
    
    # Проверка кулдауна через cooldown_service
    can_use, remaining = await cooldown_service.check_cooldown(
        user_id=user_id,
        command='itsme',
        duration=COOLDOWN_HOURS * 3600,  # 24 часа в секундах
        cooldown_type=CooldownType.NORMAL
    )
    
    if not can_use:
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        await update.message.reply_text(
            f"⏳ Подождите {hours}ч {minutes}мин перед созданием новой анкеты"
        )
        return
    
    context.user_data['rate_step'] = 'name'
    context.user_data['waiting_for'] = 'rate_name'
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=RATING_CALLBACKS['cancel'])]]
    
    await update.message.reply_text(
        "⭐ *TopPeople Budapest*\n\n"
        "🎯 Шаг 1/6: *Ваше имя*\n\n"
        "Как вас представить?\n"
        "Пример: Анна",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============= STEP HANDLERS =============

async def handle_rate_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка имени"""
    name = update.message.text.strip()
    
    if len(name) < 2 or len(name) > 50:
        await update.message.reply_text("❌ Имя: 2-50 символов")
        return
    
    context.user_data['rate_name'] = name
    context.user_data['rate_step'] = 'photo'
    context.user_data['waiting_for'] = 'rate_photo'
    
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data=RATING_CALLBACKS['back'])]]
    
    safe_name = safe_markdown(name)
    await update.message.reply_text(
        f"✅ Имя: *{safe_name}*\n\n"
        f"🎯 Шаг 2/6: *Фото или видео*\n\n"
        f"Отправьте фото или короткое видео",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_rate_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка фото или видео"""
    media_type = None
    file_id = None
    
    # Проверяем фото
    if update.message.photo:
        media_type = 'photo'
        file_id = update.message.photo[-1].file_id
    
    # Проверяем видео
    elif update.message.video:
        media_type = 'video'
        file_id = update.message.video.file_id
        
        # Проверка длительности видео (макс 60 секунд)
        if update.message.video.duration > 60:
            await update.message.reply_text("❌ Видео должно быть не длиннее 60 секунд")
            return
    
    else:
        await update.message.reply_text("❌ Отправьте фото или видео")
        return
    
    context.user_data['rate_media_type'] = media_type
    context.user_data['rate_media_file_id'] = file_id
    context.user_data['rate_step'] = 'age'
    context.user_data['waiting_for'] = 'rate_age'
    
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data=RATING_CALLBACKS['back'])]]
    
    media_text = "Фото" if media_type == 'photo' else "Видео"
    
    await update.message.reply_text(
        f"✅ {media_text} добавлено\n\n"
        f"🎯 Шаг 3/6: *Возраст*\n\n"
        f"Ваш возраст \\({MIN_AGE}\\-{MAX_AGE}\\)",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='MarkdownV2'
    )

async def handle_rate_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка возраста"""
    try:
        age = int(update.message.text.strip())
        if age < MIN_AGE or age > MAX_AGE:
            await update.message.reply_text(f"❌ Возраст: {MIN_AGE}-{MAX_AGE} лет")
            return
    except ValueError:
        await update.message.reply_text("❌ Введите число")
        return
    
    context.user_data['rate_age'] = age
    context.user_data['rate_step'] = 'about'
    context.user_data['waiting_for'] = 'rate_about'
    
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data=RATING_CALLBACKS['back'])]]
    
    await update.message.reply_text(
        f"✅ Возраст: *{age} лет*\n\n"
        f"🎯 Шаг 4/6: *О себе*\n\n"
        f"Опишите себя \\({MAX_ABOUT_WORDS} слова, макс\\. {MAX_WORD_LENGTH} символов\\)\n"
        f"Пример: красотка модель инстаграм",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='MarkdownV2'
    )

async def handle_rate_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка описания"""
    about = update.message.text.strip()
    
    error = validate_about(about)
    if error:
        await update.message.reply_text(error)
        return
    
    context.user_data['rate_about'] = about
    context.user_data['rate_step'] = 'profile'
    context.user_data['waiting_for'] = 'rate_profile'
    
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data=RATING_CALLBACKS['back'])]]
    
    safe_about = safe_markdown(about)
    await update.message.reply_text(
        f"✅ О себе: *{safe_about}*\n\n"
        f"🎯 Шаг 5/6: *Ссылка на профиль*\n\n"
        f"Telegram: @username или t\\.me/username\n"
        f"Instagram: допускаются ссылки с UTM\\-параметрами\n\n"
        f"Примеры:\n"
        f"• @anna\\_budapest\n"
        f"• https://instagram\\.com/anna\n"
        f"• https://www\\.instagram\\.com/anna?igsh=xxx&utm\\_source=qr",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='MarkdownV2'
    )

async def handle_rate_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ссылки на профиль с валидацией Instagram"""
    profile_input = update.message.text.strip()
    
    # Валидация и очистка URL
    cleaned_url = validate_profile_url(profile_input)
    
    if not cleaned_url:
        await update.message.reply_text(
            "❌ Неверная ссылка\n\n"
            "Допустимые форматы:\n"
            "• @username\n"
            "• t.me/username\n"
            "• instagram.com/username\n"
            "• instagram.com/username?параметры"
        )
        return
    
    context.user_data['rate_profile'] = cleaned_url
    context.user_data['rate_step'] = 'gender'
    context.user_data['waiting_for'] = None
    
    keyboard = [
        [
            InlineKeyboardButton("🙋🏼‍♂️ Парень", callback_data=f"{RATING_CALLBACKS['gender']}:boy"),
            InlineKeyboardButton("🙋🏼‍♀️ Девушка", callback_data=f"{RATING_CALLBACKS['gender']}:girl")
        ],
        [InlineKeyboardButton("⬅️ Назад", callback_data=RATING_CALLBACKS['back'])]
    ]
    
    safe_url = safe_markdown(cleaned_url)
    await update.message.reply_text(
        f"✅ Профиль: {safe_url}\n\n"
        f"🎯 Шаг 6/6: *Пол*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='MarkdownV2'
    )

# ============= PUBLISH =============

async def publish_rate_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Публикация в модерацию"""
    media_type = context.user_data.get('rate_media_type', 'photo')
    media_file_id = context.user_data.get('rate_media_file_id')
    name = context.user_data.get('rate_name')
    profile_url = context.user_data.get('rate_profile')
    age = context.user_data.get('rate_age')
    about = context.user_data.get('rate_about')
    gender = context.user_data.get('rate_gender')
    
    user_id = update.effective_user.id
    username = update.effective_user.username or f"ID{user_id}"
    
    if not all([media_file_id, name, profile_url, age, about, gender]):
        await update.callback_query.edit_message_text("❌ Ошибка: не хватает данных")
        return
    
    try:
        post_id = len(rating_data['posts']) + 1
        catalog_number = await generate_catalog_number()
        
        rating_data['posts'][post_id] = {
            'name': name,
            'profile_url': profile_url,
            'age': age,
            'about': about,
            'gender': gender,
            'media_type': media_type,
            'media_file_id': media_file_id,
            'author_user_id': user_id,
            'author_username': username,
            'catalog_number': catalog_number,
            'created_at': datetime.now(),
            'votes': {},
            'status': 'pending'
        }
        
        # УСТАНАВЛИВАЕМ КУЛДАУН через cooldown_service
        await cooldown_service.set_cooldown(
            user_id=user_id,
            command='itsme',
            duration=COOLDOWN_HOURS * 3600,
            cooldown_type=CooldownType.NORMAL
        )
        
        if profile_url not in rating_data['profiles']:
            rating_data['profiles'][profile_url] = {
                'name': name,
                'age': age,
                'about': about,
                'gender': gender,
                'total_score': 0,
                'vote_count': 0,
                'post_ids': []
            }
        
        rating_data['profiles'][profile_url]['post_ids'].append(post_id)
        
        logger.info(f"Rating post {post_id} (#{catalog_number}) created by @{username}")
        
        await send_rating_to_moderation(
            update, context, post_id, media_type, media_file_id,
            name, profile_url, age, about, gender, username, catalog_number
        )
        
        # Clear data
        for key in ['rate_media_type', 'rate_media_file_id', 'rate_name', 'rate_profile', 
                    'rate_age', 'rate_about', 'rate_gender', 'rate_step', 'waiting_for']:
            context.user_data.pop(key, None)
        
        gender_emoji = "🙋🏼‍♂️" if gender == "boy" else "🙋🏼‍♀️"
        media_text = "📹" if media_type == 'video' else "📸"
        
        safe_name = safe_markdown(name)
        safe_about = safe_markdown(about)
        
        await update.callback_query.edit_message_text(
            f"✅ *Заявка отправлена\\!*\n\n"
            f"{media_text} {media_type\\.title()}\n"
            f"👤 {safe_name}\n"
            f"{gender_emoji} {age} лет\n"
            f"💬 {safe_about}\n"
            f"🆔 \\#{catalog_number}\n\n"
            f"⏳ Ожидайте проверки",
            parse_mode='MarkdownV2'
        )
        
    except Exception as e:
        logger.error(f"Error publishing: {e}", exc_info=True)
        await update.callback_query.edit_message_text(f"❌ Ошибка: {str(e)[:100]}")

async def send_rating_to_moderation(
    update, context, post_id, media_type, media_file_id,
    name, profile_url, age, about, gender, author_username, catalog_number
):
    """Отправка в модерацию"""
    bot = context.bot
    
    try:
        keyboard = [
            [InlineKeyboardButton("✏️ Редактировать", callback_data=f"{RATING_MOD_CALLBACKS['edit']}:{post_id}")],
            [
                InlineKeyboardButton("✅ Опубликовать", callback_data=f"{RATING_MOD_CALLBACKS['approve']}:{post_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"{RATING_MOD_CALLBACKS['reject']}:{post_id}")
            ]
        ]
        
        gender_text = "Парень" if gender == "boy" else "Девушка"
        gender_emoji = "🙋🏼‍♂️" if gender == "boy" else "🙋🏼‍♀️"
        media_emoji = "📹" if media_type == 'video' else "📸"
        
        # Форматируем ссылку
        if profile_url.startswith('@'):
            if 'instagram' not in profile_url:
                formatted_name = f"[{name}](https://t.me/{profile_url[1:]})"
            else:
                formatted_name = f"[{name}]({profile_url})"
        elif 'instagram.com' in profile_url:
            formatted_name = f"[{name}]({profile_url})"
        else:
            formatted_name = name
        
        safe_name = safe_markdown(name)
        safe_about = safe_markdown(about)
        
        caption = (
            f"🆕 *Новая заявка TopPeople*\n\n"
            f"{media_emoji} Медиа: {media_type}\n"
            f"👤 {formatted_name}\n"
            f"{gender_emoji} {gender_text}, {age} лет\n"
            f"💬 {safe_about}\n"
            f"🆔 \\#{catalog_number}\n"
            f"📤 @{author_username}\n\n"
            f"❓ Ваше действие?"
        )
        
        # Отправляем в зависимости от типа медиа
        if media_type == 'video':
            msg = await bot.send_video(
                chat_id=Config.MODERATION_GROUP_ID,
                video=media_file_id,
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='MarkdownV2'
            )
        else:
            msg = await bot.send_photo(
                chat_id=Config.MODERATION_GROUP_ID,
                photo=media_file_id,
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='MarkdownV2'
            )
        
        rating_data['posts'][post_id]['moderation_message_id'] = msg.message_id
        rating_data['posts'][post_id]['moderation_group_id'] = Config.MODERATION_GROUP_ID
        
        logger.info(f"Rating post {post_id} sent to moderation")
        
    except Exception as e:
        logger.error(f"Error sending to moderation: {e}", exc_info=True)
        raise

# ============= MODERATION =============

async def approve_rating_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Одобрение и публикация"""
    query = update.callback_query
    
    if post_id not in rating_data['posts']:
        await query.answer("❌ Пост не найден", show_alert=True)
        return
    
    post = rating_data['posts'][post_id]
    
    try:
        BUDAPEST_PEOPLE_ID = Config.STATS_CHANNELS.get('budapest_people', -1003088023508)
        
        gender_text = "Парень" if post['gender'] == "boy" else "Девушка"
        profile_url = post['profile_url']
        media_type = post.get('media_type', 'photo')
        
        # Форматируем имя со ссылкой
        if profile_url.startswith('@'):
            if 'instagram' not in profile_url:
                formatted_name = f"[{post['name']}](https://t.me/{profile_url[1:]})"
            else:
                formatted_name = f"[{post['name']}]({profile_url})"
        elif 'instagram.com' in profile_url:
            formatted_name = f"[{post['name']}]({profile_url})"
        else:
            formatted_name = post['name']
        
        keyboard = [
            [
                InlineKeyboardButton("😭 -2 (0)", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:-2"),
                InlineKeyboardButton("👎 -1 (0)", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:-1"),
                InlineKeyboardButton("😐 0 (0)", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:0"),
                InlineKeyboardButton("👍 +1 (0)", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:1"),
                InlineKeyboardButton("🔥 +2 (0)", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:2"),
            ],
            [InlineKeyboardButton(f"⭐ Рейтинг: 0 | Голосов: 0", callback_data=RATING_CALLBACKS['noop'])]
        ]
        
        safe_name = safe_markdown(post['name'])
        safe_about = safe_markdown(post['about'])
        
        caption = (
            f"⭐ *TopPeople Budapest*\n\n"
            f"👤 {formatted_name}\n"
            f"{gender_text}, {post['age']} лет\n"
            f"💬 {safe_about}\n\n"
            f"🆔 \\#{post['catalog_number']}\n\n"
            f"Оцените участника:"
        )
        
        # Публикуем в зависимости от типа медиа
        if media_type == 'video':
            msg = await context.bot.send_video(
                chat_id=BUDAPEST_PEOPLE_ID,
                video=post['media_file_id'],
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='MarkdownV2'
            )
        else:
            msg = await context.bot.send_photo(
                chat_id=BUDAPEST_PEOPLE_ID,
                photo=post['media_file_id'],
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='MarkdownV2'
            )
        
        post['message_id'] = msg.message_id
        post['published_channel_id'] = BUDAPEST_PEOPLE_ID
        post['status'] = 'published'
        post['published_link'] = f"https://t.me/c/{str(BUDAPEST_PEOPLE_ID)[4:]}/{msg.message_id}"
        
        # Добавляем в каталог
        from services.catalog_service import catalog_service
        
        category = '👱🏻‍♀️ TopGirls' if post['gender'] == 'girl' else '🤵🏼‍♂️ TopBoys'
        
        catalog_post_id = await catalog_service.add_post(
            user_id=post['author_user_id'],
            catalog_link=post['published_link'],
            category=category,
            name=post['name'],
            tags=[post['about'], gender_text, f"{post['age']}"],
            media_type=media_type,
            media_file_id=post['media_file_id'],
            media_group_id=None,
            media_json=[post['media_file_id']],
            author_username=post.get('author_username'),
            author_id=post['author_user_id']
        )
        
        if catalog_post_id:
            from services.db import db
            from models import CatalogPost
            from sqlalchemy import update as sql_update
            
            async with db.get_session() as session:
                await session.execute(
                    sql_update(CatalogPost)
                    .where(CatalogPost.id == catalog_post_id)
                    .values(catalog_number=post['catalog_number'])
                )
                await session.commit()
        
        await query.edit_message_reply_markup(reply_markup=None)
        await query.edit_message_caption(
            caption=f"{query.message.caption}\n\n✅ *ОПУБЛИКОВАНО*",
            parse_mode='MarkdownV2'
        )
        
        # Уведомляем автора
        try:
            safe_name_author = safe_markdown(post['name'])
            await context.bot.send_message(
                chat_id=post['author_user_id'],
                text=(
                    f"🎉 *Ваша заявка одобрена\\!*\n\n"
                    f"👤 {safe_name_author}\n"
                    f"🆔 \\#{post['catalog_number']}\n\n"
                    f"🔗 [Ваш пост]({safe_markdown(post['published_link'])})\n\n"
                    f"✅ Теперь вы в TopPeople\\!"
                ),
                parse_mode='MarkdownV2'
            )
        except Exception as e:
            logger.warning(f"Could not notify author: {e}")
        
        await query.answer("✅ Опубликовано", show_alert=False)
        logger.info(f"Rating post {post_id} approved")
        
    except Exception as e:
        logger.error(f"Error approving: {e}", exc_info=True)
        await query.answer(f"❌ Ошибка: {str(e)[:100]}", show_alert=True)

async def reject_rating_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Отклонение поста"""
    query = update.callback_query
    
    if post_id not in rating_data['posts']:
        await query.answer("❌ Пост не найден", show_alert=True)
        return
    
    try:
        post = rating_data['posts'][post_id]
        author_user_id = post.get('author_user_id')
        
        del rating_data['posts'][post_id]
        
        await query.edit_message_reply_markup(reply_markup=None)
        await query.edit_message_caption(
            caption=f"{query.message.caption}\n\n❌ *ОТКЛОНЕНО*",
            parse_mode='MarkdownV2'
        )
        
        if author_user_id:
            try:
                await context.bot.send_message(
                    chat_id=author_user_id,
                    text="❌ Ваша заявка в TopPeople отклонена"
                )
            except:
                pass
        
        await query.answer("❌ Отклонено", show_alert=False)
        logger.info(f"Rating post {post_id} rejected")
        
    except Exception as e:
        logger.error(f"Error rejecting: {e}")
        await query.answer(f"❌ Ошибка: {str(e)[:100]}", show_alert=True)

# ============= VOTING (с лимитом 1 голос навсегда) =============

async def handle_vote(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int, vote_value: int):
    """Обработка голосования с лимитом 1 голос на пост"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    # Проверяем лимит голосования
    can_vote = await check_vote_limit(user_id, post_id)
    
    if not can_vote:
        await query.answer("❌ Вы уже оценили этот пост", show_alert=True)
        return
    
    if post_id not in rating_data['posts']:
        await query.answer("❌ Пост не найден", show_alert=True)
        return
    
    post = rating_data['posts'][post_id]
    
    # Записываем голос
    if user_id not in rating_data['user_votes']:
        rating_data['user_votes'][user_id] = {}
    
    rating_data['user_votes'][user_id][post_id] = vote_value
    
    # Обновляем голоса поста
    if 'votes' not in post:
        post['votes'] = {}
    
    post['votes'][user_id] = vote_value
    
    # Обновляем профиль
    profile_url = post.get('profile_url')
    if profile_url and profile_url in rating_data['profiles']:
        profile = rating_data['profiles'][profile_url]
        
        # Пересчитываем общий рейтинг
        all_votes = []
        for pid in profile.get('post_ids', []):
            if pid in rating_data['posts']:
                all_votes.extend(rating_data['posts'][pid].get('votes', {}).values())
        
        profile['total_score'] = sum(all_votes)
        profile['vote_count'] = len(all_votes)
    
    # Обновляем кнопки
    votes = post.get('votes', {})
    vote_counts = {-2: 0, -1: 0, 0: 0, 1: 0, 2: 0}
    
    for v in votes.values():
        if v in vote_counts:
            vote_counts[v] += 1
    
    total_score = sum(votes.values())
    vote_count = len(votes)
    
    keyboard = [
        [
            InlineKeyboardButton(f"😭 -2 ({vote_counts[-2]})", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:-2"),
            InlineKeyboardButton(f"👎 -1 ({vote_counts[-1]})", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:-1"),
            InlineKeyboardButton(f"😐 0 ({vote_counts[0]})", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:0"),
            InlineKeyboardButton(f"👍 +1 ({vote_counts[1]})", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:1"),
            InlineKeyboardButton(f"🔥 +2 ({vote_counts[2]})", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:2"),
        ],
        [InlineKeyboardButton(f"⭐ Рейтинг: {total_score} | Голосов: {vote_count}", callback_data=RATING_CALLBACKS['noop'])]
    ]
    
    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        await query.answer(f"✅ Ваша оценка: {vote_value:+d}", show_alert=False)
        logger.info(f"User {user_id} voted {vote_value} on post {post_id}")
    except Exception as e:
        logger.error(f"Error updating vote buttons: {e}")
        await query.answer("✅ Голос учтён", show_alert=False)

# ============= CALLBACKS =============

async def handle_rate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка публичных callback"""
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split(":")
    
    if data_parts[0].startswith('rtpc_'):
        action = data_parts[0][5:]
    else:
        action = data_parts[0]
    
    if action == 'gender':
        value = data_parts[1] if len(data_parts) > 1 else None
        context.user_data['rate_gender'] = value
        await publish_rate_post(update, context)
    
    elif action == 'vote':
        post_id = int(data_parts[1]) if len(data_parts) > 1 else None
        vote_value = int(data_parts[2]) if len(data_parts) > 2 else 0
        
        if post_id:
            await handle_vote(update, context, post_id, vote_value)
    
    elif action == 'cancel':
        for key in ['rate_media_type', 'rate_media_file_id', 'rate_name', 'rate_profile', 
                    'rate_age', 'rate_about', 'rate_gender', 'rate_step', 'waiting_for']:
            context.user_data.pop(key, None)
        await query.edit_message_text("❌ Заявка отменена")
    
    elif action == 'noop':
        pass  # Пустое действие для кнопок с рейтингом

async def handle_rate_moderation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка модерационных callback"""
    query = update.callback_query
    
    data_parts = query.data.split(":")
    
    if data_parts[0].startswith('rtmc_'):
        action = data_parts[0][5:]
    else:
        action = data_parts[0]
    
    post_id = int(data_parts[1]) if len(data_parts) > 1 and data_parts[1].isdigit() else None
    
    if not Config.is_moderator(update.effective_user.id):
        await query.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    if action == 'approve':
        await approve_rating_post(update, context, post_id)
    elif action == 'reject':
        await reject_rating_post(update, context, post_id)

# ============= STATS COMMANDS =============

async def toppeople_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Топ-10 в Будапеште"""
    if not rating_data['profiles']:
        await update.message.reply_text("❌ Нет данных")
        return
    
    sorted_profiles = sorted(
        rating_data['profiles'].items(),
        key=lambda x: x[1]['total_score'],
        reverse=True
    )[:10]
    
    text = "⭐ *TOPinBUDAPEST*\n\n"
    
    for i, (profile_url, data) in enumerate(sorted_profiles, 1):
        gender_emoji = "🙋🏼‍♂️" if data['gender'] == 'boy' else "🙋🏼‍♀️"
        safe_name = safe_markdown(data.get('name', ''))
        safe_url = safe_markdown(profile_url)
        
        text += (
            f"{i}\\. {safe_name} \\({safe_url}\\)\n"
            f"   {gender_emoji} {data.get('age')} лет\n"
            f"   ⭐ {data['total_score']} \\| 📊 {data['vote_count']}\n\n"
        )
    
    await update.message.reply_text(text, parse_mode='MarkdownV2')

async def topboys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Топ-10 парней"""
    profiles = {url: data for url, data in rating_data['profiles'].items() if data['gender'] == 'boy'}
    
    if not profiles:
        await update.message.reply_text("❌ Нет данных")
        return
    
    sorted_profiles = sorted(profiles.items(), key=lambda x: x[1]['total_score'], reverse=True)[:10]
    
    text = "🕺 *TOP10 BOYS*\n\n"
    
    for i, (url, data) in enumerate(sorted_profiles, 1):
        safe_name = safe_markdown(data.get('name', ''))
        text += f"{i}\\. {safe_name} — ⭐ {data['total_score']} \\({data['vote_count']}\\)\n"
    
    await update.message.reply_text(text, parse_mode='MarkdownV2')

async def topgirls_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Топ-10 девушек"""
    profiles = {url: data for url, data in rating_data['profiles'].items() if data['gender'] == 'girl'}
    
    if not profiles:
        await update.message.reply_text("❌ Нет данных")
        return
    
    sorted_profiles = sorted(profiles.items(), key=lambda x: x[1]['total_score'], reverse=True)[:10]
    
    text = "👱‍♀️ *TOP10 GIRLS*\n\n"
    
    for i, (url, data) in enumerate(sorted_profiles, 1):
        safe_name = safe_markdown(data.get('name', ''))
        text += f"{i}\\. {safe_name} — 🌟 {data['total_score']} \\({data['vote_count']}\\)\n"
    
    await update.message.reply_text(text, parse_mode='MarkdownV2')

async def toppeoplereset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сброс рейтинга - только админ"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только админы")
        return
    
    await update.message.reply_text(
        "⚠️ *ВНИМАНИЕ: ПОЛНЫЙ СБРОС РЕЙТИНГА*\n\n"
        "Это удалит все очки, голоса и историю\n\n"
        "Подтверждаете?",
        parse_mode='Markdown'
    )

__all__ = [
    'itsme_command',
    'handle_rate_photo',
    'handle_rate_profile',
    'handle_rate_age',
    'handle_rate_name',
    'handle_rate_about',
    'handle_rate_callback',
    'handle_rate_moderation_callback',
    'toppeople_command',
    'topboys_command',
    'topgirls_command',
    'toppeoplereset_command',
    'rating_data',
    'RATING_CALLBACKS',
    'RATING_MOD_CALLBACKS',
]
