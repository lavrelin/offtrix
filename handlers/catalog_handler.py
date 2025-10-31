import logging
import re
from typing import Optional, Dict
from telegram import Update, Bot
from telegram.ext import ContextTypes
from telegram.error import BadRequest, Forbidden
from config import Config
from services.catalog_service import catalog_service, CATALOG_CATEGORIES
from services.cooldown import cooldown_service, CooldownType
from keyboards.catalog_keyboards import (
    CATALOG_CALLBACKS,
    get_navigation_keyboard,
    get_catalog_card_keyboard,
    get_category_keyboard,
    get_rating_keyboard,
    get_cancel_search_keyboard,
    get_cancel_keyboard,
    get_cancel_review_keyboard,
)

logger = logging.getLogger(__name__)

REVIEW_COOLDOWN_HOURS = 8
REVIEW_MAX_LENGTH = 500
REVIEW_MIN_LENGTH = 3

user_reviewed_posts = {}

def safe_markdown(text: str) -> str:
    if not text:
        return ""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    result = str(text)
    for char in special_chars:
        result = result.replace(char, f'\\{char}')
    return result

def check_user_reviewed_post(user_id: int, post_id: int) -> bool:
    if user_id not in user_reviewed_posts:
        return False
    return post_id in user_reviewed_posts[user_id]

def mark_post_as_reviewed(user_id: int, post_id: int):
    if user_id not in user_reviewed_posts:
        user_reviewed_posts[user_id] = set()
    user_reviewed_posts[user_id].add(post_id)
    logger.info(f"User {user_id} reviewed post {post_id}")

async def extract_media_from_link(bot: Bot, telegram_link: str) -> Optional[Dict]:
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
        try:
            await bot.get_chat(chat_id)
        except (Forbidden, BadRequest):
            return {'success': False, 'message': '❌ Бот не имеет доступа к каналу'}
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
                result = {'success': False, 'message': '⚠️ Медиа не найдено'}
            try:
                await bot.delete_message(
                    chat_id=Config.MODERATION_GROUP_ID,
                    message_id=forwarded.message_id
                )
            except:
                pass
            return result
        except (BadRequest, Forbidden):
            return {'success': False, 'message': '❌ Не удалось импортировать медиа'}
    except Exception as e:
        logger.error(f"Media extraction error: {e}")
        return {'success': False, 'message': f'❌ Ошибка: {str(e)[:100]}'}

async def send_catalog_post(bot: Bot, chat_id: int, post: Dict, index: int, total: int) -> bool:
    try:
        catalog_number = post.get('catalog_number', '????')
        card_text = (
            f"📄 Пост {catalog_number}\n"
            f"├ 📁 {post.get('category', 'Не указана')}\n"
            f"├ 📝 {post.get('name', 'Без названия')}\n"
        )
        tags = post.get('tags', [])
        if tags and isinstance(tags, list):
            pattern = r'[^\w\-]'
            clean_tags = [
                f"#{re.sub(pattern, '', str(tag).replace(' ', '_'))}"
                for tag in tags[:3]
                if tag
            ]
            if clean_tags:
                card_text += f"├ 🏷️ {' '.join(clean_tags)}\n"
        review_count = post.get('review_count', 0)
        if review_count >= 5:
            rating = post.get('rating', 0)
            stars = "⭐" * min(5, int(rating))
            card_text += f"├ ⭐ {stars} {rating:.1f} ({review_count})\n"
        else:
            card_text += f"├ ⭐ —\n"
        card_text += f"└ 📍 {index}/{total}"
        keyboard = get_catalog_card_keyboard(post, catalog_number)
        media_type = post.get('media_type')
        media_file_id = post.get('media_file_id')
        if media_type == 'photo' and media_file_id:
            await bot.send_photo(chat_id=chat_id, photo=media_file_id, caption=card_text, reply_markup=keyboard)
        elif media_type == 'video' and media_file_id:
            await bot.send_video(chat_id=chat_id, video=media_file_id, caption=card_text, reply_markup=keyboard)
        else:
            await bot.send_message(chat_id=chat_id, text=card_text, reply_markup=keyboard)
        await catalog_service.increment_views(post['id'])
        return True
    except Exception as e:
        logger.error(f"Error sending catalog post: {e}")
        return False

