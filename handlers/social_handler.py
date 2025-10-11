# -*- coding: utf-8 -*-
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)

async def giveaway_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о розыгрышах"""

    keyboard = [
        [InlineKeyboardButton("🫦 Полная информация", url="https://t.me/budapestpartners")],
        [InlineKeyboardButton("👄 Канал с розыгрышами", url="https://t.me/budapestpartners")],
        [InlineKeyboardButton("👅 Главное меню", callback_data="menu:back")]
    ]

    text = (
        "🔋 **СИСТЕМА РОЗЫГРЫШЕЙ TRIX**\n\n"
        "🧖 **Ежедневно**\n"
        "• TopDayPost — лучший пост дня (5 $)\n"
        "• TopDayComment — лучший комментарий дня (5 $)\n\n"
        
        "🧖‍♂️ **Еженедельно**\n"
        "• WeeklyRoll — 3 случайных победителя по 5 $\n"
        "• NeedTryMore — угадай слово, 3 победителя по 10 $\n"
        "• TopWeek — лучший пост недели (10 $)\n"
        "• 7TT — выдача 7 TrixTicket\n\n"
        
        "🧖‍♀️ **Ежемесячно**\n"
        "• Member — раздача 100 $ среди участников сообществ\n"
        "• TrixTicket — розыгрыш среди обладателей TrixTicket\n"
        "• Catalog43X — случайный розыгрыш услуги мастера из каталога, победителю оплачивается сеанс/консультация, результаты через 48 ч\n\n"
        
        "💡 **Правила**\n"
        "• Быть участником Трикс комьюнити\n"
        "• Фейковые аккаунты исключаются\n"
        "• Выплаты — в USDT в течение 24 ч\n\n"
        "🧑‍💻 **Оплата за действия /trixmoney**\n"
        "Выполняйте задания и получайте денежные награды.\n"
        "Выполненные заявки отправляйте в @trixilvebot\n\n"
        "Задания:\n"
        "• Active3x — Оплата за активность в соцсетях (3$)\n"
        "• RaidTrix — рекламные сообщения, оплата за пиар 1-5$\n"
        "• Ref — регистрация и верификация, 5$ + TrixTicket\n"
        "• Look — предлагайте свой контент, награды 2-10$\n\n"
        "🎲 Используй каждый шанс!\n"
        "Все обновления, результаты, статистика победителей: https://t.me/budapestpartners"
    )

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


__all__ = ['giveaway_command']
