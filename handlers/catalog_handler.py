# -*- coding: utf-8 -*-
"""
Handler для каталога услуг - ПОЛНАЯ ВЕРСИЯ 5.0

Исправления v5.0:
- ✅ Реклама: можно добавлять карточку ИЛИ внешнюю ссылку
- ✅ Отзывы: исправлена обработка текста после звезд
- ✅ Приоритеты: указание по ID, очистка, редактирование
- ✅ Новая команда /admincataloginfo
- ✅ Улучшенные команды управления рекламой

Версия: 5.0.0
Дата: 25.10.2025
"""
import logging
import re
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from config import Config
from services.catalog_service import catalog_service, CATALOG_CATEGORIES

logger = logging.getLogger(__name__)


# ============= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =============

async def extract_media_from_link(bot: Bot, telegram_link: str) -> Optional[Dict]:
    """Автоматический импорт медиа из поста с улучшенным логированием"""
    try:
        if not telegram_link or 't.me/' not in telegram_link:
            logger.warning(f"Invalid link format: {telegram_link}")
            return {
                'success': False,
                'message': '❌ Неверная ссылка'
            }
        
        match = re.search(r't\.me/([^/]+)/(\d+)', telegram_link)
        if not match:
            logger.warning(f"Could not parse link: {telegram_link}")
            return {
                'success': False,
                'message': '❌ Не удалось извлечь данные из ссылки'
            }
        
        channel_username = match.group(1)
        message_id = int(match.group(2))
        
        logger.info(f"Parsing link: channel={channel_username}, msg_id={message_id}")
        
        if channel_username.startswith('@'):
            channel_username = channel_username[1:]
        
        if channel_username.startswith('-100'):
            chat_id = int(channel_username)
        else:
            chat_id = f"@{channel_username}"
        
        logger.info(f"Attempting to fetch from chat_id={chat_id}, message_id={message_id}")
        
        try:
            logger.info("Method 1: Trying forwardMessage...")
            forwarded = await bot.forward_message(
                chat_id=bot.id,
                from_chat_id=chat_id,
                message_id=message_id
            )
            
            result = None
            if forwarded.photo:
                result = {
                    'success': True,
                    'type': 'photo',
                    'file_id': forwarded.photo[-1].file_id,
                    'media_group_id': forwarded.media_group_id,
                    'media_json': [forwarded.photo[-1].file_id],
                    'message': '✅ Фото импортировано'
                }
                logger.info(f"✅ Photo imported: {result['file_id'][:20]}...")
            elif forwarded.video:
                result = {
                    'success': True,
                    'type': 'video',
                    'file_id': forwarded.video.file_id,
                    'media_group_id': forwarded.media_group_id,
                    'media_json': [forwarded.video.file_id],
                    'message': '✅ Видео импортировано'
                }
                logger.info(f"✅ Video imported: {result['file_id'][:20]}...")
            elif forwarded.document:
                result = {
                    'success': True,
                    'type': 'document',
                    'file_id': forwarded.document.file_id,
                    'media_group_id': forwarded.media_group_id,
                    'media_json': [forwarded.document.file_id],
                    'message': '✅ Документ импортирован'
                }
                logger.info(f"✅ Document imported: {result['file_id'][:20]}...")
            elif forwarded.animation:
                result = {
                    'success': True,
                    'type': 'animation',
                    'file_id': forwarded.animation.file_id,
                    'media_group_id': forwarded.media_group_id,
                    'media_json': [forwarded.animation.file_id],
                    'message': '✅ Анимация импортирована'
                }
                logger.info(f"✅ Animation imported: {result['file_id'][:20]}...")
            else:
                logger.warning("No media found in forwarded message")
                result = {
                    'success': False,
                    'message': '⚠️ Медиа не найдено в посте'
                }
            
            try:
                await bot.delete_message(chat_id=bot.id, message_id=forwarded.message_id)
                logger.info("Cleaned up forwarded message")
            except Exception as del_error:
                logger.warning(f"Could not delete forwarded message: {del_error}")
            
            return result
            
        except TelegramError as forward_error:
            error_text = str(forward_error).lower()
            logger.error(f"Method 1 failed: {forward_error}")
            
            if 'forbidden' in error_text or 'chat not found' in error_text:
                return {
                    'success': False,
                    'message': (
                        '❌ Бот не может получить доступ к каналу\n\n'
                        '**Решение:**\n'
                        '1. Добавьте бота в канал как администратора\n'
                        '2. Или загрузите медиа вручную\n'
                        '3. Продолжайте заполнение, медиа можно добавить позже'
                    )
                }
            elif 'message to forward not found' in error_text:
                return {
                    'success': False,
                    'message': '❌ Сообщение не найдено (удалено или неверный ID)'
                }
            else:
                return {
                    'success': False,
                    'message': f'⚠️ Не удалось импортировать медиа\n\nОшибка: {str(forward_error)[:100]}'
                }
        
    except Exception as e:
        logger.error(f"Critical error in extract_media_from_link: {e}", exc_info=True)
        return {
            'success': False,
            'message': f'❌ Ошибка импорта: {str(e)[:100]}'
        }


