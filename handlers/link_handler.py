# -*- coding: utf-8 -*-
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
import logging

logger = logging.getLogger(__name__)

# ТЕСТОВЫЕ ССЫЛКИ TRIX (временно все на @TrixLiveBot)
TRIX_LINKS = [
    {
        'id': 1,
        'name': '🙅‍♂️ Канал Будапешт',
        'url': 'https://t.me/Trixlivebot',
        'description': 'Основной канал сообщества Будапешта'
    },
    {
        'id': 2,
        'name': '🙅‍♀️ Чат Будапешт',
        'url': 'https://t.me/Trixlivebot',
        'description': 'Чат для общения участников сообщества'
    },
    {
        'id': 3,
        'name': '🙅 Каталог услуг',
        'url': 'https://t.me/Trixlivebot',
        'description': 'Каталог услуг и специалистов Будапешта'
    },
    {
        'id': 4,
        'name': '🕵️‍♂️ Барахолка (КОП)',
        'url': 'https://t.me/Trixlivebot',
        'description': 'Купля, продажа, обмен товаров'
    }
]

async def trixlinks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать все ссылки с inline кнопками"""
    
    # Создаем inline кнопки для каждой ссылки
    keyboard = []
    
    for link in TRIX_LINKS:
        keyboard.append([
            InlineKeyboardButton(link['name'], url=link['url'])
        ])
    
    # Добавляем кнопку возврата
    keyboard.append([
        InlineKeyboardButton("🔙 Главное меню", callback_data="menu:back")
    ])
    
    text = (
        "🔗 *ПОЛЕЗНЫЕ ССЫЛКИ TRIX*\n\n"
        "📱 Наши главные площадки для общения и взаимодействия:\n\n"
        "🙅‍♂️ Канал Будапешт\n"
        "📝 Основной канал сообщества Будапешта\n\n"
        "🙅‍♀️ Чат Будапешт\n"
        "📝 Чат для общения участников сообщества\n\n"
        "🙅 Каталог услуг\n"
        "📝 Каталог услуг и специалистов Будапешта\n\n"
        "🕵️‍♂️ Барахолка (КОП)\n"
        "📝 Купля, продажа, обмен товаров\n\n"
        "👆 Нажмите на кнопку чтобы перейти\n\n"
        "⚠️ *ТЕСТОВЫЙ РЕЖИМ*: Все ссылки временно ведут на @TrixLiveBot"
    )
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

__all__ = ['trixlinks_command']
