import logging
import re
from typing import Optional, Dict
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ContextTypes
from telegram.error import TelegramError, BadRequest, Forbidden
from config import Config
from services.catalog_service import catalog_service, CATALOG_CATEGORIES
from services.cooldown import cooldown_service, CooldownType

logger = logging.getLogger(__name__)

# ============= CALLBACK PREFIXES (УНИКАЛЬНЫЕ V8) =============
CATALOG_CALLBACKS = {
    'next': 'ctpc_next',
    'finish': 'ctpc_finish',
    'restart': 'ctpc_restart',
    'search': 'ctpc_search',
    'cancel_search': 'ctpc_cancel_search',
    'category': 'ctpc_cat',
    'click': 'ctpc_click',
    'add_cat': 'ctpc_add_cat',
    'rate': 'ctpc_rate',
    'cancel_review': 'ctpc_cancel_review',
    'cancel': 'ctpc_cancel',
    'cancel_top': 'ctpc_cancel_top',
    'follow_menu': 'ctpc_follow_menu',
    'follow_cat': 'ctpc_follow_cat',
    'my_follows': 'ctpc_my_follows',
    'unfollow': 'ctpc_unfollow',
    'unfollow_all': 'ctpc_unfollow_all',
    'reviews_menu': 'ctpc_reviews_menu',
    'view_reviews': 'ctpc_view_reviews',
    'write_review': 'ctpc_write_review',
    'close_menu': 'ctpc_close_menu',
}

# ============= SETTINGS =============
REVIEW_COOLDOWN_HOURS = 8  # 8 часов кулдаун на ВСЕ отзывы
REVIEW_MAX_LENGTH = 500
REVIEW_MIN_LENGTH = 3

# ============= REVIEW TRACKING =============
# Хранит информацию о том, кто и какие карточки уже оценил
user_reviewed_posts = {}  # {user_id: set(post_ids)}

def safe_markdown(text: str) -> str:
    """Безопасное экранирование для Markdown"""
    if not text:
        return ""
    
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    result = str(text)
    for char in special_chars:
        result = result.replace(char, f'\\{char}')
    
    return result

def check_user_reviewed_post(user_id: int, post_id: int) -> bool:
    """
    Проверка: оставлял ли пользователь отзыв на эту карточку
    Returns: True если уже оставлял
    """
    if user_id not in user_reviewed_posts:
        return False
    
    return post_id in user_reviewed_posts[user_id]

def mark_post_as_reviewed(user_id: int, post_id: int):
    """Отметить что пользователь оставил отзыв на карточку"""
    if user_id not in user_reviewed_posts:
        user_reviewed_posts[user_id] = set()
    
    user_reviewed_posts[user_id].add(post_id)
    logger.info(f"User {user_id} marked as reviewed post {post_id}")

# ============= NAVIGATION KEYBOARD =============

def get_navigation_keyboard() -> InlineKeyboardMarkup:
    """Получить постоянную клавиатуру навигации"""
    keyboard = [
        [
            InlineKeyboardButton("➡️ Еще", callback_data=CATALOG_CALLBACKS['next']),
            InlineKeyboardButton("⏹️ Стоп", callback_data=CATALOG_CALLBACKS['finish'])
        ],
        [InlineKeyboardButton("🔍 Поиск", callback_data=CATALOG_CALLBACKS['search'])]
    ]
    return InlineKeyboardMarkup(keyboard)
# ============= MEDIA EXTRACTION =============

async def extract_media_from_link(bot: Bot, telegram_link: str) -> Optional[Dict]:
    """Извлечение медиа из Telegram поста"""
    try:
        if not telegram_link or 't.me/' not in telegram_link:
            return {'success': False, 'message': '❌ Неверная ссылка'}
        
        match = re.search(r't\.me/([^/]+)/(\d+)', telegram_link)
        if not match:
            return {'success': False, 'message': '❌ Не удалось извлечь данные'}
        
        channel_username = match.group(1).lstrip('@')
        message_id = int(match.group(2))
        
        if channel_username.startswith('-'):
            chat_id = int(channel_username)
        elif channel_username.isdigit():
            chat_id = int(f"-100{channel_username}")
        else:
            chat_id = f"@{channel_username}"
        
        logger.info(f"📥 Extracting from: {chat_id}/{message_id}")
        
        try:
            await bot.get_chat(chat_id)
        except (Forbidden, BadRequest) as e:
            logger.error(f"❌ No access: {e}")
            return {
                'success': False,
                'message': '❌ Бот не имеет доступа к каналу'
            }
        
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
                    'message': '⚠️ Медиа не найдено в посте'
                }
            
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
                'message': '❌ Не удалось импортировать медиа'
            }
            
    except Exception as e:
        logger.error(f"❌ Media extraction error: {e}", exc_info=True)
        return {'success': False, 'message': f'❌ Ошибка: {str(e)[:100]}'}

