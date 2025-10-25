# -*- coding: utf-8 -*-
"""
Система рейтинга TopPeople Budapest - ВЕРСИЯ 5.0

НОВЫЙ ФУНКЦИОНАЛ v5.0:
- ✅ Кулдаун 3 часа на создание заявки
- ✅ Поле "Имя" для отображения
- ✅ Возраст 18-70 лет
- ✅ Описание "О себе" (3 слова по 7 символов)
- ✅ Ссылка форматируется как кликабельное имя
- ✅ Уникальный ID из каталога (catalog_number)
- ✅ Редактирование в группе модерации
- ✅ @username автора в заявке
- ✅ Автор получает ссылку после публикации
- ✅ Автоматическое добавление в каталог
- ✅ Рейтинг отображается в /catalog
- ✅ Выбор пола через /addgirltocat и /addboytocat логику

Версия: 5.0.0
Дата: 25.10.2025
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ContextTypes
from config import Config
from datetime import datetime, timedelta
import logging
import re
import random
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ============= ХРАНИЛИЩЕ ДАННЫХ =============

rating_data = {
    'posts': {},           # ID поста -> данные поста
    'profiles': {},        # profile_url -> профиль пользователя
    'user_votes': {},      # (user_id, post_id) -> голос
    'cooldowns': {}        # user_id -> timestamp последней заявки
}

# ============= НАСТРОЙКИ =============

COOLDOWN_HOURS = 3
MIN_AGE = 18
MAX_AGE = 70
MAX_ABOUT_WORDS = 3
MAX_WORD_LENGTH = 7

# ============= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =============

async def check_cooldown(user_id: int) -> Optional[str]:
    """Проверить кулдаун пользователя. Возвращает None если можно, иначе строку с ошибкой"""
    if user_id in rating_data['cooldowns']:
        last_submission = rating_data['cooldowns'][user_id]
        time_passed = datetime.now() - last_submission
        cooldown_time = timedelta(hours=COOLDOWN_HOURS)
        
        if time_passed < cooldown_time:
            remaining = cooldown_time - time_passed
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            return f"⏳ Подождите {hours}ч {minutes}мин перед следующей заявкой"
    
    return None

async def generate_catalog_number() -> int:
    """Генерировать уникальный номер как в каталоге"""
    from services.catalog_service import catalog_service
    
    # Получаем занятые номера из каталога
    async from services.db import db
    from models import CatalogPost
    from sqlalchemy import select
    
    try:
        async with db.get_session() as session:
            # Пробуем 100 раз сгенерировать уникальный номер
            for _ in range(100):
                number = random.randint(1, 9999)
                
                # Проверяем в БД каталога
                result = await session.execute(
                    select(CatalogPost.id).where(CatalogPost.catalog_number == number)
                )
                
                if not result.scalar_one_or_none():
                    # Проверяем в rating_data
                    used_in_rating = any(
                        post.get('catalog_number') == number 
                        for post in rating_data['posts'].values()
                    )
                    
                    if not used_in_rating:
                        return number
            
            raise Exception("Could not generate unique catalog number")
    except Exception as e:
        logger.error(f"Error generating catalog number: {e}")
        # Fallback: просто случайное число
        return random.randint(1000, 9999)

def validate_about(text: str) -> Optional[str]:
    """Валидация поля 'О себе'. Возвращает None если ОК, иначе ошибку"""
    words = text.strip().split()
    
    if len(words) > MAX_ABOUT_WORDS:
        return f"❌ Максимум {MAX_ABOUT_WORDS} слова"
    
    for word in words:
        if len(word) > MAX_WORD_LENGTH:
            return f"❌ Слово '{word}' больше {MAX_WORD_LENGTH} символов"
    
    return None

# ============= ОСНОВНАЯ КОМАНДА /itsme =============

async def itsme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать процесс создания заявки в TopPeople - /itsme"""
    user_id = update.effective_user.id
    
    # Проверяем кулдаун
    cooldown_msg = await check_cooldown(user_id)
    if cooldown_msg:
        await update.message.reply_text(cooldown_msg)
        return
    
    context.user_data['rate_step'] = 'name'
    context.user_data['waiting_for'] = 'rate_name'
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="rate:cancel")]]
    
    text = (
        "**⭐ TopPeople Budapest**\n\n"
        "🎯 Шаг 1/6: **Ваше имя**\n\n"
        "Как вас представить?\n"
        "Пример: Анна"
    )
    
    await update.message.reply_text(
        text, 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode='Markdown'
    )

