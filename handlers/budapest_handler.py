# -*- coding: utf-8 -*-
"""
Budapest Post Handler - НОВЫЙ
Prefix: bp_ (budapest post)

Функционал:
- Анонимные посты
- Посты с username
- Поддержка текста + медиа (фото/видео)
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from services.db import db
from services.cooldown import cooldown_service
from services.filter_service import FilterService
from models import User, Post, PostStatus
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

# ============= UNIQUE CALLBACK PREFIX: bp_ =============
BP_CALLBACKS = {
    'anon': 'bp_anon',               # Anonymous post
    'user': 'bp_user',               # Post with username
    'preview': 'bp_prev',            # Show preview
    'send': 'bp_send',               # Send to moderation
    'edit': 'bp_edit',               # Edit text
    'add_media': 'bp_media',         # Add media
    'cancel': 'bp_cancel',           # Cancel
    'back': 'bp_back',               # Back to menu
}

async def handle_budapest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unified budapest callback handler"""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    logger.info(f"Budapest action: {action}")
    
    handlers = {
        BP_CALLBACKS['anon']: start_anonymous_post,
        BP_CALLBACKS['user']: start_username_post,
        BP_CALLBACKS['preview']: show_budapest_preview,
        BP_CALLBACKS['send']: send_budapest_to_moderation,
        BP_CALLBACKS['edit']: edit_budapest_text,
        BP_CALLBACKS['add_media']: request_budapest_media,
        BP_CALLBACKS['cancel']: cancel_budapest,
        BP_CALLBACKS['back']: show_budapest_preview,
    }
    
    handler = handlers.get(action)
    if handler:
        await handler(update, context)
    else:
        await query.answer("⚠️  Неизвестное действие", show_alert=True)

