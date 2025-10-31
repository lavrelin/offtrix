# -*- coding: utf-8 -*-
"""
Baraholka Handler - НОВЫЙ
Prefix: bar_ (baraholka)

Разделы:
- 💰 Продам
- 🔎 Куплю
- 🎁 Отдам
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

# ============= UNIQUE CALLBACK PREFIX: bar_ =============
BAR_CALLBACKS = {
    'sell': 'bar_sell',              # Продам
    'buy': 'bar_buy',                # Куплю
    'give': 'bar_give',              # Отдам
    'preview': 'bar_prev',           # Preview
    'send': 'bar_send',              # Send to moderation
    'edit': 'bar_edit',              # Edit text
    'add_media': 'bar_media',        # Add media
    'cancel': 'bar_cancel',          # Cancel
    'back': 'bar_back',              # Back
}

BARAHOLKA_CATEGORIES = {
    'sell': '💰 Продам',
    'buy': '🔎 Куплю',
    'give': '🎁 Отдам'
}

async def handle_baraholka_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unified baraholka callback handler"""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    logger.info(f"Baraholka action: {action}")
    
    handlers = {
        BAR_CALLBACKS['sell']: lambda u, c: start_baraholka_post(u, c, 'sell'),
        BAR_CALLBACKS['buy']: lambda u, c: start_baraholka_post(u, c, 'buy'),
        BAR_CALLBACKS['give']: lambda u, c: start_baraholka_post(u, c, 'give'),
        BAR_CALLBACKS['preview']: show_baraholka_preview,
        BAR_CALLBACKS['send']: send_baraholka_to_moderation,
        BAR_CALLBACKS['edit']: edit_baraholka_text,
        BAR_CALLBACKS['add_media']: request_baraholka_media,
        BAR_CALLBACKS['cancel']: cancel_baraholka,
        BAR_CALLBACKS['back']: show_baraholka_preview,
    }
    
    handler = handlers.get(action)
    if handler:
        await handler(update, context)
    else:
        await query.answer("⚠️  Неизвестное действие", show_alert=True)

