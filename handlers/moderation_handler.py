# -*- coding: utf-8 -*-
"""
Moderation Handler v6.0 - SIMPLIFIED
Prefix: mod_ (уникальный для модерации)
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from services.db import db
from models import Post, PostStatus
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

# ============= УНИКАЛЬНЫЕ CALLBACK ПРЕФИКСЫ: mod_ =============
MOD_CALLBACKS = {
    'approve': 'mod_approve',    # Одобрить (формат: mod_approve:post_id)
    'reject': 'mod_reject',      # Отклонить (формат: mod_reject:post_id)
}

async def handle_moderation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unified moderation callback handler"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    # Проверка прав
    if not Config.is_moderator(user_id):
        await query.answer("❌ Нет прав", show_alert=True)
        return
    
    await query.answer()
    
    # Парсим callback: mod_approve:123
    parts = query.data.split(":")
    action = parts[0]
    post_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
    
    if not post_id:
        await query.edit_message_text("❌ ID поста не указан")
        return
    
    if action == MOD_CALLBACKS['approve']:
        await start_approve(update, context, post_id)
    elif action == MOD_CALLBACKS['reject']:
        await start_reject(update, context, post_id)

# ============= ОДОБРЕНИЕ =============

async def start_approve(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Начать процесс одобрения"""
    try:
        async with db.get_session() as session:
            result = await session.execute(select(Post).where(Post.id == post_id))
            post = result.scalar_one_or_none()
            
            if not post:
                await update.callback_query.answer("❌ Пост не найден", show_alert=True)
                return
            
            # Сохраняем данные для ожидания ссылки
            context.user_data.update({
                'mod_post_id': post_id,
                'mod_user_id': post.user_id,
                'mod_waiting_for': 'approve_link'
            })
        
        # Убираем кнопки
        try:
            await update.callback_query.edit_message_reply_markup(reply_markup=None)
        except:
            pass
        
        # Инструкция модератору
        instruction = (
            f"✅ **ОДОБРЕНИЕ ПОСТА #{post_id}**\n\n"
            f"📎 Отправьте ссылку на опубликованный пост:\n"
            f"Пример: `https://t.me/snghu/1234`"
        )
        
        await update.callback_query.message.reply_text(
            instruction,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Approve error: {e}", exc_info=True)

# ============= ОТКЛОНЕНИЕ =============

async def start_reject(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Начать процесс отклонения"""
    try:
        async with db.get_session() as session:
            result = await session.execute(select(Post).where(Post.id == post_id))
            post = result.scalar_one_or_none()
            
            if not post:
                await update.callback_query.answer("❌ Пост не найден", show_alert=True)
                return
            
            # Сохраняем данные для ожидания причины
            context.user_data.update({
                'mod_post_id': post_id,
                'mod_user_id': post.user_id,
                'mod_waiting_for': 'reject_reason'
            })
        
        # Убираем кнопки
        try:
            await update.callback_query.edit_message_reply_markup(reply_markup=None)
        except:
            pass
        
        # Инструкция модератору
        instruction = (
            f"❌ **ОТКЛОНЕНИЕ ПОСТА #{post_id}**\n\n"
            f"📝 Напишите причину отклонения:"
        )
        
        await update.callback_query.message.reply_text(instruction)
        
    except Exception as e:
        logger.error(f"Reject error: {e}", exc_info=True)

# ============= ОБРАБОТКА ТЕКСТА ОТ МОДЕРАТОРА =============

async def handle_moderation_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текста от модератора"""
    waiting = context.user_data.get('mod_waiting_for')
    
    if waiting == 'approve_link':
        await process_approve_link(update, context)
        return True
    elif waiting == 'reject_reason':
        await process_reject_reason(update, context)
        return True
    
    return False

# ============= ОБРАБОТКА ОДОБРЕНИЯ =============

async def process_approve_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработать ссылку при одобрении"""
    try:
        link = update.message.text.strip()
        post_id = context.user_data.get('mod_post_id')
        user_id = context.user_data.get('mod_user_id')
        
        # Проверка формата ссылки
        if not link.startswith('https://t.me/'):
            await update.message.reply_text(
                "❌ Неверный формат ссылки\n"
                "Формат: `https://t.me/channelname/123`",
                parse_mode='Markdown'
            )
            return
        
        # Обновляем статус в БД
        async with db.get_session() as session:
            result = await session.execute(select(Post).where(Post.id == post_id))
            post = result.scalar_one_or_none()
            
            if post:
                post.status = PostStatus.APPROVED
                await session.commit()
        
        # Уведомляем пользователя
        keyboard = [[InlineKeyboardButton("📺 Перейти к посту", url=link)]]
        
        await context.bot.send_message(
            user_id,
            f"✅ **Ваш пост одобрен!**\n\n"
            f"📝 Пост опубликован в канале\n\n"
            f"🔗 {link}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        # Подтверждение модератору
        await update.message.reply_text(
            f"✅ **ПОСТ #{post_id} ОДОБРЕН**\n"
            f"Пользователь ID {user_id} уведомлен"
        )
        
        # Очищаем данные
        for key in ['mod_post_id', 'mod_user_id', 'mod_waiting_for']:
            context.user_data.pop(key, None)
        
    except Exception as e:
        logger.error(f"Approve process error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {str(e)[:200]}")

# ============= ОБРАБОТКА ОТКЛОНЕНИЯ =============

async def process_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработать причину при отклонении"""
    try:
        reason = update.message.text.strip()
        post_id = context.user_data.get('mod_post_id')
        user_id = context.user_data.get('mod_user_id')
        
        # Проверка длины причины
        if len(reason) < 5:
            await update.message.reply_text(
                "❌ Причина слишком короткая (минимум 5 символов)"
            )
            return
        
        # Обновляем статус в БД
        async with db.get_session() as session:
            result = await session.execute(select(Post).where(Post.id == post_id))
            post = result.scalar_one_or_none()
            
            if post:
                post.status = PostStatus.REJECTED
                await session.commit()
        
        # Уведомляем пользователя
        await context.bot.send_message(
            user_id,
            f"❌ **Ваш пост отклонен**\n\n"
            f"📝 Причина:\n{reason}\n\n"
            f"💡 Вы можете создать новую публикацию\n\n"
            f"/start"
        )
        
        # Подтверждение модератору
        await update.message.reply_text(
            f"❌ **ПОСТ #{post_id} ОТКЛОНЕН**\n"
            f"Пользователь ID {user_id} уведомлен\n"
            f"Причина: {reason}"
        )
        
        # Очищаем данные
        for key in ['mod_post_id', 'mod_user_id', 'mod_waiting_for']:
            context.user_data.pop(key, None)
        
    except Exception as e:
        logger.error(f"Reject process error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {str(e)[:200]}")

__all__ = [
    'handle_moderation_callback',
    'handle_moderation_text',
    'MOD_CALLBACKS'
]
