# -*- coding: utf-8 -*-
"""
Optimized Publication Handler
Prefix: pbc_ (publication callback)
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from services.db import db
from services.cooldown import CooldownService
from services.hashtags import HashtagService
from services.filter_service import FilterService
from models import User, Post, PostStatus
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

# ============= CALLBACK PREFIX: pbc_ =============
PUB_CALLBACKS = {
    'buy': 'pbc_buy', 'work': 'pbc_wrk', 'rent': 'pbc_rnt',
    'sell': 'pbc_sell', 'free': 'pbc_free', 'crypto': 'pbc_cry',
    'other': 'pbc_oth', 'events': 'pbc_evt',
    'preview': 'pbc_prv', 'send': 'pbc_snd', 'edit': 'pbc_edt',
    'cancel': 'pbc_cnl', 'cancel_confirm': 'pbc_cnc',
    'add_media': 'pbc_adm', 'back': 'pbc_bck'
}

SUBCATEGORY_NAMES = {
    'buy': '🕵🏻‍♀️ Куплю', 'work': '👷 Работа', 'rent': '🏚️ Аренда',
    'sell': '🕵🏽 Продам', 'events': '🎉 События', 'free': '🕵🏼 Отдам',
    'other': '❔ Другое', 'crypto': '🪙 Криптовалюта'
}

async def handle_publication_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unified publication callback handler"""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    logger.info(f"Publication action: {action}")
    
    # Category selection
    if action in [PUB_CALLBACKS[k] for k in SUBCATEGORY_NAMES.keys()]:
        subcategory_key = next(k for k, v in PUB_CALLBACKS.items() if v == action)
        await start_post_creation(update, context, subcategory_key)
        return
    
    # Action handlers
    handlers = {
        PUB_CALLBACKS['preview']: show_preview,
        PUB_CALLBACKS['send']: send_to_moderation,
        PUB_CALLBACKS['edit']: edit_post,
        PUB_CALLBACKS['cancel']: cancel_post_with_reason,
        PUB_CALLBACKS['cancel_confirm']: cancel_post,
        PUB_CALLBACKS['add_media']: request_media,
        PUB_CALLBACKS['back']: show_preview
    }
    
    handler = handlers.get(action)
    if handler:
        await handler(update, context)
    else:
        await query.answer("Неизвестное действие", show_alert=True)

