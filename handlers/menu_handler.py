# -*- coding: utf-8 -*-
"""
Optimized Menu Handler with unique callback prefixes
Prefix: mnc_ (menu callback)
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)

# ============= CALLBACK PREFIX: mnc_ =============
MENU_CALLBACKS = {
    'write': 'mnc_w',           # Show write menu
    'read': 'mnc_r',            # Show main menu
    'budapest': 'mnc_bp',       # Budapest menu
    'services': 'mnc_srv',      # Services (Piar)
    'actual': 'mnc_act',        # Actual posts
    'back': 'mnc_bk',           # Back to main
    'announcements': 'mnc_ann', # Announcements submenu
    'news': 'mnc_nws',          # News category
    'overheard': 'mnc_ovr',     # Overheard category
    'complaints': 'mnc_cmp'     # Complaints category
}

async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unified menu callback handler"""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    logger.info(f"Menu action: {action}")
    
    handlers = {
        MENU_CALLBACKS['write']: show_write_menu,
        MENU_CALLBACKS['read']: show_main_menu,
        MENU_CALLBACKS['back']: show_main_menu,
        MENU_CALLBACKS['budapest']: show_budapest_menu,
        MENU_CALLBACKS['services']: start_piar,
        MENU_CALLBACKS['actual']: start_actual_post,
        MENU_CALLBACKS['announcements']: show_announcements_menu,
        MENU_CALLBACKS['news']: lambda u, c: start_category_post(u, c, "🗯️ Будапешт", "🔔 Новости"),
        MENU_CALLBACKS['overheard']: lambda u, c: start_category_post(u, c, "🗯️ Будапешт", "🔕 Подслушано", True),
        MENU_CALLBACKS['complaints']: lambda u, c: start_category_post(u, c, "🗯️ Будапешт", "👸🏼 Жалобы", True)
    }
    
    handler = handlers.get(action)
    if handler:
        await handler(update, context)
    else:
        await query.answer("Функция в разработке", show_alert=True)

async def show_budapest_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Budapest category menu"""
    keyboard = [
        [InlineKeyboardButton("📣 Объявления", callback_data=MENU_CALLBACKS['announcements'])],
        [InlineKeyboardButton("🔔 Новости", callback_data=MENU_CALLBACKS['news'])],
        [InlineKeyboardButton("🔕 Подслушано", callback_data=MENU_CALLBACKS['overheard'])],
        [InlineKeyboardButton("👸🏼 Жалобы", callback_data=MENU_CALLBACKS['complaints'])],
        [InlineKeyboardButton("🔙 Назад", callback_data=MENU_CALLBACKS['write'])]
    ]
    
    text = (
        "🙅‍♂️ *Пост в Будапешт*\n\n"
        "📣 *Объявления* - товары, услуги, поиски\n"
        "🔔 *Новости* - актуальная информация\n"
        "🔕 *Подслушано* - анонимные истории\n"
        "👑 *Жалобы* - анонимные недовольства"
    )
    
    await update.callback_query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )

async def show_announcements_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Announcements subcategories"""
    keyboard = [
        [
            InlineKeyboardButton("🕵🏻‍♀️ Куплю", callback_data="pbc_buy"),
            InlineKeyboardButton("👷‍♀️ Работа", callback_data="pbc_wrk")
        ],
        [
            InlineKeyboardButton("🕵🏼 Отдам", callback_data="pbc_free"),
            InlineKeyboardButton("🏢 Аренда", callback_data="pbc_rnt")
        ],
        [
            InlineKeyboardButton("🕵🏻‍♂️ Продам", callback_data="pbc_sell"),
            InlineKeyboardButton("🪙 Криптовалюта", callback_data="pbc_cry")
        ],
        [
            InlineKeyboardButton("🫧 Ищу", callback_data="pbc_oth"),
            InlineKeyboardButton("✖️уё Будапешт", callback_data="pbc_evt")
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data=MENU_CALLBACKS['budapest'])]
    ]
    
    await update.callback_query.edit_message_text(
        "📣 *Объявления*\n\nВыберите подкатегорию:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def start_piar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start Services form"""
    context.user_data['piar_data'] = {}
    context.user_data['waiting_for'] = 'piar_name'
    context.user_data['piar_step'] = 'name'
    
    keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data=MENU_CALLBACKS['write'])]]

    text = (
        "🪄 *Заявка в каталог Будапешта*\n\n"
        "🧲 *Цель:* упростить поиск услуг и мастеров\n\n"
        "💡 *Шаг 1 из 8*\n"
        "💭 Напишите своё имя, псевдоним:"
    )
    
    await update.callback_query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )

async def start_actual_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start Actual post"""
    context.user_data['post_data'] = {
        'category': '⚡️Актуальное',
        'is_actual': True
    }
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=MENU_CALLBACKS['write'])]]
    
    text = (
        "⚡️ *Актуальное*\n\n"
        "💡 Срочные и важные сообщения\n"
        "📌 Будут закреплены в чате\n\n"
        "🫧 *Примеры:*\n"
        "- Ищу стоматолога на сегодня\n"
        "- Срочно нужен перевозчик\n"
        "- Потерял паспорт на вокзале\n\n"
        "⚡️ *Введите текст:*"
    )

    await update.callback_query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )
    context.user_data['waiting_for'] = 'post_text'

async def start_category_post(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                              category: str, subcategory: str, anonymous: bool = False):
    """Start post creation"""
    context.user_data['post_data'] = {
        'category': category,
        'subcategory': subcategory,
        'anonymous': anonymous
    }
    
    keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data=MENU_CALLBACKS['budapest'])]]
    
    anon_text = " (анонимно)" if anonymous else ""
    text = f"{category} → {subcategory}{anon_text}\n\n🤳 Отправьте текст, фото, видео:"
    
    await update.callback_query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )
    context.user_data['waiting_for'] = 'post_text'

async def show_write_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Write menu"""
    keyboard = [
        [InlineKeyboardButton("Пост в 🙅‍♂️Будапешт/🕵🏼‍♀️КОП", callback_data=MENU_CALLBACKS['budapest'])],
        [InlineKeyboardButton("Заявка в 🙅Каталог Услуг", callback_data=MENU_CALLBACKS['services'])],
        [InlineKeyboardButton("⚡️Актуальное", callback_data=MENU_CALLBACKS['actual'])],
        [InlineKeyboardButton("🚶‍♀️Читать", callback_data=MENU_CALLBACKS['read'])]
    ]
    
    text = (
        "• *Разделы публикаций*\n\n"
        "*🙅‍♂️ Будапешт / 🕵🏼‍♀️ КОП*\n"
        "Объявления, новости, жалобы\n\n"
        "*🙅 Каталог Услуг*\n"
        "Мастера и специалисты\n\n"
        "*⚡️ Актуальное*\n"
        "Срочные сообщения"
    )
    
    await update.callback_query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main menu"""
    from handlers.start_handler import show_main_menu as original_show_main_menu
    await original_show_main_menu(update, context)

# Export callbacks for use in other handlers
__all__ = ['handle_menu_callback', 'MENU_CALLBACKS']