async def start_anonymous_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start anonymous budapest post"""
    context.user_data['budapest_post'] = {
        'anonymous': True,
        'category': '📢 Будапешт',
        'text': None,
        'media': []
    }
    context.user_data['waiting_for'] = 'budapest_text'
    
    keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data=BP_CALLBACKS['cancel'])]]
    
    text = (
        "📩 **Анонимный пост в Будапешт**\n\n"
        "✍️ Напишите текст поста и/или отправьте фото/видео\n\n"
        "💡 Ваш username не будет виден в публикации"
    )
    
    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def start_username_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start post with username"""
    context.user_data['budapest_post'] = {
        'anonymous': False,
        'category': '📢 Будапешт',
        'text': None,
        'media': []
    }
    context.user_data['waiting_for'] = 'budapest_text'
    
    username = update.effective_user.username
    keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data=BP_CALLBACKS['cancel'])]]
    
    text = (
        f"💬 **Пост с упоминанием @{username}**\n\n"
        "✍️ Напишите текст поста и/или отправьте фото/видео\n\n"
        "💡 В публикации будет указан ваш username"
    )
    
    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_budapest_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text input for budapest post"""
    if context.user_data.get('waiting_for') != 'budapest_text':
        return
    
    text = update.message.text or update.message.caption
    
    if not text and not update.message.photo and not update.message.video:
        await update.message.reply_text("❌ Отправьте текст или медиа")
        return
    
    # Проверка на запрещенные ссылки
    filter_service = FilterService()
    if text and filter_service.contains_banned_link(text):
        if not Config.is_moderator(update.effective_user.id):
            await update.message.reply_text("🚫 Обнаружена запрещенная ссылка!")
            return
    
    if 'budapest_post' not in context.user_data:
        context.user_data['budapest_post'] = {
            'anonymous': True,
            'category': '📢 Будапешт',
            'text': None,
            'media': []
        }
    
    # Сохраняем текст
    if text:
        context.user_data['budapest_post']['text'] = text
    
    # Сохраняем медиа
    if update.message.photo:
        context.user_data['budapest_post']['media'].append({
            'type': 'photo',
            'file_id': update.message.photo[-1].file_id
        })
    elif update.message.video:
        context.user_data['budapest_post']['media'].append({
            'type': 'video',
            'file_id': update.message.video.file_id
        })
    
    context.user_data['waiting_for'] = None
    
    keyboard = [
        [
            InlineKeyboardButton("📸 Добавить медиа", callback_data=BP_CALLBACKS['add_media']),
            InlineKeyboardButton("👁️ Предпросмотр", callback_data=BP_CALLBACKS['preview'])
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data=BP_CALLBACKS['cancel'])]
    ]
    
    await update.message.reply_text(
        "✅ Сохранено!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_budapest_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle media input for budapest post"""
    if context.user_data.get('waiting_for') != 'budapest_media':
        return
    
    if 'budapest_post' not in context.user_data:
        return
    
    # Добавляем медиа
    if update.message.photo:
        context.user_data['budapest_post']['media'].append({
            'type': 'photo',
            'file_id': update.message.photo[-1].file_id
        })
    elif update.message.video:
        context.user_data['budapest_post']['media'].append({
            'type': 'video',
            'file_id': update.message.video.file_id
        })
    else:
        return
    
    media_count = len(context.user_data['budapest_post']['media'])
    
    keyboard = [
        [
            InlineKeyboardButton(f"➕ Ещё (всего {media_count})", callback_data=BP_CALLBACKS['add_media']),
            InlineKeyboardButton("👁️ Предпросмотр", callback_data=BP_CALLBACKS['preview'])
        ]
    ]
    
    await update.message.reply_text(
        f"✅ Медиа добавлено ({media_count} шт.)",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_budapest_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show preview of budapest post"""
    if 'budapest_post' not in context.user_data:
        await update.callback_query.edit_message_text("❌ Данные не найдены")
        return
    
    post_data = context.user_data['budapest_post']
    
    # Формируем превью
    text = post_data.get('text', '(без текста)')
    anonymous = post_data.get('anonymous', True)
    media = post_data.get('media', [])
    
    preview_text = f"📢 **Предпросмотр поста**\n\n"
    preview_text += f"{'📩 Анонимно' if anonymous else f'💬 От @{update.effective_user.username}'}\n\n"
    preview_text += f"📝 Текст:\n{text}\n\n"
    preview_text += f"📸 Медиа: {len(media)} шт.\n\n"
    preview_text += "#Будапешт @snghu"
    
    keyboard = [
        [
            InlineKeyboardButton("📨 Отправить на модерацию", callback_data=BP_CALLBACKS['send']),
            InlineKeyboardButton("✏️ Изменить", callback_data=BP_CALLBACKS['edit'])
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data=BP_CALLBACKS['cancel'])]
    ]
    
    try:
        await update.callback_query.delete_message()
    except:
        pass
    
    # Показываем медиа
    if media:
        for i, item in enumerate(media[:5]):
            try:
                caption = f"📸 Медиа {i+1}/{len(media)}" if i == 0 else None
                if item['type'] == 'photo':
                    await update.effective_message.reply_photo(item['file_id'], caption=caption)
                elif item['type'] == 'video':
                    await update.effective_message.reply_video(item['file_id'], caption=caption)
            except Exception as e:
                logger.error(f"Error showing media: {e}")
    
    # Показываем текст с кнопками
    await update.effective_message.reply_text(
        preview_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def send_budapest_to_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send budapest post to moderation"""
    user_id = update.effective_user.id
    post_data = context.user_data.get('budapest_post')
    
    if not post_data:
        await update.callback_query.edit_message_text("❌ Данные не найдены")
        return
    
    try:
        if not db.session_maker:
            await update.callback_query.edit_message_text("❌ БД недоступна")
            return
        
        async with db.get_session() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            
            if not user:
                await update.callback_query.edit_message_text("❌ Пользователь не найден. /start")
                return
            
            # Проверка кулдауна
            can_post, remaining = await cooldown_service.check_cooldown(
                user_id, 'budapest_post', Config.COOLDOWN_SECONDS
            )
            
            if not can_post and not Config.is_moderator(user_id):
                minutes = remaining // 60
                await update.callback_query.edit_message_text(
                    f"⏳ Следующий пост через {minutes} минут"
                )
                return
            
            # Создаём пост
            post = Post(
                user_id=int(user_id),
                category='📢 Будапешт',
                subcategory=None,
                text=str(post_data.get('text', ''))[:4096],
                media=list(post_data.get('media', [])),
                hashtags=['#Будапешт'],
                anonymous=bool(post_data.get('anonymous', True)),
                status=PostStatus.PENDING,
                is_piar=False
            )
            session.add(post)
            await session.flush()
            await session.commit()
            await session.refresh(post)
            
            # Отправляем в группу модерации
            await send_to_mod_group(update, context, post, user, post_data)
            
            # Обновляем кулдаун
            await cooldown_service.set_cooldown(user_id, 'budapest_post', Config.COOLDOWN_SECONDS)
            
            # Очищаем данные
            context.user_data.pop('budapest_post', None)
            context.user_data.pop('waiting_for', None)
            
            await update.callback_query.edit_message_text(
                "✅ **Пост отправлен на модерацию!**\n\n"
                "⏰ Ожидайте уведомление о публикации"
            )
            
    except Exception as e:
        logger.error(f"Error sending budapest post: {e}", exc_info=True)
        await update.callback_query.edit_message_text("❌ Ошибка отправки")

async def send_to_mod_group(update: Update, context: ContextTypes.DEFAULT_TYPE,
                            post: Post, user: User, post_data: dict):
    """Send to moderation group"""
    bot = context.bot
    username = user.username or f"ID_{user.id}"
    anonymous = post_data.get('anonymous', True)
    
    mod_text = (
        f"📢 **НОВЫЙ ПОСТ - БУДАПЕШТ**\n\n"
        f"👤 От: @{username} (ID: {user.id})\n"
        f"{'📩 Анонимно' if anonymous else '💬 С упоминанием'}\n\n"
        f"📝 Текст:\n{post.text[:300]}"
    )
    
    if len(post.text) > 300:
        mod_text += "..."
    
    if post.media:
        mod_text += f"\n\n📸 Медиа: {len(post.media)} шт."
    
    keyboard = [[
        InlineKeyboardButton("✅ Опубликовать", callback_data=f"mod_app:{post.id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"mod_rej:{post.id}")
    ]]
    
    try:
        # Отправляем медиа
        if post.media:
            for item in post.media[:3]:
                if item['type'] == 'photo':
                    await bot.send_photo(Config.MODERATION_GROUP_ID, item['file_id'])
                elif item['type'] == 'video':
                    await bot.send_video(Config.MODERATION_GROUP_ID, item['file_id'])
        
        # Отправляем текст с кнопками
        await bot.send_message(
            Config.MODERATION_GROUP_ID,
            mod_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error sending to mod group: {e}")

async def request_budapest_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request more media"""
    context.user_data['waiting_for'] = 'budapest_media'
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=BP_CALLBACKS['preview'])]]
    
    await update.callback_query.edit_message_text(
        "📸 Отправьте фото или видео:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def edit_budapest_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit budapest text"""
    context.user_data['waiting_for'] = 'budapest_text'
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=BP_CALLBACKS['preview'])]]
    
    await update.callback_query.edit_message_text(
        "✏️ Отправьте новый текст:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cancel_budapest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel budapest post"""
    context.user_data.pop('budapest_post', None)
    context.user_data.pop('waiting_for', None)
    
    from handlers.menu_handler_new import show_write_menu
    await show_write_menu(update, context)

# Export
__all__ = [
    'handle_budapest_callback',
    'handle_budapest_text',
    'handle_budapest_media',
    'BP_CALLBACKS'
]
