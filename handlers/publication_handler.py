# -*- coding: utf-8 -*-
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes
from config import Config
from services.db import db
from services.hashtags import HashtagService
from services.filter_service import FilterService
from models import User, Post, PostStatus
from sqlalchemy import select
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Канал для публикаций
BUDAPEST_PEOPLE_CHANNEL = -1003114019170

# Cooldown - 1 час
COOLDOWN_SECONDS = 3600

async def handle_publication_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle publication callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")
    action = data[1] if len(data) > 1 else None
    
    logger.info(f"Publication callback action: {action}")
    
    if action == "cat":
        # Subcategory selected
        subcategory = data[2] if len(data) > 2 else None
        await start_post_creation(update, context, subcategory)
    elif action == "preview":
        await show_preview(update, context)
    elif action == "send":
        await send_to_moderation(update, context)
    elif action == "edit":
        await edit_post(update, context)
    elif action == "cancel":
        await cancel_post_with_reason(update, context)
    elif action == "cancel_confirm":
        await cancel_post(update, context)
    elif action == "add_media":
        await request_media(update, context)
    elif action == "back":
        await show_preview(update, context)

async def start_post_creation(update: Update, context: ContextTypes.DEFAULT_TYPE, subcategory: str):
    """Start creating a post with selected subcategory"""
    subcategory_names = {
        'work': '👷 Работа',
        'rent': '🏚️ Аренда',
        'buy': '🕵🏻‍♀️ Куплю',
        'sell': '🕵🏽 Продам',
        'events': '🎉 События',
        'free': '🕵🏼 Отдам даром',
        'important': '✖️уе Будапешт',
        'other': '❔ Другое'
    }
    
    # Сохраняем данные поста
    context.user_data['post_data'] = {
        'category': '🗯️ Будапешт',
        'subcategory': subcategory_names.get(subcategory, '❔ Другое'),
        'anonymous': False
    }

    keyboard = [[InlineKeyboardButton("⏮️ Вернуться", callback_data="menu:announcements")]]
    
    await update.callback_query.edit_message_text(
        f"🗯️ Будапешт → ‼️ Объявления → {subcategory_names.get(subcategory)}\n\n"
        "💥 Напишите текст, добавьте фото, видео контент:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    context.user_data['waiting_for'] = 'post_text'

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текста от пользователя"""
    
    # Проверяем, есть ли медиа вместе с текстом
    has_media = update.message.photo or update.message.video or update.message.document
    
    # Если медиа и текст одновременно (caption)
    if has_media and update.message.caption:
        text = update.message.caption
        
        # Если ждём текст поста
        if context.user_data.get('waiting_for') == 'post_text':
            # Проверяем на запрещённые ссылки
            filter_service = FilterService()
            if filter_service.contains_banned_link(text) and not Config.is_moderator(update.effective_user.id):
                await handle_link_violation(update, context)
                return
            
            # Сохраняем текст
            if 'post_data' not in context.user_data:
                context.user_data['post_data'] = {}
            
            context.user_data['post_data']['text'] = text
            context.user_data['post_data']['media'] = []
            
            # Сохраняем медиа
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
            elif update.message.document:
                context.user_data['post_data']['media'].append({
                    'type': 'document',
                    'file_id': update.message.document.file_id
                })
            
            keyboard = [
                [
                    InlineKeyboardButton("📸 Еще медиа?", callback_data="pub:add_media"),
                    InlineKeyboardButton("💻 Предпросмотр", callback_data="pub:preview")
                ],
                [InlineKeyboardButton("🔙 Вернуться", callback_data="menu:back")]
            ]
            
            await update.message.reply_text(
                "✅ Отлично, текст и медиа сохранены!\n\n"
                "💚 Вы можете добавить еще медиа или перейти к предпросмотру?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            context.user_data['waiting_for'] = None
            return
    
    # Если только текст без медиа
    if 'waiting_for' not in context.user_data:
        return
    
    waiting_for = context.user_data['waiting_for']
    text = update.message.text if update.message.text else update.message.caption
    
    if not text:
        return
    
    logger.info(f"Text input received. waiting_for: {waiting_for}")
    
    if waiting_for == 'post_text':
        # Check for links
        filter_service = FilterService()
        if filter_service.contains_banned_link(text) and not Config.is_moderator(update.effective_user.id):
            await handle_link_violation(update, context)
            return
        
        if 'post_data' not in context.user_data:
            await update.message.reply_text(
                "🤔 Упс! Данные поста потерялись.\n"
                "Давайте начнем заново с /start"
            )
            context.user_data.pop('waiting_for', None)
            return
        
        context.user_data['post_data']['text'] = text
        context.user_data['post_data']['media'] = []
        
        keyboard = [
            [
                InlineKeyboardButton("📹 Прикрепить медиа контент", callback_data="pub:add_media"),
                InlineKeyboardButton("💁 Предпросмотр", callback_data="pub:preview")
            ],
            [InlineKeyboardButton("🚶‍♀️ Назад", callback_data="menu:back")]
        ]
        
        await update.message.reply_text(
            "🎉 Отличный текст, сохраняю!\n\n"
            "💚 Добавить ещё фото, видео или смотрим что получилось?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        context.user_data['waiting_for'] = None
        
    elif waiting_for == 'cancel_reason':
        context.user_data['cancel_reason'] = text
        await cancel_post(update, context)
        
    elif waiting_for.startswith('piar_'):
        from handlers.piar_handler import handle_piar_text
        field = waiting_for.replace('piar_', '')
        await handle_piar_text(update, context, field, text)

async def handle_media_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle media input from user"""
    # Проверяем, что пользователь в процессе добавления медиа
    if 'post_data' not in context.user_data:
        return
    
    # Принимаем медиа даже если waiting_for не установлен
    if 'media' not in context.user_data['post_data']:
        context.user_data['post_data']['media'] = []
    
    media_added = False
    
    if update.message.photo:
        # Get highest quality photo
        context.user_data['post_data']['media'].append({
            'type': 'photo',
            'file_id': update.message.photo[-1].file_id
        })
        media_added = True
        logger.info(f"Added photo: {update.message.photo[-1].file_id}")
        
    elif update.message.video:
        context.user_data['post_data']['media'].append({
            'type': 'video',
            'file_id': update.message.video.file_id
        })
        media_added = True
        logger.info(f"Added video: {update.message.video.file_id}")
        
    elif update.message.document:
        context.user_data['post_data']['media'].append({
            'type': 'document',
            'file_id': update.message.document.file_id
        })
        media_added = True
        logger.info(f"Added document: {update.message.document.file_id}")
    
    if media_added:
        total_media = len(context.user_data['post_data']['media'])
        
        keyboard = [
            [
                InlineKeyboardButton(f"💚 Добавить еще", callback_data="pub:add_media"),
                InlineKeyboardButton("🤩 Предпросмотр", callback_data="pub:preview")
            ],
            [InlineKeyboardButton("🚶 Назад", callback_data="menu:back")]
        ]
        
        await update.message.reply_text(
            f"✅ Медиа получено! (Всего: {total_media})\n\n"
            "💚 Добавить еще или смотреть результат?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        context.user_data['waiting_for'] = None

async def request_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request media from user"""
    context.user_data['waiting_for'] = 'post_media'
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="pub:preview")]]
    
    await update.callback_query.edit_message_text(
        "📹 Поделитесь фото, видео или документом:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show post preview with media first, then buttons"""
    if 'post_data' not in context.user_data:
        await update.callback_query.edit_message_text("😵 Ошибка: данные поста не найдены")
        return
    
    post_data = context.user_data['post_data']
    
    # Generate hashtags
    hashtag_service = HashtagService()
    hashtags = hashtag_service.generate_hashtags(
        post_data.get('category'),
        post_data.get('subcategory')
    )
    
    # Build preview text
    preview_text = f"{post_data.get('text', '')}\n\n"
    preview_text += f"{' '.join(hashtags)}\n\n"
    preview_text += Config.DEFAULT_SIGNATURE
    
    keyboard = [
        [
            InlineKeyboardButton("📨 Отправить на модерацию", callback_data="pub:send"),
            InlineKeyboardButton("📝 Изменить", callback_data="pub:edit")
        ],
        [InlineKeyboardButton("🚗 Отмена", callback_data="pub:cancel")]
    ]
    
    # ИСПРАВЛЕНО: Сначала удаляем старое сообщение с кнопками
    try:
        if update.callback_query:
            await update.callback_query.delete_message()
    except:
        pass
    
    # ИСПРАВЛЕНО: Сначала показываем медиа, если есть
    media = post_data.get('media', [])
    if media:
        try:
            for i, media_item in enumerate(media[:5]):
                caption = None
                if i == 0:
                    caption = f"💿 Медиа файлы ({len(media)} шт.)"
                
                if media_item.get('type') == 'photo':
                    await update.effective_message.reply_photo(
                        photo=media_item['file_id'],
                        caption=caption
                    )
                elif media_item.get('type') == 'video':
                    await update.effective_message.reply_video(
                        video=media_item['file_id'],
                        caption=caption
                    )
                elif media_item.get('type') == 'document':
                    await update.effective_message.reply_document(
                        document=media_item['file_id'],
                        caption=caption
                    )
        except Exception as e:
            logger.error(f"Error showing media preview: {e}")
    
    # ИСПРАВЛЕНО: Потом показываем текст с кнопками
    try:
        await update.effective_message.reply_text(
            f"🫣 *Предпросмотр поста:*\n\n{preview_text}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error sending preview text: {e}")
        await update.effective_message.reply_text(
            f"Предпросмотр поста:\n\n{preview_text}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def send_to_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send post to moderation with cooldown check"""
    user_id = update.effective_user.id
    username = update.effective_user.username or f"ID_{user_id}"
    post_data = context.user_data.get('post_data')
    
    if not post_data:
        await update.callback_query.edit_message_text("💥 Данные поста не найдены")
        return
    
    # ✅ ПРОВЕРКА COOLDOWN'А
    from main import check_cooldown, record_submission
    can_submit, remaining = check_cooldown(user_id)
    
    if not can_submit and not Config.is_admin(user_id):
        minutes = remaining // 60
        seconds = remaining % 60
        await update.callback_query.edit_message_text(
            f"⏰ **Ограничение по времени**\n\n"
            f"Вы сможете отправить следующую заявку через:\n"
            f"⏳ {minutes} минут {seconds} секунд",
            parse_mode='Markdown'
        )
        logger.info(f"User {user_id} tried to post with cooldown remaining: {remaining}s")
        return
    
    try:
        # ПРОВЕРКА БД
        if not db.session_maker:
            logger.error("Database not available")
            await update.callback_query.edit_message_text(
                "😖 База данных недоступна. Попробуйте позже или обратитесь к администратору."
            )
            return
        
        async with db.get_session() as session:
            # Get user
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                logger.warning(f"User {user_id} not found in database")
                await update.callback_query.edit_message_text(
                    "😩 Пользователь не найден. Используйте /start для регистрации."
                )
                return
            
            # СОЗДАЕМ ПОСТ
            create_post_data = {
                'user_id': int(user_id),
                'category': str(post_data.get('category', ''))[:255] if post_data.get('category') else None,
                'subcategory': str(post_data.get('subcategory', ''))[:255] if post_data.get('subcategory') else None,
                'text': str(post_data.get('text', ''))[:4096] if post_data.get('text') else None,
                'hashtags': list(post_data.get('hashtags', [])),
                'anonymous': bool(post_data.get('anonymous', False)),
                'media': list(post_data.get('media', [])),
                'status': PostStatus.PENDING,
                'is_piar': False,
                'username': username
            }
            
            # Create post
            post = Post(**create_post_data)
            session.add(post)
            await session.flush()
            
            post_id = post.id
            logger.info(f"Created post with ID: {post_id} from user {user_id}")
            
            await session.commit()
            
            # ОТПРАВЛЯЕМ НА МОДЕРАЦИЮ
            await send_to_moderation_group(update, context, post, user, post_data, username)
            
            # ЗАПИСЫВАЕМ COOLDOWN
            record_submission(user_id)
            
            # Clean up
            context.user_data.pop('post_data', None)
            context.user_data.pop('waiting_for', None)
            
            # СООБЩЕНИЕ ПОЛЬЗОВАТЕЛЮ
            await update.callback_query.edit_message_text(
                "✅ **Ваша заявка отправлена на модерацию!**\n\n"
                "⏳ Ожидайте решение модераторов...\n\n"
                "📩 Ссылка на публикацию придет в личные сообщения"
            )
            
    except Exception as e:
        logger.error(f"Error sending to moderation: {e}", exc_info=True)
        await update.callback_query.edit_message_text(
            "😖 Ошибка при отправке на модерацию"
        )

async def send_to_moderation_group(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                   post: Post, user: User, post_data: dict, username: str):
    """Send post to moderation group"""
    bot = context.bot
    
    category = post.category or 'Unknown'
    subcategory = post.subcategory or ''
    
    mod_text = (
        f"📨 **НОВАЯ ЗАЯВКА**\n\n"
        f"👤 От: @{username} (ID: {user.id})\n"
        f"📅 Дата: {post.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"📚 Категория: {category}"
    )
    
    if subcategory:
        mod_text += f" → {subcategory}"
    
    if post.media:
        media_count = len(post.media) if isinstance(post.media, list) else 0
        if media_count > 0:
            mod_text += f"\n📎 Медиа: {media_count} файл(ов)"
    
    if post.text:
        post_text = post.text[:300] + "..." if len(post.text) > 300 else post.text
        mod_text += f"\n\n📝 Текст:\n{post_text}"
    
    # КНОПКИ МОДЕРАЦИИ
    keyboard = [
        [
            InlineKeyboardButton("✅ Опубликовать на канал", callback_data=f"mod:approve:{post.id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"mod:reject:{post.id}")
        ]
    ]
    
    try:
        # Проверяем доступность группы модерации
        try:
            await bot.get_chat(Config.MODERATION_GROUP_ID)
        except Exception as chat_error:
            logger.error(f"Cannot access moderation group: {chat_error}")
            await bot.send_message(
                chat_id=user.id,
                text="⚠️ Группа модерации недоступна. Обратитесь к администратору."
            )
            return

        # Отправляем медиа если есть
        if post.media and isinstance(post.media, list):
            for i, media_item in enumerate(post.media):
                try:
                    if not media_item or not isinstance(media_item, dict):
                        continue
                        
                    file_id = media_item.get('file_id')
                    media_type = media_item.get('type')
                    
                    if not file_id or not media_type:
                        continue
                    
                    caption = f"📷 Медиа {i+1}/{len(post.media)}"
                    
                    if media_type == 'photo':
                        await bot.send_photo(
                            chat_id=Config.MODERATION_GROUP_ID,
                            photo=file_id,
                            caption=caption
                        )
                    elif media_type == 'video':
                        await bot.send_video(
                            chat_id=Config.MODERATION_GROUP_ID,
                            video=file_id,
                            caption=caption
                        )
                    elif media_type == 'document':
                        await bot.send_document(
                            chat_id=Config.MODERATION_GROUP_ID,
                            document=file_id,
                            caption=caption
                        )
                        
                except Exception as e:
                    logger.error(f"Error sending media: {e}")
                    continue
        
        # Отправляем текст с кнопками
        try:
            message = await bot.send_message(
                chat_id=Config.MODERATION_GROUP_ID,
                text=mod_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            logger.info(f"✅ Post {post.id} sent to moderation successfully")
        except Exception as text_error:
            logger.error(f"Error sending moderation text: {text_error}")
            simple_text = f"Новая заявка от @{username}\nКатегория: {category}\nТекст: {(post.text or '')[:200]}..."
            message = await bot.send_message(
                chat_id=Config.MODERATION_GROUP_ID,
                text=simple_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        # Сохраняем message ID для отслеживания
        try:
            from sqlalchemy import text
            async with db.get_session() as session:
                await session.execute(
                    text("UPDATE posts SET moderation_message_id = :msg_id WHERE id = :post_id"),
                    {"msg_id": message.message_id, "post_id": int(post.id)}
                )
                await session.commit()
        except Exception as save_error:
            logger.warning(f"Could not save moderation_message_id: {save_error}")
            
    except Exception as e:
        logger.error(f"❌ Error sending to moderation group: {e}", exc_info=True)

async def publish_to_channel(bot, post: Post, user: User):
    """Publish approved post to Budapest People channel"""
    try:
        # Получаем текст поста
        post_text = f"{post.text}\n\n"
        
        # Добавляем хештеги
        if post.hashtags:
            hashtags_text = " ".join(str(tag) for tag in post.hashtags)
            post_text += f"{hashtags_text}\n\n"
        
        # Добавляем подпись
        if not post.anonymous and user.username:
            post_text += f"✍️ @{user.username}"
        
        post_text += f"\n{Config.DEFAULT_SIGNATURE}"
        
        # Отправляем медиа если есть
        if post.media and isinstance(post.media, list) and len(post.media) > 0:
            for i, media_item in enumerate(post.media):
                try:
                    if not media_item or not isinstance(media_item, dict):
                        continue
                    
                    file_id = media_item.get('file_id')
                    media_type = media_item.get('type')
                    
                    if not file_id or not media_type:
                        continue
                    
                    # Только для первого медиа добавляем полный текст
                    caption = post_text if i == 0 else None
                    
                    if media_type == 'photo':
                        msg = await bot.send_photo(
                            chat_id=BUDAPEST_PEOPLE_CHANNEL,
                            photo=file_id,
                            caption=caption,
                            parse_mode='HTML' if caption else None
                        )
                    elif media_type == 'video':
                        msg = await bot.send_video(
                            chat_id=BUDAPEST_PEOPLE_CHANNEL,
                            video=file_id,
                            caption=caption,
                            parse_mode='HTML' if caption else None
                        )
                    
                except Exception as e:
                    logger.error(f"Error publishing media: {e}")
                    continue
        else:
            # Если нет медиа, отправляем текст
            msg = await bot.send_message(
                chat_id=BUDAPEST_PEOPLE_CHANNEL,
                text=post_text,
                parse_mode='HTML'
            )
        
        logger.info(f"✅ Post {post.id} published to channel")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error publishing to channel: {e}")
        return False

async def cancel_post_with_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for cancellation reason"""
    keyboard = [
        [InlineKeyboardButton("🤔 Передумал", callback_data="pub:cancel_confirm")],
        [InlineKeyboardButton("👎 Ошибка в тексте", callback_data="pub:cancel_confirm")],
        [InlineKeyboardButton("👈 Назад", callback_data="pub:preview")]
    ]
    
    await update.callback_query.edit_message_text(
        "💭 Укажите причину отмены:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_link_violation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle link violation"""
    await update.message.reply_text(
        "🚫 Обнаружена запрещенная ссылка!\n"
        "Ссылки запрещены в публикациях."
    )
    context.user_data.pop('waiting_for', None)

async def edit_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit post before sending"""
    context.user_data['waiting_for'] = 'post_text'
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="pub:preview")]]
    
    await update.callback_query.edit_message_text(
        "✏️ Отправьте новый текст публикации:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cancel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel post creation"""
    context.user_data.pop('post_data', None)
    context.user_data.pop('waiting_for', None)
    context.user_data.pop('cancel_reason', None)
    
    from handlers.start_handler import show_main_menu
    await show_main_menu(update, context)

__all__ = [
    'handle_publication_callback',
    'handle_text_input',
    'handle_media_input',
    'publish_to_channel'
]