async def start_post_creation(update: Update, context: ContextTypes.DEFAULT_TYPE, subcategory: str):
    """Start post creation"""
    context.user_data['post_data'] = {
        'category': '🗯️ Будапешт',
        'subcategory': SUBCATEGORY_NAMES.get(subcategory, '❔ Другое'),
        'anonymous': False
    }

    keyboard = [[InlineKeyboardButton("⏮️ Вернуться", callback_data="mnc_ann")]]
    
    await update.callback_query.edit_message_text(
        f"🗯️ Будапешт → {SUBCATEGORY_NAMES.get(subcategory)}\n\n"
        "💥 Напишите текст, добавьте медиа:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    context.user_data['waiting_for'] = 'post_text'

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text input"""
    # Check for media with caption
    if (update.message.photo or update.message.video) and update.message.caption:
        text = update.message.caption
        if context.user_data.get('waiting_for') == 'post_text':
            filter_service = FilterService()
            if filter_service.contains_banned_link(text) and not Config.is_moderator(update.effective_user.id):
                await update.message.reply_text("🚫 Обнаружена запрещенная ссылка!")
                return
            
            if 'post_data' not in context.user_data:
                context.user_data['post_data'] = {}
            
            context.user_data['post_data']['text'] = text
            context.user_data['post_data']['media'] = []
            
            # Save media
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
                    InlineKeyboardButton("📸 Еще медиа", callback_data=PUB_CALLBACKS['add_media']),
                    InlineKeyboardButton("💻 Предпросмотр", callback_data=PUB_CALLBACKS['preview'])
                ],
                [InlineKeyboardButton("🔙 Назад", callback_data=PUB_CALLBACKS['back'])]
            ]
            
            await update.message.reply_text(
                "✅ Текст и медиа сохранены!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            context.user_data['waiting_for'] = None
            return
    
    # Text only
    if not context.user_data.get('waiting_for') == 'post_text':
        return
    
    text = update.message.text or update.message.caption
    if not text:
        return
    
    filter_service = FilterService()
    if filter_service.contains_banned_link(text) and not Config.is_moderator(update.effective_user.id):
        await update.message.reply_text("🚫 Запрещенная ссылка!")
        return
    
    if 'post_data' not in context.user_data:
        await update.message.reply_text("🤔 Данные потерялись. /start")
        return
    
    context.user_data['post_data']['text'] = text
    context.user_data['post_data']['media'] = []
    
    keyboard = [
        [
            InlineKeyboardButton("📹 Медиа", callback_data=PUB_CALLBACKS['add_media']),
            InlineKeyboardButton("💁 Предпросмотр", callback_data=PUB_CALLBACKS['preview'])
        ],
        [InlineKeyboardButton("🚶‍♀️ Назад", callback_data="mnc_bk")]
    ]
    
    await update.message.reply_text(
        "🎉 Текст сохранён!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data['waiting_for'] = None

async def handle_media_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle media input"""
    if 'post_data' not in context.user_data:
        return
    
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
                InlineKeyboardButton("💚 Еще", callback_data=PUB_CALLBACKS['add_media']),
                InlineKeyboardButton("🤩 Предпросмотр", callback_data=PUB_CALLBACKS['preview'])
            ]
        ]
        
        await update.message.reply_text(
            f"✅ Медиа получено! ({total})",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def show_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show preview"""
    if 'post_data' not in context.user_data:
        await update.callback_query.edit_message_text("😵 Данные не найдены")
        return
    
    post_data = context.user_data['post_data']
    
    # Generate hashtags
    hashtag_service = HashtagService()
    if post_data.get('is_actual'):
        hashtags = ['#Актуальное⚡️', '@Trixlivebot']
    else:
        hashtags = hashtag_service.generate_hashtags(
            post_data.get('category'),
            post_data.get('subcategory')
        )
    
    preview_text = f"{post_data.get('text', '')}\n\n{' '.join(hashtags)}\n\n{Config.DEFAULT_SIGNATURE}"
    
    keyboard = [
        [
            InlineKeyboardButton("📨 На модерацию", callback_data=PUB_CALLBACKS['send']),
            InlineKeyboardButton("📝 Изменить", callback_data=PUB_CALLBACKS['edit'])
        ],
        [InlineKeyboardButton("🚗 Отмена", callback_data=PUB_CALLBACKS['cancel'])]
    ]
    
    try:
        await update.callback_query.delete_message()
    except:
        pass
    
    # Show media first
    media = post_data.get('media', [])
    if media:
        for i, item in enumerate(media[:5]):
            try:
                caption = f"💿 Медиа ({len(media)} шт.)" if i == 0 else None
                if item['type'] == 'photo':
                    await update.effective_message.reply_photo(photo=item['file_id'], caption=caption)
                elif item['type'] == 'video':
                    await update.effective_message.reply_video(video=item['file_id'], caption=caption)
            except Exception as e:
                logger.error(f"Preview media error: {e}")
    
    # Show text with buttons
    await update.effective_message.reply_text(
        f"🫣 *Предпросмотр:*\n\n{preview_text}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def send_to_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send to moderation"""
    user_id = update.effective_user.id
    post_data = context.user_data.get('post_data')
    
    if not post_data:
        await update.callback_query.edit_message_text("💥 Данные не найдены")
        return
    
    try:
        if not db.session_maker:
            await update.callback_query.edit_message_text("😖 БД недоступна")
            return
        
        async with db.get_session() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            
            if not user:
                await update.callback_query.edit_message_text("😩 Пользователь не найден. /start")
                return
            
            # Check cooldown
            from services.cooldown import cooldown_service
            try:
                can_post, remaining = await cooldown_service.can_post(user_id)
            except:
                can_post = cooldown_service.simple_can_post(user_id)
                remaining = cooldown_service.get_remaining_time(user_id)
            
            if not can_post and not Config.is_moderator(user_id):
                await update.callback_query.edit_message_text(
                    f"💤 Подождите {remaining // 60} минут"
                )
                return
            
            # Create post
            post = Post(
                user_id=int(user_id),
                category=str(post_data.get('category', ''))[:255],
                subcategory=str(post_data.get('subcategory', ''))[:255],
                text=str(post_data.get('text', ''))[:4096],
                hashtags=list(post_data.get('hashtags', [])),
                anonymous=bool(post_data.get('anonymous', False)),
                media=list(post_data.get('media', [])),
                status=PostStatus.PENDING,
                is_piar=False
            )
            session.add(post)
            await session.flush()
            await session.commit()
            await session.refresh(post)
            
            # Send to mod group
            await send_to_mod_group(update, context, post, user)
            
            # Update cooldown
            try:
                await cooldown_service.update_cooldown(user_id)
            except:
                cooldown_service.set_last_post_time(user_id)
            
            context.user_data.pop('post_data', None)
            context.user_data.pop('waiting_for', None)
            
            await update.callback_query.edit_message_text(
                "✅ Отправлено на модерацию!\n⏹️ Ожидайте ссылку в ЛС"
            )
            
    except Exception as e:
        logger.error(f"Send to moderation error: {e}", exc_info=True)
        await update.callback_query.edit_message_text("😖 Ошибка отправки")

async def send_to_mod_group(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                            post: Post, user: User):
    """Send to moderation group - compact version"""
    bot = context.bot
    is_actual = context.user_data.get('post_data', {}).get('is_actual', False)
    
    username = user.username or f"ID_{user.id}"
    mod_text = (
        f"{'⚡️ АКТУАЛЬНОЕ' if is_actual else '🚨 Заявочка'}\n\n"
        f"💌 @{username} (ID: {user.id})\n"
        f"📚 {post.category}"
    )
    
    if post.subcategory:
        mod_text += f" → {post.subcategory}"
    if post.text:
        mod_text += f"\n\n📝 {post.text[:300]}..."
    
    keyboard = [[
        InlineKeyboardButton(
            "✅ В ЧАТ" if is_actual else "✅ Опубликовать",
            callback_data=f"mdc_{'ac' if is_actual else 'ap'}:{post.id}"
        ),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"mdc_rj:{post.id}")
    ]]
    
    try:
        # Send media
        if post.media:
            for item in post.media[:3]:
                if item['type'] == 'photo':
                    await bot.send_photo(Config.MODERATION_GROUP_ID, item['file_id'])
                elif item['type'] == 'video':
                    await bot.send_video(Config.MODERATION_GROUP_ID, item['file_id'])
        
        # Send text with buttons
        await bot.send_message(
            Config.MODERATION_GROUP_ID,
            mod_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Send to mod group error: {e}")

async def request_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request media"""
    context.user_data['waiting_for'] = 'post_media'
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data=PUB_CALLBACKS['preview'])]]
    await update.callback_query.edit_message_text(
        "📹 Отправьте медиа:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def edit_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit post"""
    context.user_data['waiting_for'] = 'post_text'
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data=PUB_CALLBACKS['preview'])]]
    await update.callback_query.edit_message_text(
        "✏️ Новый текст:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cancel_post_with_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask cancellation reason"""
    keyboard = [
        [InlineKeyboardButton("🤔 Передумал", callback_data=PUB_CALLBACKS['cancel_confirm'])],
        [InlineKeyboardButton("👎 Ошибка", callback_data=PUB_CALLBACKS['cancel_confirm'])],
        [InlineKeyboardButton("👈Назад", callback_data=PUB_CALLBACKS['preview'])]
    ]
    await update.callback_query.edit_message_text(
        "💭 Причина отмены:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cancel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel post"""
    context.user_data.pop('post_data', None)
    context.user_data.pop('waiting_for', None)
    from handlers.start_handler import show_main_menu
    await show_main_menu(update, context)

__all__ = ['handle_publication_callback', 'handle_text_input', 'handle_media_input', 'PUB_CALLBACKS']
