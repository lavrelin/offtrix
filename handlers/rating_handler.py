# -*- coding: utf-8 -*-
"""
Система рейтинга с опросами
Голоса конвертируются в очки и агрегируются по профилю и полу
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from datetime import datetime
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ============= ХРАНИЛИЩЕ ДАННЫХ =============

rating_data = {
    'posts': {},
    'profiles': {},
    'user_votes': {}
}

# ============= ОСНОВНЫЕ КОМАНДЫ =============

async def itsme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать процесс публикации фото с опросом - /itsme"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("🤣 Только админы могут создавать опросы")
        return
    
    context.user_data['rate_step'] = 'photo'
    keyboard = [[InlineKeyboardButton("🚗 Отмена", callback_data="rate:cancel")]]
    
    text = (
        "**❤️ TopPeople Budapest — время заявить о себе**\n\n"
        "Добавь фото, чтобы попасть в ленту лучших и привлечь внимание 🔥\n\n"
        "Покажи себя и подними активность своего 🌀аккаунта."
    )
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    context.user_data['waiting_for'] = 'rate_photo'

async def handle_rate_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка фото для опроса"""
    if not update.message.photo:
        await update.message.reply_text("👻 Отправьте фотографию")
        return
    
    context.user_data['rate_photo_file_id'] = update.message.photo[-1].file_id
    context.user_data['rate_step'] = 'profile'
    context.user_data['waiting_for'] = 'rate_profile'
    
    keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="rate:back")]]
    
    text = (
        "✅ Фото добавлено\n\n"
        "💁🏻 Следующий шаг\n\n"
        "• Отправьте ссылку на профиль или username\n"
        "Пример: 🌀username или https://instagram.com/username"
    )
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_rate_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка профиля"""
    profile_url = update.message.text.strip()
    
    if not profile_url or len(profile_url) < 3:
        await update.message.reply_text("🚔 Неверный формат ссылки")
        return
    
    if profile_url.startswith('@'):
        profile_url = profile_url[1:]
    elif not profile_url.startswith('http'):
        profile_url = f"@{profile_url}"
    
    context.user_data['rate_profile'] = profile_url
    context.user_data['rate_step'] = 'gender'
    context.user_data['waiting_for'] = None
    
    keyboard = [
        [
            InlineKeyboardButton("🦸‍♂️ Boy", callback_data="rate:gender:boy"),
            InlineKeyboardButton("🦸‍♀️ Girl", callback_data="rate:gender:girl")
        ],
        [
            InlineKeyboardButton("❓ Непонятно", callback_data="rate:gender:unknown"),
            InlineKeyboardButton("↩️ Назад", callback_data="rate:back")
        ]
    ]
    
    text = (
        "🪪 Profile: " + profile_url + "\n\n"
        "Укажите пол\n\n"
        "🙋🏼‍♂️ Man? /🙋🏼‍♀️ Girl? "
    )
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

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
        step = context.user_data.get('rate_step', 'photo')
        if step == 'profile':
            context.user_data['rate_step'] = 'photo'
            context.user_data['waiting_for'] = 'rate_photo'
            keyboard = [[InlineKeyboardButton("🚗 Отмена", callback_data="rate:cancel")]]
            await query.edit_message_text(
                "🧑🏼‍💻 Добавьте своё лучшее фото",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        elif step == 'gender':
            context.user_data['rate_step'] = 'profile'
            context.user_data['waiting_for'] = 'rate_profile'
            keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="rate:back")]]
            await query.edit_message_text(
                "🔗 Отправьте ссылку на профиль",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    elif action == "cancel":
        context.user_data.pop('rate_photo_file_id', None)
        context.user_data.pop('rate_profile', None)
        context.user_data.pop('rate_gender', None)
        context.user_data.pop('rate_step', None)
        context.user_data.pop('waiting_for', None)
        
        await query.edit_message_text("❌ Отменено")

async def publish_rate_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить пост на модерацию"""
    photo_file_id = context.user_data.get('rate_photo_file_id')
    profile_url = context.user_data.get('rate_profile')
    gender = context.user_data.get('rate_gender')
    
    if not all([photo_file_id, profile_url, gender]):
        await update.callback_query.edit_message_text("❌ Ошибка: не хватает данных")
        return
    
    try:
        post_id = len(rating_data['posts']) + 1
        
        rating_data['posts'][post_id] = {
            'profile_url': profile_url,
            'gender': gender,
            'photo_file_id': photo_file_id,
            'created_at': datetime.now(),
            'votes': {},
            'status': 'pending'
        }
        
        if profile_url not in rating_data['profiles']:
            rating_data['profiles'][profile_url] = {
                'gender': gender,
                'total_score': 0,
                'vote_count': 0,
                'post_ids': []
            }
        
        rating_data['profiles'][profile_url]['post_ids'].append(post_id)
        
        logger.info(f"Rating post {post_id} created for {profile_url}, sending to moderation")
        
        await send_rating_to_moderation(update, context, post_id, photo_file_id, profile_url, gender)
        
        context.user_data.pop('rate_photo_file_id', None)
        context.user_data.pop('rate_profile', None)
        context.user_data.pop('rate_gender', None)
        context.user_data.pop('rate_step', None)
        
        await update.callback_query.edit_message_text(
            f"✅ **Пост отправлен!**\n\n"
            f"🪪 Аккаунт: {profile_url}\n"
            f"👩🏻‍🤝‍👨🏼 Пол: {gender.upper()}\n"
            f"#️⃣ Post iD: {post_id}\n\n"
            f"🙄 Проверка...",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error preparing rate post: {e}")
        await update.callback_query.edit_message_text(f"❌ Ошибка при подготовке: {e}")

async def send_rating_to_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                     post_id: int, photo_file_id: str, 
                                     profile_url: str, gender: str):
    """Отправить пост на модерацию"""
    bot = context.bot
    
    try:
        keyboard = [
            [
                InlineKeyboardButton("✅ Опубликовать в 🛜SocialMedia 🍭People in Budapest", callback_data=f"rate_mod:approve:{post_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"rate_mod:reject:{post_id}")
            ]
        ]
        
        caption = (
            f"🚨 **🆕 заявка от ⭐️TopPeople**\n\n"
            f"🪪 Профиль: {profile_url}\n"
            f"👩‍❤️‍👨 Пол: {gender.upper()}\n"
            f"📇 Post ID: {post_id}\n"
            f"🗓️ Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"❓ Ваше действие:"
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
        logger.error(f"Error sending rating post to moderation: {e}")
        raise

async def handle_rate_moderation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle moderation callbacks for rating posts"""
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

async def approve_rating_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Одобрить и опубликовать пост"""
    query = update.callback_query
    
    if post_id not in rating_data['posts']:
        await query.answer("❌ Пост не найден", show_alert=True)
        return
    
    post = rating_data['posts'][post_id]
    profile_url = post['profile_url']
    gender = post['gender']
    photo_file_id = post['photo_file_id']
    
    try:
        BUDAPEST_PEOPLE_ID = -1003114019170
        
        keyboard = [
            [
                InlineKeyboardButton("😭 -2 (0)", callback_data=f"rate:vote:{post_id}:-2"),
                InlineKeyboardButton("👎 -1 (0)", callback_data=f"rate:vote:{post_id}:-1"),
                InlineKeyboardButton("😐 0 (0)", callback_data=f"rate:vote:{post_id}:0"),
                InlineKeyboardButton("👍 +1 (0)", callback_data=f"rate:vote:{post_id}:1"),
                InlineKeyboardButton("🔥 +2 (0)", callback_data=f"rate:vote:{post_id}:2"),
            ],
            [InlineKeyboardButton(f"⭐️ Score: 0 | Votes: 0", callback_data="rate:noop")]
        ]
        
        caption = f"👍 Оценка 👎 {profile_url}\n\n👫 Gender: {gender.upper()}\n\n👩🏻‍⚖️ Выберите оценку"
        
        msg = await context.bot.send_photo(
            chat_id=BUDAPEST_PEOPLE_ID,
            photo=photo_file_id,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        post['message_id'] = msg.message_id
        post['published_channel_id'] = BUDAPEST_PEOPLE_ID
        post['status'] = 'published'
        
        await query.edit_message_reply_markup(reply_markup=None)
        
        new_caption = (
            f"{query.message.caption}\n\n"
            f"✅ **ОДОБРЕНО И ОПУБЛИКОВАНО**\n"
            f"В 🏆 Top Budapest / Взаимные❤️💬➡️ / Люди Будапешт"
        )
        
        await query.edit_message_caption(
            caption=new_caption,
            parse_mode='Markdown'
        )
        
        await query.answer("🛜 SocialMedia 🦹🏻People in Budapest 🇭🇺", show_alert=False)
        logger.info(f"Rating post {post_id} approved and published")
        
    except Exception as e:
        logger.error(f"Error approving rating post: {e}", exc_info=True)
        await query.answer(f"❌ Ошибка: {e}", show_alert=True)

async def reject_rating_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Отклонить пост"""
    query = update.callback_query
    
    if post_id not in rating_data['posts']:
        await query.answer("❌ Пост не найден", show_alert=True)
        return
    
    try:
        if post_id in rating_data['posts']:
            del rating_data['posts'][post_id]
        
        await query.edit_message_reply_markup(reply_markup=None)
        
        new_caption = (
            f"{query.message.caption}\n\n"
            f"❌ **ОТКЛОНЕНО**"
        )
        
        await query.edit_message_caption(
            caption=new_caption,
            parse_mode='Markdown'
        )
        
        await query.answer("❌ Пост отклонен и удален", show_alert=False)
        logger.info(f"Rating post {post_id} rejected")
        
    except Exception as e:
        logger.error(f"Error rejecting rating post: {e}")
        await query.answer(f"❌ Ошибка: {e}", show_alert=True)

async def handle_vote(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int, vote_value: int):
    """ГЛАВНАЯ ФУНКЦИЯ - Обработка голоса"""
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
        
        # Сохраняем новый голос
        rating_data['user_votes'][vote_key] = vote_value
        post['votes'][user_id] = vote_value
        
        # Пересчитываем очки для профиля
        if profile_url in rating_data['profiles']:
            profile = rating_data['profiles'][profile_url]
            
            total_score = sum(post['votes'].values())
            vote_count = len(post['votes'])
            
            profile['total_score'] = total_score
            profile['vote_count'] = vote_count
            
            logger.info(f"User {username} voted {vote_value} for post {post_id}")
        
        # Обновляем кнопки с новыми числами
        stats = get_post_stats(post_id)
        keyboard = [
            [
                InlineKeyboardButton(f"😭 -2 ({stats['-2']})", callback_data=f"rate:vote:{post_id}:-2"),
                InlineKeyboardButton(f"👎 -1 ({stats['-1']})", callback_data=f"rate:vote:{post_id}:-1"),
                InlineKeyboardButton(f"😐 0 ({stats['0']})", callback_data=f"rate:vote:{post_id}:0"),
                InlineKeyboardButton(f"👍 +1 ({stats['1']})", callback_data=f"rate:vote:{post_id}:1"),
                InlineKeyboardButton(f"🔥 +2 ({stats['2']})", callback_data=f"rate:vote:{post_id}:2"),
            ],
            [InlineKeyboardButton(f"⭐️ Score: {profile['total_score']} | Votes: {profile['vote_count']}", 
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
        await query.answer(f"❌ Ошибка: {e}", show_alert=True)

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
    
    text = "⭐️ **TOPinBUDAPEST**\n\n"
    
    for i, (profile_url, data) in enumerate(sorted_profiles, 1):
        text += (
            f"{i}. **{profile_url}**\n"
            f"   ⭐️ Рейтинг: {data['total_score']}\n"
            f"   👩🏻‍⚖️ Оценок: {data['vote_count']}\n"
            f"   👩🏼‍🤝‍👨🏻 Пол: {data['gender'].upper()}\n\n"
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
        text += f"{i}. {profile_url} — ⭐️ {data['total_score']} ({data['vote_count']} голосов)\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def topgirls_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """TOP10💃 - /topgirls"""
    profiles = {url: data for url, data in rating_data['profiles'].items() if data['gender'] == 'girl'}
    
    if not profiles:
        await update.message.reply_text("❌ Нет данных")
        return
    
    sorted_profiles = sorted(profiles.items(), key=lambda x: x[1]['total_score'], reverse=True)[:10]
    
    text = "👱‍♀️ **ТОП10 GIRLS**\n\n"
    
    for i, (profile_url, data) in enumerate(sorted_profiles, 1):
        text += f"{i}. {profile_url} — 🌟 {data['total_score']} ({data['vote_count']} голосов)\n"
    
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

__all__ = [
    'itsme_command',
    'handle_rate_photo',
    'handle_rate_profile',
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
