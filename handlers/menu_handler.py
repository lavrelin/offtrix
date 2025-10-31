# -*- coding: utf-8 -*-
"""
Menu Handler v2.0 - SIMPLIFIED
Prefix: menu_

Структура:
1. Пост в Будапешт (анонимно / с username) + медиа
2. Заявка в Каталог Услуг
3. Предложить на Барахолке (продам / куплю / отдам) + медиа
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)

# ============= UNIQUE CALLBACK PREFIX: menu_ =============
MENU_CALLBACKS = {
    'write': 'menu_write',           # Show write menu
    'back': 'menu_back',             # Back to main menu
    'budapest': 'menu_bp',           # Budapest post
    'catalog': 'menu_cat',           # Catalog service
    'baraholka': 'menu_bar',         # Baraholka/trade
}

async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unified menu callback handler"""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    logger.info(f"Menu action: {action}")
    
    handlers = {
        MENU_CALLBACKS['write']: show_write_menu,
        MENU_CALLBACKS['back']: show_main_menu,
        MENU_CALLBACKS['budapest']: start_budapest_post,
        MENU_CALLBACKS['catalog']: start_catalog,
        MENU_CALLBACKS['baraholka']: start_baraholka,
    }
    
    handler = handlers.get(action)
    if handler:
        await handler(update, context)
    else:
        await query.answer("⚠️  Функция в разработке", show_alert=True)

async def show_write_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show write menu - SIMPLIFIED VERSION"""
    keyboard = [
        [InlineKeyboardButton("📢 Пост в Будапешт", callback_data=MENU_CALLBACKS['budapest'])],
        [InlineKeyboardButton("📋 Заявка в Каталог Услуг", callback_data=MENU_CALLBACKS['catalog'])],
        [InlineKeyboardButton("🛒 Предложить на Барахолке", callback_data=MENU_CALLBACKS['baraholka'])],
        [InlineKeyboardButton("◀️ Назад", callback_data=MENU_CALLBACKS['back'])]
    ]
    
    text = (
        "### Разделы публикаций\n\n"
        
        "**📢 Пост в Будапешт**\n"
        "Публикация в канал @snghu\n"
        "Можно анонимно или с упоминанием\n\n"
        
        "**📋 Заявка в Каталог Услуг**\n"
        "Добавить свои услуги в @catalogtrix\n"
        "Мастера, специалисты, бизнес\n\n"
        
        "**🛒 Предложить на Барахолке**\n"
        "Продать, купить или отдать товары\n"
        "Публикация в @hungarytrade"
    )
    
    await update.callback_query.edit_message_text(
        text, 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode='Markdown'
    )

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show main menu"""
    from handlers.start_handler import show_main_menu as original_show_main_menu
    await original_show_main_menu(update, context)

async def start_budapest_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start Budapest post - show anonymous/username choice"""
    keyboard = [
        [InlineKeyboardButton("📩 Анонимно", callback_data="bp_anon")],
        [InlineKeyboardButton("💬 С username", callback_data="bp_user")],
        [InlineKeyboardButton("◀️ Назад", callback_data=MENU_CALLBACKS['write'])]
    ]
    
    text = (
        "📢 **Пост в Будапешт**\n\n"
        "Выберите тип публикации:\n\n"
        "📩 **Анонимно** - без упоминания автора\n"
        "💬 **С username** - с вашим @username\n\n"
        "После выбора напишите текст и/или отправьте медиа"
    )
    
    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def start_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start catalog - redirect to piar_handler"""
    # This redirects to existing piar_handler (без изменений)
    context.user_data['piar_data'] = {}
    context.user_data['waiting_for'] = 'piar_name'
    context.user_data['piar_step'] = 'name'
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=MENU_CALLBACKS['write'])]]
    
    text = (
        "📋 **Заявка в Каталог Услуг**\n\n"
        "🎯 Цель: упростить поиск услуг и мастеров\n\n"
        "💡 **Шаг 1 из 8**\n"
        "📝 Напишите своё имя или псевдоним:"
    )
    
    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def start_baraholka(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start baraholka - show sell/buy/give menu"""
    keyboard = [
        [InlineKeyboardButton("💰 Продам", callback_data="bar_sell")],
        [InlineKeyboardButton("🔎 Куплю", callback_data="bar_buy")],
        [InlineKeyboardButton("🎁 Отдам", callback_data="bar_give")],
        [InlineKeyboardButton("◀️ Назад", callback_data=MENU_CALLBACKS['write'])]
    ]
    
    text = (
        "🛒 **Барахолка**\n\n"
        "Выберите раздел:\n\n"
        "💰 **Продам** - продать товар\n"
        "🔎 **Куплю** - ищу товар для покупки\n"
        "🎁 **Отдам** - отдать даром\n\n"
        "После выбора напишите текст и/или отправьте фото товара"
    )
    
    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# Export
__all__ = ['handle_menu_callback', 'MENU_CALLBACKS']