async def catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    posts = await catalog_service.get_random_posts_mixed(user_id, count=5)
    if not posts:
        await update.message.reply_text("❌ Каталог пуст")
        return
    for i, post in enumerate(posts, 1):
        await send_catalog_post(context.bot, update.effective_chat.id, post, i, len(posts))
    await update.message.reply_text("🔄 Навигация:", reply_markup=get_navigation_keyboard())

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['catalog_search'] = True
    await update.message.reply_text(
        "🔍 Введите запрос для поиска:",
        reply_markup=get_cancel_search_keyboard()
    )

async def addtocatalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data['catalog_add'] = {'step': 'link', 'user_id': user_id}
    await update.message.reply_text(
        "➕ *Добавить в каталог*\n\n"
        "🎯 Шаг 1/5\n\n"
        "Отправьте ссылку на пост (https://t\\.me/\\.\\.\\.):",
        parse_mode='Markdown',
        reply_markup=get_cancel_keyboard()
    )

async def review_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    can_use, remaining = await cooldown_service.check_cooldown(
        user_id=user_id,
        command='review',
        duration=REVIEW_COOLDOWN_HOURS * 3600,
        cooldown_type=CooldownType.NORMAL
    )
    if not can_use:
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        await update.message.reply_text(
            f"⏳ Следующий отзыв через: {hours}ч {minutes}м"
        )
        return
    await update.message.reply_text(
        "⭐ *Оставить отзыв*\n\n"
        "Отправьте номер поста для отзыва",
        parse_mode='Markdown'
    )

async def categoryfollow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔔 Подписки пока недоступны")

async def addgirltocat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админов")
        return
    await update.message.reply_text("👱🏻‍♀️ Отправьте ссылку на профиль девушки")

async def addboytocat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админов")
        return
    await update.message.reply_text("🤵🏼‍♂️ Отправьте ссылку на профиль парня")

async def handle_catalog_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    data_parts = query.data.split(":")
    if data_parts[0].startswith('ch_'):
        action = data_parts[0][3:]
    else:
        action = data_parts[0]
    
    async def safe_edit(text: str, markup=None):
        try:
            if markup:
                await query.edit_message_text(text, reply_markup=markup, parse_mode='MarkdownV2')
            else:
                await query.edit_message_text(text, parse_mode='MarkdownV2')
        except Exception:
            await query.answer(text[:200])
    
    if action == 'next':
        await query.answer()
        posts = await catalog_service.get_random_posts_mixed(user_id, count=5)
        if posts:
            for i, post in enumerate(posts, 1):
                await send_catalog_post(context.bot, query.message.chat_id, post, i, len(posts))
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="🔄 Навигация:",
                reply_markup=get_navigation_keyboard()
            )
        else:
            await query.answer("❌ Больше нет постов", show_alert=True)
    
    elif action == 'finish':
        await catalog_service.end_session(user_id)
        await safe_edit("✅ Сессия завершена")
        await query.answer()
    
    elif action == 'search':
        context.user_data['catalog_search'] = True
        await safe_edit("🔍 Введите запрос:", get_cancel_search_keyboard())
        await query.answer()
    
    elif action == 'csearch':
        context.user_data.pop('catalog_search', None)
        await safe_edit("❌ Поиск отменён")
    
    elif action == 'rate':
        if len(data_parts) < 3:
            await query.answer("❌ Ошибка данных", show_alert=True)
            return
        post_id = int(data_parts[1])
        catalog_number = data_parts[2]
        if check_user_reviewed_post(user_id, post_id):
            await query.answer("❌ Вы уже оценили эту карточку", show_alert=True)
            return
        can_use, remaining = await cooldown_service.check_cooldown(
            user_id=user_id,
            command='review',
            duration=REVIEW_COOLDOWN_HOURS * 3600,
            cooldown_type=CooldownType.NORMAL
        )
        if not can_use:
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            await query.answer(f"⏳ Следующий отзыв через: {hours}ч {minutes}м", show_alert=True)
            return
        context.user_data['catalog_review'] = {
            'post_id': post_id,
            'catalog_number': catalog_number,
            'step': 'rating'
        }
        await safe_edit(
            f"⭐ Оценка #{catalog_number}\n\nВыберите рейтинг:",
            get_rating_keyboard(post_id, catalog_number)
        )
        await query.answer()
        rating = int(data_parts[1]) if len(data_parts) > 1 and data_parts[1].isdigit() else None
        if rating and 1 <= rating <= 5:
            context.user_data['catalog_review']['rating'] = rating
            context.user_data['catalog_review']['step'] = 'text'
            await safe_edit(
                f"✅ Рейтинг: {'⭐' * rating}\n\nНапишите отзыв:",
                get_cancel_review_keyboard()
            )
    
    elif action == 'crev':
        context.user_data.pop('catalog_review', None)
        await safe_edit("❌ Отзыв отменён")
    
    elif action == 'cancel':
        context.user_data.pop('catalog_add', None)
        await safe_edit("❌ Добавление отменено")
    
    elif action == 'addcat':
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

