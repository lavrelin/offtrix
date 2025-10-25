# -*- coding: utf-8 -*-
"""
Catalog Handler - OPTIMIZED v5.2
- Уникальные префиксы callback_data: ctc_
- Сокращенные функции
- Улучшенная обработка медиа
"""
import logging
import re
from typing import Optional, Dict
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ContextTypes
from telegram.error import TelegramError, BadRequest, Forbidden
from config import Config
from services.catalog_service import catalog_service, CATALOG_CATEGORIES

logger = logging.getLogger(__name__)

# ============= CALLBACK PREFIXES =============
CATALOG_CALLBACKS = {
    'next': 'ctc_next',
    'finish': 'ctc_finish',
    'restart': 'ctc_restart',
    'search': 'ctc_search',
    'cancel_search': 'ctc_cancel_search',
    'category': 'ctc_cat',
    'click': 'ctc_click',
    'add_cat': 'ctc_add_cat',
    'rate': 'ctc_rate',
    'cancel_review': 'ctc_cancel_review',
    'cancel': 'ctc_cancel',
    'cancel_top': 'ctc_cancel_top',
    'cancel_ad': 'ctc_cancel_ad',
    'priority_finish': 'ctc_priority_finish',
    'priority_clear': 'ctc_priority_clear',
    'priority_stats': 'ctc_priority_stats',
    'ad_by_number': 'ctc_ad_by_number',
    'ad_by_link': 'ctc_ad_by_link',
    'follow_menu': 'ctc_follow_menu',
    'follow_cat': 'ctc_follow_cat',
    'my_follows': 'ctc_my_follows',
    'unfollow': 'ctc_unfollow',
    'unfollow_all': 'ctc_unfollow_all',
    'subscribe_menu': 'ctc_subscribe_menu',
    'reviews_menu': 'ctc_reviews_menu',
    'view_reviews': 'ctc_view_reviews',
    'write_review': 'ctc_write_review',
    'remove_confirm': 'ctc_remove_confirm',
    'remove_cancel': 'ctc_remove_cancel',
    'edit': 'ctc_edit',
    'edit_cancel': 'ctc_edit_cancel',
    'close_menu': 'ctc_close_menu',
}

# ============= MEDIA EXTRACTION =============

async def extract_media_from_link(bot: Bot, telegram_link: str) -> Optional[Dict]:
    """Extract media from Telegram post - OPTIMIZED"""
    try:
        if not telegram_link or 't.me/' not in telegram_link:
            return {'success': False, 'message': '❌ Неверная ссылка'}
        
        match = re.search(r't\.me/([^/]+)/(\d+)', telegram_link)
        if not match:
            return {'success': False, 'message': '❌ Не удалось извлечь данные'}
        
        channel_username = match.group(1).lstrip('@')
        message_id = int(match.group(2))
        
        # Determine chat_id
        if channel_username.startswith('-'):
            chat_id = int(channel_username)
        elif channel_username.isdigit():
            chat_id = int(f"-100{channel_username}")
        else:
            chat_id = f"@{channel_username}"
        
        logger.info(f"📥 Extracting from: {chat_id}/{message_id}")
        
        # Check bot access
        try:
            await bot.get_chat(chat_id)
        except (Forbidden, BadRequest) as e:
            logger.error(f"❌ No access: {e}")
            return {
                'success': False,
                'message': '❌ Бот не имеет доступа к каналу\n\n'
                          '1. Добавьте @TrixLiveBot в канал\n'
                          '2. Дайте права администратора\n'
                          '3. Или загрузите медиа вручную'
            }
        
        # Forward to temp chat
        try:
            forwarded = await bot.forward_message(
                chat_id=Config.MODERATION_GROUP_ID,
                from_chat_id=chat_id,
                message_id=message_id
            )
            
            result = None
            media_map = {
                'photo': lambda m: {'type': 'photo', 'file_id': m.photo[-1].file_id},
                'video': lambda m: {'type': 'video', 'file_id': m.video.file_id},
                'document': lambda m: {'type': 'document', 'file_id': m.document.file_id},
                'animation': lambda m: {'type': 'animation', 'file_id': m.animation.file_id},
            }
            
            for media_type, extractor in media_map.items():
                if getattr(forwarded, media_type, None):
                    media_data = extractor(forwarded)
                    result = {
                        'success': True,
                        **media_data,
                        'media_group_id': forwarded.media_group_id,
                        'media_json': [media_data['file_id']],
                        'message': f'✅ {media_type.title()} импортировано'
                    }
                    break
            
            if not result:
                result = {
                    'success': False,
                    'message': '⚠️ Медиа не найдено в посте\n'
                              'Вы можете загрузить медиа вручную'
                }
            
            # Cleanup
            try:
                await bot.delete_message(
                    chat_id=Config.MODERATION_GROUP_ID,
                    message_id=forwarded.message_id
                )
            except Exception:
                pass
            
            return result
            
        except (BadRequest, Forbidden) as e:
            logger.error(f"❌ Forward failed: {e}")
            return {
                'success': False,
                'message': '❌ Не удалось импортировать медиа\n'
                          'Загрузите медиа вручную'
            }
            
    except Exception as e:
        logger.error(f"❌ Media extraction error: {e}", exc_info=True)
        return {'success': False, 'message': f'❌ Ошибка: {str(e)[:100]}'}