# ============= ОБРАБОТЧИКИ ШАГОВ =============

async def handle_rate_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка имени"""
    name = update.message.text.strip()
    
    if len(name) < 2 or len(name) > 50:
        await update.message.reply_text("❌ Имя должно быть от 2 до 50 символов")
        return
    
    context.user_data['rate_name'] = name
    context.user_data['rate_step'] = 'photo'
    context.user_data['waiting_for'] = 'rate_photo'
    
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="rate:back")]]
    
    text = f"✅ Имя: **{name}**\n\n🎯 Шаг 2/6: **Фото**\n\nОтправьте ваше лучшее фото"
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_rate_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка фото"""
    if not update.message.photo:
        await update.message.reply_text("❌ Отправьте фотографию")
        return
    
    context.user_data['rate_photo_file_id'] = update.message.photo[-1].file_id
    context.user_data['rate_step'] = 'age'
    context.user_data['waiting_for'] = 'rate_age'
    
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="rate:back")]]
    
    name = context.user_data.get('rate_name', 'Гость')
    text = f"✅ Фото добавлено\n\n🎯 Шаг 3/6: **Возраст**\n\nУкажите ваш возраст ({MIN_AGE}-{MAX_AGE})"
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_rate_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка возраста"""
    age_text = update.message.text.strip()
    
    try:
        age = int(age_text)
        if age < MIN_AGE or age > MAX_AGE:
            await update.message.reply_text(f"❌ Возраст должен быть от {MIN_AGE} до {MAX_AGE} лет")
            return
    except ValueError:
        await update.message.reply_text("❌ Введите число")
        return
    
    context.user_data['rate_age'] = age
    context.user_data['rate_step'] = 'about'
    context.user_data['waiting_for'] = 'rate_about'
    
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="rate:back")]]
    
    text = (
        f"✅ Возраст: **{age} лет**\n\n"
        f"🎯 Шаг 4/6: **О себе**\n\n"
        f"Опишите себя ({MAX_ABOUT_WORDS} слова, макс. {MAX_WORD_LENGTH} символов на слово)\n"
        f"Пример: красотка модель инстаграм"
    )
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_rate_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка описания 'О себе'"""
    about = update.message.text.strip()
    
    error = validate_about(about)
    if error:
        await update.message.reply_text(error)
        return
    
    context.user_data['rate_about'] = about
    context.user_data['rate_step'] = 'profile'
    context.user_data['waiting_for'] = 'rate_profile'
    
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="rate:back")]]
    
    text = (
        f"✅ О себе: **{about}**\n\n"
        f"🎯 Шаг 5/6: **Ссылка**\n\n"
        f"Отправьте ссылку на ваш профиль\n"
        f"Пример: @username или https://instagram.com/username"
    )
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_rate_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка профиля"""
    profile_url = update.message.text.strip()
    
    if not profile_url or len(profile_url) < 3:
        await update.message.reply_text("❌ Неверный формат ссылки")
        return
    
    # Форматируем ссылку
    if profile_url.startswith('@'):
        profile_url = profile_url[1:]
    
    # Если это инстаграм ссылка - сохраняем как есть
    if 'instagram.com' in profile_url:
        pass
    # Если это username - добавляем @
    elif not profile_url.startswith('http'):
        profile_url = f"@{profile_url}"
    
    context.user_data['rate_profile'] = profile_url
    context.user_data['rate_step'] = 'gender'
    context.user_data['waiting_for'] = None
    
    keyboard = [
        [
            InlineKeyboardButton("🙋🏼‍♂️ Парень", callback_data="rate:gender:boy"),
            InlineKeyboardButton("🙋🏼‍♀️ Девушка", callback_data="rate:gender:girl")
        ],
        [InlineKeyboardButton("⬅️ Назад", callback_data="rate:back")]
    ]
    
    text = f"✅ Профиль: {profile_url}\n\n🎯 Шаг 6/6: **Пол**\n\nУкажите ваш пол:"
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ============= ОБРАБОТКА CALLBACK =============

async def handle_rate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка всех коллбэков рейтинга"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")
    action = data[1] if len(data) > 1 else None
    value = data[2] if len(data) > 2 else None
    
    if action == "gender":
        context.user_data['rate_gender'] = value
        await publish_rate_post(update, context)
    
    elif action == "vote":
        post_id = int(value) if value else None
        vote_value = int(data[3]) if len(data) > 3 else None
        await handle_vote(update, context, post_id, vote_value)
    
    elif action == "back":
        await handle_back_navigation(update, context)
    
    elif action == "cancel":
        await cancel_rate_submission(update, context)
    
    elif action == "noop":
        await query.answer()

# ============= НАВИГАЦИЯ НАЗАД =============

async def handle_back_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки Назад"""
    query = update.callback_query
    step = context.user_data.get('rate_step', 'name')
    
    if step == 'photo':
        context.user_data['rate_step'] = 'name'
        context.user_data['waiting_for'] = 'rate_name'
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="rate:cancel")]]
        await query.edit_message_text(
            "🎯 Шаг 1/6: **Ваше имя**\n\nКак вас представить?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif step == 'age':
        context.user_data['rate_step'] = 'photo'
        context.user_data['waiting_for'] = 'rate_photo'
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="rate:back")]]
        await query.edit_message_text(
            "🎯 Шаг 2/6: **Фото**\n\nОтправьте ваше лучшее фото",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif step == 'about':
        context.user_data['rate_step'] = 'age'
        context.user_data['waiting_for'] = 'rate_age'
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="rate:back")]]
        await query.edit_message_text(
            f"🎯 Шаг 3/6: **Возраст**\n\nУкажите ваш возраст ({MIN_AGE}-{MAX_AGE})",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif step == 'profile':
        context.user_data['rate_step'] = 'about'
        context.user_data['waiting_for'] = 'rate_about'
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="rate:back")]]
        await query.edit_message_text(
            f"🎯 Шаг 4/6: **О себе**\n\nОпишите себя ({MAX_ABOUT_WORDS} слова, макс. {MAX_WORD_LENGTH} символов)",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif step == 'gender':
        context.user_data['rate_step'] = 'profile'
        context.user_data['waiting_for'] = 'rate_profile'
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="rate:back")]]
        await query.edit_message_text(
            "🎯 Шаг 5/6: **Ссылка**\n\nОтправьте ссылку на ваш профиль",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def cancel_rate_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена создания заявки"""
    query = update.callback_query
    
    context.user_data.pop('rate_photo_file_id', None)
    context.user_data.pop('rate_name', None)
    context.user_data.pop('rate_profile', None)
    context.user_data.pop('rate_age', None)
    context.user_data.pop('rate_about', None)
    context.user_data.pop('rate_gender', None)
    context.user_data.pop('rate_step', None)
    context.user_data.pop('waiting_for', None)
    
    await query.edit_message_text("❌ Заявка отменена")

# ============= ПУБЛИКАЦИЯ ПОСТА =============

async def publish_rate_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить пост на модерацию"""
    photo_file_id = context.user_data.get('rate_photo_file_id')
    name = context.user_data.get('rate_name')
    profile_url = context.user_data.get('rate_profile')
    age = context.user_data.get('rate_age')
    about = context.user_data.get('rate_about')
    gender = context.user_data.get('rate_gender')
    
    user_id = update.effective_user.id
    username = update.effective_user.username or f"ID{user_id}"
    
    if not all([photo_file_id, name, profile_url, age, about, gender]):
        await update.callback_query.edit_message_text("❌ Ошибка: не хватает данных")
        return
    
    try:
        # Генерируем уникальный ID поста
        post_id = len(rating_data['posts']) + 1
        
        # Генерируем catalog_number
        catalog_number = await generate_catalog_number()
        
        # Сохраняем пост
        rating_data['posts'][post_id] = {
            'name': name,
            'profile_url': profile_url,
            'age': age,
            'about': about,
            'gender': gender,
            'photo_file_id': photo_file_id,
            'author_user_id': user_id,
            'author_username': username,
            'catalog_number': catalog_number,
            'created_at': datetime.now(),
            'votes': {},
            'status': 'pending'
        }
        
        # Обновляем кулдаун
        rating_data['cooldowns'][user_id] = datetime.now()
        
        # Создаем профиль если нужно
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
        
        logger.info(f"Rating post {post_id} (#{catalog_number}) created by @{username} (ID: {user_id})")
        
        # Отправляем на модерацию
        await send_rating_to_moderation(update, context, post_id, photo_file_id, name, profile_url, age, about, gender, username, catalog_number)
        
        # Очищаем данные
        context.user_data.pop('rate_photo_file_id', None)
        context.user_data.pop('rate_name', None)
        context.user_data.pop('rate_profile', None)
        context.user_data.pop('rate_age', None)
        context.user_data.pop('rate_about', None)
        context.user_data.pop('rate_gender', None)
        context.user_data.pop('rate_step', None)
        context.user_data.pop('waiting_for', None)
        
        gender_emoji = "🙋🏼‍♂️" if gender == "boy" else "🙋🏼‍♀️"
        
        await update.callback_query.edit_message_text(
            f"✅ **Заявка отправлена!**\n\n"
            f"👤 {name}\n"
            f"{gender_emoji} {age} лет\n"
            f"💬 {about}\n"
            f"🆔 #{catalog_number}\n\n"
            f"⏳ Ожидайте проверки модератором"
        , parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error publishing rate post: {e}", exc_info=True)
        await update.callback_query.edit_message_text(f"❌ Ошибка: {str(e)[:100]}")

# ============= ОТПРАВКА НА МОДЕРАЦИЮ =============

async def send_rating_to_moderation(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE,
    post_id: int,
    photo_file_id: str,
    name: str,
    profile_url: str,
    age: int,
    about: str,
    gender: str,
    author_username: str,
    catalog_number: int
):
    """Отправить пост на модерацию с возможностью редактирования"""
    bot = context.bot
    
    try:
        keyboard = [
            [
                InlineKeyboardButton("✏️ Редактировать", callback_data=f"rate_mod:edit:{post_id}"),
            ],
            [
                InlineKeyboardButton("✅ Опубликовать", callback_data=f"rate_mod:approve:{post_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"rate_mod:reject:{post_id}")
            ]
        ]
        
        gender_text = "Парень" if gender == "boy" else "Девушка"
        gender_emoji = "🙋🏼‍♂️" if gender == "boy" else "🙋🏼‍♀️"
        
        # Форматируем имя как ссылку
        if profile_url.startswith('@'):
            formatted_name = f"[{name}](https://t.me/{profile_url[1:]})"
        elif 'instagram.com' in profile_url:
            formatted_name = f"[{name}]({profile_url})"
        else:
            formatted_name = f"[{name}]({profile_url})"
        
        caption = (
            f"🆕 **Новая заявка TopPeople**\n\n"
            f"👤 Имя: {formatted_name}\n"
            f"{gender_emoji} {gender_text}, {age} лет\n"
            f"💬 О себе: {about}\n"
            f"🆔 Номер: #{catalog_number}\n"
            f"📤 Автор: @{author_username}\n\n"
            f"❓ Ваше действие?"
        )
        
        msg = await bot.send_photo(
            chat_id=Config.MODERATION_GROUP_ID,
            photo=photo_file_id,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        rating_data['posts'][post_id]['moderation_message_id'] = msg.message_id
        rating_data['posts'][post_id]['moderation_group_id'] = Config.MODERATION_GROUP_ID
        
        logger.info(f"Rating post {post_id} sent to moderation (msg: {msg.message_id})")
        
    except Exception as e:
        logger.error(f"Error sending rating post to moderation: {e}", exc_info=True)
        raise

# ============= МОДЕРАЦИЯ =============

async def handle_rate_moderation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка модерации"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")
    action = data[1] if len(data) > 1 else None
    post_id = int(data[2]) if len(data) > 2 and data[2].isdigit() else None
    
    if not Config.is_moderator(update.effective_user.id):
        await query.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    if action == "approve":
        await approve_rating_post(update, context, post_id)
    elif action == "reject":
        await reject_rating_post(update, context, post_id)
    elif action == "edit":
        await start_edit_rating_post(update, context, post_id)

# ============= РЕДАКТИРОВАНИЕ В МОДЕРАЦИИ =============

async def start_edit_rating_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Начать редактирование поста"""
    query = update.callback_query
    
    if post_id not in rating_data['posts']:
        await query.answer("❌ Пост не найден", show_alert=True)
        return
    
    post = rating_data['posts'][post_id]
    
    keyboard = [
        [InlineKeyboardButton("📝 Имя", callback_data=f"rate_edit:name:{post_id}")],
        [InlineKeyboardButton("🎂 Возраст", callback_data=f"rate_edit:age:{post_id}")],
        [InlineKeyboardButton("💬 О себе", callback_data=f"rate_edit:about:{post_id}")],
        [InlineKeyboardButton("🔗 Ссылка", callback_data=f"rate_edit:profile:{post_id}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f"rate_mod:back:{post_id}")]
    ]
    
    text = (
        f"✏️ **Редактирование заявки #{post.get('catalog_number')}**\n\n"
        f"👤 Имя: {post.get('name')}\n"
        f"🎂 Возраст: {post.get('age')}\n"
        f"💬 О себе: {post.get('about')}\n"
        f"🔗 Профиль: {post.get('profile_url')}\n\n"
        f"Что изменить?"
    )
    
    try:
        await query.edit_message_caption(
            caption=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    except:
        await query.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

# ============= ОДОБРЕНИЕ ПОСТА =============

async def approve_rating_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Одобрить и опубликовать пост + добавить в каталог"""
    query = update.callback_query
    
    if post_id not in rating_data['posts']:
        await query.answer("❌ Пост не найден", show_alert=True)
        return
    
    post = rating_data['posts'][post_id]
    name = post['name']
    profile_url = post['profile_url']
    age = post['age']
    about = post['about']
    gender = post['gender']
    photo_file_id = post['photo_file_id']
    catalog_number = post['catalog_number']
    author_user_id = post['author_user_id']
    
    try:
        # 1. ПУБЛИКУЕМ В BUDAPEST_PEOPLE_ID
        BUDAPEST_PEOPLE_ID = Config.STATS_CHANNELS.get('budapest_people', -1003088023508)
        
        gender_text = "Парень" if gender == "boy" else "Девушка"
        
        # Форматируем имя как ссылку
        if profile_url.startswith('@'):
            formatted_name = f"[{name}](https://t.me/{profile_url[1:]})"
        elif 'instagram.com' in profile_url:
            formatted_name = f"[{name}]({profile_url})"
        else:
            formatted_name = f"[{name}]({profile_url})"
        
        keyboard = [
            [
                InlineKeyboardButton("😭 -2 (0)", callback_data=f"rate:vote:{post_id}:-2"),
                InlineKeyboardButton("👎 -1 (0)", callback_data=f"rate:vote:{post_id}:-1"),
                InlineKeyboardButton("😐 0 (0)", callback_data=f"rate:vote:{post_id}:0"),
                InlineKeyboardButton("👍 +1 (0)", callback_data=f"rate:vote:{post_id}:1"),
                InlineKeyboardButton("🔥 +2 (0)", callback_data=f"rate:vote:{post_id}:2"),
            ],
            [InlineKeyboardButton(f"⭐ Рейтинг: 0 | Голосов: 0", callback_data="rate:noop")]
        ]
        
        caption = (
            f"⭐ **TopPeople Budapest**\n\n"
            f"👤 {formatted_name}\n"
            f"{gender_text}, {age} лет\n"
            f"💬 {about}\n\n"
            f"🆔 #{catalog_number}\n\n"
            f"Оцените участника:"
        )
        
        msg = await context.bot.send_photo(
            chat_id=BUDAPEST_PEOPLE_ID,
            photo=photo_file_id,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        post['message_id'] = msg.message_id
        post['published_channel_id'] = BUDAPEST_PEOPLE_ID
        post['status'] = 'published'
        post['published_link'] = f"https://t.me/c/{str(BUDAPEST_PEOPLE_ID)[4:]}/{msg.message_id}"
        
        # 2. ДОБАВЛЯЕМ В КАТАЛОГ
        from services.catalog_service import catalog_service
        
        category = '👱🏻‍♀️ TopGirls' if gender == 'girl' else '🤵🏼‍♂️ TopBoys'
        
        # Создаем ссылку на пост
        catalog_link = post['published_link']
        
        catalog_post_id = await catalog_service.add_post(
            user_id=author_user_id,
            catalog_link=catalog_link,
            category=category,
            name=name,
            tags=[about, gender_text, f"{age}"],
            media_type='photo',
            media_file_id=photo_file_id,
            media_group_id=None,
            media_json=[photo_file_id],
            author_username=post.get('author_username'),
            author_id=author_user_id
        )
        
        # Устанавливаем catalog_number
        if catalog_post_id:
            from services.db import db
            from models import CatalogPost
            from sqlalchemy import select, update
            
            async with db.get_session() as session:
                await session.execute(
                    update(CatalogPost)
                    .where(CatalogPost.id == catalog_post_id)
                    .values(catalog_number=catalog_number)
                )
                await session.commit()
            
            logger.info(f"Added to catalog: post_id={catalog_post_id}, catalog_number={catalog_number}")
        
        # 3. УВЕДОМЛЯЕМ МОДЕРАТОРОВ
        await query.edit_message_reply_markup(reply_markup=None)
        
        new_caption = f"{query.message.caption}\n\n✅ **ОПУБЛИКОВАНО**"
        
        await query.edit_message_caption(caption=new_caption, parse_mode='Markdown')
        
        # 4. ОТПРАВЛЯЕМ ССЫЛКУ АВТОРУ
        try:
            author_message = (
                f"🎉 **Ваша заявка одобрена!**\n\n"
                f"👤 {name}\n"
                f"🆔 #{catalog_number}\n\n"
                f"🔗 Ваш пост: {catalog_link}\n\n"
                f"✅ Теперь вы в каталоге TopPeople!"
            )
            
            await context.bot.send_message(
                chat_id=author_user_id,
                text=author_message,
                parse_mode='Markdown'
            )
            logger.info(f"Author {author_user_id} notified about approval")
        except Exception as e:
            logger.warning(f"Could not notify author {author_user_id}: {e}")
        
        await query.answer("✅ Опубликовано и добавлено в каталог", show_alert=False)
        logger.info(f"Rating post {post_id} approved and added to catalog")
        
    except Exception as e:
        logger.error(f"Error approving rating post: {e}", exc_info=True)
        await query.answer(f"❌ Ошибка: {str(e)[:100]}", show_alert=True)

# ============= ОТКЛОНЕНИЕ ПОСТА =============

async def reject_rating_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Отклонить пост"""
    query = update.callback_query
    
    if post_id not in rating_data['posts']:
        await query.answer("❌ Пост не найден", show_alert=True)
        return
    
    try:
        post = rating_data['posts'][post_id]
        author_user_id = post.get('author_user_id')
        
        # Удаляем пост
        if post_id in rating_data['posts']:
            del rating_data['posts'][post_id]
        
        await query.edit_message_reply_markup(reply_markup=None)
        
        new_caption = f"{query.message.caption}\n\n❌ **ОТКЛОНЕНО**"
        
        await query.edit_message_caption(caption=new_caption, parse_mode='Markdown')
        
        # Уведомляем автора
        if author_user_id:
            try:
                await context.bot.send_message(
                    chat_id=author_user_id,
                    text="❌ Ваша заявка в TopPeople была отклонена модератором"
                )
            except:
                pass
        
        await query.answer("❌ Пост отклонен", show_alert=False)
        logger.info(f"Rating post {post_id} rejected")
        
    except Exception as e:
        logger.error(f"Error rejecting rating post: {e}")
        await query.answer(f"❌ Ошибка: {str(e)[:100]}", show_alert=True)

# ============= ГОЛОСОВАНИЕ =============

async def handle_vote(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int, vote_value: int):
    """Обработка голоса"""
    query = update.callback_query
    user_id = update.effective_user.id
    username = update.effective_user.username or f"ID_{user_id}"
    
    if post_id not in rating_data['posts']:
        await query.answer("❌ Пост не найден", show_alert=True)
        return
    
    post = rating_data['posts'][post_id]
    profile_url = post['profile_url']
    
    try:
        vote_key = (user_id, post_id)
        old_vote = rating_data['user_votes'].get(vote_key)
        
        rating_data['user_votes'][vote_key] = vote_value
        post['votes'][user_id] = vote_value
        
        if profile_url in rating_data['profiles']:
            profile = rating_data['profiles'][profile_url]
            
            total_score = sum(post['votes'].values())
            vote_count = len(post['votes'])
            
            profile['total_score'] = total_score
            profile['vote_count'] = vote_count
            
            logger.info(f"User {username} voted {vote_value} for post {post_id}")
        
        stats = get_post_stats(post_id)
        keyboard = [
            [
                InlineKeyboardButton(f"😭 -2 ({stats['-2']})", callback_data=f"rate:vote:{post_id}:-2"),
                InlineKeyboardButton(f"👎 -1 ({stats['-1']})", callback_data=f"rate:vote:{post_id}:-1"),
                InlineKeyboardButton(f"😐 0 ({stats['0']})", callback_data=f"rate:vote:{post_id}:0"),
                InlineKeyboardButton(f"👍 +1 ({stats['1']})", callback_data=f"rate:vote:{post_id}:1"),
                InlineKeyboardButton(f"🔥 +2 ({stats['2']})", callback_data=f"rate:vote:{post_id}:2"),
            ],
            [InlineKeyboardButton(f"⭐ Рейтинг: {profile['total_score']} | Голосов: {profile['vote_count']}", 
                                callback_data="rate:noop")]
        ]
        
        await context.bot.edit_message_reply_markup(
            chat_id=post['published_channel_id'],
            message_id=post['message_id'],
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        emoji_map = {-2: "😭", -1: "👎", 0: "😐", 1: "👍", 2: "🔥"}
        await query.answer(f"{emoji_map.get(vote_value, '?')} Ваш голос учтен!", show_alert=False)
        
    except Exception as e:
        logger.error(f"Error handling vote: {e}", exc_info=True)
        await query.answer(f"❌ Ошибка: {str(e)[:50]}", show_alert=True)

def get_post_stats(post_id: int) -> Dict[str, int]:
    """Получить статистику голосов"""
    if post_id not in rating_data['posts']:
        return {'-2': 0, '-1': 0, '0': 0, '1': 0, '2': 0}
    
    post = rating_data['posts'][post_id]
    stats = {'-2': 0, '-1': 0, '0': 0, '1': 0, '2': 0}
    
    for vote in post['votes'].values():
        stats[str(vote)] += 1
    
    return stats

# ============= КОМАНДЫ СТАТИСТИКИ =============

async def toppeople_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать топ-10 в Будапеште - /toppeople"""
    if not rating_data['profiles']:
        await update.message.reply_text("❌ Нет данных")
        return
    
    sorted_profiles = sorted(
        rating_data['profiles'].items(),
        key=lambda x: x[1]['total_score'],
        reverse=True
    )[:10]
    
    text = "⭐ **TOPinBUDAPEST**\n\n"
    
    for i, (profile_url, data) in enumerate(sorted_profiles, 1):
        gender_emoji = "🙋🏼‍♂️" if data['gender'] == 'boy' else "🙋🏼‍♀️"
        text += (
            f"{i}. {data.get('name', 'Имя')} ({profile_url})\n"
            f"   {gender_emoji} {data.get('age', '?')} лет\n"
            f"   ⭐ Рейтинг: {data['total_score']}\n"
            f"   📊 Голосов: {data['vote_count']}\n\n"
        )
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def topboys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Топ-10 мужчин - /topboys"""
    profiles = {url: data for url, data in rating_data['profiles'].items() if data['gender'] == 'boy'}
    
    if not profiles:
        await update.message.reply_text("❌ Нет данных")
        return
    
    sorted_profiles = sorted(profiles.items(), key=lambda x: x[1]['total_score'], reverse=True)[:10]
    
    text = "🕺 **TOP10 BOYS**\n\n"
    
    for i, (profile_url, data) in enumerate(sorted_profiles, 1):
        text += f"{i}. {data.get('name')} — ⭐ {data['total_score']} ({data['vote_count']} голосов)\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def topgirls_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """TOP10 девушек - /topgirls"""
    profiles = {url: data for url, data in rating_data['profiles'].items() if data['gender'] == 'girl'}
    
    if not profiles:
        await update.message.reply_text("❌ Нет данных")
        return
    
    sorted_profiles = sorted(profiles.items(), key=lambda x: x[1]['total_score'], reverse=True)[:10]
    
    text = "👱‍♀️ **ТОП10 GIRLS**\n\n"
    
    for i, (profile_url, data) in enumerate(sorted_profiles, 1):
        text += f"{i}. {data.get('name')} — 🌟 {data['total_score']} ({data['vote_count']} голосов)\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def toppeoplereset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбросить все очки - /toppeoplereset"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только админы")
        return
    
    keyboard = [
        [
            InlineKeyboardButton("✅ СБРОСИТЬ", callback_data="rate:reset:confirm"),
            InlineKeyboardButton("❌ Отмена", callback_data="rate:reset:cancel")
        ]
    ]
    
    text = (
        "⚠️ **ВНИМАНИЕ: ПОЛНЫЙ СБРОС РЕЙТИНГА**\n\n"
        "Это удалит все очки, голоса и историю\n\n"
        "Подтверждаете?"
    )
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ============= EXPORT =============

__all__ = [
    'itsme_command',
    'handle_rate_photo',
    'handle_rate_profile',
    'handle_rate_age',
    'handle_rate_name',
    'handle_rate_about',
    'handle_rate_callback',
    'handle_rate_moderation_callback',
    'handle_vote',
    'toppeople_command',
    'topboys_command',
    'topgirls_command',
    'toppeoplereset_command',
    'publish_rate_post',
    'send_rating_to_moderation',
    'approve_rating_post',
    'reject_rating_post',
    'get_post_stats',
    'rating_data'
]
