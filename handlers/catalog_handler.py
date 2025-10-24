# -*- coding: utf-8 -*-
"""
Handler для каталога услуг - ОБНОВЛЕННАЯ ВЕРСИЯ 3.2

Обновления:
- ✅ Новые команды /addgirltocat и /addboytocat
- ✅ Улучшенный импорт медиа с уведомлениями
- ✅ Обновленный поиск только по словам и тегам
- ✅ Смешанная выдача постов (4 обычных + 1 Top)
- ✅ Уведомления админу при новых отзывах

Версия: 3.2.0
Дата: 24.10.2025
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
    """Автоматический импорт медиа из поста с уведомлениями о статусе"""
    try:
        if not telegram_link or 't.me/' not in telegram_link:
            return {
                'success': False,
                'message': '❌ Неверная ссылка'
            }
        
        match = re.search(r't\.me/([^/]+)/(\d+)', telegram_link)
        if not match:
            return {
                'success': False,
                'message': '❌ Не удалось извлечь данные из ссылки'
            }
        
        channel_username = match.group(1)
        message_id = int(match.group(2))
        
        if channel_username.startswith('@'):
            channel_username = channel_username[1:]
        
        chat_id = f"@{channel_username}" if not channel_username.startswith('-100') else int(channel_username)
        
        try:
            message = await bot.forward_message(
                chat_id=bot.id,
                from_chat_id=chat_id,
                message_id=message_id
            )
            
            result = None
            if message.photo:
                result = {
                    'success': True,
                    'type': 'photo',
                    'file_id': message.photo[-1].file_id,
                    'media_group_id': message.media_group_id,
                    'media_json': [message.photo[-1].file_id],
                    'message': '✅ Фото успешно импортировано'
                }
            elif message.video:
                result = {
                    'success': True,
                    'type': 'video',
                    'file_id': message.video.file_id,
                    'media_group_id': message.media_group_id,
                    'media_json': [message.video.file_id],
                    'message': '✅ Видео успешно импортировано'
                }
            elif message.document:
                result = {
                    'success': True,
                    'type': 'document',
                    'file_id': message.document.file_id,
                    'media_group_id': message.media_group_id,
                    'media_json': [message.document.file_id],
                    'message': '✅ Документ успешно импортирован'
                }
            elif message.animation:
                result = {
                    'success': True,
                    'type': 'animation',
                    'file_id': message.animation.file_id,
                    'media_group_id': message.media_group_id,
                    'media_json': [message.animation.file_id],
                    'message': '✅ Анимация успешно импортирована'
                }
            else:
                result = {
                    'success': False,
                    'message': '⚠️ Медиа не найдено. Добавьте вручную'
                }
            
            try:
                await bot.delete_message(chat_id=bot.id, message_id=message.message_id)
            except:
                pass
            
            if result:
                logger.info(f"✅ Media extracted: {result.get('type', 'none')}, success: {result.get('success')}")
            return result
            
        except TelegramError as e:
            logger.error(f"Cannot access message: {e}")
            return {
                'success': False,
                'message': f'❌ Ошибка доступа к посту. Добавьте медиа вручную'
            }
            
    except Exception as e:
        logger.error(f"Error extracting media: {e}")
        return {
            'success': False,
            'message': f'❌ Ошибка импорта. Добавьте медиа вручную'
        }


async def send_catalog_post_with_media(bot: Bot, chat_id: int, post: Dict, index: int, total: int) -> bool:
    """Отправка карточки каталога С НОВЫМ ФОРМАТОМ"""
    try:
        # ============= НОВЫЙ ФОРМАТ КАРТОЧКИ =============
        catalog_number = post.get('catalog_number', '????')
        card_text = f"#️⃣ **Пост {catalog_number}**\n\n"
        card_text += f"📂 {post.get('category', 'Не указана')}\n"
        card_text += f"ℹ️ {post.get('name', 'Без названия')}\n\n"
        
        # Теги
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
        
        # Рейтинг (только если 10+ отзывов)
        review_count = post.get('review_count', 0)
        if review_count >= 10:
            rating = post.get('rating', 0)
            stars = "⭐" * int(rating)
            card_text += f"**Rating**: {stars} {rating:.1f} ({review_count} отзывов)\n"
        else:
            card_text += f"**Rating**: -\n"
        
        # НОВЫЕ КНОПКИ
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
        
        # Увеличиваем просмотры
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
            f"📝 {post.get('name', 'Без названия')}\n\n"
            f"🔗 Перейти: {post.get('catalog_link')}\n\n"
            f"Используйте /catalog для просмотра"
        )
        
        keyboard = [
            [InlineKeyboardButton("👀 Посмотреть", url=post.get('catalog_link'))],
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
    
    # Используем смешанную выдачу
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
        "🔍 **ПОИСК В КАТАЛОГЕ**\n\n"
        "Введите слова для поиска:\n"
        "• По названию\n"
        "• По тегам\n\n"
        "Пример: маникюр гель-лак",
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
    
    # Ищем по catalog_number
    catalog_number = int(context.args[0])
    post = await catalog_service.get_post_by_number(catalog_number)
    
    if not post:
        await update.message.reply_text(f"❌ Пост #{catalog_number} не найден")
        return
    
    # Показываем выбор звезд
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
            text += "📋 Ваши подписки:\n"
            for sub in subscriptions:
                text += f"✅ {sub.get('category')}\n"
            text += "\n"
        
        text += "Выберите действие:"
        
        keyboard = [
            [InlineKeyboardButton("➕ Подписаться на категорию", callback_data="catalog:follow_menu")],
            [InlineKeyboardButton("📋 Мои подписки", callback_data="catalog:my_follows")]
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
        "🆕 **ДОБАВЛЕНИЕ**\n\nШаг 1/5\n\n"
        "⛓️ Ссылка на пост:\n"
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
        "⛓️ Ссылка на оригинальный пост:\n"
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
        "⛓️ Ссылка на оригинальный пост:\n"
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
            "🔄 Использование: `/catalogedit [номер]`\n\n"
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
        f"🛠️ **Редактирование поста #{catalog_number}**\n\n"
        f"📂 Категория: {post.get('category')}\n"
        f"📝 Название: {post.get('name')}\n"
        f"🏷️ Теги: {', '.join(post.get('tags', []))}\n"
        f"🔗 Ссылка: {post.get('catalog_link')}\n\n"
        "Что изменить?"
    )
    
    keyboard = [
        [InlineKeyboardButton("✏️ Категорию", callback_data="catalog:edit:category")],
        [InlineKeyboardButton("📝 Название", callback_data="catalog:edit:name")],
        [InlineKeyboardButton("🏷️ Теги", callback_data="catalog:edit:tags")],
        [InlineKeyboardButton("🔗 Ссылку", callback_data="catalog:edit:link")],
        [InlineKeyboardButton("📸 Медиа", callback_data="catalog:edit:media")],
        [InlineKeyboardButton("#️⃣ Номер", callback_data="catalog:edit:number")],
        [InlineKeyboardButton("⭐ Приоритет", callback_data="catalog:edit:priority")],
        [InlineKeyboardButton("❌ Отменить", callback_data="catalog:edit_cancel")]
    ]
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def change_catalog_number_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Изменить номер поста - /changenumber [старый] [новый]"""
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
            "🔄 Использование: `/remove [номер]`\n\n"
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
        f"📋 Название: {post.get('name')}\n"
        f"📂 Категория: {post.get('category')}\n"
        f"👁️ Просмотры: {post.get('views', 0)}\n\n"
        "Вы уверены?"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Удалить", callback_data=f"catalog:remove_confirm:{post['id']}"),
            InlineKeyboardButton("❌ Отменить", callback_data="catalog:remove_cancel")
        ]
    ]
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def catalogpriority_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приоритетные посты - /catalogpriority"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    context.user_data['catalog_priority'] = {'links': [], 'step': 'collecting'}
    keyboard = [[InlineKeyboardButton("✅ Завершить", callback_data="catalog:priority_finish")]]
    await update.message.reply_text(
        "⭐ **ПРИОРИТЕТНЫЕ**\n\n"
        "Отправляйте ссылки (до 10)",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def addcatalogreklama_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить рекламу - /addcatalogreklama"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    context.user_data['catalog_ad'] = {'step': 'link'}
    keyboard = [[InlineKeyboardButton("🚫 Отмена", callback_data="catalog:cancel_ad")]]
    await update.message.reply_text(
        "📢 **РЕКЛАМА**\n\nШаг 1/2\n\nСсылка на пост:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


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
    """Обработчик callback"""
    query = update.callback_query
    await query.answer()
    data = query.data.split(":")
    action = data[1] if len(data) > 1 else None
    user_id = update.effective_user.id
    
    # ============= БАЗОВЫЕ CALLBACKS =============
    
    if action == "next":
        posts = await catalog_service.get_random_posts_mixed(user_id, count=5)
        if not posts:
            keyboard = [
                [InlineKeyboardButton("🔄 Начать заново", callback_data="catalog:restart")],
                [InlineKeyboardButton("↩️ Главное меню", callback_data="menu:back")]
            ]
            await query.edit_message_text(
                "📂 Все посты просмотрены!\n\nНажмите 🔄 для сброса",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            for i, post in enumerate(posts, 1):
                await send_catalog_post_with_media(context.bot, query.message.chat_id, post, i, len(posts))
            await query.message.delete()
    
    elif action == "finish":
        await query.edit_message_text(
            "✅ Просмотр завершён!\n\n"
            "/catalog - начать заново\n"
            "/search - поиск\n"
            "/categoryfollow - подписки"
        )
    
    elif action == "restart":
        await catalog_service.reset_session(user_id)
        await query.edit_message_text("🔄 Сессия сброшена!\n\nИспользуйте /catalog")
    
    elif action == "search":
        context.user_data['catalog_search'] = {'step': 'query'}
        keyboard = [[InlineKeyboardButton("🚫 Отмена", callback_data="catalog:cancel_search")]]
        await query.edit_message_text(
            "🔍 **ПОИСК В КАТАЛОГЕ**\n\n"
            "Введите слова для поиска:\n"
            "• По названию\n"
            "• По тегам\n\n"
            "Пример: маникюр гель-лак",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif action == "cancel_search":
        context.user_data.pop('catalog_search', None)
        await query.edit_message_text("❌ Поиск отменён")
    
    elif action == "cat":
        category = ":".join(data[2:])
        posts = await catalog_service.search_posts(category, limit=5)
        if posts:
            for i, post in enumerate(posts, 1):
                await send_catalog_post_with_media(context.bot, query.message.chat_id, post, i, len(posts))
            keyboard = [[InlineKeyboardButton("✅ Готово", callback_data="catalog:finish")]]
            await query.edit_message_text(
                f"📂 Найдено: {len(posts)}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.edit_message_text(f"❌ В категории '{category}' пока нет постов")
    
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
        
        await query.edit_message_text(
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
        
        await query.edit_message_text(
            f"✅ Оценка: {stars}\n\n"
            f"📝 Пост #{catalog_number}\n\n"
            f"Теперь напишите текст отзыва (макс. 500 символов):",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif action == "cancel_review":
        context.user_data.pop('catalog_review', None)
        await query.edit_message_text("❌ Отзыв отменён")
    
    elif action == "cancel":
        context.user_data.pop('catalog_add', None)
        await query.edit_message_text("❌ Добавление отменено")
    
    elif action == "cancel_top":
        context.user_data.pop('catalog_add_top', None)
        await query.edit_message_text("❌ Добавление Top поста отменено")
    
    elif action == "cancel_ad":
        context.user_data.pop('catalog_ad', None)
        await query.edit_message_text("❌ Добавление рекламы отменено")
    
    elif action == "priority_finish":
        links = context.user_data.get('catalog_priority', {}).get('links', [])
        if links:
            count = await catalog_service.set_priority_posts(links)
            await query.edit_message_text(f"✅ Установлено {count} приоритетных постов")
        else:
            await query.edit_message_text("❌ Ссылки не добавлены")
        context.user_data.pop('catalog_priority', None)
    
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
        
        await query.edit_message_text(
            "➕ Выберите категорию для подписки:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif action == "follow_cat":
        category = ":".join(data[2:])
        success = await catalog_service.subscribe_to_category(user_id, category)
        
        if success:
            await query.answer("✅ Подписка оформлена!", show_alert=True)
            await query.edit_message_text(
                f"🔔 Вы подписались на категорию:\n**{category}**\n\n"
                "Теперь вы будете получать уведомления о новых постах!",
                parse_mode='Markdown'
            )
        else:
            await query.answer("❌ Вы уже подписаны на эту категорию", show_alert=True)
    
    elif action == "my_follows":
        subscriptions = await catalog_service.get_user_subscriptions(user_id)
        
        if not subscriptions:
            await query.edit_message_text(
                "📋 У вас нет активных подписок\n\n"
                "/categoryfollow - управление подписками"
            )
            return
        
        text = f"📋 **ВАШИ ПОДПИСКИ** ({len(subscriptions)})\n\n"
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
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif action == "unfollow":
        category = ":".join(data[2:])
        success = await catalog_service.unsubscribe_from_category(user_id, category)
        await query.answer("✅ Отписались" if success else "❌ Ошибка", show_alert=True)
        
        # Обновляем меню подписок
        subscriptions = await catalog_service.get_user_subscriptions(user_id)
        
        if not subscriptions:
            await query.edit_message_text(
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
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif action == "unfollow_all":
        count = await catalog_service.unsubscribe_from_all(user_id)
        await query.edit_message_text(
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
        
        keyboard.append([InlineKeyboardButton("📋 Все категории", callback_data="catalog:follow_menu")])
        keyboard.append([InlineKeyboardButton("📋 Мои подписки", callback_data="catalog:my_follows")])
        keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data="catalog:close_menu")])
        
        status = "✅ Вы подписаны" if is_subscribed else "❌ Вы не подписаны"
        
        await query.edit_message_text(
            f"🔔 **ПОДПИСКА НА КАТЕГОРИЮ**\n\n"
            f"📂 {category}\n"
            f"{status}\n\n"
            "Выберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    # ============= ОТЗЫВЫ =============
    
    elif action == "reviews_menu":
        post_id = int(data[2]) if len(data) > 2 else None
        if not post_id:
            return
        
        reviews = await catalog_service.get_reviews(post_id, limit=100)
        count = len(reviews)
        
        # Получаем информацию о посте
        post = await catalog_service.get_post_by_id(post_id)
        catalog_number = post.get('catalog_number', '????') if post else '????'
        
        keyboard = [
            [InlineKeyboardButton(f"👀 Смотреть отзывы ({count})", callback_data=f"catalog:view_reviews:{post_id}")],
            [InlineKeyboardButton("✍️ Оставить отзыв", callback_data=f"catalog:write_review:{post_id}:{catalog_number}")],
            [InlineKeyboardButton("❌ Закрыть", callback_data="catalog:close_menu")]
        ]
        
        await query.edit_message_text(
            f"🧑‍🧒‍🧒 **ОТЗЫВЫ О ПОСТЕ #{catalog_number}**\n\n"
            f"Всего отзывов: {count}\n\n"
            "Выберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif action == "view_reviews":
        post_id = int(data[2]) if len(data) > 2 else None
        if not post_id:
            return
        
        reviews = await catalog_service.get_reviews(post_id, limit=10)
        post = await catalog_service.get_post_by_id(post_id)
        catalog_number = post.get('catalog_number', '????') if post else '????'
        
        if not reviews:
            await query.edit_message_text(
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
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif action == "write_review":
        post_id = int(data[2]) if len(data) > 2 else None
        catalog_number = int(data[3]) if len(data) > 3 else None
        if not post_id:
            return
        
        # Сначала выбор звезд
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
        
        await query.edit_message_text(
            f"🌟 **ОЦЕНКА ПОСТА #{catalog_number}**\n\n"
            "Выберите оценку:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    # ============= РЕДАКТИРОВАНИЕ =============
    
    elif action == "remove_confirm":
        post_id = int(data[2]) if len(data) > 2 else None
        if post_id:
            success = await catalog_service.delete_post(post_id, user_id)
            await query.edit_message_text(
                f"🗑️ Пост удалён" if success else "❌ Ошибка"
            )
    
    elif action == "remove_cancel":
        await query.edit_message_text("❌ Удаление отменено")
    
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
        
        await query.edit_message_text(prompts.get(field, "Введите новое значение:"))
    
    elif action == "edit_cancel":
        context.user_data.pop('catalog_edit', None)
        await query.edit_message_text("❌ Редактирование отменено")
    
    elif action == "close_menu":
        await query.delete_message()


# ============= TEXT HANDLER =============

async def handle_catalog_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текста"""
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
    
    # ============= ОБРАБОТКА TOP ПОСТОВ =============
    if 'catalog_add_top' in context.user_data:
        data = context.user_data['catalog_add_top']
        step = data.get('step')
        
        if step == 'link':
            if text.startswith('https://t.me/'):
                data['catalog_link'] = text
                
                # Пытаемся импортировать медиа с уведомлением
                media_result = await extract_media_from_link(context.bot, text)
                
                if media_result and media_result.get('success'):
                    data['media_type'] = media_result['type']
                    data['media_file_id'] = media_result['file_id']
                    data['media_group_id'] = media_result.get('media_group_id')
                    data['media_json'] = media_result.get('media_json', [])
                    
                    await update.message.reply_text(f"{media_result['message']}")
                else:
                    await update.message.reply_text(f"{media_result.get('message', '⚠️ Добавьте медиа вручную')}")
                
                data['step'] = 'description'
                await update.message.reply_text(
                    "📝 Шаг 2/3\n\n"
                    "Описание (до 255 символов):"
                )
            else:
                await update.message.reply_text("❌ Ссылка должна начинаться с https://t.me/")
        
        elif step == 'description':
            data['name'] = text[:255]
            data['step'] = 'tags'
            await update.message.reply_text(
                "🏷️ Шаг 3/3\n\n"
                "Теги через запятую (до 10):"
            )
        
        elif step == 'tags':
            tags = [t.strip() for t in text.split(',') if t.strip()][:10]
            data['tags'] = tags
            
            # Сохраняем пост
            category = data['category']
            post_id = await catalog_service.add_post(
                user_id=user_id,
                catalog_link=data['catalog_link'],
                category=category,
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
                
                await update.message.reply_text(
                    f"✅ Пост #{catalog_number} добавлен в {category}!\n\n"
                    f"📝 {data['name']}\n"
                    f"🏷️ {len(tags)} тегов\n"
                    f"📸 Медиа: {'Да' if data.get('media_file_id') else 'Нет'}"
                )
                
                # Уведомляем подписчиков
                await notify_subscribers_about_new_post(context.bot, post_id, category)
            else:
                await update.message.reply_text("❌ Ошибка при добавлении поста")
            
            context.user_data.pop('catalog_add_top', None)
        
        return
    
    # Обработка отзыва (ТЕКСТ ПОСЛЕ ВЫБОРА ЗВЕЗД)
    if 'catalog_review' in context.user_data and context.user_data['catalog_review'].get('step') == 'text':
        post_id = context.user_data['catalog_review'].get('post_id')
        rating = context.user_data['catalog_review'].get('rating', 5)
        
        # Передаем бота для уведомлений
        review_id = await catalog_service.add_review(
            post_id=post_id,
            user_id=user_id,
            review_text=text[:500],
            rating=rating,
            username=update.effective_user.username,
            bot=context.bot
        )
        
        if review_id:
            stars = "⭐" * rating
            await update.message.reply_text(
                f"✅ Отзыв добавлен!\n\n"
                f"Оценка: {stars}\n\n"
                f"/catalog - продолжить просмотр"
            )
        else:
            await update.message.reply_text("❌ Ошибка при добавлении отзыва")
        
        context.user_data.pop('catalog_review', None)
        return
    
    # Добавление поста
    if 'catalog_add' in context.user_data:
        data = context.user_data['catalog_add']
        step = data.get('step')
        
        if step == 'link':
            if text.startswith('https://t.me/'):
                data['catalog_link'] = text
                data['step'] = 'category'
                
                # Пытаемся извлечь медиа
                media_result = await extract_media_from_link(context.bot, text)
                if media_result and media_result.get('success'):
                    data['media_type'] = media_result['type']
                    data['media_file_id'] = media_result['file_id']
                    data['media_group_id'] = media_result.get('media_group_id')
                    data['media_json'] = media_result.get('media_json', [])
                    await update.message.reply_text(f"{media_result['message']}")
                else:
                    await update.message.reply_text(f"{media_result.get('message', '⚠️ Добавьте медиа вручную')}")
                
                keyboard = [[InlineKeyboardButton(cat, callback_data=f"catalog:add_cat:{cat}")] for cat in CATALOG_CATEGORIES.keys()]
                await update.message.reply_text(
                    "📂 Шаг 2/5\n\nВыберите категорию:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await update.message.reply_text("❌ Ссылка должна начинаться с https://t.me/")
        
        elif step == 'name':
            data['name'] = text[:255]
            data['step'] = 'media'
            await update.message.reply_text(
                "📸 Шаг 4/5\n\n"
                "Отправьте фото/видео или нажмите /skip если медиа уже загружено"
            )
        
        elif step == 'tags':
            tags = [t.strip() for t in text.split(',') if t.strip()][:10]
            data['tags'] = tags
            
            # Сохраняем пост
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
                # Получаем номер поста
                post = await catalog_service.get_post_by_id(post_id)
                catalog_number = post.get('catalog_number', '????')
                
                await update.message.reply_text(
                    f"✅ Пост #{catalog_number} добавлен в каталог!\n\n"
                    f"📂 {data['category']}\n"
                    f"📝 {data['name']}\n"
                    f"🏷️ {len(tags)} тегов\n"
                    f"📸 Медиа: {'Да' if data.get('media_file_id') else 'Нет'}"
                )
                
                # Уведомляем подписчиков
                await notify_subscribers_about_new_post(context.bot, post_id, data['category'])
            else:
                await update.message.reply_text("❌ Ошибка при добавлении поста")
            
            context.user_data.pop('catalog_add', None)
        
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
    
    # Реклама
    if 'catalog_ad' in context.user_data:
        data = context.user_data['catalog_ad']
        step = data.get('step')
        
        if step == 'link':
            if text.startswith('https://t.me/'):
                data['catalog_link'] = text
                data['step'] = 'description'
                await update.message.reply_text("📝 Шаг 2/2\n\nОписание рекламы:")
            else:
                await update.message.reply_text("❌ Ссылка должна начинаться с https://t.me/")
        
        elif step == 'description':
            ad_id = await catalog_service.add_ad_post(
                catalog_link=data['catalog_link'],
                description=text[:255]
            )
            
            if ad_id:
                await update.message.reply_text(f"✅ Реклама #{ad_id} добавлена!")
            else:
                await update.message.reply_text("❌ Ошибка при добавлении рекламы")
            
            context.user_data.pop('catalog_ad', None)
        
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
            if text.startswith('https://t.me/'):
                success = await catalog_service.update_post_field(post_id, 'catalog_link', text)
                await update.message.reply_text("✅ Ссылка обновлена!" if success else "❌ Ошибка")
            else:
                await update.message.reply_text("❌ Ссылка должна начинаться с https://t.me/")
            context.user_data.pop('catalog_edit', None)
        
        elif field == 'number':
            try:
                new_number = int(text)
                if new_number < 1 or new_number > 9999:
                    await update.message.reply_text("❌ Номер должен быть от 1 до 9999")
                else:
                    success = await catalog_service.update_post_field(post_id, 'catalog_number', new_number)
                    if success:
                        await update.message.reply_text(f"✅ Номер изменён на #{new_number}")
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
