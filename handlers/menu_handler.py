# -*- coding: utf-8 -*-
"""
Menu Handler v6.0 - SIMPLIFIED
Prefix: menu_ (уникальный для меню)
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)

# ============= УНИКАЛЬНЫЕ CALLBACK ПРЕФИКСЫ: menu_ =============
MENU_CALLBACKS = {
    'write': 'menu_write',              # Главное меню создания
    'back_main': 'menu_back_main',      # Вернуться в главное меню
    
    # Пост в Будапешт
    'budapest': 'menu_budapest',        # Пост в Будапешт (выбор анон/с username)
    'bud_anon': 'menu_bud_anon',       # Анонимно
    'bud_username': 'menu_bud_username', # С username
    
    # Каталог услуг
    'catalog': 'menu_catalog',          # Заявка в каталог
    
    # Барахолка
    'baraholka': 'menu_baraholka',      # Барахолка (выбор раздела)
    'bara_sell': 'menu_bara_sell',      # Продам
    'bara_buy': 'menu_bara_buy',        # Куплю
    'bara_give': 'menu_bara_give',      # Отдам
}

async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unified menu callback handler"""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    logger.info(f"Menu action: {action}")
    
    handlers = {
        MENU_CALLBACKS['write']: show_write_menu,
        MENU_CALLBACKS['back_main']: show_main_menu,
        MENU_CALLBACKS['budapest']: show_budapest_options,
        MENU_CALLBACKS['bud_anon']: lambda u, c: start_budapest_post(u, c, anonymous=True),
        MENU_CALLBACKS['bud_username']: lambda u, c: start_budapest_post(u, c, anonymous=False),
        MENU_CALLBACKS['catalog']: start_catalog_request,
        MENU_CALLBACKS['baraholka']: show_baraholka_menu,
        MENU_CALLBACKS['bara_sell']: lambda u, c: start_baraholka_post(u, c, 'Продам'),
        MENU_CALLBACKS['bara_buy']: lambda u, c: start_baraholka_post(u, c, 'Куплю'),
        MENU_CALLBACKS['bara_give']: lambda u, c: start_baraholka_post(u, c, 'Отдам'),
    }
    
    handler = handlers.get(action)
    if handler:
        await handler(update, context)
    else:
        await query.answer("⚠️ Неизвестная команда", show_alert=True)

# ============= МЕНЮ СОЗДАНИЯ =============

async def show_write_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Упрощенное меню создания публикаций"""
    keyboard = [
        [InlineKeyboardButton("📝 Пост в Будапешт", callback_data=MENU_CALLBACKS['budapest'])],
        [InlineKeyboardButton("🙅 Заявка в Каталог Услуг", callback_data=MENU_CALLBACKS['catalog'])],
        [InlineKeyboardButton("🛒 Предложить на Барахолке", callback_data=MENU_CALLBACKS['baraholka'])],
        [InlineKeyboardButton("🔙 Главное меню", callback_data=MENU_CALLBACKS['back_main'])]
    ]
    
    text = (
        "✍️ **Создание публикации**\n\n"
        
        "**📝 Пост в Будапешт**\n"
        "Публикация в канал Будапешт\n"
        "Анонимно или с вашим username\n\n"
        
        "**🙅 Каталог Услуг**\n"
        "Добавить свою услугу/мастера\n"
        "в каталог Будапешта\n\n"
        
        "**🛒 Барахолка**\n"
        "Продать, купить или отдать\n"
        "товары в сообществе"
    )
    
    await update.callback_query.edit_message_text(
        text, 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode='Markdown'
    )

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню"""
    from handlers.start_handler import show_main_menu as original_show_main_menu
    await original_show_main_menu(update, context)

# ============= ПОСТ В БУДАПЕШТ =============