async def handle_catalog_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if 'catalog_search' in context.user_data:
        query_text = text.strip()
        if len(query_text) < 2:
            await update.message.reply_text("❌ Запрос слишком короткий")
            return
        posts = await catalog_service.search_posts(query_text, limit=10)
        if posts:
            for i, post in enumerate(posts, 1):
                await send_catalog_post(context.bot, update.effective_chat.id, post, i, len(posts))
            await update.message.reply_text(
                f"🔍 Найдено: {len(posts)} постов",
                reply_markup=get_navigation_keyboard()
            )
        else:
            await update.message.reply_text("❌ Ничего не найдено")
        context.user_data.pop('catalog_search', None)
        return
    
    if 'catalog_review' in context.user_data:
        data = context.user_data['catalog_review']
        if data.get('step') == 'text':
            review_text = text.strip()[:REVIEW_MAX_LENGTH]
            if len(review_text) < REVIEW_MIN_LENGTH:
                await update.message.reply_text(f"❌ Отзыв слишком короткий (минимум {REVIEW_MIN_LENGTH} символа)")
                return
            post_id = data.get('post_id')
            if check_user_reviewed_post(user_id, post_id):
                await update.message.reply_text("❌ Вы уже оставили отзыв на эту карточку")
                context.user_data.pop('catalog_review', None)
                return
            review_id = await catalog_service.add_review(
                post_id=post_id,
                user_id=user_id,
                review_text=review_text,
                rating=data.get('rating', 5),
                username=update.effective_user.username,
                bot=context.bot
            )
            if review_id:
                mark_post_as_reviewed(user_id, post_id)
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
                logger.info(f"User {user_id} left review on post {post_id}")
            else:
                await update.message.reply_text("❌ Ошибка при сохранении отзыва")
            context.user_data.pop('catalog_review', None)
            return
    
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
                keyboard = get_category_keyboard(list(CATALOG_CATEGORIES.keys()))
                await update.message.reply_text(
                    "📂 Шаг 2/5\n\nВыберите категорию:",
                    reply_markup=keyboard
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
                await update.message.reply_text("📸 Шаг 4/5\n\nОтправьте фото/видео или /skip")
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

async def handle_catalog_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'catalog_add' in context.user_data:
        data = context.user_data['catalog_add']
        if data.get('step') == 'media':
            if update.message.photo:
                data['media_type'] = 'photo'
                data['media_file_id'] = update.message.photo[-1].file_id
            elif update.message.video:
                data['media_type'] = 'video'
                data['media_file_id'] = update.message.video.file_id
            else:
                await update.message.reply_text("❌ Отправьте фото или видео")
                return
            data['step'] = 'tags'
            await update.message.reply_text("#️⃣ Шаг 5/5\n\nТеги через запятую:")

__all__ = [
    'catalog_command',
    'search_command',
    'addtocatalog_command',
    'review_command',
    'categoryfollow_command',
    'addgirltocat_command',
    'addboytocat_command',
    'handle_catalog_callback',
    'handle_catalog_text',
    'handle_catalog_media',
    'CATALOG_CALLBACKS',
]
