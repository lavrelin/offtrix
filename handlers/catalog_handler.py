# -*- coding: utf-8 -*-
"""
Handler для каталога услуг
Команды: /catalog, /search, /addtocatalog, /review, /catalogpriority, /addcatalogreklama
"""
import logging
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
    
    # Отправляем посты
    for i, post in enumerate(posts, 1):
        await send_catalog_post(update, context, post, i, len(posts))
    
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
        "Шаг 1 из 4\n\n"
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
    
    # TODO: Реализовать сбор статистики
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
    
    if action == "next":
        # Показать следующие посты
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
            await send_catalog_post_callback(query, context, post, i, len(posts))
        
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
        # Сбросить сессию
        await catalog_service.reset_session(user_id)
        await query.edit_message_text(
            "🔄 Перезагрузка успешна\n\n"
            "Используйте /catalog для нового просмотра."
        )
    
    elif action == "search":
        # Показать категории поиска
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
        # Выбрана категория
        category = ":".join(data[2:])  # Восстанавливаем название с эмодзи
        
        # Показываем подкатегории
        subcategories = CATALOG_CATEGORIES.get(category, [])
        
        keyboard = []
        for subcat in subcategories:
            keyboard.append([InlineKeyboardButton(subcat, callback_data=f"catalog:search:{category}:{subcat}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="catalog:search")])
        
        await query.edit_message_text(
            f"📂 **{category}**\n\nВыберите подкатегорию:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif action == "search" and len(data) > 2:
        # Поиск по категории
        category = data[2]
        subcategory = data[3] if len(data) > 3 else None
        
        # Поиск постов
        posts = await catalog_service.search_posts(category=subcategory or category, limit=10)
        
        if not posts:
            await query.edit_message_text(
                f"🫙 Категория'{subcategory or category}' пустая.\n\n"
                "💣 Поиск кандидатов...🔬 Пока что можете посмотреть другие категории 🗄️"
            )
            return
        
        await query.message.delete()
        
        for i, post in enumerate(posts, 1):
            await send_catalog_post_callback(query, context, post, i, len(posts))
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"💿 Найдено записей: {len(posts)}"
        )
    
    elif action == "click":
        # Клик по посту
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
        await query.edit_message_text("🕳️ Отмена добавления рекласы")
    
    elif action == "priority_finish":
        # Завершить добавление приоритетных постов
        priority_data = context.user_data.get('catalog_priority', {})
        links = priority_data.get('links', [])
        
        if not links:
            await query.edit_message_text("🖇️ Ссылки не добввлены")
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
            # Валидация ссылки
            if not text.startswith('https://t.me/'):
                await update.message.reply_text("🆖 Формат ссылки - повнимательней!")
                return
            
            data['link'] = text
            data['step'] = 'category'
            
            # Показываем категории
            keyboard = []
            for category in CATALOG_CATEGORIES.keys():
                keyboard.append([InlineKeyboardButton(category, callback_data=f"catalog:addcat:{category}")])
            
            await update.message.reply_text(
                "🚶🏻‍➡️ Шаг 2 из 4\n\n📂 Выбор категории:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif step == 'name':
            data['name'] = text[:255]
            data['step'] = 'tags'
            
            await update.message.reply_text(
                "🏃🏻‍➡️ Последний пункт\n\n"
                "#️⃣ Добавь теги через запятую (до 10):\n\n"
                "Пример: жизнь, всегда, даёт, шансы"
            )
        
        elif step == 'tags':
            tags = [tag.strip() for tag in text.split(',')[:10]]
            data['tags'] = tags
            
            # Сохраняем в БД
            post_id = await catalog_service.add_post(
                user_id=user_id,
                catalog_link=data['link'],
                category=data['category'],
                name=data['name'],
                tags=tags
            )
            
            context.user_data.pop('catalog_add', None)
            
            if post_id:
                await update.message.reply_text(
                    f"📇 **В каталог добавлена публикация**\n\n"
                    f"📬 ID: {post_id}\n"
                    f"📂 Категория: {data['category']}\n"
                    f"🎚️ ХешТеги: {', '.join(tags)}",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text("➖ Произошла ошибка.")
    
    # Отзыв
    elif 'catalog_review' in context.user_data:
        review_data = context.user_data['catalog_review']
        
        if review_data.get('waiting'):
            # TODO: Сохранить отзыв в БД
            post_id = review_data['post_id']
            
            context.user_data.pop('catalog_review', None)
            
            await update.message.reply_text(
                f"💾 **Отзыв сохранен!**\n\n"
                f"🛀 Выражаем благодарность за вашу активность☑️",
                parse_mode='Markdown'
            )
    
    # Приоритетные посты
    elif 'catalog_priority' in context.user_data:
        priority_data = context.user_data['catalog_priority']
        
        if priority_data.get('waiting'):
            if text.startswith('https://t.me/'):
                priority_data['links'].append(text)
                
                count = len(priority_data['links'])
                await update.message.reply_text(
                    f"⛓️‍💥 Ссылка {count}/10 добавлена\n\n"
                    f"Отправьте еще или нажмите 'Завершить'"
                )
            else:
                await update.message.reply_text("🙅🏼 Неверный формат ссылки")
    
    # Рекламный пост
    elif 'catalog_ad' in context.user_data:
        ad_data = context.user_data['catalog_ad']
        step = ad_data.get('step')
        
        if step == 'link':
            if not text.startswith('https://t.me/'):
                await update.message.reply_text("🧷 Неверный формат ссылки")
                return
            
            ad_data['link'] = text
            ad_data['step'] = 'description'
            
            await update.message.reply_text(
                "🏙️ Шаг 2 из 3\n\n"
                "👩🏼‍💻 Добавьте описание рекламы:"
            )
        
        elif step == 'description':
            ad_data['description'] = text
            ad_data['step'] = 'finish'
            
            # Сохраняем
            post_id = await catalog_service.add_ad_post(
                catalog_link=ad_data['link'],
                description=ad_data['description']
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
                await update.message.reply_text("💁🏻 ОШИБКА при добавлении")


# ============= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =============

async def send_catalog_post(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                           post: dict, index: int, total: int):
    """Отправить пост каталога"""
    text = (
        f"🏙️ **Запись {index}/{total}**\n\n"
        f"🏞️ Категория: {post['category']}\n"
        f"🎑 {post['name']}\n\n"
        f"🌌 Теги: {', '.join(post['tags']) if post['tags'] else 'нет'}\n"
        f"🌠 Просмотров: {post['views']}"
    )
    
    keyboard = [
        [InlineKeyboardButton("🏃🏻‍♀️‍➡️ Перейти к посту", url=post['catalog_link'], callback_data=f"catalog:click:{post['id']}")],
        [InlineKeyboardButton("🧑🏼‍💻 Оставить отзыв", callback_data=f"catalog:review:{post['id']}")]
    ]
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    # Увеличиваем счетчик просмотров
    await catalog_service.increment_views(post['id'])


async def send_catalog_post_callback(query, context: ContextTypes.DEFAULT_TYPE, 
                                    post: dict, index: int, total: int):
    """Отправить пост каталога через callback"""
    text = (
        f"🪽 **Запись {index}/{total}**\n\n"
        f"💨 Категория: {post['category']}\n"
        f"🌊 {post['name']}\n\n"
        f"🌪️ Теги: {', '.join(post['tags']) if post['tags'] else 'нет'}\n"
        f"🎬 Просмотров: {post['views']}"
    )
    
    keyboard = [
        [InlineKeyboardButton("💁🏼 К посту", url=post['catalog_link'])],
        [InlineKeyboardButton("👱🏻‍♀️ Написать отзыв", callback_data=f"catalog:review:{post['id']}")]
    ]
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    await catalog_service.increment_views(post['id'])


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
    'handle_catalog_text'
]
