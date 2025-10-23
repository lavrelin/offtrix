# -*- coding: utf-8 -*-
"""
Handler для каталога услуг - ПОЛНАЯ ИСПРАВЛЕННАЯ ВЕРСИЯ
Проект: Трикс

Команды:
  - /catalog           : Просмотр каталога услуг
  - /search            : Поиск по категориям
  - /addtocatalog      : Добавить услугу в каталог
  - /review [post_id]  : Оставить отзыв
  - /catalogpriority   : (АДМИН) Установить приоритетные посты
  - /addcatalogreklama : (АДМИН) Добавить рекламный пост
  - /catalog_stats_*   : (АДМИН) Статистика
"""

import logging
from typing import Optional, List, Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, error
from telegram.ext import ContextTypes, ConversationHandler
from config import Config
from services.catalog_service import catalog_service, CATALOG_CATEGORIES

logger = logging.getLogger(__name__)

# Константы для шагов форм
STEP_LINK = 'link'
STEP_CATEGORY = 'category'
STEP_NAME = 'name'
STEP_MEDIA = 'media'
STEP_TAGS = 'tags'
STEP_DESCRIPTION = 'description'

MAX_POSTS_PER_PAGE = 5
MAX_PRIORITY_POSTS = 10
MAX_TAGS = 10
MAX_NAME_LENGTH = 255
MAX_REVIEW_LENGTH = 500
MAX_DESC_LENGTH = 1000


# ============= ПОЛЬЗОВАТЕЛЬСКИЕ КОМАНДЫ =============

async def catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Просмотр каталога услуг - /catalog
    Показывает случайные посты из каталога с возможностью фильтрации
    """
    try:
        user_id = update.effective_user.id
        count = MAX_POSTS_PER_PAGE
        
        # Получаем случайные посты
        posts = await catalog_service.get_random_posts(user_id, count=count)
        
        if not posts:
            keyboard = [
                [InlineKeyboardButton("🔄 Начать заново", callback_data="catalog:restart")],
                [InlineKeyboardButton("↩️ Главное меню", callback_data="menu:back")]
            ]
            
            await update.message.reply_text(
                "📂 Актуальных публикаций больше не осталось\n\n"
                "Нажмите 🔄 'Начать заново' чтобы обновить сессию.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        # Отправляем посты
        for i, post in enumerate(posts, 1):
            await send_catalog_post(update, context, post, i, len(posts))
        
        # Кнопки навигации
        keyboard = [
            [
                InlineKeyboardButton(f"➡️ Следующие {count}", callback_data="catalog:next"),
                InlineKeyboardButton("⏹️ Закончить", callback_data="catalog:finish")
            ],
            [InlineKeyboardButton("🕵🏻 Поиск", callback_data="catalog:search")]
        ]
        
        await update.message.reply_text(
            f"🔃 Показано постов: {len(posts)}\n\n"
            "Выберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    except Exception as e:
        logger.error(f"Error in catalog_command: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка. Попробуйте позже."
        )


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Поиск по каталогу - /search
    Показывает доступные категории для фильтрации
    """
    try:
        keyboard = []
        
        if not CATALOG_CATEGORIES:
            await update.message.reply_text(
                "📂 Категории отсутствуют. Попробуйте позже."
            )
            return
        
        for category in CATALOG_CATEGORIES.keys():
            keyboard.append(
                [InlineKeyboardButton(category, callback_data=f"catalog:cat:{category}")]
            )
        
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="menu:back")])
        
        text = (
            "🕵🏼 **ПОИСК В КАТАЛОГЕ**\n\n"
            "Выберите категорию для фильтрации:"
        )
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    except Exception as e:
        logger.error(f"Error in search_command: {e}")
        await update.message.reply_text("❌ Ошибка при загрузке категорий.")


