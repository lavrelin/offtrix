from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from services.cooldown import cooldown_service, CooldownType
from keyboards.rating_keyboards import (
    RATING_CALLBACKS,
    RATING_MOD_CALLBACKS,
    get_cancel_keyboard,
    get_back_keyboard,
    get_gender_keyboard,
    get_moderation_keyboard,
    get_voting_keyboard,
)
from datetime import datetime
import logging
import re
import random
from typing import Optional

logger = logging.getLogger(__name__)

COOLDOWN_HOURS = 24
MIN_AGE = 18
MAX_AGE = 70
MAX_ABOUT_WORDS = 3
MAX_WORD_LENGTH = 7

rating_data = {
    'posts': {},
    'profiles': {},
    'user_votes': {},
}

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
        r'(?:https?://)?(?:www\.)?instagram\.com/reel/([a-zA-Z0-9_-]+)',
    ]
    for pattern in instagram_patterns:
        match = re.search(pattern, url)
        if match:
            identifier = match.group(1)
            if '/p/' in url or '/reel/' in url:
                cleaned_url = f"https://instagram.com/{'p' if '/p/' in url else 'reel'}/{identifier}"
            else:
                cleaned_url = f"https://instagram.com/{identifier}"
            return True, cleaned_url
    return False, url

def validate_profile_url(url: str) -> Optional[str]:
    if not url or len(url) < 3:
        return None
    url = url.strip()
    if url.startswith('@'):
        username = url[1:]
        if re.match(r'^[a-zA-Z0-9_]{5,32}$', username):
            return f"@{username}"
        return None
    if 't.me/' in url:
        match = re.search(r't\.me/([a-zA-Z0-9_]{5,32})', url)
        if match:
            return f"@{match.group(1)}"
        return None
    is_valid, cleaned = validate_instagram_url(url)
    if is_valid:
        return cleaned
    if re.match(r'^[a-zA-Z0-9_]{3,}$', url):
        return f"@{url}"
    return None

async def check_vote_limit(user_id: int, post_id: int) -> bool:
    if user_id not in rating_data['user_votes']:
        return True
    return post_id not in rating_data['user_votes'][user_id]

async def generate_catalog_number() -> int:
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
    words = text.strip().split()
    if len(words) > MAX_ABOUT_WORDS:
        return f"❌ Максимум {MAX_ABOUT_WORDS} слова"
    for word in words:
        if len(word) > MAX_WORD_LENGTH:
            return f"❌ Слово '{word}' больше {MAX_WORD_LENGTH} символов"
    return None

