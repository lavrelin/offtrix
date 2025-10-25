# -*- coding: utf-8 -*-
"""
Optimized Moderation Handler
Prefix: mdc_ (moderation callback)
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from data.user_data import *
from utils.validators import parse_time
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# ============= CALLBACK PREFIX: mdc_ =============
MOD_CALLBACKS = {
    'approve': 'mdc_ap',      # Approve to channel
    'approve_chat': 'mdc_ac',  # Approve to chat
    'reject': 'mdc_rj'        # Reject
}

async def handle_moderation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unified moderation callback handler"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not Config.is_moderator(user_id):
        await query.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    await query.answer()
    
    parts = query.data.split(":")
    action = parts[0]
    post_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
    
    if not post_id:
        await query.edit_message_text("❌ ID поста не указан")
        return
    
    handlers = {
        MOD_CALLBACKS['approve']: lambda: start_approve(update, context, post_id, False),
        MOD_CALLBACKS['approve_chat']: lambda: start_approve(update, context, post_id, True),
        MOD_CALLBACKS['reject']: lambda: start_reject(update, context, post_id)
    }
    
    handler = handlers.get(action)
    if handler:
        await handler()

async def start_approve(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int, chat: bool):
    """Start approval"""
    try:
        from services.db import db
        from models import Post
        from sqlalchemy import select
        
        async with db.get_session() as session:
            result = await session.execute(select(Post).where(Post.id == post_id))
            post = result.scalar_one_or_none()
            
            if not post:
                await update.callback_query.answer("❌ Пост не найден", show_alert=True)
                return
            
            context.user_data.update({
                'mod_post_id': post_id,
                'mod_post_user_id': post.user_id,
                'mod_waiting_for': 'approve_link',
                'mod_is_chat': chat
            })
        
        try:
            await update.callback_query.edit_message_reply_markup(reply_markup=None)
        except:
            pass
        
        dest = "чате (закрепить)" if chat else "канале"
        instruction = (
            f"✅ ОДОБРЕНИЕ\n\n"
            f"📊 Post: {post_id}\n"
            f"📍 В: {dest}\n\n"
            f"📎 Отправьте ссылку:\n"
            f"https://t.me/snghu/1234"
        )
        
        await context.bot.send_message(update.effective_user.id, instruction)
        
    except Exception as e:
        logger.error(f"Approve error: {e}", exc_info=True)

async def start_reject(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Start rejection"""
    try:
        from services.db import db
        from models import Post
        from sqlalchemy import select
        
        async with db.get_session() as session:
            result = await session.execute(select(Post).where(Post.id == post_id))
            post = result.scalar_one_or_none()
            
            if not post:
                await update.callback_query.answer("❌ Пост не найден", show_alert=True)
                return
            
            context.user_data.update({
                'mod_post_id': post_id,
                'mod_post_user_id': post.user_id,
                'mod_waiting_for': 'reject_reason'
            })
        
        try:
            await update.callback_query.edit_message_reply_markup(reply_markup=None)
        except:
            pass
        
        instruction = (
            f"❌ ОТКЛОНЕНИЕ\n\n"
            f"📊 Post: {post_id}\n\n"
            f"📝 Напишите причину:"
        )
        
        await context.bot.send_message(update.effective_user.id, instruction)
        
    except Exception as e:
        logger.error(f"Reject error: {e}", exc_info=True)

