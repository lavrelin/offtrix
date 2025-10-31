# -*- coding: utf-8 -*-
"""
Publication Handler v6.0 - SIMPLIFIED
Prefix: post_ (уникальный для публикаций)
Обрабатывает: Посты в Будапешт и Барахолку
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

# ============= УНИКАЛЬНЫЕ CALLBACK ПРЕФИКСЫ: post_ =============
POST_CALLBACKS = {
    'preview': 'post_preview',          # Предпросмотр
    'send': 'post_send',                # Отправить на модерацию
    'edit': 'post_edit',                # Редактировать
    'cancel': 'post_cancel',            # Отменить
    'add_media': 'post_add_media',      # Добавить медиа
}

async def handle_post_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unified post callback handler"""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    logger.info(f"Post action: {action}")
    
    handlers = {
        POST_CALLBACKS['preview']: show_post_preview,
        POST_CALLBACKS['send']: send_post_to_moderation,
        POST_CALLBACKS['edit']: edit_post_text,
        POST_CALLBACKS['cancel']: cancel_post,
        POST_CALLBACKS['add_media']: request_post_media,
    }
    
    handler = handlers.get(action)
    if handler:
        await handler(update, context)
    else:
        await query.answer("⚠️ Неизвестная команда", show_alert=True)

# ============= ОБРАБОТКА ТЕКСТА =============