async def addtocatalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Добавить запись в каталог - /addtocatalog
    Инициирует пошаговый процесс добавления услуги
    """
    try:
        user_id = update.effective_user.id
        
        # Проверяем, нет ли уже активной сессии
        if 'catalog_add' in context.user_data:
            await update.message.reply_text(
                "⚠️ У вас уже есть активная сессия добавления. "
                "Нажмите 'Отмена' чтобы начать заново."
            )
            return
        
        # Инициализируем данные формы
        context.user_data['catalog_add'] = {'step': STEP_LINK}
        
        keyboard = [[InlineKeyboardButton("🚗 Отмена", callback_data="catalog:cancel")]]
        
        text = (
            "🆕 **ДОБАВЛЕНИЕ В КАТАЛОГ УСЛУГ**\n\n"
            "Шаг 1 из 5\n\n"
            "⛓️ Отправьте ссылку на пост в Telegram-канале:\n\n"
            "Пример: `https://t.me/catalogtrix/123`"
        )
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    except Exception as e:
        logger.error(f"Error in addtocatalog_command: {e}")
        await update.message.reply_text("❌ Произошла ошибка.")


async def review_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Оставить отзыв - /review [post_id]
    Позволяет пользователю написать отзыв о специалисте
    """
    try:
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text(
                "🔄 Использование: `/review [номер_поста]`\n\n"
                "Пример: `/review 123`",
                parse_mode='Markdown'
            )
            return
        
        post_id = int(context.args[0])
        user_id = update.effective_user.id
        
        # Проверяем существование поста
        post = await catalog_service.get_post(post_id)
        if not post:
            await update.message.reply_text(
                f"❌ Пост #{post_id} не найден."
            )
            return
        
        # Сохраняем для ожидания текста отзыва
        context.user_data['catalog_review'] = {
            'post_id': post_id,
            'waiting': True
        }
        
        keyboard = [[InlineKeyboardButton("⏮️ Отмена", callback_data="catalog:cancel_review")]]
        
        await update.message.reply_text(
            f"🖋️ **ОТЗЫВ О СПЕЦИАЛИСТЕ**\n\n"
            f"ID поста: `{post_id}`\n"
            f"Специалист: {post.get('name', 'Неизвестно')}\n\n"
            f"Ваш отзыв (макс. {MAX_REVIEW_LENGTH} символов):",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    except Exception as e:
        logger.error(f"Error in review_command: {e}")
        await update.message.reply_text("❌ Произошла ошибка.")


# ============= АДМИНСКИЕ КОМАНДЫ =============

async def catalogpriority_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Установить приоритетные посты - /catalogpriority (АДМИН)
    Позволяет администратору выбрать посты, которые будут показываться в первую очередь
    """
    if not Config.is_admin(update.effective_user.id):
        logger.warning(f"Unauthorized admin command attempt by {update.effective_user.id}")
        return
    
    try:
        context.user_data['catalog_priority'] = {'waiting': True, 'links': []}
        
        keyboard = [[InlineKeyboardButton("☑️ Завершить", callback_data="catalog:priority_finish")]]
        
        text = (
            "🔬 **ПРИОРИТЕТНЫЕ ПОСТЫ**\n\n"
            f"Отправьте до {MAX_PRIORITY_POSTS} ссылок на посты (по одной в сообщении).\n\n"
            "Эти посты будут показываться пользователям в первую очередь.\n\n"
            "ℹ️ Пример: `https://t.me/catalogtrix/123`"
        )
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    except Exception as e:
        logger.error(f"Error in catalogpriority_command: {e}")


async def addcatalogreklama_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Добавить рекламный пост - /addcatalogreklama (АДМИН)
    Позволяет администратору добавить рекламу в каталог
    """
    if not Config.is_admin(update.effective_user.id):
        logger.warning(f"Unauthorized admin command attempt by {update.effective_user.id}")
        await update.message.reply_text("👮🏼‍♂️ Секретный доступ")
        return
    
    try:
        if 'catalog_ad' in context.user_data:
            await update.message.reply_text(
                "⚠️ Уже есть активная сессия добавления рекламы."
            )
            return
        
        context.user_data['catalog_ad'] = {'step': STEP_LINK}
        
        keyboard = [[InlineKeyboardButton("⬅️ Отмена", callback_data="catalog:cancel_ad")]]
        
        text = (
            "🌚 **ДОБАВЛЕНИЕ РЕКЛАМЫ**\n\n"
            "Шаг 1 из 3\n\n"
            "⛓️ Отправьте ссылку на рекламный пост:"
        )
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    except Exception as e:
        logger.error(f"Error in addcatalogreklama_command: {e}")


# ============= СТАТИСТИКА (АДМИН) =============

async def catalog_stats_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """🔘 Статистика пользователей - /catalog_stats_users (АДМИН)"""
    if not Config.is_admin(update.effective_user.id):
        return
    
    try:
        stats = await catalog_service.get_user_stats()
        
        text = (
            "🔘 **СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ**\n\n"
            f"◽️ Запустили /catalog сегодня: {stats.get('today', 0)}\n"
            f"◻️ За неделю: {stats.get('week', 0)}\n"
            f"⬜️ За месяц: {stats.get('month', 0)}\n\n"
            f"🎦 Среднее просмотров за сессию: {stats.get('avg_views', 0):.1f}"
        )
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    except Exception as e:
        logger.error(f"Error in catalog_stats_users_command: {e}")
        await update.message.reply_text("❌ Ошибка при загрузке статистики.")


async def catalog_stats_categories_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """📁 Статистика категорий - /catalog_stats_categories (АДМИН)"""
    if not Config.is_admin(update.effective_user.id):
        return
    
    try:
        stats = await catalog_service.get_category_stats()
        
        categories_text = "\n".join([
            f"{icon} {category}: {count}"
            for (category, icon), count in stats.items()
        ])
        
        text = (
            "📁 **СТАТИСТИКА КАТЕГОРИЙ**\n\n"
            "👽 Частота просмотров по категориям:\n\n"
            f"{categories_text}"
        )
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    except Exception as e:
        logger.error(f"Error in catalog_stats_categories_command: {e}")
        await update.message.reply_text("❌ Ошибка при загрузке статистики.")


async def catalog_stats_popular_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """👨🏼‍💻 ТОП 10 публикаций - /catalog_stats_popular (АДМИН)"""
    if not Config.is_admin(update.effective_user.id):
        return
    
    try:
        top_posts = await catalog_service.get_top_posts(limit=10)
        
        posts_text = "\n".join([
            f"{i}. Пост #{post['id']} - {post['views']} кликов ({post['name']})"
            for i, post in enumerate(top_posts, 1)
        ])
        
        text = (
            "🏆 **ТОП 10 ПОПУЛЯРНЫХ ПОСТОВ**\n\n"
            f"{posts_text if posts_text else 'Нет данных'}\n\n"
            "🗿 Обновления в LIVE режиме"
        )
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    except Exception as e:
        logger.error(f"Error in catalog_stats_popular_command: {e}")
        await update.message.reply_text("❌ Ошибка при загрузке статистики.")


# ============= CALLBACK HANDLERS =============

async def handle_catalog_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик callback запросов для каталога"""
    query = update.callback_query
    
    try:
        await query.answer()
    except Exception as e:
        logger.error(f"Error answering callback: {e}")
        return
    
    try:
        data = query.data
        user_id = query.from_user.id
        
        # Парсим callback data
        if not data.startswith("catalog:"):
            return
        
        parts = data.split(":")
        action = parts[1] if len(parts) > 1 else None
        
        if action == "next":
            # Показываем следующие посты
            posts = await catalog_service.get_random_posts(user_id, count=MAX_POSTS_PER_PAGE)
            
            if not posts:
                await query.edit_message_text("📂 Больше нет постов")
                return
            
            for i, post in enumerate(posts, 1):
                await send_catalog_post_callback(query, context, post, i, len(posts))
            
            await query.edit_message_text(
                f"🔃 Показано постов: {len(posts)}\n\n"
                "Выберите действие:"
            )
        
        elif action == "finish":
            await query.edit_message_text("⏹️ Просмотр завершен")
        
        elif action == "search":
            keyboard = []
            for category in CATALOG_CATEGORIES.keys():
                keyboard.append(
                    [InlineKeyboardButton(category, callback_data=f"catalog:cat:{category}")]
                )
            
            await query.edit_message_text(
                "🕵🏼 Выберите категорию:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif action == "cat":
            # Показываем посты категории
            category = parts[2] if len(parts) > 2 else None
            
            if category not in CATALOG_CATEGORIES:
                await query.edit_message_text("❌ Неизвестная категория")
                return
            
            posts = await catalog_service.get_posts_by_category(category, limit=MAX_POSTS_PER_PAGE)
            
            if not posts:
                await query.edit_message_text(f"📂 В категории '{category}' нет постов")
                return
            
            for i, post in enumerate(posts, 1):
                await send_catalog_post_callback(query, context, post, i, len(posts))
        
        elif action == "review":
            # Открываем форму отзыва
            post_id = int(parts[2]) if len(parts) > 2 else None
            
            if not post_id:
                await query.edit_message_text("❌ Некорректный ID поста")
                return
            
            context.user_data['catalog_review'] = {
                'post_id': post_id,
                'waiting': True
            }
            
            keyboard = [[InlineKeyboardButton("⏮️ Отмена", callback_data="catalog:cancel_review")]]
            
            await query.edit_message_text(
                f"🖋️ **ОТЗЫВ О СПЕЦИАЛИСТЕ**\n\n"
                f"ID поста: `{post_id}`\n\n"
                f"Ваш отзыв (макс. {MAX_REVIEW_LENGTH} символов):",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif action == "addcat":
            # Выбор категории при добавлении поста
            category = parts[2] if len(parts) > 2 else None
            
            if 'catalog_add' not in context.user_data:
                await query.edit_message_text("❌ Сессия истекла")
                return
            
            if category not in CATALOG_CATEGORIES:
                await query.edit_message_text("❌ Неизвестная категория")
                return
            
            data = context.user_data['catalog_add']
            data['category'] = category
            data['step'] = STEP_NAME
            
            keyboard = [[InlineKeyboardButton("⏭️ Пропустить", callback_data="catalog:skip_name")]]
            
            await query.edit_message_text(
                f"🚶🏻 Шаг 2 из 5\n\n"
                f"📝 Введите название вашей услуги (макс. {MAX_NAME_LENGTH} символов):\n\n"
                f"Категория: `{category}`",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif action == "skip_media":
            # Пропускаем медиа и переходим к тегам
            if 'catalog_add' not in context.user_data:
                await query.edit_message_text("❌ Сессия истекла")
                return
            
            data = context.user_data['catalog_add']
            data['step'] = STEP_TAGS
            
            keyboard = [[InlineKeyboardButton("✅ Завершить", callback_data="catalog:finish_add")]]
            
            await query.edit_message_text(
                "🚶‍♀️ Шаг 4 из 5\n\n"
                f"#️⃣ Добавьте теги через запятую (макс. {MAX_TAGS}, каждый до 50 символов):\n\n"
                "Пример: `маникюр, педикюр, ногти`",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif action == "finish_add":
            # Завершаем добавление поста
            if 'catalog_add' not in context.user_data:
                await query.edit_message_text("❌ Сессия истекла")
                return
            
            data = context.user_data['catalog_add']
            
            post_id = await catalog_service.add_post(
                user_id=user_id,
                catalog_link=data.get('link'),
                category=data.get('category'),
                name=data.get('name', 'Без названия'),
                tags=data.get('tags', []),
                media_file_id=data.get('media_file_id'),
                media_type=data.get('media_type')
            )
            
            context.user_data.pop('catalog_add', None)
            
            if post_id:
                await query.edit_message_text(
                    f"📇 **В каталог добавлена публикация**\n\n"
                    f"📬 ID: {post_id}\n"
                    f"📂 Категория: {data.get('category', 'N/A')}\n"
                    f"🎚️ Теги: {', '.join(data.get('tags', []))}",
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text("➖ Произошла ошибка при добавлении поста.")
        
        elif action == "restart":
            # Перезапускаем каталог
            await catalog_command(update, context)
        
        elif action == "cancel":
            context.user_data.pop('catalog_add', None)
            await query.edit_message_text("🙅🏻 Добавление отменено")
        
        elif action == "cancel_review":
            context.user_data.pop('catalog_review', None)
            await query.edit_message_text("🚮 Отзыв отменен")
        
        elif action == "cancel_ad":
            context.user_data.pop('catalog_ad', None)
            await query.edit_message_text("🕳️ Добавление рекламы отменено")
        
        elif action == "priority_finish":
            priority_data = context.user_data.get('catalog_priority', {})
            links = priority_data.get('links', [])
            
            if not links:
                await query.edit_message_text("🖇️ Ссылки не добавлены")
                return
            
            count = await catalog_service.set_priority_posts(links)
            context.user_data.pop('catalog_priority', None)
            
            await query.edit_message_text(
                f"👀 Priority посты добавлены 🩶\n\n"
                f"☑️ Успешно: {count} из {len(links)}"
            )
    
    except ValueError as ve:
        logger.error(f"ValueError in handle_catalog_callback: {ve}")
        await query.edit_message_text("❌ Некорректные данные")
    except Exception as e:
        logger.error(f"Error in handle_catalog_callback: {e}")
        await query.edit_message_text("❌ Произошла ошибка")


# ============= TEXT HANDLERS =============

async def handle_catalog_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений для процессов в каталоге"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    try:
        # === ДОБАВЛЕНИЕ ПОСТА ===
        if 'catalog_add' in context.user_data:
            await handle_add_post_flow(update, context, text)
        
        # === ОТЗЫВ ===
        elif 'catalog_review' in context.user_data:
            await handle_review_flow(update, context, text)
        
        # === ПРИОРИТЕТНЫЕ ПОСТЫ (АДМИН) ===
        elif 'catalog_priority' in context.user_data:
            await handle_priority_flow(update, context, text)
        
        # === РЕКЛАМНЫЙ ПОСТ (АДМИН) ===
        elif 'catalog_ad' in context.user_data:
            await handle_ad_flow(update, context, text)
    
    except Exception as e:
        logger.error(f"Error in handle_catalog_text: {e}")
        await update.message.reply_text("❌ Произошла ошибка при обработке сообщения.")


async def handle_add_post_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Обработка потока добавления поста"""
    user_id = update.effective_user.id
    data = context.user_data['catalog_add']
    step = data.get('step')
    
    if step == STEP_LINK:
        if not text.startswith('https://t.me/'):
            await update.message.reply_text(
                "🆖 Неверный формат ссылки!\n"
                "Ссылка должна начинаться с `https://t.me/`",
                parse_mode='Markdown'
            )
            return
        
        data['link'] = text
        data['step'] = STEP_CATEGORY
        
        keyboard = []
        for category in CATALOG_CATEGORIES.keys():
            keyboard.append(
                [InlineKeyboardButton(category, callback_data=f"catalog:addcat:{category}")]
            )
        
        await update.message.reply_text(
            "🚶🏻 Шаг 2 из 5\n\n"
            "📂 Выберите категорию:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif step == STEP_NAME:
        name = text[:MAX_NAME_LENGTH]
        data['name'] = name
        data['step'] = STEP_MEDIA
        
        keyboard = [[InlineKeyboardButton("⏭️ Пропустить медиа", callback_data="catalog:skip_media")]]
        
        await update.message.reply_text(
            "🚶‍♀️ Шаг 3 из 5\n\n"
            "📸 Отправьте фото, видео или альбом:\n\n"
            "💡 Это поможет клиентам увидеть вашу работу\n\n"
            "Или нажмите 'Пропустить'",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif step == STEP_TAGS:
        tags = [tag.strip() for tag in text.split(',')[:MAX_TAGS] if tag.strip()]
        tags = [tag[:50] for tag in tags]  # Ограничиваем длину каждого тега
        data['tags'] = tags
        
        post_id = await catalog_service.add_post(
            user_id=user_id,
            catalog_link=data['link'],
            category=data['category'],
            name=data.get('name', 'Без названия'),
            tags=tags,
            media_file_id=data.get('media_file_id'),
            media_type=data.get('media_type')
        )
        
        context.user_data.pop('catalog_add', None)
        
        if post_id:
            await update.message.reply_text(
                f"📇 **В каталог добавлена публикация**\n\n"
                f"📬 ID: {post_id}\n"
                f"📂 Категория: {data['category']}\n"
                f"🎚️ Теги: {', '.join(tags) if tags else 'Нет'}",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("➖ Произошла ошибка при добавлении.")


async def handle_review_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Обработка потока отзывов"""
    review_data = context.user_data['catalog_review']
    
    if review_data.get('waiting'):
        if len(text) > MAX_REVIEW_LENGTH:
            await update.message.reply_text(
                f"⚠️ Отзыв слишком длинный! "
                f"Макс. {MAX_REVIEW_LENGTH} символов, у вас {len(text)}"
            )
            return
        
        post_id = review_data['post_id']
        user_id = update.effective_user.id
        
        # Сохраняем отзыв
        success = await catalog_service.add_review(
            post_id=post_id,
            user_id=user_id,
            text=text
        )
        
        context.user_data.pop('catalog_review', None)
        
        if success:
            await update.message.reply_text(
                f"💾 **Отзыв сохранен!**\n\n"
                f"🛀 Спасибо за вашу активность! ☑️",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("⚠️ Не удалось сохранить отзыв")


async def handle_priority_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Обработка потока приоритетных постов"""
    priority_data = context.user_data['catalog_priority']
    
    if priority_data.get('waiting'):
        if not text.startswith('https://t.me/'):
            await update.message.reply_text("🙅🏼 Неверный формат ссылки")
            return
        
        links = priority_data['links']
        if len(links) >= MAX_PRIORITY_POSTS:
            await update.message.reply_text(
                f"⚠️ Максимум {MAX_PRIORITY_POSTS} ссылок достигнут"
            )
            return
        
        links.append(text)
        count = len(links)
        
        await update.message.reply_text(
            f"⛓️‍💥 Ссылка {count}/{MAX_PRIORITY_POSTS} добавлена\n\n"
            f"Отправьте еще или нажмите 'Завершить'"
        )


async def handle_ad_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Обработка потока рекламных постов"""
    ad_data = context.user_data['catalog_ad']
    step = ad_data.get('step')
    
    if step == STEP_LINK:
        if not text.startswith('https://t.me/'):
            await update.message.reply_text("🧷 Неверный формат ссылки")
            return
        
        ad_data['link'] = text
        ad_data['step'] = STEP_DESCRIPTION
        
        await update.message.reply_text(
            "🏙️ Шаг 2 из 3\n\n"
            f"👩🏼‍💻 Добавьте описание рекламы (макс. {MAX_DESC_LENGTH} символов):"
        )
    
    elif step == STEP_DESCRIPTION:
        if len(text) > MAX_DESC_LENGTH:
            await update.message.reply_text(
                f"⚠️ Описание слишком длинное! "
                f"Макс. {MAX_DESC_LENGTH} символов"
            )
            return
        
        ad_data['description'] = text
        
        post_id = await catalog_service.add_ad_post(
            catalog_link=ad_data['link'],
            description=text
        )
        
        context.user_data.pop('catalog_ad', None)
        
        if post_id:
            await update.message.reply_text(
                f"🌌 **Реклама добавлена!**\n\n"
                f"◻️ ID: {post_id}\n\n"
                f"▫️ Отображается каждые 10 постов",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("💁🏻 Ошибка при добавлении рекламы")


# ============= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =============

async def send_catalog_post(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    post: Dict[str, Any],
    index: int,
    total: int
) -> None:
    """
    Отправить пост каталога через обычное сообщение
    """
    try:
        category = post.get('category', 'N/A')
        name = post.get('name', 'Без названия')
        tags = post.get('tags', [])
        views = post.get('views', 0)
        post_id = post.get('id')
        catalog_link = post.get('catalog_link', '#')
        
        text = (
            f"🏙️ **Запись {index}/{total}**\n\n"
            f"🏞️ Категория: `{category}`\n"
            f"🎑 **{name}**\n\n"
            f"🌌 Теги: {', '.join(tags) if tags else 'нет'}\n"
            f"🌠 Просмотров: {views}"
        )
        
        keyboard = [
            [InlineKeyboardButton("🏃🏻‍♀️ К посту", url=catalog_link)],
            [InlineKeyboardButton("🧑🏼‍💻 Отзыв", callback_data=f"catalog:review:{post_id}")]
        ]
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        # Увеличиваем счетчик просмотров
        await catalog_service.increment_views(post_id)
    
    except Exception as e:
        logger.error(f"Error in send_catalog_post: {e}")


async def send_catalog_post_callback(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    post: Dict[str, Any],
    index: int,
    total: int
) -> None:
    """
    Отправить пост каталога через callback запрос
    """
    try:
        category = post.get('category', 'N/A')
        name = post.get('name', 'Без названия')
        tags = post.get('tags', [])
        views = post.get('views', 0)
        post_id = post.get('id')
        catalog_link = post.get('catalog_link', '#')
        
        text = (
            f"🪽 **Запись {index}/{total}**\n\n"
            f"💨 Категория: `{category}`\n"
            f"🌊 **{name}**\n\n"
            f"🌪️ Теги: {', '.join(tags) if tags else 'нет'}\n"
            f"🎬 Просмотров: {views}"
        )
        
        keyboard = [
            [InlineKeyboardButton("💁🏼 К посту", url=catalog_link)],
            [InlineKeyboardButton("👱🏻‍♀️ Отзыв", callback_data=f"catalog:review:{post_id}")]
        ]
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        # Увеличиваем счетчик просмотров
        await catalog_service.increment_views(post_id)
    
    except Exception as e:
        logger.error(f"Error in send_catalog_post_callback: {e}")


# ============= ЭКСПОРТ ФУНКЦИЙ =============

__all__ = [
    'catalog_command',
    'search_command',
    'addtocatalog_command',
    'review_command',
    'catalogpriority_command',
    'addcatalogreklama_command',
    'catalog_stats_users_command',
    'catalog_stats_categories_command',
    'catalog_stats_popular_command',
    'handle_catalog_callback',
    'handle_catalog_text',
]