async def send_catalog_post_with_media(bot: Bot, chat_id: int, post: Dict, index: int, total: int) -> bool:
    """Отправка карточки каталога С НОВЫМ ФОРМАТОМ"""
    try:
        catalog_number = post.get('catalog_number', '????')
        card_text = f"#️⃣ **Пост {catalog_number}**\n\n"
        card_text += f"📂 {post.get('category', 'Не указана')}\n"
        card_text += f"ℹ️ {post.get('name', 'Без названия')}\n\n"
        
        tags = post.get('tags', [])
        if tags and isinstance(tags, list):
            tags_formatted = []
            for tag in tags[:5]:
                if tag:
                    clean_tag = re.sub(r'[^\w\-]', '', str(tag).replace(' ', '_'))
                    if clean_tag:
                        tags_formatted.append(f"#{clean_tag}")
            
            if tags_formatted:
                card_text += f"{' '.join(tags_formatted)}\n"
        
        review_count = post.get('review_count', 0)
        if review_count >= 10:
            rating = post.get('rating', 0)
            stars = "⭐" * int(rating)
            card_text += f"**Rating**: {stars} {rating:.1f} ({review_count} отзывов)\n"
        else:
            card_text += f"**Rating**: -\n"
        
        keyboard = [
            [
                InlineKeyboardButton("➡️ Перейти", url=post.get('catalog_link', '#'), callback_data=f"catalog:click:{post.get('id')}"),
                InlineKeyboardButton("🧑‍🧒‍🧒 Отзывы", callback_data=f"catalog:reviews_menu:{post.get('id')}")
            ],
            [
                InlineKeyboardButton("🆕 Подписаться", callback_data=f"catalog:subscribe_menu:{post.get('category')}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        media_type = post.get('media_type')
        media_file_id = post.get('media_file_id')
        sent = False
        
        if media_file_id and media_type:
            try:
                if media_type == 'photo':
                    await bot.send_photo(chat_id=chat_id, photo=media_file_id, caption=card_text, reply_markup=reply_markup, parse_mode='Markdown')
                elif media_type == 'video':
                    await bot.send_video(chat_id=chat_id, video=media_file_id, caption=card_text, reply_markup=reply_markup, parse_mode='Markdown')
                elif media_type == 'document':
                    await bot.send_document(chat_id=chat_id, document=media_file_id, caption=card_text, reply_markup=reply_markup, parse_mode='Markdown')
                elif media_type == 'animation':
                    await bot.send_animation(chat_id=chat_id, animation=media_file_id, caption=card_text, reply_markup=reply_markup, parse_mode='Markdown')
                sent = True
            except TelegramError:
                sent = False
        
        if not sent:
            await bot.send_message(chat_id=chat_id, text=card_text, reply_markup=reply_markup, parse_mode='Markdown', disable_web_page_preview=True)
        
        await catalog_service.increment_views(post.get('id'), chat_id)
        
        return True
    except Exception as e:
        logger.error(f"Error sending catalog post: {e}")
        return False


async def handle_catalog_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Обработка загрузки медиа при добавлении поста"""
    if 'catalog_add' not in context.user_data or context.user_data['catalog_add'].get('step') != 'media':
        return False
    
    data = context.user_data['catalog_add']
    media_type = media_file_id = None
    
    if update.message.photo:
        media_type, media_file_id = 'photo', update.message.photo[-1].file_id
    elif update.message.video:
        media_type, media_file_id = 'video', update.message.video.file_id
    elif update.message.document:
        media_type, media_file_id = 'document', update.message.document.file_id
    elif update.message.animation:
        media_type, media_file_id = 'animation', update.message.animation.file_id
    
    if media_type and media_file_id:
        data.update({
            'media_type': media_type,
            'media_file_id': media_file_id,
            'media_group_id': update.message.media_group_id,
            'media_json': [media_file_id],
            'step': 'tags'
        })
        await update.message.reply_text(
            f"✅ Медиа: {media_type}\n\n"
            "#️⃣ Теги через запятую (до 10):\n"
            "Пример: маникюр, гель-лак"
        )
        return True
    return False


async def notify_subscribers_about_new_post(bot: Bot, post_id: int, category: str):
    """Уведомить подписчиков о новом посте в категории"""
    try:
        subscribers = await catalog_service.get_category_subscribers(category)
        
        if not subscribers:
            logger.info(f"No subscribers for category {category}")
            return
        
        post = await catalog_service.get_post_by_id(post_id)
        
        if not post:
            logger.error(f"Post {post_id} not found for notification")
            return
        
        catalog_number = post.get('catalog_number', '????')
        
        text = (
            f"🆕 **НОВЫЙ ПОСТ В КАТЕГОРИИ**\n\n"
            f"#️⃣ Пост {catalog_number}\n"
            f"📂 {category}\n"
            f"📑 {post.get('name', 'Без названия')}\n\n"
            f"⛓️‍💥 Перейти: {post.get('catalog_link')}\n\n"
            f"Используйте /catalog для просмотра"
        )
        
        keyboard = [
            [InlineKeyboardButton("🙄 Посмотреть", url=post.get('catalog_link'))],
            [InlineKeyboardButton("🔕 Отписаться", callback_data=f"catalog:unfollow:{category}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        success_count = 0
        for user_id in subscribers:
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to notify user {user_id}: {e}")
        
        logger.info(f"Notified {success_count}/{len(subscribers)} subscribers about post {post_id} in {category}")
        
    except Exception as e:
        logger.error(f"Error notifying subscribers: {e}")


# ============= ОСНОВНЫЕ КОМАНДЫ =============

async def catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр каталога - /catalog (смешанная выдача 4+1)"""
    user_id = update.effective_user.id
    count = 5
    
    posts = await catalog_service.get_random_posts_mixed(user_id, count=count)
    
    if not posts:
        keyboard = [
            [InlineKeyboardButton("🔄 Начать заново", callback_data="catalog:restart")],
            [InlineKeyboardButton("↩️ Главное меню", callback_data="menu:back")]
        ]
        await update.message.reply_text(
            "📂 Актуальных публикаций больше нет\n\n"
            "Нажмите 🔄 'Начать заново'",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    for i, post in enumerate(posts, 1):
        await send_catalog_post_with_media(context.bot, update.effective_chat.id, post, i, len(posts))
    
    keyboard = [
        [
            InlineKeyboardButton(f"🔀 Следующие {count}", callback_data="catalog:next"),
            InlineKeyboardButton("⏹️ Закончить", callback_data="catalog:finish")
        ],
        [InlineKeyboardButton("🔍 Поиск", callback_data="catalog:search")]
    ]
    await update.message.reply_text(
        f"🔃 Показано: {len(posts)}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поиск только по словам и тегам - /search"""
    context.user_data['catalog_search'] = {'step': 'query'}
    
    keyboard = [[InlineKeyboardButton("🚫 Отмена", callback_data="catalog:cancel_search")]]
    
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
    """Отзыв - /review [id]"""
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
            InlineKeyboardButton("⭐", callback_data="catalog:rate:1"),
            InlineKeyboardButton("⭐⭐", callback_data="catalog:rate:2"),
            InlineKeyboardButton("⭐⭐⭐", callback_data="catalog:rate:3")
        ],
        [
            InlineKeyboardButton("⭐⭐⭐⭐", callback_data="catalog:rate:4"),
            InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data="catalog:rate:5")
        ],
        [InlineKeyboardButton("⏮️ Отмена", callback_data="catalog:cancel_review")]
    ]
    
    await update.message.reply_text(
        f"🌟 **ОЦЕНКА ПОСТА #{catalog_number}**\n\n"
        f"📝 {post.get('name', 'Без названия')}\n\n"
        "Выберите оценку:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def categoryfollow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление подписками - /categoryfollow"""
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
            [InlineKeyboardButton("✅ Подписаться на категорию", callback_data="catalog:follow_menu")],
            [InlineKeyboardButton("☑️ Мои подписки", callback_data="catalog:my_follows")]
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
    """Добавить в каталог - /addtocatalog"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    context.user_data['catalog_add'] = {'step': 'link'}
    keyboard = [[InlineKeyboardButton("🚗 Отмена", callback_data="catalog:cancel")]]
    await update.message.reply_text(
        "🛤️ **ДОБАВЛЕНИЕ**\n\nШаг 1/5\n\n"
        "🫟 Ссылка на пост:\n"
        "Пример: https://t.me/channel/123",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def addgirltocat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить в категорию TopGirls - /addgirltocat"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    context.user_data['catalog_add_top'] = {
        'step': 'link',
        'category': '👱🏻‍♀️ TopGirls'
    }
    keyboard = [[InlineKeyboardButton("🚗 Отмена", callback_data="catalog:cancel_top")]]
    await update.message.reply_text(
        "💃 **ДОБАВЛЕНИЕ В TOPGIRLS**\n\n"
        "Шаг 1/3\n\n"
        "👩🏼‍💼 Ссылка на оригинальный пост:\n"
        "Пример: https://t.me/channel/123",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def addboytocat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить в категорию TopBoys - /addboytocat"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    context.user_data['catalog_add_top'] = {
        'step': 'link',
        'category': '🤵🏼‍♂️ TopBoys'
    }
    keyboard = [[InlineKeyboardButton("🚗 Отмена", callback_data="catalog:cancel_top")]]
    await update.message.reply_text(
        "🤵 **ДОБАВЛЕНИЕ В TOPBOYS**\n\n"
        "Шаг 1/3\n\n"
        "🧏🏻‍♂️ Ссылка на оригинальный пост:\n"
        "Пример: https://t.me/channel/123",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def edit_catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Редактирование записи - /catalogedit [id]"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            "🧑🏼‍💻 Use: `/catalogedit [номер]`\n\n"
            "Пример: `/catalogedit 1234`",
            parse_mode='Markdown'
        )
        return
    
    catalog_number = int(context.args[0])
    post = await catalog_service.get_post_by_number(catalog_number)
    
    if not post:
        await update.message.reply_text(f"❌ Пост #{catalog_number} не найден")
        return
    
    context.user_data['catalog_edit'] = {'post_id': post['id'], 'post_data': post, 'catalog_number': catalog_number}
    
    text = (
        f"⚙️ **Редактирование поста #{catalog_number}**\n\n"
        f"📂 Категория: {post.get('category')}\n"
        f"📇 Название: {post.get('name')}\n"
        f"#️⃣ Теги: {', '.join(post.get('tags', []))}\n"
        f"🔗 Ссылка: {post.get('catalog_link')}\n\n"
        "Что изменить?"
    )
    
    keyboard = [
        [InlineKeyboardButton("🗂️ Категорию", callback_data="catalog:edit:category")],
        [InlineKeyboardButton("💁🏻 Название", callback_data="catalog:edit:name")],
        [InlineKeyboardButton("#️⃣ Теги", callback_data="catalog:edit:tags")],
        [InlineKeyboardButton("🔗 Ссылку", callback_data="catalog:edit:link")],
        [InlineKeyboardButton("💿 Медиа", callback_data="catalog:edit:media")],
        [InlineKeyboardButton("🆔 Номер", callback_data="catalog:edit:number")],
        [InlineKeyboardButton("⭐ Приоритет", callback_data="catalog:edit:priority")],
        [InlineKeyboardButton("❌ Отменить", callback_data="catalog:edit_cancel")]
    ]
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def change_catalog_number_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Изменить 🆔 поста - /changenumber [старый] [новый]"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "🔄 Использование: `/changenumber [старый] [новый]`\n\n"
            "Пример: `/changenumber 1234 5678`",
            parse_mode='Markdown'
        )
        return
    
    try:
        old_number = int(context.args[0])
        new_number = int(context.args[1])
        
        if new_number < 1 or new_number > 9999:
            await update.message.reply_text("❌ Новый номер должен быть от 1 до 9999")
            return
        
        success = await catalog_service.change_catalog_number(old_number, new_number)
        
        if success:
            await update.message.reply_text(
                f"✅ Номер изменён!\n\n"
                f"#{old_number} → #{new_number}"
            )
        else:
            await update.message.reply_text(
                f"❌ Ошибка!\n\n"
                f"Возможные причины:\n"
                f"• Пост #{old_number} не найден\n"
                f"• Номер #{new_number} уже занят"
            )
            
    except ValueError:
        await update.message.reply_text("❌ Номера должны быть числами")


async def remove_catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление записи - /remove [id]"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            "🖍️ Использование: `/remove [номер]`\n\n"
            "Пример: `/remove 1234`",
            parse_mode='Markdown'
        )
        return
    
    catalog_number = int(context.args[0])
    post = await catalog_service.get_post_by_number(catalog_number)
    
    if not post:
        await update.message.reply_text(f"❌ Пост #{catalog_number} не найден")
        return
    
    text = (
        f"⚠️ **Удаление поста #{catalog_number}**\n\n"
        f"ℹ️ Название: {post.get('name')}\n"
        f"📁 Категория: {post.get('category')}\n"
        f"👁️ Просмотры: {post.get('views', 0)}\n\n"
        "Подтверждаете❓"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("❗️ Удалить", callback_data=f"catalog:remove_confirm:{post['id']}"),
            InlineKeyboardButton("⬅️ Отменить", callback_data="catalog:remove_cancel")
        ]
    ]
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def catalogpriority_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление приоритетными постами - /catalogpriority [номера] или clear"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    # Специальная команда: clear
    if context.args and context.args[0].lower() == 'clear':
        count = await catalog_service.clear_all_priorities()
        await update.message.reply_text(f"✅ Очищено {count} приоритетов")
        return
    
    # Если есть аргументы - это номера постов
    if context.args:
        post_numbers = []
        for arg in context.args:
            try:
                num = int(arg)
                if 1 <= num <= 9999:
                    post_numbers.append(num)
            except ValueError:
                continue
        
        if post_numbers:
            success_count = await catalog_service.set_priority_by_numbers(post_numbers)
            await update.message.reply_text(
                f"✅ Установлено {success_count}/{len(post_numbers)} приоритетных постов\n\n"
                f"Номера: {', '.join(f'#{n}' for n in post_numbers)}"
            )
            return
    
    # Иначе - показать текущие приоритеты и меню
    priority_stats = await catalog_service.get_priority_stats()
    posts = priority_stats.get('posts', [])
    
    if not posts:
        text = "⭐ **ПРИОРИТЕТНЫЕ ПОСТЫ** (0/10)\n\n"
        text += "Нет приоритетных постов\n\n"
    else:
        text = f"⭐ **ПРИОРИТЕТНЫЕ ПОСТЫ** ({len(posts)}/10)\n\n"
        for idx, post in enumerate(posts, 1):
            text += f"{idx}. #{post['catalog_number']} - {post['name'][:30]}...\n"
        text += "\n"
    
    text += (
        "**Управление:**\n"
        "• `/catalogpriority [номера]` - установить\n"
        "  Пример: `/catalogpriority 1234 5678 9012`\n"
        "• `/catalogpriority clear` - очистить все\n"
        "• `/catalogpriority` - показать текущие"
    )
    
    keyboard = [
        [InlineKeyboardButton("🗑 Очистить все", callback_data="catalog:priority_clear")],
        [InlineKeyboardButton("📊 Статистика", callback_data="catalog:priority_stats")]
    ]
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def addcatalogreklama_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить рекламу - /addcatalogreklama [номер] или создать новую"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    # ВАРИАНТ 1: Указан номер поста - сделать его рекламным
    if context.args and context.args[0].isdigit():
        catalog_number = int(context.args[0])
        
        post = await catalog_service.get_post_by_number(catalog_number)
        
        if not post:
            await update.message.reply_text(f"❌ Пост #{catalog_number} не найден")
            return
        
        success = await catalog_service.set_post_as_ad(post['id'])
        
        if success:
            await update.message.reply_text(
                f"✅ Пост #{catalog_number} теперь рекламный\n\n"
                f"📝 {post['name']}\n"
                f"📂 {post['category']}"
            )
        else:
            await update.message.reply_text("❌ Ошибка при установке рекламы")
        
        return
    
    # ВАРИАНТ 2: Показать меню выбора
    context.user_data['catalog_ad'] = {'step': 'choice'}
    
    keyboard = [
        [InlineKeyboardButton("🆔 Сделать существующую карточку рекламной", callback_data="catalog:ad_by_number")],
        [InlineKeyboardButton("🔗 Создать новую рекламную карточку", callback_data="catalog:ad_by_link")],
        [InlineKeyboardButton("🚫 Отмена", callback_data="catalog:cancel_ad")]
    ]
    
    await update.message.reply_text(
        "💎 **ДОБАВИТЬ РЕКЛАМУ**\n\n"
        "Выберите способ:\n\n"
        "1️⃣ Сделать существующую карточку рекламной (по номеру)\n"
        "2️⃣ Создать новую рекламную карточку (внешняя ссылка + описание)",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def catalogads_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список рекламных постов - /catalogads"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админов")
        return
    
    ad_stats = await catalog_service.get_ad_stats()
    ads = ad_stats.get('ads', [])
    
    if not ads:
        await update.message.reply_text("💎 Нет рекламных постов")
        return
    
    text = f"💎 **РЕКЛАМНЫЕ ПОСТЫ** ({len(ads)})\n\n"
    
    for idx, ad in enumerate(ads, 1):
        ctr = (ad['clicks'] / ad['views'] * 100) if ad['views'] > 0 else 0
        text += (
            f"{idx}. #{ad['catalog_number']} - {ad['name'][:30]}...\n"
            f"   👁 {ad['views']} | 🖱 {ad['clicks']} ({ctr:.1f}%)\n\n"
        )
    
    total_views = ad_stats.get('total_views', 0)
    total_clicks = ad_stats.get('total_clicks', 0)
    avg_ctr = ad_stats.get('avg_ctr', 0)
    
    text += (
        f"📈 **Итого:**\n"
        f"👁 {total_views:,} просмотров\n"
        f"🖱 {total_clicks:,} кликов\n"
        f"📊 CTR: {avg_ctr:.1f}%"
    )
    
    await update.message.reply_text(text, parse_mode='Markdown')


async def removeads_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить рекламу - /removeads [номер]"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админов")
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            "Использование: `/removeads [номер]`\n"
            "Пример: `/removeads 1234`",
            parse_mode='Markdown'
        )
        return
    
    catalog_number = int(context.args[0])
    success = await catalog_service.remove_ad_by_number(catalog_number)
    
    if success:
        await update.message.reply_text(f"✅ Реклама удалена с поста #{catalog_number}")
    else:
        await update.message.reply_text(f"❌ Пост #{catalog_number} не найден или не является рекламным")


async def admincataloginfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список всех команд каталога - /admincataloginfo"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    text = (
        "📋 **КОМАНДЫ КАТАЛОГА**\n\n"
        
        "👤 **ПОЛЬЗОВАТЕЛЬСКИЕ:**\n"
        "/catalog - просмотр каталога\n"
        "/search - поиск по каталогу\n"
        "/review [номер] - оставить отзыв\n"
        "/categoryfollow - подписки на категории\n\n"
        
        "👑 **АДМИНСКИЕ:**\n"
        "/addtocatalog - добавить пост\n"
        "/addgirltocat - добавить в TopGirls\n"
        "/addboytocat - добавить в TopBoys\n"
        "/catalogedit [номер] - редактировать\n"
        "/remove [номер] - удалить пост\n"
        "/changenumber [старый] [новый] - изменить ID\n\n"
        
        "⭐ **ПРИОРИТЕТЫ:**\n"
        "/catalogpriority - управление\n"
        "/catalogpriority [номера] - установить\n"
        "  Пример: `/catalogpriority 1234 5678`\n"
        "/catalogpriority clear - очистить\n\n"
        
        "💎 **РЕКЛАМА:**\n"
        "/addcatalogreklama - меню добавления\n"
        "/addcatalogreklama [номер] - по номеру карточки\n"
        "/catalogads - список рекламы\n"
        "/removeads [номер] - удалить рекламу\n\n"
        
        "📊 **СТАТИСТИКА:**\n"
        "/catalogview - уникальные просмотры\n"
        "/catalogviews - топ по просмотрам\n"
        "/catalog_stats_users - общая статистика\n"
        "/catalog_stats_categories - по категориям\n"
        "/catalog_stats_popular - топ-10\n"
        "/catalog_stats_priority - приоритеты\n"
        "/catalog_stats_reklama - реклама\n\n"
        
        "💡 **ПОДСКАЗКИ:**\n"
        "• Номер - это уникальный ID поста (1-9999)\n"
        "• Приоритетные посты показываются чаще\n"
        "• Максимум 10 приоритетных постов\n"
        "• Реклама: карточка из каталога ИЛИ внешняя ссылка"
    )
    
    await update.message.reply_text(text, parse_mode='Markdown')


async def catalogview_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотры и переходы уникальных пользователей - /catalogview"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    try:
        unique_viewers = await catalog_service.get_unique_viewers()
        unique_clickers = await catalog_service.get_unique_clickers()
        top_posts = await catalog_service.get_top_posts_with_clicks(limit=20)
        
        text = "📊 **СТАТИСТИКА ПРОСМОТРОВ**\n\n"
        text += f"👥 Уникальных пользователей с просмотрами: {unique_viewers}\n"
        text += f"🖱 Уникальных пользователей с переходами: {unique_clickers}\n\n"
        text += "📈 **ТОП-20 ПОСТОВ:**\n\n"
        
        for idx, (post_id, views, clicks, name, catalog_number) in enumerate(top_posts, 1):
            emoji = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
            ctr = (clicks / views * 100) if views > 0 else 0
            text += f"{emoji} #{catalog_number} - {name[:25]}...\n"
            text += f"   👁 {views} | 🖱 {clicks} | CTR: {ctr:.1f}%\n\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in catalogview: {e}")
        await update.message.reply_text("❌ Ошибка")


async def catalogviews_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика просмотров - /catalogviews"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    try:
        stats = await catalog_service.get_views_stats(limit=20)
        if not stats:
            await update.message.reply_text("📊 Статистика пуста")
            return
        
        text = "📊 **ТОП-20 ПО ПРОСМОТРАМ**\n\n"
        for idx, (post_id, views, name, catalog_number) in enumerate(stats, 1):
            emoji = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else "▪️"
            text += f"{emoji} #{catalog_number}: {views} 👁 - {name[:30]}...\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ Ошибка")


async def catalog_stats_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика пользователей - /catalog_stats_users"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    try:
        stats = await catalog_service.get_catalog_stats()
        text = (
            f"👥 **СТАТИСТИКА**\n\n"
            f"📊 Постов: {stats.get('total_posts', 0)}\n"
            f"📸 С медиа: {stats.get('posts_with_media', 0)} ({stats.get('media_percentage', 0)}%)\n"
            f"📄 Без медиа: {stats.get('posts_without_media', 0)}\n\n"
            f"👁 Просмотров: {stats.get('total_views', 0)}\n"
            f"🔗 Переходов: {stats.get('total_clicks', 0)}\n"
            f"📈 CTR: {stats.get('ctr', 0)}%\n\n"
            f"🔥 Сессий: {stats.get('active_sessions', 0)}\n"
            f"💬 Отзывов: {stats.get('total_reviews', 0)}"
        )
        await update.message.reply_text(text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ Ошибка")


async def catalog_stats_categories_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика категорий - /catalog_stats_categories"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    try:
        stats = await catalog_service.get_category_stats()
        if not stats:
            await update.message.reply_text("📁 Статистика пуста")
            return
        
        text = "📁 **ПО КАТЕГОРИЯМ**\n\n"
        for category, count in stats.items():
            text += f"▪️ {category}: {count}\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ Ошибка")


async def catalog_stats_popular_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ТОП-10 - /catalog_stats_popular"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    try:
        stats = await catalog_service.get_views_stats(limit=10)
        if not stats:
            await update.message.reply_text("🏆 ТОП пуст")
            return
        
        text = "🏆 **ТОП-10**\n\n"
        for idx, (post_id, views, name, catalog_number) in enumerate(stats, 1):
            emoji = ["🥇", "🥈", "🥉"][idx-1] if idx <= 3 else f"{idx}."
            text += f"{emoji} #{catalog_number} {name[:30]}... - {views} 👁\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ Ошибка")


async def catalog_stats_priority_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика приоритетных постов - /catalog_stats_priority"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    try:
        priority_stats = await catalog_service.get_priority_stats()
        
        if not priority_stats.get('posts'):
            await update.message.reply_text("⭐ Нет приоритетных постов")
            return
        
        posts = priority_stats.get('posts', [])
        avg_ctr = priority_stats.get('avg_ctr', 0)
        normal_ctr = priority_stats.get('normal_ctr', 0)
        improvement = priority_stats.get('improvement', 0)
        
        text = f"⭐ **ПРИОРИТЕТНЫЕ ПОСТЫ** ({len(posts)}/10)\n\n"
        
        for idx, post in enumerate(posts, 1):
            emoji = ["🥇", "🥈", "🥉"][idx-1] if idx <= 3 else f"{idx}️⃣"
            ctr = (post['clicks'] / post['views'] * 100) if post['views'] > 0 else 0
            catalog_number = post.get('catalog_number', '????')
            
            text += (
                f"{emoji} #{catalog_number} | {post['name'][:20]}...\n"
                f"   👁 {post['views']} | 🖱 {post['clicks']} ({ctr:.1f}%)\n\n"
            )
        
        text += (
            f"📈 **Сравнение:**\n"
            f"• Приоритетные CTR: {avg_ctr:.1f}%\n"
            f"• Обычные посты CTR: {normal_ctr:.1f}%\n"
            f"• Прирост эффективности: +{improvement:.1f}%\n\n"
        )
        
        if len(posts) < 10:
            text += f"💡 Слоты {len(posts)+1}-10 свободны"
        
        keyboard = [[InlineKeyboardButton("⭐ Управление приоритетами", callback_data="catalog:manage_priority")]]
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error in catalog_stats_priority: {e}")
        await update.message.reply_text("❌ Ошибка")


async def catalog_stats_reklama_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика рекламы - /catalog_stats_reklama"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    try:
        ad_stats = await catalog_service.get_ad_stats()
        
        if not ad_stats.get('ads'):
            await update.message.reply_text("💎 Нет активных рекламных кампаний")
            return
        
        ads = ad_stats.get('ads', [])
        total_views = ad_stats.get('total_views', 0)
        total_clicks = ad_stats.get('total_clicks', 0)
        avg_ctr = ad_stats.get('avg_ctr', 0)
        
        text = f"💎 **СТАТИСТИКА РЕКЛАМЫ**\n\n📊 Активные кампании ({len(ads)}):\n\n"
        
        for idx, ad in enumerate(ads, 1):
            ctr = (ad['clicks'] / ad['views'] * 100) if ad['views'] > 0 else 0
            catalog_number = ad.get('catalog_number', '????')
            
            text += (
                f"{idx}️⃣ #{catalog_number} {ad['name'][:25]}...\n"
                f"   👁 {ad['views']} | 🖱 {ad['clicks']}\n"
                f"   📈 CTR: {ctr:.1f}%\n\n"
            )
        
        text += (
            f"📈 **Общая статистика:**\n"
            f"• Всего показов: {total_views:,}\n"
            f"• Всего кликов: {total_clicks:,}\n"
            f"• Средний CTR: {avg_ctr:.1f}%\n"
        )
        
        keyboard = [
            [InlineKeyboardButton("💎 Управление рекламой", callback_data="catalog:manage_ads")],
            [InlineKeyboardButton("📊 Детальная аналитика", callback_data="catalog:detailed_ads")]
        ]
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error in catalog_stats_reklama: {e}")
        await update.message.reply_text("❌ Ошибка")


# ============= CALLBACKS =============

async def handle_catalog_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback - ПОЛНАЯ ВЕРСИЯ"""
    query = update.callback_query
    await query.answer()
    data = query.data.split(":")
    action = data[1] if len(data) > 1 else None
    user_id = update.effective_user.id
    
    async def safe_edit(text, keyboard=None, parse_mode='Markdown'):
        """Безопасное редактирование"""
        try:
            await query.edit_message_text(
                text,
                reply_markup=keyboard,
                parse_mode=parse_mode
            )
        except Exception:
            try:
                await query.edit_message_caption(
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode=parse_mode
                )
            except Exception:
                await query.message.reply_text(
                    text,
                    reply_markup=keyboard,
                    parse_mode=parse_mode
                )
    
    # ============= БАЗОВЫЕ CALLBACKS =============
    
    if action == "next":
        posts = await catalog_service.get_random_posts_mixed(user_id, count=5)
        if not posts:
            keyboard = [
                [InlineKeyboardButton("🔄 Начать заново", callback_data="catalog:restart")],
                [InlineKeyboardButton("↩️ Главное меню", callback_data="menu:back")]
            ]
            await safe_edit(
                "✅ Все посты просмотрены!\n\nНажмите 🔄 для сброса",
                InlineKeyboardMarkup(keyboard)
            )
        else:
            for i, post in enumerate(posts, 1):
                await send_catalog_post_with_media(context.bot, query.message.chat_id, post, i, len(posts))
            await query.message.delete()
    
    elif action == "finish":
        await safe_edit(
            "✅ Просмотр завершён!\n\n"
            "/catalog - начать заново\n"
            "/search - поиск\n"
            "/categoryfollow - подписки на категории"
        )
        
    elif action == "restart":
        await catalog_service.reset_session(user_id)
        await safe_edit("🔄 Перезапуск!\n\nИспользуйте /catalog")
    
    elif action == "search":
        context.user_data['catalog_search'] = {'step': 'query'}
        keyboard = [[InlineKeyboardButton("🚫 Отмена", callback_data="catalog:cancel_search")]]
        await safe_edit(
            "🔍 **ПОИСК В КАТАЛОГЕ**\n\n"
            "Введите слова для поиска:\n"
            "• По названию\n"
            "• По тегам\n\n"
            "Пример: ТриксБот",
            InlineKeyboardMarkup(keyboard)
        )
    
    elif action == "cancel_search":
        context.user_data.pop('catalog_search', None)
        await safe_edit("❌ Поиск отменён")
    
    elif action == "cat":
        category = ":".join(data[2:])
        posts = await catalog_service.search_posts(category, limit=5)
        if posts:
            for i, post in enumerate(posts, 1):
                await send_catalog_post_with_media(context.bot, query.message.chat_id, post, i, len(posts))
            keyboard = [[InlineKeyboardButton("✅ Готово", callback_data="catalog:finish")]]
            await safe_edit(
                f"👌 Обнаружено: {len(posts)}",
                InlineKeyboardMarkup(keyboard)
            )
        else:
            await safe_edit(f"❌ В категории '{category}' пока нет постов")
    
    elif action == "click":
        post_id = int(data[2]) if len(data) > 2 else None
        if post_id:
            await catalog_service.increment_clicks(post_id, user_id)
    
    # ============= CALLBACK ДЛЯ ВЫБОРА КАТЕГОРИИ ПРИ ДОБАВЛЕНИИ =============
    elif action == "add_cat":
        if 'catalog_add' not in context.user_data:
            await query.answer("❌ Сессия истекла", show_alert=True)
            return
        
        category = ":".join(data[2:])
        context.user_data['catalog_add']['category'] = category
        context.user_data['catalog_add']['step'] = 'name'
        
        await safe_edit(
            f"✅ Категория: {category}\n\n"
            f"📝 Шаг 3/5\n\n"
            f"Название (до 255 символов):"
        )
    
    # ============= ОТЗЫВЫ С ВЫБОРОМ ЗВЕЗД =============
    elif action == "rate":
        if 'catalog_review' not in context.user_data:
            await query.answer("❌ Сессия истекла", show_alert=True)
            return
        
        rating = int(data[2]) if len(data) > 2 else 5
        context.user_data['catalog_review']['rating'] = rating
        context.user_data['catalog_review']['step'] = 'text'
        
        stars = "⭐" * rating
        catalog_number = context.user_data['catalog_review'].get('catalog_number')
        
        keyboard = [[InlineKeyboardButton("⏮️ Отмена", callback_data="catalog:cancel_review")]]
        
        await safe_edit(
            f"✅ Оценка: {stars}\n\n"
            f"📝 Пост #{catalog_number}\n\n"
            f"Теперь напишите текст отзыва (макс. 500 символов):",
            InlineKeyboardMarkup(keyboard)
        )
    
    elif action == "cancel_review":
        context.user_data.pop('catalog_review', None)
        await safe_edit("❌ Отзыв отменён")
    
    elif action == "cancel":
        context.user_data.pop('catalog_add', None)
        await safe_edit("❌ Добавление отменено")
    
    elif action == "cancel_top":
        context.user_data.pop('catalog_add_top', None)
        await safe_edit("❌ Добавление Top поста отменено")
    
    elif action == "cancel_ad":
        context.user_data.pop('catalog_ad', None)
        await safe_edit("❌ Добавление рекламы отменено")
    
    elif action == "priority_finish":
        links = context.user_data.get('catalog_priority', {}).get('links', [])
        if links:
            count = await catalog_service.set_priority_posts(links)
            await safe_edit(f"✅ Установлено {count} приоритетных постов")
        else:
            await safe_edit("❌ Ссылки не добавлены")
        context.user_data.pop('catalog_priority', None)
    
    elif action == "priority_clear":
        count = await catalog_service.clear_all_priorities()
        await safe_edit(f"✅ Очищено {count} приоритетов")
    
    elif action == "priority_stats":
        stats = await catalog_service.get_priority_stats()
        posts = stats.get('posts', [])
        
        if not posts:
            await safe_edit("⭐ Нет приоритетных постов")
            return
        
        text = f"📊 **СТАТИСТИКА ПРИОРИТЕТОВ** ({len(posts)}/10)\n\n"
        
        for idx, post in enumerate(posts, 1):
            ctr = (post['clicks'] / post['views'] * 100) if post['views'] > 0 else 0
            text += (
                f"{idx}. #{post['catalog_number']}\n"
                f"   {post['name'][:25]}...\n"
                f"   👁 {post['views']} | 🖱 {post['clicks']} ({ctr:.1f}%)\n\n"
            )
        
        avg_ctr = stats.get('avg_ctr', 0)
        normal_ctr = stats.get('normal_ctr', 0)
        improvement = stats.get('improvement', 0)
        
        text += (
            f"📈 **Эффективность:**\n"
            f"• Приоритеты: {avg_ctr:.1f}%\n"
            f"• Обычные: {normal_ctr:.1f}%\n"
            f"• Прирост: +{improvement:.1f}%"
        )
        
        await safe_edit(text)
    
    # ============= РЕКЛАМА - НОВЫЕ CALLBACKS =============
    
    elif action == "ad_by_number":
        context.user_data['catalog_ad'] = {'step': 'number'}
        await safe_edit(
            "🆔 **Сделать карточку рекламной**\n\n"
            "Введите номер существующей карточки (1-9999):"
        )
    
    elif action == "ad_by_link":
        context.user_data['catalog_ad'] = {'step': 'link'}
        await safe_edit(
            "🔗 **Создать новую рекламную карточку**\n\n"
            "Шаг 1/2\n\n"
            "Введите внешнюю ссылку:\n"
            "Пример: https://example.com/promo"
        )
    
    # ============= ПОДПИСКИ =============
    
    elif action == "follow_menu":
        keyboard = []
        for main_cat in CATALOG_CATEGORIES.keys():
            keyboard.append([InlineKeyboardButton(
                main_cat, 
                callback_data=f"catalog:follow_cat:{main_cat}"
            )])
        keyboard.append([InlineKeyboardButton("📋 Мои подписки", callback_data="catalog:my_follows")])
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="catalog:finish")])
        
        await safe_edit(
            "➕ Выберите категорию для подписки:",
            InlineKeyboardMarkup(keyboard)
        )
    
    elif action == "follow_cat":
        category = ":".join(data[2:])
        success = await catalog_service.subscribe_to_category(user_id, category)
        
        if success:
            await query.answer("✅ Подписка оформлена!", show_alert=True)
            await safe_edit(
                f"🔔 Подписка на:\n**{category}**\n\n"
                "👌 Вы будете получать уведомления о новых постах добавленых в категорию!"
            )
        else:
            await query.answer("❌ Вы уже подписаны на эту категорию", show_alert=True)
    
    elif action == "my_follows":
        subscriptions = await catalog_service.get_user_subscriptions(user_id)
        
        if not subscriptions:
            await safe_edit(
                "📭 У вас нет активных подписок\n\n"
                "/categoryfollow - меню подписок"
            )
            return
        
        text = f"🗃️ **ВАШИ ПОДПИСКИ** ({len(subscriptions)})\n\n"
        keyboard = []
        
        for sub in subscriptions:
            category = sub.get('category')
            text += f"✅ {category}\n"
            keyboard.append([
                InlineKeyboardButton(
                    f"🔕 Отписаться от '{category}'",
                    callback_data=f"catalog:unfollow:{category}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔕 Отписаться от всех", callback_data="catalog:unfollow_all")])
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="catalog:follow_menu")])
        
        await safe_edit(text, InlineKeyboardMarkup(keyboard))
    
    elif action == "unfollow":
        category = ":".join(data[2:])
        success = await catalog_service.unsubscribe_from_category(user_id, category)
        await query.answer("✅ Отписались" if success else "❌ Ошибка", show_alert=True)
        
        subscriptions = await catalog_service.get_user_subscriptions(user_id)
        
        if not subscriptions:
            await safe_edit(
                "📋 У вас нет активных подписок\n\n"
                "/categoryfollow - управление подписками"
            )
            return
        
        text = f"📋 **ВАШИ ПОДПИСКИ** ({len(subscriptions)})\n\n"
        keyboard = []
        
        for sub in subscriptions:
            cat = sub.get('category')
            text += f"✅ {cat}\n"
            keyboard.append([
                InlineKeyboardButton(
                    f"🔕 Отписаться от '{cat}'",
                    callback_data=f"catalog:unfollow:{cat}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔕 Отписаться от всех", callback_data="catalog:unfollow_all")])
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="catalog:follow_menu")])
        
        await safe_edit(text, InlineKeyboardMarkup(keyboard))
    
    elif action == "unfollow_all":
        count = await catalog_service.unsubscribe_from_all(user_id)
        await safe_edit(
            f"✅ Отписались от всех категорий ({count})\n\n"
            "/categoryfollow - управление подписками"
        )
    
    elif action == "subscribe_menu":
        category = ":".join(data[2:])
        
        subscriptions = await catalog_service.get_user_subscriptions(user_id)
        is_subscribed = any(s.get('category') == category for s in subscriptions)
        
        keyboard = []
        
        if is_subscribed:
            keyboard.append([InlineKeyboardButton(
                f"🔕 Отписаться от '{category}'",
                callback_data=f"catalog:unfollow:{category}"
            )])
        else:
            keyboard.append([InlineKeyboardButton(
                f"🔔 Подписаться на '{category}'",
                callback_data=f"catalog:follow_cat:{category}"
            )])
        
        keyboard.append([InlineKeyboardButton("📂 Все категории", callback_data="catalog:follow_menu")])
        keyboard.append([InlineKeyboardButton("👌 Мои подписки", callback_data="catalog:my_follows")])
        keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data="catalog:close_menu")])
        
        status = "✅ Вы подписаны" if is_subscribed else "❌ Вы не подписаны"
        
        await safe_edit(
            f"🔔 **ПОДПИСКА НА КАТЕГОРИЮ**\n\n"
            f"📂 {category}\n"
            f"{status}\n\n"
            "Выберите действие:",
            InlineKeyboardMarkup(keyboard)
        )
    
    # ============= ОТЗЫВЫ =============
    
    elif action == "reviews_menu":
        post_id = int(data[2]) if len(data) > 2 else None
        if not post_id:
            return
        
        reviews = await catalog_service.get_reviews(post_id, limit=100)
        count = len(reviews)
        
        post = await catalog_service.get_post_by_id(post_id)
        catalog_number = post.get('catalog_number', '????') if post else '????'
        
        keyboard = [
            [InlineKeyboardButton(f"🫣 Смотреть отзывы ({count})", callback_data=f"catalog:view_reviews:{post_id}")],
            [InlineKeyboardButton("🤭 Оставить отзыв", callback_data=f"catalog:write_review:{post_id}:{catalog_number}")],
            [InlineKeyboardButton("❌ Закрыть", callback_data="catalog:close_menu")]
        ]
        
        await safe_edit(
            f"🧑‍🧒‍🧒 **ОТЗЫВЫ О ПОСТЕ #{catalog_number}**\n\n"
            f"Всего отзывов: {count}\n\n"
            "Выберите действие:",
            InlineKeyboardMarkup(keyboard)
        )
    
    elif action == "view_reviews":
        post_id = int(data[2]) if len(data) > 2 else None
        if not post_id:
            return
        
        reviews = await catalog_service.get_reviews(post_id, limit=10)
        post = await catalog_service.get_post_by_id(post_id)
        catalog_number = post.get('catalog_number', '????') if post else '????'
        
        if not reviews:
            await safe_edit(
                f"📝 Отзывов о посте #{catalog_number} пока нет\n\n"
                "/catalog - продолжить просмотр"
            )
            return
        
        text = f"👀 **ОТЗЫВЫ О ПОСТЕ #{catalog_number}**\n\n"
        
        for idx, review in enumerate(reviews, 1):
            username = review.get('username', 'Аноним')
            rating = "⭐" * review.get('rating', 5)
            text += f"{idx}. @{username} - {rating}\n"
            text += f"   {review.get('review_text', 'Без текста')[:100]}\n\n"
        
        keyboard = [
            [InlineKeyboardButton("✍️ Оставить отзыв", callback_data=f"catalog:write_review:{post_id}:{catalog_number}")],
            [InlineKeyboardButton("⬅️ Назад", callback_data=f"catalog:reviews_menu:{post_id}")]
        ]
        
        await safe_edit(text, InlineKeyboardMarkup(keyboard))
    
    elif action == "write_review":
        post_id = int(data[2]) if len(data) > 2 else None
        catalog_number = int(data[3]) if len(data) > 3 else None
        if not post_id:
            return
        
        context.user_data['catalog_review'] = {
            'post_id': post_id,
            'catalog_number': catalog_number,
            'step': 'rating'
        }
        
        keyboard = [
            [
                InlineKeyboardButton("⭐", callback_data="catalog:rate:1"),
                InlineKeyboardButton("⭐⭐", callback_data="catalog:rate:2"),
                InlineKeyboardButton("⭐⭐⭐", callback_data="catalog:rate:3")
            ],
            [
                InlineKeyboardButton("⭐⭐⭐⭐", callback_data="catalog:rate:4"),
                InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data="catalog:rate:5")
            ],
            [InlineKeyboardButton("❌ Отмена", callback_data="catalog:cancel_review")]
        ]
        
        await safe_edit(
            f"🌟 **ОЦЕНКА ПОСТА #{catalog_number}**\n\n"
            "Выберите оценку:",
            InlineKeyboardMarkup(keyboard)
        )
    
    # ============= РЕДАКТИРОВАНИЕ =============
    
    elif action == "remove_confirm":
        post_id = int(data[2]) if len(data) > 2 else None
        if post_id:
            success = await catalog_service.delete_post(post_id, user_id)
            await safe_edit(f"🗑️ Пост удалён" if success else "❌ Ошибка")
    
    elif action == "remove_cancel":
        await safe_edit("❌ Удаление отменено")
    
    elif action == "edit":
        field = data[2] if len(data) > 2 else None
        post_id = context.user_data.get('catalog_edit', {}).get('post_id')
        
        if not post_id:
            await query.answer("❌ Пост не найден", show_alert=True)
            return
        
        context.user_data['catalog_edit']['field'] = field
        context.user_data['catalog_edit']['waiting'] = True
        
        prompts = {
            'category': "Выберите новую категорию:",
            'name': "Введите новое название:",
            'tags': "Введите новые теги через запятую:",
            'link': "Введите новую ссылку:",
            'media': "Отправьте новое медиа:",
            'number': "Введите новый номер (1-9999):"
        }
        
        await safe_edit(prompts.get(field, "Введите новое значение:"))
    
    elif action == "edit_cancel":
        context.user_data.pop('catalog_edit', None)
        await safe_edit("❌ Редактирование отменено")
    
    elif action == "close_menu":
        await query.delete_message()