async def itsme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    can_use, remaining = await cooldown_service.check_cooldown(
        user_id=user_id,
        command='itsme',
        duration=COOLDOWN_HOURS * 3600,
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
    await update.message.reply_text(
        "⭐ *TopPeople Budapest*\n\n"
        "🎯 Шаг 1/6: *Ваше имя*\n\n"
        "Как вас представить?\n"
        "Пример: Анна",
        reply_markup=get_cancel_keyboard(),
        parse_mode='Markdown'
    )

async def handle_rate_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 2 or len(name) > 50:
        await update.message.reply_text("❌ Имя: 2-50 символов")
        return
    context.user_data['rate_name'] = name
    context.user_data['rate_step'] = 'photo'
    context.user_data['waiting_for'] = 'rate_photo'
    safe_name = safe_markdown(name)
    await update.message.reply_text(
        f"✅ Имя: *{safe_name}*\n\n"
        f"🎯 Шаг 2/6: *Фото или видео*\n\n"
        f"Отправьте фото или короткое видео",
        reply_markup=get_back_keyboard(),
        parse_mode='Markdown'
    )

async def handle_rate_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('rate_step') != 'photo':
        return
    media_type = None
    media_file_id = None
    if update.message.photo:
        media_type = 'photo'
        media_file_id = update.message.photo[-1].file_id
    elif update.message.video:
        media_type = 'video'
        media_file_id = update.message.video.file_id
    else:
        await update.message.reply_text("❌ Отправьте фото или видео")
        return
    context.user_data['rate_media_type'] = media_type
    context.user_data['rate_media_file_id'] = media_file_id
    context.user_data['rate_step'] = 'profile'
    context.user_data['waiting_for'] = 'rate_profile'
    await update.message.reply_text(
        "✅ Медиа загружено\n\n"
        "🎯 Шаг 3/6: *Профиль*\n\n"
        "Ваш Instagram или Telegram профиль:",
        parse_mode='Markdown'
    )

async def handle_rate_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('rate_step') != 'profile':
        return
    profile = update.message.text.strip()
    validated = validate_profile_url(profile)
    if not validated:
        await update.message.reply_text("❌ Неверный формат\nПример: @username или instagram.com/username")
        return
    context.user_data['rate_profile'] = validated
    context.user_data['rate_step'] = 'age'
    context.user_data['waiting_for'] = 'rate_age'
    await update.message.reply_text(
        f"✅ Профиль: {validated}\n\n"
        f"🎯 Шаг 4/6: *Возраст*\n\n"
        f"Ваш возраст ({MIN_AGE}-{MAX_AGE}):",
        parse_mode='Markdown'
    )

async def handle_rate_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('rate_step') != 'age':
        return
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
    await update.message.reply_text(
        f"✅ Возраст: {age}\n\n"
        f"🎯 Шаг 5/6: *О себе*\n\n"
        f"Опишите себя ({MAX_ABOUT_WORDS} слова, макс {MAX_WORD_LENGTH} букв/слово):",
        parse_mode='Markdown'
    )

async def handle_rate_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('rate_step') != 'about':
        return
    about = update.message.text.strip()
    error = validate_about(about)
    if error:
        await update.message.reply_text(error)
        return
    context.user_data['rate_about'] = about
    context.user_data['rate_step'] = 'gender'
    await update.message.reply_text(
        f"✅ О себе: {about}\n\n"
        f"🎯 Шаг 6/6: *Пол*",
        reply_markup=get_gender_keyboard(),
        parse_mode='Markdown'
    )

async def publish_rate_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    name = context.user_data.get('rate_name')
    media_type = context.user_data.get('rate_media_type')
    media_file_id = context.user_data.get('rate_media_file_id')
    profile = context.user_data.get('rate_profile')
    age = context.user_data.get('rate_age')
    about = context.user_data.get('rate_about')
    gender = context.user_data.get('rate_gender')
    if not all([name, media_type, media_file_id, profile, age, about, gender]):
        await query.edit_message_text("❌ Ошибка: неполные данные")
        return
    post_id = len(rating_data['posts']) + 1
    catalog_number = await generate_catalog_number()
    post_data = {
        'post_id': post_id,
        'user_id': user_id,
        'name': name,
        'media_type': media_type,
        'media_file_id': media_file_id,
        'profile_url': profile,
        'age': age,
        'about': about,
        'gender': gender,
        'catalog_number': catalog_number,
        'votes': {},
        'status': 'pending',
        'created_at': datetime.utcnow()
    }
    rating_data['posts'][post_id] = post_data
    caption = (
        f"📋 Анкета #{post_id}\n\n"
        f"👤 {name}\n"
        f"🔗 {profile}\n"
        f"🎂 {age} лет\n"
        f"💭 {about}\n"
        f"👥 {'Девушка' if gender == 'girl' else 'Парень'}\n"
        f"📄 Номер: {catalog_number}"
    )
    try:
        if media_type == 'photo':
            mod_msg = await context.bot.send_photo(
                chat_id=Config.MODERATION_GROUP_ID,
                photo=media_file_id,
                caption=caption,
                reply_markup=get_moderation_keyboard(post_id)
            )
        else:
            mod_msg = await context.bot.send_video(
                chat_id=Config.MODERATION_GROUP_ID,
                video=media_file_id,
                caption=caption,
                reply_markup=get_moderation_keyboard(post_id)
            )
        post_data['moderation_message_id'] = mod_msg.message_id
        await cooldown_service.set_cooldown(
            user_id=user_id,
            command='itsme',
            duration=COOLDOWN_HOURS * 3600,
            cooldown_type=CooldownType.NORMAL
        )
        await query.edit_message_text(
            f"✅ Анкета отправлена на модерацию!\n\n"
            f"📄 Номер: {catalog_number}\n"
            f"⏳ Новая анкета через {COOLDOWN_HOURS}ч"
        )
        logger.info(f"Rating post {post_id} (#{catalog_number}) sent to moderation")
    except Exception as e:
        logger.error(f"Error sending to moderation: {e}")
        await query.edit_message_text(f"❌ Ошибка: {str(e)[:100]}")
    for key in ['rate_media_type', 'rate_media_file_id', 'rate_name', 'rate_profile', 
                'rate_age', 'rate_about', 'rate_gender', 'rate_step', 'waiting_for']:
        context.user_data.pop(key, None)

async def approve_rating_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    query = update.callback_query
    if post_id not in rating_data['posts']:
        await query.answer("❌ Пост не найден", show_alert=True)
        return
    post = rating_data['posts'][post_id]
    if post['status'] != 'pending':
        await query.answer("❌ Уже обработано", show_alert=True)
        return
    try:
        caption = (
            f"👤 {post['name']}\n"
            f"🔗 {post['profile_url']}\n"
            f"🎂 {post['age']} лет\n"
            f"💭 {post['about']}\n\n"
            f"📄 {post['catalog_number']}"
        )
        category = '👱🏻‍♀️ TopGirls' if post['gender'] == 'girl' else '🤵🏼‍♂️ TopBoys'
        target_channel = Config.CATALOG_CHANNEL_ID
        if post['media_type'] == 'photo':
            pub_msg = await context.bot.send_photo(
                chat_id=target_channel,
                photo=post['media_file_id'],
                caption=caption,
                reply_markup=get_voting_keyboard(post_id)
            )
        else:
            pub_msg = await context.bot.send_video(
                chat_id=target_channel,
                video=post['media_file_id'],
                caption=caption,
                reply_markup=get_voting_keyboard(post_id)
            )
        post['status'] = 'approved'
        post['published_message_id'] = pub_msg.message_id
        post['published_link'] = f"https://t.me/c/{str(target_channel)[4:]}/{pub_msg.message_id}"
        if post['profile_url'] not in rating_data['profiles']:
            rating_data['profiles'][post['profile_url']] = {
                'name': post['name'],
                'age': post['age'],
                'gender': post['gender'],
                'post_ids': [],
                'total_score': 0,
                'vote_count': 0
            }
        rating_data['profiles'][post['profile_url']]['post_ids'].append(post_id)
        from services.catalog_service import catalog_service
        await catalog_service.add_post(
            user_id=post['user_id'],
            catalog_link=post['published_link'],
            category=category,
            name=f"{post['name']} ({post['age']})",
            tags=[post['about'], category],
            media_type=post['media_type'],
            media_file_id=post['media_file_id'],
            author_username=post['profile_url'],
            author_id=post['user_id']
        )
        await query.edit_message_caption(
            caption=f"{caption}\n\n✅ Одобрено\n🔗 {post['published_link']}"
        )
        await query.answer("✅ Опубликовано", show_alert=False)
        logger.info(f"Rating post {post_id} approved")
    except Exception as e:
        logger.error(f"Error approving: {e}")
        await query.answer(f"❌ Ошибка: {str(e)[:100]}", show_alert=True)

async def reject_rating_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    query = update.callback_query
    if post_id not in rating_data['posts']:
        await query.answer("❌ Пост не найден", show_alert=True)
        return
    post = rating_data['posts'][post_id]
    if post['status'] != 'pending':
        await query.answer("❌ Уже обработано", show_alert=True)
        return
    try:
        post['status'] = 'rejected'
        await query.edit_message_caption(caption=query.message.caption + "\n\n❌ Отклонено")
        try:
            await context.bot.send_message(
                chat_id=post['user_id'],
                text="❌ Ваша анкета не прошла модерацию\nПопробуйте снова через 24ч"
            )
        except:
            pass
        await query.answer("❌ Отклонено", show_alert=False)
        logger.info(f"Rating post {post_id} rejected")
    except Exception as e:
        logger.error(f"Error rejecting: {e}")
        await query.answer(f"❌ Ошибка: {str(e)[:100]}", show_alert=True)

async def handle_vote(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int, vote_value: int):
    query = update.callback_query
    user_id = update.effective_user.id
    can_vote = await check_vote_limit(user_id, post_id)
    if not can_vote:
        await query.answer("❌ Вы уже оценили этот пост", show_alert=True)
        return
    if post_id not in rating_data['posts']:
        await query.answer("❌ Пост не найден", show_alert=True)
        return
    post = rating_data['posts'][post_id]
    if user_id not in rating_data['user_votes']:
        rating_data['user_votes'][user_id] = {}
    rating_data['user_votes'][user_id][post_id] = vote_value
    if 'votes' not in post:
        post['votes'] = {}
    post['votes'][user_id] = vote_value
    profile_url = post.get('profile_url')
    if profile_url and profile_url in rating_data['profiles']:
        profile = rating_data['profiles'][profile_url]
        all_votes = []
        for pid in profile.get('post_ids', []):
            if pid in rating_data['posts']:
                all_votes.extend(rating_data['posts'][pid].get('votes', {}).values())
        profile['total_score'] = sum(all_votes)
        profile['vote_count'] = len(all_votes)
    votes = post.get('votes', {})
    vote_counts = {-2: 0, -1: 0, 0: 0, 1: 0, 2: 0}
    for v in votes.values():
        if v in vote_counts:
            vote_counts[v] += 1
    total_score = sum(votes.values())
    vote_count = len(votes)
    try:
        await query.edit_message_reply_markup(
            reply_markup=get_voting_keyboard(post_id, vote_counts, total_score, vote_count)
        )
        await query.answer(f"✅ Ваша оценка: {vote_value:+d}", show_alert=False)
        logger.info(f"User {user_id} voted {vote_value} on post {post_id}")
    except Exception as e:
        logger.error(f"Error updating vote buttons: {e}")
        await query.answer("✅ Голос учтён", show_alert=False)

async def handle_rate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data_parts = query.data.split(":")
    if data_parts[0].startswith('rh_'):
        action = data_parts[0][3:]
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
        pass

async def handle_rate_moderation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data_parts = query.data.split(":")
    if data_parts[0].startswith('rhm_'):
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

async def toppeople_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