async def handle_post_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текста для всех типов постов"""
    waiting_for = context.user_data.get('waiting_for')
    
    # Проверяем что это пост (budapest или baraholka)
    if waiting_for not in ['budapest_text', 'baraholka_text']:
        return False
    
    # Получаем текст
    text = update.message.text or update.message.caption
    if not text:
        return False
    
    # Проверка на запрещенные ссылки
    filter_service = FilterService()
    if filter_service.contains_banned_link(text) and not Config.is_moderator(update.effective_user.id):
        await update.message.reply_text("🚫 Обнаружена запрещенная ссылка!")
        return True
    
    if 'post_data' not in context.user_data:
        await update.message.reply_text("🤔 Данные потерялись. /start")
        return True
    
    # Сохраняем текст
    context.user_data['post_data']['text'] = text
    context.user_data['post_data']['media'] = []
    
    # Если есть медиа с текстом
    if update.message.photo:
        context.user_data['post_data']['media'].append({
            'type': 'photo',
            'file_id': update.message.photo[-1].file_id
        })
    elif update.message.video:
        context.user_data['post_data']['media'].append({
            'type': 'video',
            'file_id': update.message.video.file_id
        })
    
    keyboard = [
        [
            InlineKeyboardButton("📸 Добавить медиа", callback_data=POST_CALLBACKS['add_media']),
            InlineKeyboardButton("👁️ Предпросмотр", callback_data=POST_CALLBACKS['preview'])
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data=POST_CALLBACKS['cancel'])]
    ]
    
    await update.message.reply_text(
        "✅ Текст сохранен!\n\nМожете добавить медиа или посмотреть предпросмотр",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    context.user_data['waiting_for'] = None
    return True

# ============= ОБРАБОТКА МЕДИА =============

async def handle_post_media_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка медиа для постов"""
    if 'post_data' not in context.user_data:
        return False
    
    post_type = context.user_data['post_data'].get('type')
    if post_type not in ['budapest', 'baraholka']:
        return False
    
    if 'media' not in context.user_data['post_data']:
        context.user_data['post_data']['media'] = []
    
    media_added = False
    
    if update.message.photo:
        context.user_data['post_data']['media'].append({
            'type': 'photo',
            'file_id': update.message.photo[-1].file_id
        })
        media_added = True
    elif update.message.video:
        context.user_data['post_data']['media'].append({
            'type': 'video',
            'file_id': update.message.video.file_id
        })
        media_added = True
    elif update.message.document:
        context.user_data['post_data']['media'].append({
            'type': 'document',
            'file_id': update.message.document.file_id
        })
        media_added = True
    
    if media_added:
        total = len(context.user_data['post_data']['media'])
        keyboard = [
            [
                InlineKeyboardButton("➕ Еще медиа", callback_data=POST_CALLBACKS['add_media']),
                InlineKeyboardButton("👁️ Предпросмотр", callback_data=POST_CALLBACKS['preview'])
            ]
        ]
        
        await update.message.reply_text(
            f"✅ Медиа добавлено! (всего: {total})",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return True
    
    return False

# ============= ПРЕДПРОСМОТР =============

async def show_post_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать предпросмотр поста"""
    if 'post_data' not in context.user_data:
        await update.callback_query.edit_message_text("❌ Данные не найдены")
        return
    
    post_data = context.user_data['post_data']
    post_type = post_data.get('type', 'budapest')
    
    # Формируем текст
    text = post_data.get('text', '')
    
    # Добавляем хештеги
    if post_type == 'budapest':
        hashtags = "#Будапешт"
        if post_data.get('anonymous'):
            text += f"\n\n{hashtags}"
        else:
            username = update.effective_user.username or "Пользователь"
            text += f"\n\n{hashtags}\n📝 @{username}"
    elif post_type == 'baraholka':
        section = post_data.get('subcategory', '')
        username = update.effective_user.username or "Пользователь"
        text += f"\n\n#Барахолка #{section}\n📝 @{username}"
    
    text += f"\n\n{Config.DEFAULT_SIGNATURE}"
    
    # Кнопки
    keyboard = [
        [
            InlineKeyboardButton("✅ Отправить", callback_data=POST_CALLBACKS['send']),
            InlineKeyboardButton("✏️ Изменить", callback_data=POST_CALLBACKS['edit'])
        ],
        [InlineKeyboardButton("❌ Отменить", callback_data=POST_CALLBACKS['cancel'])]
    ]
    
    try:
        await update.callback_query.delete_message()
    except:
        pass
    
    # Показываем медиа
    media = post_data.get('media', [])
    if media:
        for i, item in enumerate(media[:5]):
            try:
                caption = f"📎 Медиа ({len(media)} шт.)" if i == 0 else None
                if item['type'] == 'photo':
                    await update.effective_message.reply_photo(
                        photo=item['file_id'], 
                        caption=caption
                    )
                elif item['type'] == 'video':
                    await update.effective_message.reply_video(
                        video=item['file_id'], 
                        caption=caption
                    )
            except Exception as e:
                logger.error(f"Error showing media: {e}")
    
    # Показываем текст с кнопками
    await update.effective_message.reply_text(
        f"👁️ **Предпросмотр:**\n\n{text}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============= ОТПРАВКА НА МОДЕРАЦИЮ =============

async def send_post_to_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить пост на модерацию"""
    user_id = update.effective_user.id
    post_data = context.user_data.get('post_data')
    
    if not post_data:
        await update.callback_query.edit_message_text("❌ Данные не найдены")
        return
    
    try:
        if not db.session_maker:
            await update.callback_query.edit_message_text("❌ БД недоступна")
            return
        
        async with db.get_session() as session:
            # Получаем пользователя
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            
            if not user:
                await update.callback_query.edit_message_text("❌ Пользователь не найден. /start")
                return
            
            # Проверяем cooldown
            can_post, remaining = await cooldown_service.check_cooldown(
                user_id, 'post', Config.COOLDOWN_SECONDS
            )
            
            if not can_post and not Config.is_moderator(user_id):
                hours = remaining // 3600
                minutes = (remaining % 3600) // 60
                await update.callback_query.edit_message_text(
                    f"⏳ Следующий пост можно создать через {hours}ч {minutes}м"
                )
                return
            
            # Создаем пост
            post = Post(
                user_id=int(user_id),
                category=str(post_data.get('category', ''))[:255],
                subcategory=str(post_data.get('subcategory', ''))[:255] if post_data.get('subcategory') else None,
                text=str(post_data.get('text', ''))[:4096],
                hashtags=[], 
                anonymous=bool(post_data.get('anonymous', False)),
                media=list(post_data.get('media', [])),
                status=PostStatus.PENDING,
                is_piar=False
            )
            session.add(post)
            await session.flush()
            await session.commit()
            await session.refresh(post)
            
            # Отправляем в модерацию
            await send_to_mod_group(update, context, post, user, post_data)
            
            # Устанавливаем cooldown
            await cooldown_service.set_cooldown(user_id, 'post', Config.COOLDOWN_SECONDS)
            
            # Очищаем данные
            context.user_data.pop('post_data', None)
            context.user_data.pop('waiting_for', None)
            
            await update.callback_query.edit_message_text(
                "✅ **Пост отправлен на модерацию!**\n\n"
                "После проверки вы получите уведомление с ссылкой на публикацию."
            )
            
    except Exception as e:
        logger.error(f"Error sending post: {e}", exc_info=True)
        await update.callback_query.edit_message_text("❌ Ошибка при отправке")

async def send_to_mod_group(update: Update, context: ContextTypes.DEFAULT_TYPE,
                            post: Post, user: User, post_data: dict):
    """Отправить в группу модерации"""
    bot = context.bot
    username = user.username or f"ID_{user.id}"
    
    post_type = post_data.get('type', 'budapest')
    anonymous = post_data.get('anonymous', False)
    
    # Формируем сообщение для модераторов
    mod_text = f"📝 **НОВЫЙ ПОСТ**\n\n"
    
    if post_type == 'budapest':
        mod_text += f"📍 Канал: Будапешт\n"
        mod_text += f"👤 От: @{username} (ID: {user.id})\n"
        mod_text += f"🎭 Тип: {'Анонимно' if anonymous else 'С username'}\n\n"
    elif post_type == 'baraholka':
        section = post_data.get('subcategory', '')
        mod_text += f"📍 Канал: Барахолка - {section}\n"
        mod_text += f"👤 От: @{username} (ID: {user.id})\n\n"
    
    mod_text += f"📝 Текст:\n{post.text[:500]}"
    if len(post.text) > 500:
        mod_text += "..."
    
    if post.media:
        mod_text += f"\n\n📎 Медиа: {len(post.media)} файл(ов)"
    
    # Кнопки модерации
    keyboard = [[
        InlineKeyboardButton("✅ Одобрить", callback_data=f"mod_approve:{post.id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"mod_reject:{post.id}")
    ]]
    
    try:
        # Отправляем медиа
        if post.media:
            for item in post.media[:3]:
                try:
                    if item['type'] == 'photo':
                        await bot.send_photo(Config.MODERATION_GROUP_ID, item['file_id'])
                    elif item['type'] == 'video':
                        await bot.send_video(Config.MODERATION_GROUP_ID, item['file_id'])
                except Exception as e:
                    logger.error(f"Error sending media to mod: {e}")
        
        # Отправляем текст с кнопками
        await bot.send_message(
            Config.MODERATION_GROUP_ID,
            mod_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        logger.info(f"Post {post.id} sent to moderation")
        
    except Exception as e:
        logger.error(f"Error sending to mod group: {e}")

# ============= ДОПОЛНИТЕЛЬНЫЕ ДЕЙСТВИЯ =============

async def request_post_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запросить добавление медиа"""
    context.user_data['waiting_for'] = 'post_media'
    keyboard = [[InlineKeyboardButton("🔙 Предпросмотр", callback_data=POST_CALLBACKS['preview'])]]
    await update.callback_query.edit_message_text(
        "📸 Отправьте фото, видео или документ:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def edit_post_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Редактировать текст поста"""
    post_type = context.user_data.get('post_data', {}).get('type', 'budapest')
    
    if post_type == 'budapest':
        context.user_data['waiting_for'] = 'budapest_text'
    elif post_type == 'baraholka':
        context.user_data['waiting_for'] = 'baraholka_text'
    
    keyboard = [[InlineKeyboardButton("🔙 Предпросмотр", callback_data=POST_CALLBACKS['preview'])]]
    await update.callback_query.edit_message_text(
        "✏️ Напишите новый текст:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cancel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменить создание поста"""
    context.user_data.pop('post_data', None)
    context.user_data.pop('waiting_for', None)
    
    from handlers.start_handler import show_main_menu
    await show_main_menu(update, context)

__all__ = [
    'handle_post_callback', 
    'handle_post_text_input', 
    'handle_post_media_input',
    'POST_CALLBACKS'
]
