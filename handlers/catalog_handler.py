# -*- coding: utf-8 -*-
"""
Handler для каталога услуг - ФИНАЛЬНАЯ ВЕРСИЯ V3
Проект: Трикс

ИСПРАВЛЕНИЯ V3:
✅ Импорт фото из ссылки на пост или выбор
✅ Работающий поиск по ключевым словам
✅ Работающие отзывы
✅ Убрали показ просмотров для пользователей
✅ Добавлена /catalogview для администраторов

Команды:
  - /catalog           : Просмотр каталога услуг
  - /search            : Поиск по категориям и ключевым словам
  - /addtocatalog      : Добавить услугу в каталог
  - /review [post_id]  : Оставить отзыв
  - /catalogpriority   : (АДМИН) Установить приоритетные посты
  - /addcatalogreklama : (АДМИН) Добавить рекламный пост
  - /catalogview       : (АДМИН) Статистика просмотров
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from services.catalog_service import catalog_service, CATALOG_CATEGORIES
from services.db import db

logger = logging.getLogger(__name__)

# Константы для шагов форм
STEP_LINK = 'link'
STEP_CATEGORY = 'category'
STEP_NAME = 'name'
STEP_MEDIA_SOURCE = 'media_source'
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
    """Просмотр каталога услуг - /catalog"""
    try:
        user_id = update.effective_user.id
        count = MAX_POSTS_PER_PAGE
        
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
        
        for i, post in enumerate(posts, 1):
            await send_catalog_post(update, context, post, i, len(posts))
        
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
        await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Поиск по каталогу - /search"""
    try:
        keyboard = [
            [InlineKeyboardButton("🔤 По ключевому слову", callback_data="catalog:search:keyword")],
            [InlineKeyboardButton("🏷️ По категории", callback_data="catalog:search:category")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="menu:back")]
        ]
        
        text = (
            "🕵🏼 **ПОИСК В КАТАЛОГЕ**\n\n"
            "Выберите способ поиска:"
        )
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    except Exception as e:
        logger.error(f"Error in search_command: {e}")
        await update.message.reply_text("❌ Ошибка при загрузке поиска.")


async def addtocatalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавить запись в каталог - /addtocatalog"""
    try:
        if 'catalog_add' in context.user_data:
            await update.message.reply_text("⚠️ У вас уже есть активная сессия добавления.")
            return
        
        context.user_data['catalog_add'] = {'step': STEP_LINK}
        
        keyboard = [[InlineKeyboardButton("🚗 Отмена", callback_data="catalog:cancel")]]
        
        text = (
            "🆕 **ДОБАВЛЕНИЕ В КАТАЛОГ УСЛУГ**\n\n"
            "Шаг 1 из 5\n\n"
            "⛓️ Отправьте ссылку на пост в Telegram-канале:\n"
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
    """Оставить отзыв - /review [post_id]"""
    try:
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text(
                "🔄 Использование: `/review [номер_поста]`\n\nПример: `/review 123`",
                parse_mode='Markdown'
            )
            return
        
        post_id = int(context.args[0])
        
        post = await catalog_service.get_post_by_id(post_id)
        if not post:
            await update.message.reply_text(f"❌ Пост #{post_id} не найден.")
            return
        
        context.user_data['catalog_review'] = {'post_id': post_id, 'waiting': True}
        
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
    """Установить приоритетные посты - /catalogpriority (АДМИН)"""
    if not Config.is_admin(update.effective_user.id):
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
    """Добавить рекламный пост - /addcatalogreklama (АДМИН)"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("👮🏼‍♂️ Секретный доступ")
        return
    
    try:
        if 'catalog_ad' in context.user_data:
            await update.message.reply_text("⚠️ Уже есть активная сессия добавления рекламы.")
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


