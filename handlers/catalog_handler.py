# -*- coding: utf-8 -*-
"""
Handler для каталога услуг - ПОЛНАЯ ВЕРСИЯ С МЕДИА
Команды: /catalog, /search, /addtocatalog, /review, /catalogpriority, /addcatalogreklama
"""
import logging
from typing import Optional, Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from services.catalog_service import catalog_service, CATALOG_CATEGORIES

logger = logging.getLogger(__name__)

# ============= ПОЛЬЗОВАТЕЛЬСКИЕ КОМАНДЫ =============

async def catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр каталога услуг - /catalog"""
    user_id = update.effective_user.id
    
    # Получаем 5-10 случайных постов
    count = 5
    posts = await catalog_service.get_random_posts(user_id, count=count)
    
    if not posts:
        keyboard = [
            [InlineKeyboardButton("🔄 Начать заново", callback_data="catalog:restart")],
            [InlineKeyboardButton("↩️ Главное меню", callback_data="menu:back")]
        ]
        
        await update.message.reply_text(
            "📂 Актуальных публикаций больше не осталось\n\n"
            "Нажмите 🔄'Начать заново' чтобы обновить сессию.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # Отправляем посты С МЕДИА
    for i, post in enumerate(posts, 1):
        await send_catalog_post_with_media(
            context.bot,
            update.effective_chat.id,
            post,
            i,
            len(posts)
        )
    
    # Кнопки навигации
    keyboard = [
        [
            InlineKeyboardButton(f"➡️ Следующие {count}", callback_data="catalog:next"),
            InlineKeyboardButton("⏹️ Закончить", callback_data="catalog:finish")
        ],
        [InlineKeyboardButton("🕵🏻‍♀️ Поиск", callback_data="catalog:search")]
    ]
    
    await update.message.reply_text(
        f"🔃 Показано постов: {len(posts)}\n\n"
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поиск по каталогу - /search"""
    
    # Показываем категории
    keyboard = []
    for category in CATALOG_CATEGORIES.keys():
        keyboard.append([InlineKeyboardButton(category, callback_data=f"catalog:cat:{category}")])
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="menu:back")])
    
    text = (
        "🕵🏼‍♀️ **ПОИСК В КАТАЛОГЕ**\n\n"
        "Выберите категорию:"
    )
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def addtocatalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить запись в каталог - /addtocatalog"""
    user_id = update.effective_user.id
    
    # Инициализируем данные формы
    context.user_data['catalog_add'] = {'step': 'link'}
    
    keyboard = [[InlineKeyboardButton("🚗 Отмена", callback_data="catalog:cancel")]]
    
    text = (
        "🆕 **ДОБАВЛЕНИЕ В КАТАЛОГ УСЛУГ**\n\n"
        "Шаг 1 из 5\n\n"
        "⛓️ Отправьте ссылку на пост в Telegram-канале:\n"
        "Пример: https://t.me/catalogtrix/123"
    )
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def review_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🤳🏼Оставить отзыв - /review [post_id]"""
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            "🔄 Использование: `/review [номер_поста]`\n\n"
            "Пример: `/review 123`",
            parse_mode='Markdown'
        )
        return
    
    post_id = int(context.args[0])
    user_id = update.effective_user.id
    
    # Сохраняем для ожидания текста отзыва
    context.user_data['catalog_review'] = {
        'post_id': post_id,
        'waiting': True
    }
    
    keyboard = [[InlineKeyboardButton("⏮️ Отмена", callback_data="catalog:cancel_review")]]
    
    await update.message.reply_text(
        f"🖋️ **ОТЗЫВ О СПЕЦИАЛИСТЕ**\n\n"
        f"ID поста: {post_id}\n\n"
        f"Ваш отзыв (макс. 500 символов):",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


# ============= АДМИНСКИЕ КОМАНДЫ =============

async def catalogpriority_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🧬Установить приоритетные посты - /catalogpriority (скрытая админская)"""
    if not Config.is_admin(update.effective_user.id):
        return
    
    context.user_data['catalog_priority'] = {'waiting': True, 'links': []}
    
    keyboard = [[InlineKeyboardButton("☑️ Завершить", callback_data="catalog:priority_finish")]]
    
    text = (
        "🔬 **ПРИОРИТЕТНЫЕ ПОСТЫ**\n\n"
        "Отправьте до 10 ссылок на посты (по одной в сообщении).\n\n"
        "Эти посты будут показываться пользователям в первую очередь.\n\n"
        "ℹ️ Пример: https://t.me/catalogtrix/123"
    )
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def addcatalogreklama_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить рекламный пост - /addcatalogreklama"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("👮🏼‍♂️ Секретный доступ")
        return
    
    context.user_data['catalog_ad'] = {'step': 'link'}
    
    keyboard = [[InlineKeyboardButton("⬅️ Отбой", callback_data="catalog:cancel_ad")]]
    
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


# ============= СТАТИСТИКА (АДМИН) =============

async def catalog_stats_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔘 Статистика пользователей - /catalog_stats_users"""
    if not Config.is_admin(update.effective_user.id):
        return
    
    text = (
        "🔘 **СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ**\n\n"
        "◽️ Запустили /catalog сегодня: 0\n"
        "◻️ За неделю: 0\n"
        "⬜️ За месяц: 0\n\n"
        "🎦 Среднее просмотров за сессию: 0"
    )
    
    await update.message.reply_text(text, parse_mode='Markdown')


async def catalog_stats_categories_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """📁 Статистика категорий - /catalog_stats_categories"""
    if not Config.is_admin(update.effective_user.id):
        return
    
    text = (
        "📁 **СТАТИСТИКА КАТЕГОРИЙ**\n\n"
        "👽 Частота просмотров по категориям:\n\n"
        "👩🏽‍🦳 Красота и уход: 0\n"
        "🏥 Здоровье и тело: 0\n"
        "🔣 Услуги и помощь: 0\n"
        "📓 Обучение и развитие: 0\n"
        "🦍 Досуг и впечатления: 0"
    )
    
    await update.message.reply_text(text, parse_mode='Markdown')


async def catalog_stats_popular_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """👨🏼‍💻ТОП10 публикаций - /catalog_stats_popular"""
    if not Config.is_admin(update.effective_user.id):
        return
    
    text = (
        "🏆 **💻 TOP10 ПОПУЛЯРНЫХ ПОСТОВ**\n\n"
        "1. Пост #123 - 150 кликов\n"
        "2. Пост #456 - 120 кликов\n"
        "...\n\n"
        "🗿 Обновления в LIVE режиме"
    )
    
    await update.message.reply_text(text, parse_mode='Markdown')


# ============= CALLBACK HANDLERS =============

async def handle_catalog_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback для каталога"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")
    action = data[1] if len(data) > 1 else None
    
    user_id = update.effective_user.id
    
    # ===== НАВИГАЦИЯ =====
    if action == "next":
        count = 5
        posts = await catalog_service.get_random_posts(user_id, count=count)
        
        if not posts:
            await query.edit_message_text(
                "🎦 Каталог полностью просмотрен\n\n"
                "🤳🏼 Команда /catalog обновляет сессию."
            )
            return
        
        await query.message.delete()
        
        for i, post in enumerate(posts, 1):
            await send_catalog_post_with_media(
                context.bot,
                query.message.chat_id,
                post,
                i,
                len(posts)
            )
        
        keyboard = [
            [
                InlineKeyboardButton(f"🎑 Ещё {count}", callback_data="catalog:next"),
                InlineKeyboardButton("⚓️ Закончить", callback_data="catalog:finish")
            ]
        ]
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"🌃 Просмотрено: {len(posts)}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif action == "finish":
        await query.edit_message_text(
            "🔭 Просмотр каталога завершен!\n\n"
            "Стабильно добавляем новые посты в каталог\n\n"
            "Команда /start – главное меню"
        )
    
    elif action == "restart":
        await catalog_service.reset_session(user_id)
        await query.edit_message_text(
            "🔄 Перезагрузка успешна\n\n"
            "Используйте /catalog для нового просмотра."
        )
    
    # ===== ПОИСК =====
    elif action == "search":
        keyboard = []
        for category in CATALOG_CATEGORIES.keys():
            keyboard.append([InlineKeyboardButton(category, callback_data=f"catalog:cat:{category}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="catalog:back_main")])
        
        await query.edit_message_text(
            "🔦 **ПОИСК**\n\nВыберите категорию:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif action == "cat":
        category = ":".join(data[2:])
        subcategories = CATALOG_CATEGORIES.get(category, [])
        
        keyboard = []
        for subcat in subcategories:
            keyboard.append([InlineKeyboardButton(subcat, callback_data=f"catalog:searchcat:{category}:{subcat}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="catalog:search")])
        
        await query.edit_message_text(
            f"📂 **{category}**\n\nВыберите подкатегорию:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif action == "searchcat":
        category = data[2] if len(data) > 2 else None
        subcategory = data[3] if len(data) > 3 else None
        
        posts = await catalog_service.search_posts(category=subcategory or category, limit=10)
        
        if not posts:
            await query.edit_message_text(
                f"🫙 Категория '{subcategory or category}' пустая.\n\n"
                "💣 Поиск кандидатов...🔬 Пока что можете посмотреть другие категории 🗄️"
            )
            return
        
        await query.message.delete()
        
        for i, post in enumerate(posts, 1):
            await send_catalog_post_with_media(
                context.bot,
                query.message.chat_id,
                post,
                i,
                len(posts)
            )
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"💿 Найдено записей: {len(posts)}"
        )
    
    # ===== ДОБАВЛЕНИЕ КАТЕГОРИИ =====
    elif action == "addcat":
        category = ":".join(data[2:])
        
        if 'catalog_add' not in context.user_data:
            await query.answer("Ошибка: данные формы потеряны", show_alert=True)
            return
        
        context.user_data['catalog_add']['category'] = category
        context.user_data['catalog_add']['step'] = 'name'
        
        await query.edit_message_text(
            f"✅ Категория: {category}\n\n"
            f"🚶‍♀️ Шаг 3 из 5\n\n"
            f"📝 Введите название/описание:",
            parse_mode='Markdown'
        )
    
    # ===== ПРОПУСК МЕДИА =====
    elif action == "skip_media":
        if 'catalog_add' not in context.user_data:
            await query.answer("Ошибка: данные формы потеряны", show_alert=True)
            return
        
        context.user_data['catalog_add']['step'] = 'tags'
        
        await query.edit_message_text(
            "⏭️ Медиа пропущено\n\n"
            "🏃🏻‍➡️ Последний пункт\n\n"
            "#️⃣ Добавь теги через запятую (до 10):\n\n"
            "Пример: жизнь, всегда, даёт, шансы"
        )
    
    # ===== ДЕЙСТВИЯ =====
    elif action == "click":
        post_id = int(data[2]) if len(data) > 2 else None
        if post_id:
            await catalog_service.increment_clicks(post_id)
            await query.answer("🧷 Переход по ссылке 🆗", show_alert=False)
    
    elif action == "cancel":
        context.user_data.pop('catalog_add', None)
        await query.edit_message_text("🙅🏻 Добавление отменено")
    
    elif action == "cancel_review":
        context.user_data.pop('catalog_review', None)
        await query.edit_message_text("🚮 Отзыв в мусорку")
    
    elif action == "cancel_ad":
        context.user_data.pop('catalog_ad', None)
        await query.edit_message_text("🕳️ Отмена добавления рекламы")
    
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
            f"☑️ Уже: {count} из {len(links)}"
        )


# ============= TEXT HANDLERS =============

async def handle_catalog_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текста для каталога"""
    user_id = update.effective_user.id
    text = update.message.text
    
    # Добавление поста
    if 'catalog_add' in context.user_data:
        data = context.user_data['catalog_add']
        step = data.get('step')
        
        if step == 'link':
            if not text.startswith('https://t.me/'):
                await update.message.reply_text("🆖 Формат ссылки - повнимательней!")
                return
            
            data['link'] = text
            data['step'] = 'category'
            
            keyboard = []
            for category in CATALOG_CATEGORIES.keys():
                keyboard.append([InlineKeyboardButton(category, callback_data=f"catalog:addcat:{category}")])
            
            await update.message.reply_text(
                "🚶🏻‍➡️ Шаг 2 из 5\n\n📂 Выбор категории:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif step == 'name':
            data['name'] = text[:255]
            data['step'] = 'media'
            
            keyboard = [[InlineKeyboardButton("⏭️ Пропустить медиа", callback_data="catalog:skip_media")]]
            
            # Пытаемся автоматически получить медиа из ссылки
            media_extracted = await extract_media_from_link(context.bot, data['link'])
            
            if media_extracted:
                # Медиа успешно извлечено
                data['media_type'] = media_extracted['type']
                data['media_file_id'] = media_extracted['file_id']
                data['media_group_id'] = media_extracted.get('media_group_id')
                data['media_json'] = media_extracted.get('media_json', [])
                data['step'] = 'tags'
                
                await update.message.reply_text(
                    f"✅ Медиа автоматически получено из поста!\n"
                    f"📎 Тип: {media_extracted['type']}\n\n"
                    "🏃🏻‍➡️ Последний пункт\n\n"
                    "#️⃣ Добавь теги через запятую (до 10):\n\n"
                    "Пример: маникюр, гель-лак, наращивание"
                )
            else:
                # Не удалось получить автоматически - предлагаем вручную
                keyboard = [[InlineKeyboardButton("⏭️ Пропустить медиа", callback_data="catalog:skip_media")]]
                
                await update.message.reply_text(
                    "⚠️ Не удалось автоматически получить медиа из поста\n\n"
                    "🚶‍♀️ Шаг 4 из 5\n\n"
                    "📸 Отправьте фото, видео, GIF или альбом вручную:\n\