# ============= SEND POST WITH MEDIA =============

async def send_catalog_post(bot: Bot, chat_id: int, post: Dict, index: int, total: int) -> bool:
    """Send catalog card - OPTIMIZED"""
    try:
        catalog_number = post.get('catalog_number', '????')
        
        # Build card text
        card_text = (
            f"#️⃣ **Пост {catalog_number}**\n\n"
            f"📂 {post.get('category', 'Не указана')}\n"
            f"ℹ️ {post.get('name', 'Без названия')}\n\n"
        )
        
        # Add tags
        tags = post.get('tags', [])
        if tags and isinstance(tags, list):
            clean_tags = [f"#{re.sub(r'[^\w\-]', '', str(tag).replace(' ', '_'))}" 
                         for tag in tags[:5] if tag]
            if clean_tags:
                card_text += f"{' '.join(clean_tags)}\n"
        
        # Add rating
        review_count = post.get('review_count', 0)
        if review_count >= 10:
            rating = post.get('rating', 0)
            stars = "⭐" * int(rating)
            card_text += f"**Rating**: {stars} {rating:.1f} ({review_count} отзывов)\n"
        else:
            card_text += "**Rating**: -\n"
        
        # Build keyboard
        keyboard = [
            [
                InlineKeyboardButton("➡️ Перейти", url=post.get('catalog_link', '#'), 
                                   callback_data=f"{CATALOG_CALLBACKS['click']}:{post.get('id')}"),
                InlineKeyboardButton("🧑‍🧒‍🧒 Отзывы", 
                                   callback_data=f"{CATALOG_CALLBACKS['reviews_menu']}:{post.get('id')}")
            ],
            [InlineKeyboardButton("🆕 Подписаться", 
                                callback_data=f"{CATALOG_CALLBACKS['subscribe_menu']}:{post.get('category')}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send with media if available
        media_type = post.get('media_type')
        media_file_id = post.get('media_file_id')
        
        if media_file_id and media_type:
            send_funcs = {
                'photo': bot.send_photo,
                'video': bot.send_video,
                'document': bot.send_document,
                'animation': bot.send_animation,
            }
            
            send_func = send_funcs.get(media_type)
            if send_func:
                try:
                    await send_func(
                        chat_id=chat_id,
                        **{media_type: media_file_id},
                        caption=card_text,
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                    await catalog_service.increment_views(post.get('id'), chat_id)
                    return True
                except TelegramError:
                    pass
        
        # Fallback to text
        await bot.send_message(
            chat_id=chat_id,
            text=card_text,
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        await catalog_service.increment_views(post.get('id'), chat_id)
        return True
        
    except Exception as e:
        logger.error(f"Error sending catalog post: {e}")
        return False

# ============= COMMANDS =============

async def catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Browse catalog - /catalog"""
    user_id = update.effective_user.id
    posts = await catalog_service.get_random_posts_mixed(user_id, count=5)
    
    if not posts:
        keyboard = [
            [InlineKeyboardButton("🔄 Начать заново", callback_data=CATALOG_CALLBACKS['restart'])],
            [InlineKeyboardButton("↩️ Главное меню", callback_data="mnc_back")]
        ]
        await update.message.reply_text(
            "📂 Актуальных публикаций больше нет\n\nНажмите 🔄 'Начать заново'",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    for i, post in enumerate(posts, 1):
        await send_catalog_post(context.bot, update.effective_chat.id, post, i, len(posts))
    
    keyboard = [
        [
            InlineKeyboardButton("🔀 Следующие 5", callback_data=CATALOG_CALLBACKS['next']),
            InlineKeyboardButton("⏹️ Закончить", callback_data=CATALOG_CALLBACKS['finish'])
        ],
        [InlineKeyboardButton("🔍 Поиск", callback_data=CATALOG_CALLBACKS['search'])]
    ]
    await update.message.reply_text(
        f"🔃 Показано: {len(posts)}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search catalog - /search"""
    context.user_data['catalog_search'] = {'step': 'query'}
    
    keyboard = [[InlineKeyboardButton("🚫 Отмена", callback_data=CATALOG_CALLBACKS['cancel_search'])]]
    
    await update.message.reply_text(
        "🔎 **ПОИСК В КАТАЛОГЕ**\n\n"
        "Введите слова для поиска:\n"
        "• По названию\n"
        "• По тегам\n\n"
        "Пример: ресницы",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def review_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Leave review - /review [id]"""
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            "🔄 Использование: `/review [номер]`\n\n"
            "Пример: `/review 1234`",
            parse_mode='Markdown'
        )
        return
    
    catalog_number = int(context.args[0])
    post = await catalog_service.get_post_by_number(catalog_number)
    
    if not post:
        await update.message.reply_text(f"❌ Пост #{catalog_number} не найден")
        return
    
    context.user_data['catalog_review'] = {
        'post_id': post['id'],
        'catalog_number': catalog_number,
        'step': 'rating'
    }
    
    keyboard = [
        [
            InlineKeyboardButton("⭐", callback_data=f"{CATALOG_CALLBACKS['rate']}:1"),
            InlineKeyboardButton("⭐⭐", callback_data=f"{CATALOG_CALLBACKS['rate']}:2"),
            InlineKeyboardButton("⭐⭐⭐", callback_data=f"{CATALOG_CALLBACKS['rate']}:3")
        ],
        [
            InlineKeyboardButton("⭐⭐⭐⭐", callback_data=f"{CATALOG_CALLBACKS['rate']}:4"),
            InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data=f"{CATALOG_CALLBACKS['rate']}:5")
        ],
        [InlineKeyboardButton("⏮️ Отмена", callback_data=CATALOG_CALLBACKS['cancel_review'])]
    ]
    
    await update.message.reply_text(
        f"🌟 **ОЦЕНКА ПОСТА #{catalog_number}**\n\n"
        f"📝 {post.get('name', 'Без названия')}\n\n"
        "Выберите оценку:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def categoryfollow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manage subscriptions - /categoryfollow"""
    user_id = update.effective_user.id
    
    try:
        subscriptions = await catalog_service.get_user_subscriptions(user_id)
        
        text = "🔔 **ПОДПИСКИ НА КАТЕГОРИИ**\n\n"
        
        if subscriptions:
            text += "☑️ Ваши подписки:\n"
            for sub in subscriptions:
                text += f"✅ {sub.get('category')}\n"
            text += "\n"
        
        text += "Выберите действие:"
        
        keyboard = [
            [InlineKeyboardButton("✅ Подписаться", callback_data=CATALOG_CALLBACKS['follow_menu'])],
            [InlineKeyboardButton("☑️ Мои подписки", callback_data=CATALOG_CALLBACKS['my_follows'])]
        ]
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error in categoryfollow: {e}")
        await update.message.reply_text("❌ Ошибка при загрузке подписок")

async def addtocatalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add to catalog - /addtocatalog"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    context.user_data['catalog_add'] = {'step': 'link'}
    keyboard = [[InlineKeyboardButton("🚗 Отмена", callback_data=CATALOG_CALLBACKS['cancel'])]]
    
    await update.message.reply_text(
        "🛤️ **ДОБАВЛЕНИЕ**\n\nШаг 1/5\n\n"
        "🫟 Ссылка на пост:\n"
        "Пример: https://t.me/channel/123",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============= ADMIN COMMANDS (SHORTENED) =============

async def addgirltocat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add to TopGirls - /addgirltocat"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админов")
        return
    
    context.user_data['catalog_add_top'] = {'step': 'link', 'category': '👱🏻‍♀️ TopGirls'}
    keyboard = [[InlineKeyboardButton("🚗 Отмена", callback_data=CATALOG_CALLBACKS['cancel_top'])]]
    
    await update.message.reply_text(
        "💃 **ДОБАВЛЕНИЕ В TOPGIRLS**\n\nШаг 1/3\n\n"
        "👩🏼‍💼 Ссылка на оригинальный пост:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def addboytocat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add to TopBoys - /addboytocat"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админов")
        return
    
    context.user_data['catalog_add_top'] = {'step': 'link', 'category': '🤵🏼‍♂️ TopBoys'}
    keyboard = [[InlineKeyboardButton("🚗 Отмена", callback_data=CATALOG_CALLBACKS['cancel_top'])]]
    
    await update.message.reply_text(
        "🤵 **ДОБАВЛЕНИЕ В TOPBOYS**\n\nШаг 1/3\n\n"
        "🧏🏻‍♂️ Ссылка на оригинальный пост:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============= MORE ADMIN COMMANDS (Continued in next file) =============

async def handle_catalog_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle media upload - OPTIMIZED"""
    if 'catalog_add' not in context.user_data or context.user_data['catalog_add'].get('step') != 'media':
        return False
    
    data = context.user_data['catalog_add']
    
    media_map = {
        'photo': lambda m: ('photo', m.photo[-1].file_id),
        'video': lambda m: ('video', m.video.file_id),
        'document': lambda m: ('document', m.document.file_id),
        'animation': lambda m: ('animation', m.animation.file_id),
    }
    
    for media_type, extractor in media_map.items():
        if getattr(update.message, media_type, None):
            media_type, file_id = extractor(update.message)
            data.update({
                'media_type': media_type,
                'media_file_id': file_id,
                'media_group_id': update.message.media_group_id,
                'media_json': [file_id],
                'step': 'tags'
            })
            await update.message.reply_text(
                f"✅ Медиа: {media_type}\n\n"
                "#️⃣ Теги через запятую (до 10):\n"
                "Пример: маникюр, гель-лак"
            )
            return True
    
    return False

# ============= CALLBACK HANDLER =============

async def handle_catalog_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all catalog callbacks - OPTIMIZED"""
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split(":")
    
    # Remove prefix
    if data_parts[0].startswith('ctc_'):
        action = data_parts[0][4:]  # Remove 'ctc_' prefix
    else:
        action = data_parts[0]
    
    user_id = update.effective_user.id
    
    async def safe_edit(text, keyboard=None):
        try:
            await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
        except Exception:
            try:
                await query.edit_message_caption(caption=text, reply_markup=keyboard, parse_mode='Markdown')
            except Exception:
                await query.message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')
    
    # ============= NAVIGATION =============
    
    if action == 'next':
        posts = await catalog_service.get_random_posts_mixed(user_id, count=5)
        if not posts:
            keyboard = [
                [InlineKeyboardButton("🔄 Начать заново", callback_data=CATALOG_CALLBACKS['restart'])],
                [InlineKeyboardButton("↩️ Главное меню", callback_data="mnc_back")]
            ]
            await safe_edit("✅ Все посты просмотрены!\n\nНажмите 🔄 для сброса", InlineKeyboardMarkup(keyboard))
        else:
            for i, post in enumerate(posts, 1):
                await send_catalog_post(context.bot, query.message.chat_id, post, i, len(posts))
            await query.message.delete()
    
    elif action == 'finish':
        await safe_edit(
            "✅ Просмотр завершён!\n\n"
            "/catalog - начать заново\n"
            "/search - поиск\n"
            "/categoryfollow - подписки"
        )
    
    elif action == 'restart':
        await catalog_service.reset_session(user_id)
        await safe_edit("🔄 Перезапуск!\n\nИспользуйте /catalog")
    
    elif action == 'search':
        context.user_data['catalog_search'] = {'step': 'query'}
        keyboard = [[InlineKeyboardButton("🚫 Отмена", callback_data=CATALOG_CALLBACKS['cancel_search'])]]
        await safe_edit(
            "🔍 **ПОИСК**\n\nВведите слова для поиска:",
            InlineKeyboardMarkup(keyboard)
        )
    
    elif action == 'cancel_search':
        context.user_data.pop('catalog_search', None)
        await safe_edit("❌ Поиск отменён")
    
    elif action == 'click':
        post_id = int(data_parts[1]) if len(data_parts) > 1 else None
        if post_id:
            await catalog_service.increment_clicks(post_id, user_id)
    
    elif action == 'rate':
        if 'catalog_review' not in context.user_data:
            await query.answer("❌ Сессия истекла", show_alert=True)
            return
        
        rating = int(data_parts[1]) if len(data_parts) > 1 else 5
        context.user_data['catalog_review']['rating'] = rating
        context.user_data['catalog_review']['step'] = 'text'
        
        catalog_number = context.user_data['catalog_review'].get('catalog_number')
        stars = "⭐" * rating
        
        keyboard = [[InlineKeyboardButton("⏮️ Отмена", callback_data=CATALOG_CALLBACKS['cancel_review'])]]
        
        await safe_edit(
            f"✅ Оценка: {stars}\n\n"
            f"📝 Пост #{catalog_number}\n\n"
            f"Теперь напишите текст отзыва (макс. 500 символов):",
            InlineKeyboardMarkup(keyboard)
        )
    
    # More handlers continue...

# ============= TEXT HANDLER =============

async def handle_catalog_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text input - OPTIMIZED"""
    user_id = update.effective_user.id
    text = update.message.text
    
    # Search
    if 'catalog_search' in context.user_data:
        query_text = text.strip()
        
        if len(query_text) < 2:
            await update.message.reply_text("❌ Запрос слишком короткий")
            return
        
        posts = await catalog_service.search_posts(query_text, limit=10)
        
        if posts:
            for i, post in enumerate(posts, 1):
                await send_catalog_post(context.bot, update.effective_chat.id, post, i, len(posts))
            
            keyboard = [[InlineKeyboardButton("✅ Готово", callback_data=CATALOG_CALLBACKS['finish'])]]
            await update.message.reply_text(
                f"🔍 Найдено: {len(posts)}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text("❌ Ничего не найдено")
        
        context.user_data.pop('catalog_search', None)
        return
    
    # Review text
    if 'catalog_review' in context.user_data:
        data = context.user_data['catalog_review']
        
        if data.get('step') == 'text':
            review_text = text.strip()[:500]
            
            if len(review_text) < 3:
                await update.message.reply_text("❌ Отзыв слишком короткий")
                return
            
            review_id = await catalog_service.add_review(
                post_id=data.get('post_id'),
                user_id=user_id,
                review_text=review_text,
                rating=data.get('rating', 5),
                username=update.effective_user.username,
                bot=context.bot
            )
            
            if review_id:
                await update.message.reply_text(
                    f"✅ Отзыв сохранён!\n\n"
                    f"#{data.get('catalog_number')}\n"
                    f"Спасибо за ваш отзыв!"
                )
            else:
                await update.message.reply_text("❌ Ошибка")
            
            context.user_data.pop('catalog_review', None)
            return
    
    # Add post
    if 'catalog_add' in context.user_data:
        data = context.user_data['catalog_add']
        step = data.get('step')
        
        if step == 'link':
            if text.startswith('https://t.me/'):
                data['catalog_link'] = text
                
                await update.message.reply_text("⏳ Импортирую медиа...")
                
                media_result = await extract_media_from_link(context.bot, text)
                
                if media_result and media_result.get('success'):
                    data.update({
                        'media_type': media_result['type'],
                        'media_file_id': media_result['file_id'],
                        'media_group_id': media_result.get('media_group_id'),
                        'media_json': media_result.get('media_json', [])
                    })
                    await update.message.reply_text(f"✅ Медиа импортировано: {media_result['type']}")
                
                data['step'] = 'category'
                
                keyboard = [[InlineKeyboardButton(cat, callback_data=f"{CATALOG_CALLBACKS['add_cat']}:{cat}")] 
                           for cat in CATALOG_CATEGORIES.keys()]
                await update.message.reply_text(
                    "📂 Шаг 2/5\n\nВыберите категорию:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await update.message.reply_text("❌ Ссылка должна начинаться с https://t.me/")
        
        elif step == 'name':
            data['name'] = text[:255]
            
            if data.get('media_file_id'):
                data['step'] = 'tags'
                await update.message.reply_text(
                    f"✅ Название: {text[:50]}\n\n"
                    f"#️⃣ Шаг 4/4\n\nТеги через запятую:"
                )
            else:
                data['step'] = 'media'
                await update.message.reply_text(
                    "📸 Шаг 4/5\n\nОтправьте фото/видео или /skip"
                )
        
        elif text == '/skip' and step == 'media':
            data['step'] = 'tags'
            await update.message.reply_text("#️⃣ Шаг 4/4\n\nТеги через запятую:")
        
        elif step == 'tags':
            tags = [t.strip() for t in text.split(',') if t.strip()][:10]
            data['tags'] = tags
            
            post_id = await catalog_service.add_post(
                user_id=user_id,
                catalog_link=data['catalog_link'],
                category=data['category'],
                name=data['name'],
                tags=tags,
                media_type=data.get('media_type'),
                media_file_id=data.get('media_file_id'),
                media_group_id=data.get('media_group_id'),
                media_json=data.get('media_json', [])
            )
            
            if post_id:
                post = await catalog_service.get_post_by_id(post_id)
                await update.message.reply_text(
                    f"✅ Пост #{post.get('catalog_number')} добавлен!\n\n"
                    f"📂 {data['category']}\n"
                    f"📝 {data['name']}\n"
                    f"🏷️ {len(tags)} тегов"
                )
            else:
                await update.message.reply_text("❌ Ошибка")
            
            context.user_data.pop('catalog_add', None)
        
        return

__all__ = [
    'catalog_command',
    'search_command',
    'review_command',
    'categoryfollow_command',
    'addtocatalog_command',
    'addgirltocat_command',
    'addboytocat_command',
    'handle_catalog_callback',
    'handle_catalog_text',
    'handle_catalog_media',
    'CATALOG_CALLBACKS',
]