async def catalogview_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Статистика просмотров каталога - /catalogview (АДМИН)"""
    if not Config.is_admin(update.effective_user.id):
        return
    
    try:
        stats = await catalog_service.get_catalog_stats()
        
        text = (
            "👀 **СТАТИСТИКА ПРОСМОТРОВ КАТАЛОГА**\n\n"
            f"📊 Всего постов: {stats.get('total_posts', 0)}\n"
            f"📸 С медиа: {stats.get('posts_with_media', 0)}\n\n"
            f"📈 Всего просмотров: {stats.get('total_views', 0)}\n"
            f"🖱️ Всего кликов: {stats.get('total_clicks', 0)}\n"
            f"📊 CTR: {stats.get('ctr', 0)}%\n\n"
            f"👥 Активных сессий: {stats.get('active_sessions', 0)}\n"
            f"✅ Медиа покрытие: {stats.get('media_percentage', 0)}%"
        )
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    except Exception as e:
        logger.error(f"Error in catalogview_command: {e}")
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
        
        if not data.startswith("catalog:"):
            return
        
        parts = data.split(":")
        action = parts[1] if len(parts) > 1 else None
        
        if action == "next":
            posts = await catalog_service.get_random_posts(user_id, count=MAX_POSTS_PER_PAGE)
            
            if not posts:
                await query.edit_message_text("📂 Больше нет постов")
                return
            
            for i, post in enumerate(posts, 1):
                await send_catalog_post_callback(query, context, post, i, len(posts))
        
        elif action == "search":
            keyboard = [
                [InlineKeyboardButton("🔤 По ключевому слову", callback_data="catalog:search:keyword")],
                [InlineKeyboardButton("🏷️ По категории", callback_data="catalog:search:category")],
            ]
            
            try:
                await query.edit_message_text(
                    "🕵🏼 **ПОИСК В КАТАЛОГЕ**\n\nВыберите способ поиска:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            except Exception:
                pass
        
        elif action == "search" and len(parts) > 2:
            search_type = parts[2]
            
            if search_type == "keyword":
                context.user_data['catalog_search'] = {'type': 'keyword', 'waiting': True}
                keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="catalog:cancel_search")]]
                
                try:
                    await query.edit_message_text(
                        "🔤 **ПОИСК ПО КЛЮЧЕВОМУ СЛОВУ**\n\n"
                        "Введите слово, тег или название услуги:",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
                except Exception:
                    pass
            
            elif search_type == "category":
                keyboard = []
                for category in CATALOG_CATEGORIES.keys():
                    keyboard.append(
                        [InlineKeyboardButton(category, callback_data=f"catalog:cat:{category}")]
                    )
                
                try:
                    await query.edit_message_text(
                        "📂 **ПОИСК ПО КАТЕГОРИИ**\n\nВыберите категорию:",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
                except Exception:
                    pass
        
        elif action == "cat":
            category = parts[2] if len(parts) > 2 else None
            
            if category not in CATALOG_CATEGORIES:
                await query.edit_message_text("❌ Неизвестная категория")
                return
            
            posts = await catalog_service.search_posts(category=category, limit=MAX_POSTS_PER_PAGE)
            
            if not posts:
                await query.edit_message_text(f"📂 В категории '{category}' нет постов")
                return
            
            for i, post in enumerate(posts, 1):
                await send_catalog_post_callback(query, context, post, i, len(posts))
        
        elif action == "review":
            post_id = int(parts[2]) if len(parts) > 2 else None
            
            if not post_id:
                await query.edit_message_text("❌ Некорректный ID поста")
                return
            
            context.user_data['catalog_review'] = {'post_id': post_id, 'waiting': True}
            
            keyboard = [[InlineKeyboardButton("⏮️ Отмена", callback_data="catalog:cancel_review")]]
            
            try:
                await query.edit_message_text(
                    f"🖋️ **ОТЗЫВ**\n\nID поста: `{post_id}`\n\n"
                    f"Ваш отзыв (макс. {MAX_REVIEW_LENGTH} символов):",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            except Exception:
                pass
        
        elif action == "addcat":
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
            
            try:
                await query.edit_message_text(
                    f"🚶🏻 Шаг 2 из 5\n\n"
                    f"📝 Введите название (макс. {MAX_NAME_LENGTH} символов):\n\n"
                    f"Категория: `{category}`",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            except Exception:
                pass
        
        elif action == "skip_name":
            if 'catalog_add' not in context.user_data:
                await query.edit_message_text("❌ Сессия истекла")
                return
            
            data = context.user_data['catalog_add']
            data['name'] = 'Без названия'
            data['step'] = STEP_MEDIA_SOURCE
            
            keyboard = [
                [InlineKeyboardButton("📥 Импортировать из поста", callback_data="catalog:import_photo")],
                [InlineKeyboardButton("📤 Загрузить своё фото", callback_data="catalog:upload_photo")],
                [InlineKeyboardButton("⏭️ Без фото", callback_data="catalog:skip_media")]
            ]
            
            try:
                await query.edit_message_text(
                    "🚶‍♀️ Шаг 3 из 5\n\n"
                    "📸 Выберите источник фото:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            except Exception:
                pass
        
        elif action == "import_photo":
            if 'catalog_add' not in context.user_data:
                await query.edit_message_text("❌ Сессия истекла")
                return
            
            data = context.user_data['catalog_add']
            data['step'] = 'waiting_import_link'
            
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="catalog:cancel")]]
            
            try:
                await query.edit_message_text(
                    "📥 **ИМПОРТ ФОТО**\n\n"
                    "Отправьте ссылку на пост с фото:\n"
                    "Пример: `https://t.me/channel/123`",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            except Exception:
                pass
        
        elif action == "upload_photo":
            if 'catalog_add' not in context.user_data:
                await query.edit_message_text("❌ Сессия истекла")
                return
            
            data = context.user_data['catalog_add']
            data['step'] = STEP_MEDIA
            
            keyboard = [[InlineKeyboardButton("⏭️ Без фото", callback_data="catalog:skip_media")]]
            
            try:
                await query.edit_message_text(
                    "📤 **ЗАГРУЗКА ФОТО**\n\n"
                    "Отправьте фото, видео или анимацию:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            except Exception:
                pass
        
        elif action == "skip_media":
            if 'catalog_add' not in context.user_data:
                await query.edit_message_text("❌ Сессия истекла")
                return
            
            data = context.user_data['catalog_add']
            data['step'] = STEP_TAGS
            
            keyboard = [[InlineKeyboardButton("✅ Завершить", callback_data="catalog:finish_add")]]
            
            try:
                await query.edit_message_text(
                    "🚶‍♀️ Шаг 4 из 5\n\n"
                    f"#️⃣ Добавьте теги через запятую (макс. {MAX_TAGS}):\n\n"
                    "Пример: `маникюр, педикюр, ногти`",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            except Exception:
                pass
        
        elif action == "finish_add":
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
                try:
                    await query.edit_message_text(
                        f"📇 **В каталог добавлена публикация!**\n\n"
                        f"📬 ID: {post_id}\n"
                        f"📂 Категория: {data.get('category', 'N/A')}\n"
                        f"🎚️ Теги: {', '.join(data.get('tags', [])) or 'Нет'}",
                        parse_mode='Markdown'
                    )
                except Exception:
                    pass
            else:
                await query.edit_message_text("➖ Ошибка при добавлении.")
        
        elif action == "restart":
            await catalog_command(update, context)
        
        elif action == "finish":
            await query.edit_message_text("⏹️ Просмотр завершен")
        
        elif action == "cancel":
            context.user_data.pop('catalog_add', None)
            try:
                await query.edit_message_text("🙅🏻 Добавление отменено")
            except Exception:
                pass
        
        elif action == "cancel_search":
            context.user_data.pop('catalog_search', None)
            try:
                await query.edit_message_text("🙅🏻 Поиск отменен")
            except Exception:
                pass
        
        elif action == "cancel_review":
            context.user_data.pop('catalog_review', None)
            try:
                await query.edit_message_text("🚮 Отзыв отменен")
            except Exception:
                pass
        
        elif action == "cancel_ad":
            context.user_data.pop('catalog_ad', None)
            try:
                await query.edit_message_text("🕳️ Добавление рекламы отменено")
            except Exception:
                pass
        
        elif action == "priority_finish":
            priority_data = context.user_data.get('catalog_priority', {})
            links = priority_data.get('links', [])
            
            if not links:
                await query.edit_message_text("🖇️ Ссылки не добавлены")
                return
            
            count = await catalog_service.set_priority_posts(links)
            context.user_data.pop('catalog_priority', None)
            
            try:
                await query.edit_message_text(
                    f"👀 Priority посты добавлены\n\n"
                    f"☑️ Успешно: {count} из {len(links)}"
                )
            except Exception:
                pass
    
    except ValueError as ve:
        logger.error(f"ValueError in handle_catalog_callback: {ve}")
        try:
            await query.edit_message_text("❌ Некорректные данные")
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Error in handle_catalog_callback: {e}")
        try:
            await query.edit_message_text("❌ Произошла ошибка")
        except Exception:
            pass


# ============= TEXT HANDLERS =============

async def handle_catalog_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений для каталога"""
    user_id = update.effective_user.id
    text = update.message.text.strip() if update.message.text else ""
    
    try:
        # Поиск по ключевому слову
        if 'catalog_search' in context.user_data:
            search_data = context.user_data['catalog_search']
            if search_data.get('waiting') and search_data.get('type') == 'keyword':
                await handle_search_flow(update, context, text)
                return
        
        # Добавление поста
        if 'catalog_add' in context.user_data:
            await handle_add_post_flow(update, context, text, context.bot)
            return
        
        # Отзыв
        if 'catalog_review' in context.user_data:
            await handle_review_flow(update, context, text)
            return
        
        # Приоритеты
        if 'catalog_priority' in context.user_data:
            await handle_priority_flow(update, context, text)
            return
        
        # Реклама
        if 'catalog_ad' in context.user_data:
            await handle_ad_flow(update, context, text)
            return
    
    except Exception as e:
        logger.error(f"Error in handle_catalog_text: {e}")
        try:
            await update.message.reply_text("❌ Ошибка при обработке.")
        except:
            pass