# ============= SEND POST WITH MEDIA =============

async def send_catalog_post(bot: Bot, chat_id: int, post: Dict, index: int, total: int) -> bool:
    try:
        catalog_number = post.get('catalog_number', '????')
        
        card_text = (
            f"┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            f"┃          🏷️ #{catalog_number}           ┃\n"
            f"┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫\n"
            f"┃ 📂 {post.get('category', 'Не указана'):<25} ┃\n"
            f"┃ 📝 {post.get('name', 'Без названия'):<25} ┃\n"
            f"┣───────────────────────────────┫\n"
        )
        
        tags = post.get('tags', [])
        if tags:
            clean_tags = [f"#{re.sub(r'[^\w\-]', '', str(tag).replace(' ', '_'))}" for tag in tags[:3]]
            tags_line = ' '.join(clean_tags)
            if len(tags_line) > 28: tags_line = tags_line[:25] + "..."
            card_text += f"┃ 🏷️ {tags_line:<25} ┃\n"
        
        review_count = post.get('review_count', 0)
        if review_count >= 3:
            rating = post.get('rating', 0)
            stars = "⭐" * min(5, int(rating))
            card_text += f"┃ ⭐ {stars} {rating:.1f} ({review_count}){' ' * 10} ┃\n"
        else:
            card_text += f"┃ ⭐ —{' ' * 25} ┃\n"
        
        card_text += f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
        card_text += f"📍 {index}/{total}"

        keyboard = [[
            InlineKeyboardButton("🌐 Перейти", url=post.get('catalog_link', '#')),
            InlineKeyboardButton("💬 Отзывы", callback_data=f"{CATALOG_CALLBACKS['reviews_menu']}:{post.get('id')}")
        ]]
        
        # Остальной код отправки без изменений...
        
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
                        reply_markup=reply_markup
                    )
                    await catalog_service.increment_views(post.get('id'), chat_id)
                    return True
                except TelegramError:
                    pass
        
        await bot.send_message(
            chat_id=chat_id,
            text=card_text,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
        await catalog_service.increment_views(post.get('id'), chat_id)
        return True
        
    except Exception as e:
        logger.error(f"Error sending catalog post: {e}")
        return False

# ============= COMMANDS =============

async def catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр каталога - /catalog"""
    user_id = update.effective_user.id
    posts = await catalog_service.get_random_posts_mixed(user_id, count=5)
    
    if not posts:
        keyboard = [
            [InlineKeyboardButton("🔄 Заново", callback_data=CATALOG_CALLBACKS['restart'])],
            [InlineKeyboardButton("📋 Меню", callback_data="mnc_back")]
        ]
        await update.message.reply_text(
            "📭 Публикаций нет\n\nНажмите 🔄 для обновления",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    for i, post in enumerate(posts, 1):
        await send_catalog_post(context.bot, update.effective_chat.id, post, i, len(posts))
    
    await update.message.reply_text(
        f"📊 Показано: {len(posts)}",
        reply_markup=get_navigation_keyboard()
    )

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поиск в каталоге - /search"""
    context.user_data['catalog_search'] = {'step': 'query'}
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=CATALOG_CALLBACKS['cancel_search'])]]
    
    await update.message.reply_text(
        "🔍 *Поиск по каталогу*\n\n"
        "Введите запрос для поиска:\n"
        "• Название\n"
        "• Теги\n"
        "• Категория\n\n"
        "Например: *массаж*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def review_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Оставить отзыв - /review [id]"""
    user_id = update.effective_user.id
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            "⭐ *Оценка поста*\n\n"
            "Формат: `/review [номер]`\n"
            "Пример: `/review 1234`",
            parse_mode='Markdown'
        )
        return
    
    catalog_number = int(context.args[0])
    post = await catalog_service.get_post_by_number(catalog_number)
    
    if not post:
        await update.message.reply_text(f"❌ Пост #{catalog_number} не найден")
        return
    
    post_id = post['id']
    
    if check_user_reviewed_post(user_id, post_id):
        await update.message.reply_text(f"❌ Вы уже оценили этот пост")
        return
    
    can_review, remaining = await cooldown_service.check_cooldown(
        user_id=user_id,
        command='review',
        duration=REVIEW_COOLDOWN_HOURS * 3600,
        cooldown_type=CooldownType.NORMAL
    )
    
    if not can_review:
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        await update.message.reply_text(f"⏳ Следующий отзыв через {hours}ч {minutes}м")
        return
    
    context.user_data['catalog_review'] = {
        'post_id': post_id,
        'catalog_number': catalog_number,
        'step': 'rating'
    }
    
    keyboard = [
        [
            InlineKeyboardButton("1 ⭐", callback_data=f"{CATALOG_CALLBACKS['rate']}:1"),
            InlineKeyboardButton("2 ⭐⭐", callback_data=f"{CATALOG_CALLBACKS['rate']}:2"),
            InlineKeyboardButton("3 ⭐⭐⭐", callback_data=f"{CATALOG_CALLBACKS['rate']}:3")
        ],
        [
            InlineKeyboardButton("4 ⭐⭐⭐⭐", callback_data=f"{CATALOG_CALLBACKS['rate']}:4"),
            InlineKeyboardButton("5 ⭐⭐⭐⭐⭐", callback_data=f"{CATALOG_CALLBACKS['rate']}:5")
        ],
        [InlineKeyboardButton("↩️ Назад", callback_data=CATALOG_CALLBACKS['cancel_review'])]
    ]
    
    await update.message.reply_text(
        f"⭐ *Оценка поста #{catalog_number}*\n\n"
        f"📝 {safe_markdown(post.get('name', 'Без названия'))}\n\n"
        "Выберите оценку:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def categoryfollow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление подписками - /categoryfollow"""
    user_id = update.effective_user.id
    
    try:
        subscriptions = await catalog_service.get_user_subscriptions(user_id)
        
        text = "🔔 *Мои подписки*\n\n"
        
        if subscriptions:
            text += "📋 Ваши категории:\n"
            for sub in subscriptions:
                text += f"• {sub.get('category')}\n"
            text += "\n"
        else:
            text += "📭 Нет активных подписок\n\n"
        
        text += "Выберите действие:"
        
        keyboard = [
            [InlineKeyboardButton("➕ Подписаться", callback_data=CATALOG_CALLBACKS['follow_menu'])],
            [InlineKeyboardButton("📋 Мои подписки", callback_data=CATALOG_CALLBACKS['my_follows'])]
        ]
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error in categoryfollow: {e}")
        await update.message.reply_text("❌ Ошибка загрузки подписок")
        
async def addtocatalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить в каталог - /addtocatalog"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    context.user_data['catalog_add'] = {'step': 'link'}
    keyboard = [[InlineKeyboardButton("🚫 Отмена", callback_data=CATALOG_CALLBACKS['cancel'])]]
    
    await update.message.reply_text(
        "🛤️ *ДОБАВЛЕНИЕ В КАТАЛОГ*\n\nШаг 1/5\n\n"
        "🔗 Ссылка на пост:\n"
        "Пример: https://t.me/channel/123",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def addgirltocat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить в TopGirls - /addgirltocat"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админов")
        return
    
    context.user_data['catalog_add_top'] = {'step': 'link', 'category': '👱🏻‍♀️ TopGirls'}
    keyboard = [[InlineKeyboardButton("🚫 Отмена", callback_data=CATALOG_CALLBACKS['cancel_top'])]]
    
    await update.message.reply_text(
        "💃 *ДОБАВЛЕНИЕ В TOPGIRLS*\n\nШаг 1/3\n\n"
        "👩🏼‍💼 Ссылка на оригинальный пост:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def addboytocat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить в TopBoys - /addboytocat"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админов")
        return
    
    context.user_data['catalog_add_top'] = {'step': 'link', 'category': '🤵🏼‍♂️ TopBoys'}
    keyboard = [[InlineKeyboardButton("🚫 Отмена", callback_data=CATALOG_CALLBACKS['cancel_top'])]]
    
    await update.message.reply_text(
        "🤵 *ДОБАВЛЕНИЕ В TOPBOYS*\n\nШаг 1/3\n\n"
        "🧏🏻‍♂️ Ссылка на оригинальный пост:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============= MEDIA HANDLER =============

async def handle_catalog_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Обработка загрузки медиа"""
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
    """Обработка всех callback каталога"""
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split(":")
    
    if data_parts[0].startswith('ctpc_'):
        action = data_parts[0][5:]
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
            "🔍 *ПОИСК*\n\nВведите слова для поиска:",
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
            f"📝 Пост \\#{catalog_number}\n\n"
            f"Теперь напишите текст отзыва \\({REVIEW_MIN_LENGTH}\\-{REVIEW_MAX_LENGTH} символов\\):",
            InlineKeyboardMarkup(keyboard)
        )
    
    elif action == 'cancel_review':
        context.user_data.pop('catalog_review', None)
        await safe_edit("❌ Отзыв отменён")
    
    elif action == 'cancel':
        context.user_data.pop('catalog_add', None)
        await safe_edit("❌ Добавление отменено")
    
    elif action == 'cancel_top':
        context.user_data.pop('catalog_add_top', None)
        await safe_edit("❌ Добавление отменено")
    
    elif action == 'add_cat':
        if 'catalog_add' not in context.user_data:
            await query.answer("❌ Сессия истекла", show_alert=True)
            return
        
        category = ":".join(data_parts[1:]) if len(data_parts) > 1 else "Общее"
        context.user_data['catalog_add']['category'] = category
        context.user_data['catalog_add']['step'] = 'name'
        
        safe_category = safe_markdown(category)
        
        await safe_edit(
            f"✅ Категория: {safe_category}\n\n"
            f"📝 Шаг 3/5\n\nНазвание \\(макс\\. 255 символов\\):"
        )

# ============= TEXT HANDLER =============

async def handle_catalog_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстового ввода"""
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
            
            # ПОСТОЯННАЯ НАВИГАЦИЯ
            await update.message.reply_text(
                f"🔍 Найдено: {len(posts)} постов",
                reply_markup=get_navigation_keyboard()
            )
        else:
            await update.message.reply_text("❌ Ничего не найдено")
        
        context.user_data.pop('catalog_search', None)
        return
    
    # Review text
    if 'catalog_review' in context.user_data:
        data = context.user_data['catalog_review']
        
        if data.get('step') == 'text':
            review_text = text.strip()[:REVIEW_MAX_LENGTH]
            
            if len(review_text) < REVIEW_MIN_LENGTH:
                await update.message.reply_text(f"❌ Отзыв слишком короткий (минимум {REVIEW_MIN_LENGTH} символа)")
                return
            
            post_id = data.get('post_id')
            
            # Проверка что не оставлял отзыв на эту карточку
            if check_user_reviewed_post(user_id, post_id):
                await update.message.reply_text("❌ Вы уже оставили отзыв на эту карточку")
                context.user_data.pop('catalog_review', None)
                return
            
            # Добавляем отзыв
            review_id = await catalog_service.add_review(
                post_id=post_id,
                user_id=user_id,
                review_text=review_text,
                rating=data.get('rating', 5),
                username=update.effective_user.username,
                bot=context.bot
            )
            
            if review_id:
                # ОТМЕЧАЕМ что пользователь оставил отзыв на эту карточку
                mark_post_as_reviewed(user_id, post_id)
                
                # УСТАНАВЛИВАЕМ КУЛДАУН 8 часов на ВСЕ отзывы
                await cooldown_service.set_cooldown(
                    user_id=user_id,
                    command='review',
                    duration=REVIEW_COOLDOWN_HOURS * 3600,
                    cooldown_type=CooldownType.NORMAL
                )
                
                await update.message.reply_text(
                    f"✅ Отзыв сохранён!\n\n"
                    f"#{data.get('catalog_number')}\n"
                    f"Спасибо за ваш отзыв!\n\n"
                    f"⏳ Следующий отзыв можно оставить через {REVIEW_COOLDOWN_HOURS}ч"
                )
                
                logger.info(f"User {user_id} left review on post {post_id} with {REVIEW_COOLDOWN_HOURS}h cooldown")
            else:
                await update.message.reply_text("❌ Ошибка при сохранении отзыва")
            
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
                await update.message.reply_text("❌ Ссылка должна начинаться с https://t\\.me/", parse_mode='Markdown')
        
        elif step == 'name':
            data['name'] = text[:255]
            
            if data.get('media_file_id'):
                data['step'] = 'tags'
                safe_text = safe_markdown(text[:50])
                await update.message.reply_text(
                    f"✅ Название: {safe_text}\n\n"
                    f"#️⃣ Шаг 4/4\n\nТеги через запятую:",
                    parse_mode='MarkdownV2'
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
                await update.message.reply_text("❌ Ошибка при добавлении")
            
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
