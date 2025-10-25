# -*- coding: utf-8 -*-
"""
Rating Handler (TopPeople) - OPTIMIZED v5.2
- Уникальные префиксы: rtc_ (rating), rmc_ (moderation)
- Сокращенные функции
- 6-шаговая анкета
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

# ============= CALLBACK PREFIXES =============
RATING_CALLBACKS = {
    'gender': 'rtc_gender',
    'vote': 'rtc_vote',
    'back': 'rtc_back',
    'cancel': 'rtc_cancel',
    'noop': 'rtc_noop',
}

RATING_MOD_CALLBACKS = {
    'edit': 'rmc_edit',
    'approve': 'rmc_approve',
    'reject': 'rmc_reject',
    'back': 'rmc_back',
}

# ============= SETTINGS =============
COOLDOWN_HOURS = 3
MIN_AGE = 18
MAX_AGE = 70
MAX_ABOUT_WORDS = 3
MAX_WORD_LENGTH = 7

# ============= DATA STORAGE =============
rating_data = {
    'posts': {},
    'profiles': {},
    'user_votes': {},
    'cooldowns': {}
}

# ============= HELPER FUNCTIONS =============

async def check_cooldown(user_id: int) -> Optional[str]:
    """Check cooldown"""
    if user_id in rating_data['cooldowns']:
        last = rating_data['cooldowns'][user_id]
        passed = datetime.now() - last
        cooldown = timedelta(hours=COOLDOWN_HOURS)
        
        if passed < cooldown:
            remaining = cooldown - passed
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            return f"⏳ Подождите {hours}ч {minutes}мин"
    
    return None

async def generate_catalog_number() -> int:
    """Generate unique catalog number"""
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
    """Validate 'About' field"""
    words = text.strip().split()
    
    if len(words) > MAX_ABOUT_WORDS:
        return f"❌ Максимум {MAX_ABOUT_WORDS} слова"
    
    for word in words:
        if len(word) > MAX_WORD_LENGTH:
            return f"❌ Слово '{word}' больше {MAX_WORD_LENGTH} символов"
    
    return None

# ============= MAIN COMMAND =============

async def itsme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start TopPeople submission - /itsme"""
    user_id = update.effective_user.id
    
    cooldown_msg = await check_cooldown(user_id)
    if cooldown_msg:
        await update.message.reply_text(cooldown_msg)
        return
    
    context.user_data['rate_step'] = 'name'
    context.user_data['waiting_for'] = 'rate_name'
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=RATING_CALLBACKS['cancel'])]]
    
    await update.message.reply_text(
        "**⭐ TopPeople Budapest**\n\n"
        "🎯 Шаг 1/6: **Ваше имя**\n\n"
        "Как вас представить?\n"
        "Пример: Анна",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============= STEP HANDLERS =============

async def handle_rate_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle name"""
    name = update.message.text.strip()
    
    if len(name) < 2 or len(name) > 50:
        await update.message.reply_text("❌ Имя: 2-50 символов")
        return
    
    context.user_data['rate_name'] = name
    context.user_data['rate_step'] = 'photo'
    context.user_data['waiting_for'] = 'rate_photo'
    
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data=RATING_CALLBACKS['back'])]]
    
    await update.message.reply_text(
        f"✅ Имя: **{name}**\n\n🎯 Шаг 2/6: **Фото**\n\nОтправьте фото",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_rate_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo"""
    if not update.message.photo:
        await update.message.reply_text("❌ Отправьте фото")
        return
    
    context.user_data['rate_photo_file_id'] = update.message.photo[-1].file_id
    context.user_data['rate_step'] = 'age'
    context.user_data['waiting_for'] = 'rate_age'
    
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data=RATING_CALLBACKS['back'])]]
    
    await update.message.reply_text(
        f"✅ Фото добавлено\n\n🎯 Шаг 3/6: **Возраст**\n\nВозраст ({MIN_AGE}-{MAX_AGE})",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_rate_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle age"""
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
        f"✅ Возраст: **{age} лет**\n\n"
        f"🎯 Шаг 4/6: **О себе**\n\n"
        f"Опишите себя ({MAX_ABOUT_WORDS} слова, макс. {MAX_WORD_LENGTH} символов)\n"
        f"Пример: красотка модель инстаграм",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_rate_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle about"""
    about = update.message.text.strip()
    
    error = validate_about(about)
    if error:
        await update.message.reply_text(error)
        return
    
    context.user_data['rate_about'] = about
    context.user_data['rate_step'] = 'profile'
    context.user_data['waiting_for'] = 'rate_profile'
    
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data=RATING_CALLBACKS['back'])]]
    
    await update.message.reply_text(
        f"✅ О себе: **{about}**\n\n"
        f"🎯 Шаг 5/6: **Ссылка**\n\n"
        f"Ссылка на профиль\n"
        f"Пример: @username или instagram.com/username",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_rate_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle profile link"""
    profile_url = update.message.text.strip()
    
    if not profile_url or len(profile_url) < 3:
        await update.message.reply_text("❌ Неверная ссылка")
        return
    
    # Format link
    if profile_url.startswith('@'):
        profile_url = profile_url[1:]
    
    if 'instagram.com' not in profile_url and not profile_url.startswith('http'):
        profile_url = f"@{profile_url}"
    
    context.user_data['rate_profile'] = profile_url
    context.user_data['rate_step'] = 'gender'
    context.user_data['waiting_for'] = None
    
    keyboard = [
        [
            InlineKeyboardButton("🙋🏼‍♂️ Парень", callback_data=f"{RATING_CALLBACKS['gender']}:boy"),
            InlineKeyboardButton("🙋🏼‍♀️ Девушка", callback_data=f"{RATING_CALLBACKS['gender']}:girl")
        ],
        [InlineKeyboardButton("⬅️ Назад", callback_data=RATING_CALLBACKS['back'])]
    ]
    
    await update.message.reply_text(
        f"✅ Профиль: {profile_url}\n\n🎯 Шаг 6/6: **Пол**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============= PUBLISH =============

async def publish_rate_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Publish to moderation"""
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
        post_id = len(rating_data['posts']) + 1
        catalog_number = await generate_catalog_number()
        
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
        
        rating_data['cooldowns'][user_id] = datetime.now()
        
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
            update, context, post_id, photo_file_id,
            name, profile_url, age, about, gender, username, catalog_number
        )
        
        # Clear data
        for key in ['rate_photo_file_id', 'rate_name', 'rate_profile', 'rate_age', 'rate_about', 'rate_gender', 'rate_step', 'waiting_for']:
            context.user_data.pop(key, None)
        
        gender_emoji = "🙋🏼‍♂️" if gender == "boy" else "🙋🏼‍♀️"
        
        await update.callback_query.edit_message_text(
            f"✅ **Заявка отправлена!**\n\n"
            f"👤 {name}\n"
            f"{gender_emoji} {age} лет\n"
            f"💬 {about}\n"
            f"🆔 #{catalog_number}\n\n"
            f"⏳ Ожидайте проверки",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error publishing: {e}", exc_info=True)
        await update.callback_query.edit_message_text(f"❌ Ошибка: {str(e)[:100]}")

async def send_rating_to_moderation(
    update, context, post_id, photo_file_id,
    name, profile_url, age, about, gender, author_username, catalog_number
):
    """Send to moderation"""
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
        
        if profile_url.startswith('@'):
            formatted_name = f"[{name}](https://t.me/{profile_url[1:]})"
        elif 'instagram.com' in profile_url:
            formatted_name = f"[{name}]({profile_url})"
        else:
            formatted_name = f"[{name}]({profile_url})"
        
        caption = (
            f"🆕 **Новая заявка TopPeople**\n\n"
            f"👤 {formatted_name}\n"
            f"{gender_emoji} {gender_text}, {age} лет\n"
            f"💬 {about}\n"
            f"🆔 #{catalog_number}\n"
            f"📤 @{author_username}\n\n"
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
        
        logger.info(f"Rating post {post_id} sent to moderation")
        
    except Exception as e:
        logger.error(f"Error sending to moderation: {e}", exc_info=True)
        raise

# ============= MODERATION =============

async def approve_rating_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Approve and publish"""
    query = update.callback_query
    
    if post_id not in rating_data['posts']:
        await query.answer("❌ Пост не найден", show_alert=True)
        return
    
    post = rating_data['posts'][post_id]
    
    try:
        BUDAPEST_PEOPLE_ID = Config.STATS_CHANNELS.get('budapest_people', -1003088023508)
        
        gender_text = "Парень" if post['gender'] == "boy" else "Девушка"
        profile_url = post['profile_url']
        
        if profile_url.startswith('@'):
            formatted_name = f"[{post['name']}](https://t.me/{profile_url[1:]})"
        elif 'instagram.com' in profile_url:
            formatted_name = f"[{post['name']}]({profile_url})"
        else:
            formatted_name = f"[{post['name']}]({profile_url})"
        
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
        
        caption = (
            f"⭐ **TopPeople Budapest**\n\n"
            f"👤 {formatted_name}\n"
            f"{gender_text}, {post['age']} лет\n"
            f"💬 {post['about']}\n\n"
            f"🆔 #{post['catalog_number']}\n\n"
            f"Оцените участника:"
        )
        
        msg = await context.bot.send_photo(
            chat_id=BUDAPEST_PEOPLE_ID,
            photo=post['photo_file_id'],
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        post['message_id'] = msg.message_id
        post['published_channel_id'] = BUDAPEST_PEOPLE_ID
        post['status'] = 'published'
        post['published_link'] = f"https://t.me/c/{str(BUDAPEST_PEOPLE_ID)[4:]}/{msg.message_id}"
        
        # Add to catalog
        from services.catalog_service import catalog_service
        
        category = '👱🏻‍♀️ TopGirls' if post['gender'] == 'girl' else '🤵🏼‍♂️ TopBoys'
        
        catalog_post_id = await catalog_service.add_post(
            user_id=post['author_user_id'],
            catalog_link=post['published_link'],
            category=category,
            name=post['name'],
            tags=[post['about'], gender_text, f"{post['age']}"],
            media_type='photo',
            media_file_id=post['photo_file_id'],
            media_group_id=None,
            media_json=[post['photo_file_id']],
            author_username=post.get('author_username'),
            author_id=post['author_user_id']
        )
        
        if catalog_post_id:
            from services.db import db
            from models import CatalogPost
            from sqlalchemy import update
            
            async with db.get_session() as session:
                await session.execute(
                    update(CatalogPost)
                    .where(CatalogPost.id == catalog_post_id)
                    .values(catalog_number=post['catalog_number'])
                )
                await session.commit()
        
        await query.edit_message_reply_markup(reply_markup=None)
        await query.edit_message_caption(
            caption=f"{query.message.caption}\n\n✅ **ОПУБЛИКОВАНО**",
            parse_mode='Markdown'
        )
        
        # Notify author
        try:
            await context.bot.send_message(
                chat_id=post['author_user_id'],
                text=(
                    f"🎉 **Ваша заявка одобрена!**\n\n"
                    f"👤 {post['name']}\n"
                    f"🆔 #{post['catalog_number']}\n\n"
                    f"🔗 Ваш пост: {post['published_link']}\n\n"
                    f"✅ Теперь вы в TopPeople!"
                ),
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.warning(f"Could not notify author: {e}")
        
        await query.answer("✅ Опубликовано", show_alert=False)
        logger.info(f"Rating post {post_id} approved")
        
    except Exception as e:
        logger.error(f"Error approving: {e}", exc_info=True)
        await query.answer(f"❌ Ошибка: {str(e)[:100]}", show_alert=True)

async def reject_rating_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Reject post"""
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
            caption=f"{query.message.caption}\n\n❌ **ОТКЛОНЕНО**",
            parse_mode='Markdown'
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

# ============= CALLBACKS =============

async def handle_rate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle rating callbacks"""
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split(":")
    
    if data_parts[0].startswith('rtc_'):
        action = data_parts[0][4:]
    else:
        action = data_parts[0]
    
    if action == 'gender':
        value = data_parts[1] if len(data_parts) > 1 else None
        context.user_data['rate_gender'] = value
        await publish_rate_post(update, context)
    
    elif action == 'cancel':
        for key in ['rate_photo_file_id', 'rate_name', 'rate_profile', 'rate_age', 'rate_about', 'rate_gender', 'rate_step', 'waiting_for']:
            context.user_data.pop(key, None)
        await query.edit_message_text("❌ Заявка отменена")

async def handle_rate_moderation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle moderation callbacks"""
    query = update.callback_query
    
    data_parts = query.data.split(":")
    
    if data_parts[0].startswith('rmc_'):
        action = data_parts[0][4:]
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
    """Top-10 in Budapest"""
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
            f"{i}. {data.get('name')} ({profile_url})\n"
            f"   {gender_emoji} {data.get('age')} лет\n"
            f"   ⭐ {data['total_score']} | 📊 {data['vote_count']}\n\n"
        )
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def topboys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Top-10 boys"""
    profiles = {url: data for url, data in rating_data['profiles'].items() if data['gender'] == 'boy'}
    
    if not profiles:
        await update.message.reply_text("❌ Нет данных")
        return
    
    sorted_profiles = sorted(profiles.items(), key=lambda x: x[1]['total_score'], reverse=True)[:10]
    
    text = "🕺 **TOP10 BOYS**\n\n"
    
    for i, (url, data) in enumerate(sorted_profiles, 1):
        text += f"{i}. {data.get('name')} — ⭐ {data['total_score']} ({data['vote_count']})\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def topgirls_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Top-10 girls"""
    profiles = {url: data for url, data in rating_data['profiles'].items() if data['gender'] == 'girl'}
    
    if not profiles:
        await update.message.reply_text("❌ Нет данных")
        return
    
    sorted_profiles = sorted(profiles.items(), key=lambda x: x[1]['total_score'], reverse=True)[:10]
    
    text = "👱‍♀️ **TOP10 GIRLS**\n\n"
    
    for i, (url, data) in enumerate(sorted_profiles, 1):
        text += f"{i}. {data.get('name')} — 🌟 {data['total_score']} ({data['vote_count']})\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def toppeoplereset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset all ratings - admin only"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только админы")
        return
    
    await update.message.reply_text(
        "⚠️ **ВНИМАНИЕ: ПОЛНЫЙ СБРОС РЕЙТИНГА**\n\n"
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