async def handle_moderation_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle moderator text input"""
    waiting = context.user_data.get('mod_waiting_for')
    
    if waiting == 'approve_link':
        await process_approve_link(update, context)
    elif waiting == 'reject_reason':
        await process_reject_reason(update, context)

async def process_approve_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process approval with link"""
    try:
        link = update.message.text.strip()
        post_id = context.user_data.get('mod_post_id')
        user_id = context.user_data.get('mod_post_user_id')
        is_chat = context.user_data.get('mod_is_chat', False)
        
        if not link.startswith('https://t.me/'):
            await update.message.reply_text("❌ Неверный формат ссылки")
            return
        
        # Update status
        from services.db import db
        from models import Post, PostStatus
        from sqlalchemy import select
        
        async with db.get_session() as session:
            result = await session.execute(select(Post).where(Post.id == post_id))
            post = result.scalar_one_or_none()
            
            if post:
                post.status = PostStatus.APPROVED
                await session.commit()
        
        # Notify user
        dest = "чате" if is_chat else "канале"
        keyboard = [[InlineKeyboardButton("📺 Перейти", url=link)]]
        
        await context.bot.send_message(
            user_id,
            f"✅ Заявка одобрена!\n\n📝 Пост в {dest}\n\n🔗 {link}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        await update.message.reply_text(f"✅ ОДОБРЕНО\nПользователь уведомлён")
        
        # Clear context
        for key in ['mod_post_id', 'mod_post_user_id', 'mod_waiting_for', 'mod_is_chat']:
            context.user_data.pop(key, None)
        
    except Exception as e:
        logger.error(f"Approve process error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {str(e)[:200]}")

async def process_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process rejection with reason"""
    try:
        reason = update.message.text.strip()
        post_id = context.user_data.get('mod_post_id')
        user_id = context.user_data.get('mod_post_user_id')
        
        if len(reason) < 5:
            await update.message.reply_text("❌ Причина слишком короткая (мин. 5)")
            return
        
        # Update status
        from services.db import db
        from models import Post, PostStatus
        from sqlalchemy import select
        
        async with db.get_session() as session:
            result = await session.execute(select(Post).where(Post.id == post_id))
            post = result.scalar_one_or_none()
            
            if post:
                post.status = PostStatus.REJECTED
                await session.commit()
        
        # Notify user
        await context.bot.send_message(
            user_id,
            f"❌ Заявка отклонена\n\n📝 Причина:\n{reason}\n\n💡 Создайте новую заявку\n\n/start"
        )
        
        await update.message.reply_text(f"❌ ОТКЛОНЕНО\nПользователь уведомлён")
        
        # Clear context
        for key in ['mod_post_id', 'mod_post_user_id', 'mod_waiting_for']:
            context.user_data.pop(key, None)
        
    except Exception as e:
        logger.error(f"Reject process error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {str(e)[:200]}")

# ============= MODERATION COMMANDS =============

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban user"""
    if not Config.is_moderator(update.effective_user.id):
        return
    
    if not context.args:
        await update.message.reply_text("📝 /ban @username причина")
        return
    
    username = context.args[0].lstrip('@')
    reason = ' '.join(context.args[1:]) or "Не указана"
    
    user_data = get_user_by_username(username)
    if not user_data:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    ban_user(user_data['id'], reason)
    await update.message.reply_text(f"✅ @{username} забанен")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban user"""
    if not Config.is_moderator(update.effective_user.id):
        return
    
    if not context.args:
        await update.message.reply_text("📝 /unban @username")
        return
    
    username = context.args[0].lstrip('@')
    user_data = get_user_by_username(username)
    
    if user_data:
        unban_user(user_data['id'])
        await update.message.reply_text(f"✅ @{username} разбанен")

async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mute user"""
    if not Config.is_moderator(update.effective_user.id):
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("📝 /mute @username 10m")
        return
    
    username = context.args[0].lstrip('@')
    seconds = parse_time(context.args[1])
    
    if not seconds:
        await update.message.reply_text("❌ Неверный формат времени")
        return
    
    user_data = get_user_by_username(username)
    if user_data:
        until = datetime.now() + timedelta(seconds=seconds)
        mute_user(user_data['id'], until)
        await update.message.reply_text(f"✅ @{username} замучен на {context.args[1]}")

async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unmute user"""
    if not Config.is_moderator(update.effective_user.id):
        return
    
    if not context.args:
        await update.message.reply_text("📝 /unmute @username")
        return
    
    username = context.args[0].lstrip('@')
    user_data = get_user_by_username(username)
    
    if user_data:
        unmute_user(user_data['id'])
        await update.message.reply_text(f"✅ @{username} размучен")

async def banlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show banned users"""
    if not Config.is_moderator(update.effective_user.id):
        return
    
    banned = get_banned_users()
    
    if not banned:
        await update.message.reply_text("📋 Нет забаненных")
        return
    
    text = f"🚫 Забанено: {len(banned)}\n\n"
    for user in banned[:20]:
        text += f"• @{user['username']} - {user.get('ban_reason', 'Не указана')}\n"
    
    await update.message.reply_text(text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show stats"""
    if not Config.is_moderator(update.effective_user.id):
        return
    
    stats = get_user_stats()
    
    text = (
        f"📊 СТАТИСТИКА\n\n"
        f"👥 Пользователей: {stats['total_users']}\n"
        f"🟢 Активных 24ч: {stats['active_24h']}\n"
        f"💬 Сообщений: {stats['total_messages']}\n"
        f"🚫 Забанено: {stats['banned_count']}"
    )
    
    await update.message.reply_text(text)

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top users"""
    if not Config.is_moderator(update.effective_user.id):
        return
    
    limit = 10
    if context.args and context.args[0].isdigit():
        limit = int(context.args[0])
    
    top_users = get_top_users(limit)
    
    text = f"🏆 ТОП {limit}\n\n"
    for i, user in enumerate(top_users, 1):
        text += f"{i}. @{user['username']} - {user['message_count']}\n"
    
    await update.message.reply_text(text)

async def lastseen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show last seen"""
    if not Config.is_moderator(update.effective_user.id):
        return
    
    if not context.args:
        await update.message.reply_text("📝 /lastseen @username")
        return
    
    username = context.args[0].lstrip('@')
    user_data = get_user_by_username(username)
    
    if user_data:
        last = user_data['last_activity'].strftime('%d.%m.%Y %H:%M')
        await update.message.reply_text(f"⏰ @{username}\n{last}")

__all__ = [
    'handle_moderation_callback', 'handle_moderation_text',
    'ban_command', 'unban_command', 'mute_command', 'unmute_command',
    'banlist_command', 'stats_command', 'top_command', 'lastseen_command',
    'MOD_CALLBACKS'
]