async def start_baraholka_post(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    """Start baraholka post"""
    context.user_data['baraholka_post'] = {
        'category': BARAHOLKA_CATEGORIES[category],
        'category_key': category,
        'text': None,
        'media': []
    }
    context.user_data['waiting_for'] = 'baraholka_text'
    
    keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data=BAR_CALLBACKS['cancel'])]]
    
    category_name = BARAHOLKA_CATEGORIES[category]
    
    examples = {
        'sell': "Например: Продам iPhone 13, 128GB, отличное состояние, 150к",
        'buy': "Например: Куплю велосипед в хорошем состоянии, бюджет до 50к",
        'give': "Например: Отдам детские вещи 2-3 года, самовывоз"
    }
    
    text = (
        f"{category_name}\n\n"
        f"✍️ Напишите описание товара и/или отправьте фото\n\n"
        f"💡 {examples[category]}"
    )
    
    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_baraholka_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text input for baraholka"""
    if context.user_data.get('waiting_for') != 'baraholka_text':
        return
    
    text = update.message.text or update.message.caption
    
    if not text and not update.message.photo and not update.message.video:
        await update.message.reply_text("❌ Отправьте текст или фото товара")
        return
    
    # Проверка на запрещенные ссылки
    filter_service = FilterService()
    if text and filter_service.contains_banned_link(text):
        if not Config.is_moderator(update.effective_user.id):
            await update.message.reply_text("🚫 Обнаружена запрещенная ссылка!")
            return
    
    if 'baraholka_post' not in context.user_data:
        context.user_data['baraholka_post'] = {
            'category': '💰 Продам',
            'category_key': 'sell',
            'text': None,
            'media': []
        }
    
    # Сохраняем текст
    if text:
        context.user_data['baraholka_post']['text'] = text
    
    # Сохраняем медиа
    if update.message.photo:
        context.user_data['baraholka_post']['media'].append({
            'type': 'photo',
            'file_id': update.message.photo[-1].file_id
        })
    elif update.message.video:
        context.user_data['baraholka_post']['media'].append({
            'type': 'video',
            'file_id': update.message.video.file_id
        })
    
    context.user_data['waiting_for'] = None
    
    keyboard = [
        [
            InlineKeyboardButton("📸 Добавить фото", callback_data=BAR_CALLBACKS['add_media']),
            InlineKeyboardButton("👁️ Предпросмотр", callback_data=BAR_CALLBACKS['preview'])
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data=BAR_CALLBACKS['cancel'])]
    ]
    
    await update.message.reply_text(
        "✅ Сохранено!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_baraholka_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle media input for baraholka"""
    if context.user_data.get('waiting_for') != 'baraholka_media':
        return
    
    if 'baraholka_post' not in context.user_data:
        return
    
    # Добавляем медиа
    if update.message.photo:
        context.user_data['baraholka_post']['media'].append({
            'type': 'photo',
            'file_id': update.message.photo[-1].file_id
        })
    elif update.message.video:
        context.user_data['baraholka_post']['media'].append({
            'type': 'video',
            'file_id': update.message.video.file_id
        })
    else:
        return
    
    media_count = len(context.user_data['baraholka_post']['media'])
    
    keyboard = [
        [
            InlineKeyboardButton(f"➕ Ещё (всего {media_count})", callback_data=BAR_CALLBACKS['add_media']),
            InlineKeyboardButton("👁️ Предпросмотр", callback_data=BAR_CALLBACKS['preview'])
        ]
    ]
    
    await update.message.reply_text(
        f"✅ Фото добавлено ({media_count} шт.)",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_baraholka_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show preview of baraholka post"""
    if 'baraholka_post' not in context.user_data:
        await update.callback_query.edit_message_text("❌ Данные не найдены")
        return
    
    post_data = context.user_data['baraholka_post']
    
    # Формируем превью
    category = post_data.get('category', '💰 Продам')
    text = post_data.get('text', '(без описания)')
    media = post_data.get('media', [])
    
    preview_text = f"🛒 **Предпросмотр**\n\n"
    preview_text += f"📂 Раздел: {category}\n\n"
    preview_text += f"📝 Описание:\n{text}\n\n"
    preview_text += f"📸 Фото: {len(media)} шт.\n\n"
    preview_text += f"#Барахолка @hungarytrade"
    
    keyboard = [
        [
            InlineKeyboardButton("📨 Отправить на модерацию", callback_data=BAR_CALLBACKS['send']),
            InlineKeyboardButton("✏️ Изменить", callback_data=BAR_CALLBACKS['edit'])
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data=BAR_CALLBACKS['cancel'])]
    ]
    
    try:
        await update.callback_query.delete_message()
    except:
        pass
    
    # Показываем медиа
    if media:
        for i, item in enumerate(media[:5]):
            try:
                caption = f"📸 Фото {i+1}/{len(media)}" if i == 0 else None
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

async def send_baraholka_to_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send baraholka post to moderation"""
    user_id = update.effective_user.id
    post_data = context.user_data.get('baraholka_post')
    
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
                user_id, 'baraholka_post', Config.COOLDOWN_SECONDS
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
                category='🛒 Барахолка',
                subcategory=post_data.get('category'),
                text=str(post_data.get('text', ''))[:4096],
                media=list(post_data.get('media', [])),
                hashtags=['#Барахолка', post_data.get('category')],
                anonymous=False,
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
            await cooldown_service.set_cooldown(user_id, 'baraholka_post', Config.COOLDOWN_SECONDS)
            
            # Очищаем данные
            context.user_data.pop('baraholka_post', None)
            context.user_data.pop('waiting_for', None)
            
            await update.callback_query.edit_message_text(
                "✅ **Объявление отправлено на модерацию!**\n\n"
                "⏰ Ожидайте уведомление о публикации"
            )
            
    except Exception as e:
        logger.error(f"Error sending baraholka post: {e}", exc_info=True)
        await update.callback_query.edit_message_text("❌ Ошибка отправки")

async def send_to_mod_group(update: Update, context: ContextTypes.DEFAULT_TYPE,
                            post: Post, user: User, post_data: dict):
    """Send to moderation group"""
    bot = context.bot
    username = user.username or f"ID_{user.id}"
    category = post_data.get('category', '💰 Продам')
    
    mod_text = (
        f"🛒 **НОВОЕ ОБЪЯВЛЕНИЕ - БАРАХОЛКА**\n\n"
        f"👤 От: @{username} (ID: {user.id})\n"
        f"📂 Раздел: {category}\n\n"
        f"📝 Описание:\n{post.text[:300]}"
    )
    
    if len(post.text) > 300:
        mod_text += "..."
    
    if post.media:
        mod_text += f"\n\n📸 Фото: {len(post.media)} шт."
    
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

async def request_baraholka_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request more media"""
    context.user_data['waiting_for'] = 'baraholka_media'
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=BAR_CALLBACKS['preview'])]]
    
    await update.callback_query.edit_message_text(
        "📸 Отправьте фото товара:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def edit_baraholka_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit baraholka text"""
    context.user_data['waiting_for'] = 'baraholka_text'
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=BAR_CALLBACKS['preview'])]]
    
    await update.callback_query.edit_message_text(
        "✏️ Отправьте новое описание:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cancel_baraholka(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel baraholka post"""
    context.user_data.pop('baraholka_post', None)
    context.user_data.pop('waiting_for', None)
    
    from handlers.menu_handler_new import show_write_menu
    await show_write_menu(update, context)

# Export
__all__ = [
    'handle_baraholka_callback',
    'handle_baraholka_text',
    'handle_baraholka_media',
    'BAR_CALLBACKS'
]