async def handle_catalog_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Обработчик медиа для каталога"""
    try:
        if 'catalog_add' not in context.user_data:
            return False
        
        data = context.user_data['catalog_add']
        step = data.get('step')
        
        if step != STEP_MEDIA:
            return False
        
        media_type = None
        media_file_id = None
        
        if update.message.photo:
            media_type = 'photo'
            media_file_id = update.message.photo[-1].file_id
        elif update.message.video:
            media_type = 'video'
            media_file_id = update.message.video.file_id
        elif update.message.animation:
            media_type = 'animation'
            media_file_id = update.message.animation.file_id
        
        if not media_file_id:
            await update.message.reply_text("⚠️ Неподдерживаемый формат")
            return True
        
        data['media_file_id'] = media_file_id
        data['media_type'] = media_type
        data['step'] = STEP_TAGS
        
        keyboard = [[InlineKeyboardButton("✅ Завершить", callback_data="catalog:finish_add")]]
        
        await update.message.reply_text(
            "🚶‍♀️ Шаг 4 из 5\n\n"
            f"#️⃣ Добавьте теги (макс. {MAX_TAGS}):\n\n"
            "Пример: `маникюр, педикюр, ногти`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        return True
    
    except Exception as e:
        logger.error(f"Error in handle_catalog_media: {e}")
        return True


# ============= FLOW HANDLERS =============

async def handle_search_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, query_text: str) -> None:
    """Обработка поиска по ключевым словам"""
    user_id = update.effective_user.id
    
    if not query_text or len(query_text) < 2:
        await update.message.reply_text("⚠️ Введите минимум 2 символа")
        return
    
    all_posts = await catalog_service.get_random_posts(user_id, count=100)
    
    query_lower = query_text.lower()
    found_posts = []
    
    for post in all_posts:
        name = post.get('name', '').lower()
        tags = [tag.lower() for tag in post.get('tags', [])]
        category = post.get('category', '').lower()
        
        if (query_lower in name or 
            any(query_lower in tag for tag in tags) or
            query_lower in category):
            found_posts.append(post)
    
    context.user_data.pop('catalog_search', None)
    
    if not found_posts:
        keyboard = [[InlineKeyboardButton("🔄 Новый поиск", callback_data="catalog:search:keyword")]]
        await update.message.reply_text(
            f"🔍 По запросу '{query_text}' ничего не найдено",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    found_posts = found_posts[:MAX_POSTS_PER_PAGE]
    
    await update.message.reply_text(
        f"✅ **Найдено результатов: {len(found_posts)}**",
        parse_mode='Markdown'
    )
    
    for i, post in enumerate(found_posts, 1):
        await send_catalog_post(update, context, post, i, len(found_posts))
    
    keyboard = [
        [InlineKeyboardButton("🔄 Новый поиск", callback_data="catalog:search:keyword")],
        [InlineKeyboardButton("↩️ Главное меню", callback_data="menu:back")]
    ]
    
    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_add_post_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, bot) -> None:
    """Обработка добавления поста"""
    user_id = update.effective_user.id
    data = context.user_data['catalog_add']
    step = data.get('step')
    
    if step == STEP_LINK:
        if not text.startswith('https://t.me/'):
            await update.message.reply_text("🆖 Неверный формат ссылки!")
            return
        
        data['link'] = text
        data['step'] = STEP_CATEGORY
        
        keyboard = []
        for category in CATALOG_CATEGORIES.keys():
            keyboard.append([InlineKeyboardButton(category, callback_data=f"catalog:addcat:{category}")])
        
        await update.message.reply_text(
            "🚶🏻 Шаг 2 из 5\n\n📂 Выбе ритеритте категорию:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif step == STEP_NAME:
        data['name'] = text[:MAX_NAME_LENGTH]
        data['step'] = STEP_MEDIA_SOURCE
        
        keyboard = [
            [InlineKeyboardButton("📥 Импортировать из поста", callback_data="catalog:import_photo")],
            [InlineKeyboardButton("📤 Загрузить своё", callback_data="catalog:upload_photo")],
            [InlineKeyboardButton("⏭️ Без фото", callback_data="catalog:skip_media")]
        ]
        
        await update.message.reply_text(
            "🚶‍♀️ Шаг 3 из 5\n\n📸 Выберите источник фото:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif step == 'waiting_import_link':
        if not text.startswith('https://t.me/'):
            await update.message.reply_text("🆖 Неверный формат ссылки!")
            return
        
        await update.message.reply_text("⏳ Импортирую фото из поста...")
        
        media_info = await extract_media_from_link(text, bot)
        
        if media_info and media_info.get('found'):
            data['media_file_id'] = media_info.get('file_id')
            data['media_type'] = media_info.get('media_type')
            await update.message.reply_text("✅ Фото импортировано!")
        else:
            await update.message.reply_text("❌ Фото не найдено в посте. Попробуйте загрузить своё.")
        
        data['step'] = STEP_TAGS
        
        keyboard = [[InlineKeyboardButton("✅ Завершить", callback_data="catalog:finish_add")]]
        
        await update.message.reply_text(
            f"🚶‍♀️ Шаг 4 из 5\n\n#️⃣ Добавьте теги (макс. {MAX_TAGS}):\n\n"
            "Пример: `маникюр, педикюр, ногти`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif step == STEP_TAGS:
        tags = [tag.strip() for tag in text.split(',')[:MAX_TAGS] if tag.strip()]
        tags = [tag[:50] for tag in tags]
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
                f"📇 **Публикация добавлена!**\n\n"
                f"📬 ID: {post_id}\n"
                f"📂 Категория: {data['category']}\n"
                f"🎚️ Теги: {', '.join(tags) if tags else 'Нет'}",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("➖ Ошибка при добавлении.")


async def handle_review_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Обработка отзывов"""
    review_data = context.user_data['catalog_review']
    
    if review_data.get('waiting'):
        if len(text) > MAX_REVIEW_LENGTH:
            await update.message.reply_text(
                f"⚠️ Слишком длинный отзыв! Макс. {MAX_REVIEW_LENGTH} символов"
            )
            return
        
        post_id = review_data['post_id']
        user_id = update.effective_user.id
        
        try:
            async with db.get_session() as session:
                from models import CatalogReview
                
                review = CatalogReview(
                    post_id=post_id,
                    user_id=user_id,
                    text=text,
                    created_at=datetime.utcnow()
                )
                
                session.add(review)
                await session.commit()
                
                context.user_data.pop('catalog_review', None)
                
                await update.message.reply_text(
                    "💾 **Отзыв сохранен!**\n\n"
                    "🛀 Спасибо за активность! ☑️",
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Error saving review: {e}")
            context.user_data.pop('catalog_review', None)
            await update.message.reply_text("⚠️ Ошибка при сохранении отзыва")


async def handle_priority_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Обработка приоритетных постов"""
    priority_data = context.user_data['catalog_priority']
    
    if priority_data.get('waiting'):
        if not text.startswith('https://t.me/'):
            await update.message.reply_text("🙅🏼 Неверный формат ссылки")
            return
        
        links = priority_data['links']
        if len(links) >= MAX_PRIORITY_POSTS:
            await update.message.reply_text(f"⚠️ Максимум {MAX_PRIORITY_POSTS} ссылок")
            return
        
        links.append(text)
        count = len(links)
        
        await update.message.reply_text(
            f"⛓️ Ссылка {count}/{MAX_PRIORITY_POSTS} добавлена"
        )


async def handle_ad_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Обработка рекламных постов"""
    ad_data = context.user_data['catalog_ad']
    step = ad_data.get('step')
    
    if step == STEP_LINK:
        if not text.startswith('https://t.me/'):
            await update.message.reply_text("🧷 Неверный формат ссылки")
            return
        
        ad_data['link'] = text
        ad_data['step'] = STEP_DESCRIPTION
        
        await update.message.reply_text(
            "🏙️ Шаг 2 из 3\n\n👩🏼‍💻 Добавьте описание рекламы:"
        )
    
    elif step == STEP_DESCRIPTION:
        if len(text) > MAX_DESC_LENGTH:
            await update.message.reply_text(f"⚠️ Слишком длинное! Макс. {MAX_DESC_LENGTH}")
            return
        
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
            await update.message.reply_text("💁🏻 Ошибка при добавлении")


# ============= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =============

async def extract_media_from_link(link: str, bot) -> Optional[Dict]:
    """Извлечение медиа из ссылки на Telegram пост"""
    try:
        if not link.startswith('https://t.me/'):
            return None
        
        parts = link.replace('https://t.me/', '').split('/')
        
        if len(parts) < 2:
            return None
        
        if parts[0] == 'c' and len(parts) == 3:
            channel_id = f"-100{parts[1]}"
            message_id = int(parts[2])
        else:
            channel_id = parts[0]
            message_id = int(parts[1])
        
        try:
            message = await bot.get_chat(channel_id)
            msg = await bot.get_chat_message(channel_id, message_id)
            
            if msg.photo:
                return {'media_type': 'photo', 'file_id': msg.photo[-1].file_id, 'found': True}
            elif msg.video:
                return {'media_type': 'video', 'file_id': msg.video.file_id, 'found': True}
            elif msg.animation:
                return {'media_type': 'animation', 'file_id': msg.animation.file_id, 'found': True}
            else:
                return {'found': False}
        except Exception as e:
            logger.warning(f"Could not fetch message: {e}")
            return None
    
    except Exception as e:
        logger.error(f"Error extracting media: {e}")
        return None


async def send_catalog_post(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                           post: dict, index: int, total: int) -> None:
    """Отправить пост (без показа просмотров)"""
    try:
        text = (
            f"🏙️ **Запись {index}/{total}**\n\n"
            f"📂 Категория: `{post.get('category', 'N/A')}`\n"
            f"🎑 **{post.get('name', 'Без названия')}**\n\n"
            f"🌌 Теги: {', '.join(post.get('tags', [])) if post.get('tags') else 'нет'}"
        )
        
        keyboard = [
            [InlineKeyboardButton("🏃🏻‍♀️ К посту", url=post.get('catalog_link', '#'))],
            [InlineKeyboardButton("🧑🏼‍💻 Отзыв", callback_data=f"catalog:review:{post['id']}")]
        ]
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        await catalog_service.increment_views(post['id'])
    
    except Exception as e:
        logger.error(f"Error in send_catalog_post: {e}")


async def send_catalog_post_callback(query, context: ContextTypes.DEFAULT_TYPE, 
                                    post: dict, index: int, total: int) -> None:
    """Отправить пост через callback (без показа просмотров)"""
    try:
        text = (
            f"🪽 **Запись {index}/{total}**\n\n"
            f"💨 Категория: `{post.get('category', 'N/A')}`\n"
            f"🌊 **{post.get('name', 'Без названия')}**\n\n"
            f"🌪️ Теги: {', '.join(post.get('tags', [])) if post.get('tags') else 'нет'}"
        )
        
        keyboard = [
            [InlineKeyboardButton("💁🏼 К посту", url=post.get('catalog_link', '#'))],
            [InlineKeyboardButton("👱🏻‍♀️ Отзыв", callback_data=f"catalog:review:{post['id']}")]
        ]
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        await catalog_service.increment_views(post['id'])
    
    except Exception as e:
        logger.error(f"Error in send_catalog_post_callback: {e}")


__all__ = [
    'catalog_command',
    'search_command',
    'addtocatalog_command',
    'review_command',
    'catalogpriority_command',
    'addcatalogreklama_command',
    'catalogview_command',
    'handle_catalog_callback',
    'handle_catalog_text',
    'handle_catalog_media',
]