async def show_budapest_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор: анонимно или с username"""
    keyboard = [
        [InlineKeyboardButton("📩 Анонимно", callback_data=MENU_CALLBACKS['bud_anon'])],
        [InlineKeyboardButton("💬 С моим username", callback_data=MENU_CALLBACKS['bud_username'])],
        [InlineKeyboardButton("🔙 Назад", callback_data=MENU_CALLBACKS['write'])]
    ]
    
    text = (
        "📝 **Пост в Будапешт**\n\n"
        "Выберите способ публикации:\n\n"
        
        "**📩 Анонимно**\n"
        "Ваше имя не будет указано в посте\n\n"
        
        "**💬 С username**\n"
        "Ваш @username будет виден в посте"
    )
    
    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def start_budapest_post(update: Update, context: ContextTypes.DEFAULT_TYPE, anonymous: bool):
    """Начать создание поста в Будапешт"""
    context.user_data['post_data'] = {
        'category': '🙅‍♂️ Будапешт',
        'anonymous': anonymous,
        'type': 'budapest'
    }
    context.user_data['waiting_for'] = 'budapest_text'
    
    anon_text = "анонимно" if anonymous else "с вашим username"
    
    keyboard = [[InlineKeyboardButton("🔙 Отмена", callback_data=MENU_CALLBACKS['write'])]]
    
    text = (
        f"📝 **Пост в Будапешт** ({anon_text})\n\n"
        "Напишите текст вашего поста.\n"
        "Можете добавить:\n"
        "• Текст\n"
        "• Фото\n"
        "• Видео\n\n"
        "💡 После отправки пост пройдет модерацию"
    )
    
    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============= КАТАЛОГ УСЛУГ =============

async def start_catalog_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Перенаправить на piar handler для каталога"""
    # Вызываем существующий piar handler
    context.user_data['piar_data'] = {}
    context.user_data['waiting_for'] = 'piar_name'
    context.user_data['piar_step'] = 'name'
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data=MENU_CALLBACKS['write'])]]
    
    text = (
        "🙅 **Заявка в Каталог Услуг**\n\n"
        "🎯 Цель: упростить поиск услуг и мастеров\n\n"
        "**Шаг 1 из 8**\n"
        "💭 Напишите ваше имя или псевдоним:"
    )
    
    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============= БАРАХОЛКА =============

async def show_baraholka_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню выбора раздела барахолки"""
    keyboard = [
        [InlineKeyboardButton("💰 Продам", callback_data=MENU_CALLBACKS['bara_sell'])],
        [InlineKeyboardButton("🔎 Куплю", callback_data=MENU_CALLBACKS['bara_buy'])],
        [InlineKeyboardButton("🎁 Отдам", callback_data=MENU_CALLBACKS['bara_give'])],
        [InlineKeyboardButton("🔙 Назад", callback_data=MENU_CALLBACKS['write'])]
    ]
    
    text = (
        "🛒 **Барахолка Будапешта**\n\n"
        "Выберите раздел:\n\n"
        
        "**💰 Продам**\n"
        "Продажа товаров и услуг\n\n"
        
        "**🔎 Куплю**\n"
        "Поиск товаров для покупки\n\n"
        
        "**🎁 Отдам**\n"
        "Отдать даром или обменять"
    )
    
    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def start_baraholka_post(update: Update, context: ContextTypes.DEFAULT_TYPE, section: str):
    """Начать создание поста на барахолке"""
    context.user_data['post_data'] = {
        'category': '🛒 Барахолка',
        'subcategory': section,
        'anonymous': False,
        'type': 'baraholka'
    }
    context.user_data['waiting_for'] = 'baraholka_text'
    
    emoji_map = {
        'Продам': '💰',
        'Куплю': '🔎',
        'Отдам': '🎁'
    }
    
    keyboard = [[InlineKeyboardButton("🔙 Отмена", callback_data=MENU_CALLBACKS['baraholka'])]]
    
    text = (
        f"{emoji_map.get(section, '🛒')} **Барахолка: {section}**\n\n"
        "Напишите описание:\n"
        "• Что предлагаете/ищете\n"
        "• Цена (если применимо)\n"
        "• Контакты\n"
        "• Можете прикрепить фото\n\n"
        "💡 Пост пройдет модерацию"
    )
    
    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

__all__ = ['handle_menu_callback', 'MENU_CALLBACKS', 'show_write_menu', 'show_main_menu']