# ============= TEXT HANDLER =============

async def handle_catalog_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текста - ПОЛНАЯ ВЕРСИЯ С ИСПРАВЛЕНИЯМИ"""
    user_id = update.effective_user.id
    text = update.message.text
    
    # ============= ПОИСК =============
    if 'catalog_search' in context.user_data:
        query_text = text.strip()
        
        if len(query_text) < 2:
            await update.message.reply_text("❌ Запрос слишком короткий (минимум 2 символа)")
            return
        
        posts = await catalog_service.search_posts(query_text, limit=10)
        
        if posts:
            for i, post in enumerate(posts, 1):
                await send_catalog_post_with_media(context.bot, update.effective_chat.id, post, i, len(posts))
            
            keyboard = [[InlineKeyboardButton("✅ Готово", callback_data="catalog:finish")]]
            await update.message.reply_text(
                f"🔍 Найдено: {len(posts)} по запросу \"{query_text}\"",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(f"❌ Ничего не найдено по запросу \"{query_text}\"")
        
        context.user_data.pop('catalog_search', None)
        return
    
    # ============= ОТЗЫВЫ - ИСПРАВЛЕНО =============
    if 'catalog_review' in context.user_data:
        data = context.user_data['catalog_review']
        step = data.get('step')
        
        if step == 'text':
            review_text = text.strip()
            
            if len(review_text) < 3:
                await update.message.reply_text("❌ Отзыв слишком короткий (минимум 3 символа)")
                return
            
            if len(review_text) > 500:
                review_text = review_text[:500]
            
            post_id = data.get('post_id')
            rating = data.get('rating', 5)
            catalog_number = data.get('catalog_number', '????')
            
            review_id = await catalog_service.add_review(
                post_id=post_id,
                user_id=user_id,
                review_text=review_text,
                rating=rating,
                username=update.effective_user.username,
                bot=context.bot  # <- ВАЖНО для уведомлений
            )
            
            if review_id:
                stars = "⭐" * rating
                await update.message.reply_text(
                    f"✅ Отзыв сохранён!\n\n"
                    f"#{catalog_number}\n"
                    f"Оценка: {stars}\n"
                    f"Текст: \"{review_text[:100]}...\"\n\n"
                    f"Спасибо за ваш отзыв!"
                )
            else:
                await update.message.reply_text("❌ Ошибка при сохранении отзыва")
            
            context.user_data.pop('catalog_review', None)
            return
    
    # Добавление поста - ИСПРАВЛЕННАЯ ЛОГИКА
    if 'catalog_add' in context.user_data:
        data = context.user_data['catalog_add']
        step = data.get('step')

        if step == 'link':
            if text.startswith('https://t.me/'):
                data['catalog_link'] = text
                
                await update.message.reply_text("⏳ Импортирую медиа из поста...")
                
                media_result = await extract_media_from_link(context.bot, text)
                
                if media_result and media_result.get('success'):
                    data['media_type'] = media_result['type']
                    data['media_file_id'] = media_result['file_id']
                    data['media_group_id'] = media_result.get('media_group_id')
                    data['media_json'] = media_result.get('media_json', [])
                    
                    media_emoji = {
                        'photo': '📸', 
                        'video': '🎬', 
                        'document': '📄', 
                        'animation': '🎞️'
                    }.get(media_result['type'], '📎')
                    
                    await update.message.reply_text(
                        f"{media_emoji} **Медиа импортировано!**\n\n"
                        f"Тип: {media_result['type']}\n"
                        f"✅ Будет добавлено в каталог автоматически",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(
                        f"⚠️ **Медиа не импортировано**\n\n"
                        f"{media_result.get('message', 'Не удалось получить доступ к посту')}\n\n"
                        f"💡 Вы сможете добавить медиа вручную на следующем шаге",
                        parse_mode='Markdown'
                    )
                
                data['step'] = 'category'
                
                keyboard = [[InlineKeyboardButton(cat, callback_data=f"catalog:add_cat:{cat}")] for cat in CATALOG_CATEGORIES.keys()]
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
                media_emoji = {
                    'photo': '📸', 
                    'video': '🎬', 
                    'document': '📄', 
                    'animation': '🎞️'
                }.get(data.get('media_type'), '📎')
                
                await update.message.reply_text(
                    f"✅ Название: {text[:50]}\n"
                    f"{media_emoji} Медиа импортировано из оригинального поста\n\n"
                    f"#️⃣ Шаг 4/4\n\n"
                    f"Теги через запятую (до 10):\n"
                    f"Пример: маникюр, гель-лак"
                )
            else:
                data['step'] = 'media'
                await update.message.reply_text(
                    "📸 Шаг 4/5\n\n"
                    "Отправьте фото/видео или нажмите /skip если медиа не нужно"
                )
        
        elif text == '/skip' and step == 'media':
            data['step'] = 'tags'
            await update.message.reply_text(
                "⏩ Медиа пропущено\n\n"
                "#️⃣ Шаг 4/4\n\n"
                "Теги через запятую (до 10):\n"
                "Пример: маникюр, гель-лак"
            )
            return
        
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
                catalog_number = post.get('catalog_number', '????')
                
                has_media = "Да" if data.get('media_file_id') else "Нет"
                media_info = f" ({data.get('media_type')})" if data.get('media_type') else ""
                
                await update.message.reply_text(
                    f"✅ Пост #{catalog_number} добавлен в каталог!\n\n"
                    f"📂 {data['category']}\n"
                    f"📝 {data['name']}\n"
                    f"🏷️ {len(tags)} тегов\n"
                    f"📸 Медиа: {has_media}{media_info}"
                )
                
                await notify_subscribers_about_new_post(context.bot, post_id, data['category'])
            else:
                await update.message.reply_text("❌ Ошибка при добавлении поста")
            
            context.user_data.pop('catalog_add', None)
        
        return
    
    # ============= РЕКЛАМА - НОВАЯ ЛОГИКА =============
    if 'catalog_ad' in context.user_data:
        data = context.user_data['catalog_ad']
        step = data.get('step')
        
        # ВАРИАНТ 1: Указан номер карточки
        if step == 'number':
            try:
                catalog_number = int(text.strip())
                if catalog_number < 1 or catalog_number > 9999:
                    await update.message.reply_text("❌ Номер должен быть от 1 до 9999")
                    return
                
                post = await catalog_service.get_post_by_number(catalog_number)
                
                if not post:
                    await update.message.reply_text(f"❌ Пост #{catalog_number} не найден")
                    return
                
                success = await catalog_service.set_post_as_ad(post['id'])
                
                if success:
                    await update.message.reply_text(
                        f"✅ Пост #{catalog_number} теперь рекламный!\n\n"
                        f"📝 {post['name']}\n"
                        f"📂 {post['category']}"
                    )
                else:
                    await update.message.reply_text("❌ Ошибка")
                
                context.user_data.pop('catalog_ad', None)
                
            except ValueError:
                await update.message.reply_text("❌ Введите число")
            
            return
        
        # ВАРИАНТ 2: Внешняя ссылка - создать новую рекламную карточку
        elif step == 'link':
            # Проверяем что это ссылка
            if not text.startswith('http'):
                await update.message.reply_text("❌ Введите корректную ссылку (начинается с http)")
                return
            
            data['catalog_link'] = text
            data['step'] = 'description'
            
            await update.message.reply_text(
                "✅ Ссылка сохранена\n\n"
                "📝 Шаг 2/2\n\n"
                "Введите описание рекламы (до 255 символов):"
            )
            return
        
        elif step == 'description':
            description = text.strip()[:255]
            
            # Создаем рекламную карточку с внешней ссылкой
            ad_id = await catalog_service.add_ad_post(
                catalog_link=data['catalog_link'],
                description=description
            )
            
            if ad_id:
                post = await catalog_service.get_post_by_id(ad_id)
                catalog_number = post.get('catalog_number', '????') if post else '????'
                
                await update.message.reply_text(
                    f"✅ Реклама #{catalog_number} добавлена!\n\n"
                    f"🔗 Ссылка: {data['catalog_link']}\n"
                    f"📝 Описание: {description}"
                )
            else:
                await update.message.reply_text("❌ Ошибка при добавлении рекламы")
            
            context.user_data.pop('catalog_ad', None)
            return
    
    # Приоритетные посты
    if 'catalog_priority' in context.user_data and context.user_data['catalog_priority'].get('step') == 'collecting':
        if text.startswith('https://t.me/'):
            links = context.user_data['catalog_priority'].get('links', [])
            links.append(text)
            context.user_data['catalog_priority']['links'] = links
            
            await update.message.reply_text(
                f"✅ Добавлено: {len(links)}/10\n\n"
                "Отправьте ещё ссылки или нажмите 'Завершить'"
            )
        return
    
    # Редактирование поста
    if 'catalog_edit' in context.user_data and context.user_data['catalog_edit'].get('waiting'):
        post_id = context.user_data['catalog_edit'].get('post_id')
        field = context.user_data['catalog_edit'].get('field')
        
        if field == 'name':
            success = await catalog_service.update_post_field(post_id, 'name', text[:255])
            await update.message.reply_text("✅ Название обновлено!" if success else "❌ Ошибка")
            context.user_data.pop('catalog_edit', None)
        
        elif field == 'tags':
            tags = [t.strip() for t in text.split(',') if t.strip()][:10]
            success = await catalog_service.update_post_field(post_id, 'tags', tags)
            await update.message.reply_text(f"✅ Теги обновлены ({len(tags)})!" if success else "❌ Ошибка")
            context.user_data.pop('catalog_edit', None)
        
        elif field == 'link':
            if text.startswith('https://t.me/') or text.startswith('http'):
                success = await catalog_service.update_post_field(post_id, 'catalog_link', text)
                await update.message.reply_text("✅ Ссылка обновлена!" if success else "❌ Ошибка")
            else:
                await update.message.reply_text("❌ Ссылка должна начинаться с http")
            context.user_data.pop('catalog_edit', None)
        
        elif field == 'number':
            try:
                new_number = int(text)
                if new_number < 1 or new_number > 9999:
                    await update.message.reply_text("❌ Номер должен быть от 1 до 9999")
                else:
                    success = await catalog_service.update_post_field(post_id, 'catalog_number', new_number)
                    if success:
                        await update.message.reply_text(f"✅ Теперь номер iD #{new_number}")
                    else:
                        await update.message.reply_text("❌ Этот номер уже занят или произошла ошибка")
            except ValueError:
                await update.message.reply_text("❌ Введите число от 1 до 9999")
            context.user_data.pop('catalog_edit', None)


__all__ = [
    'catalog_command',
    'search_command',
    'review_command',
    'categoryfollow_command',
    'addtocatalog_command',
    'addgirltocat_command',
    'addboytocat_command',
    'edit_catalog_command',
    'remove_catalog_command',
    'catalogpriority_command',
    'addcatalogreklama_command',
    'catalogads_command',
    'removeads_command',
    'admincataloginfo_command',
    'catalogview_command',
    'catalogviews_command',
    'catalog_stats_users_command',
    'catalog_stats_categories_command',
    'catalog_stats_popular_command',
    'catalog_stats_priority_command',
    'catalog_stats_reklama_command',
    'handle_catalog_callback',
    'handle_catalog_text',
    'handle_catalog_media',
    'change_catalog_number_command'
]
