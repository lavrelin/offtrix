# -*- coding: utf-8 -*-
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)

async def social_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать социальные сети TRIX"""
    
    keyboard = [
        [InlineKeyboardButton("🟧 INSTAGRAM", url="https://www.instagram.com/budapesttrix?igsh=ZXlrNmo4NDdyN2Vz&utm_source=qr")],
        [InlineKeyboardButton("📘 FACEBOOK", url="https://www.facebook.com/share/g/1EKwURtZ13/?mibextid=wwXIfr")],
        [InlineKeyboardButton("🧵 THREADS", url="https://www.threads.com/@budapesttrix?igshid=NTc4MTIwNjQ2YQ==")],
        [InlineKeyboardButton("🌀 TELEGRAM", url="https://t.me/trixilvebot")],
        [InlineKeyboardButton("▫️ MENU", callback_data="menu:back")]
    ]
    
    text = (
        "⚡️ **СОЦИАЛЬНЫЕ СЕТИ TRIX**\n\n"
        "✅ Follow:\n\n"
        
        "🟧 **INSTAGRAM** — фото, stories, актуальные новости (@budapesttrix)\n\n"
        "📘 **FACEBOOK** — дублирование телеграм контента\n\n"
        "🧵 **THREADS** — короткие посты и общение (@budapesttrix)\n\n"
        "🌀 **TELEGRAM** — личная связь с администрацией\n\n"
        "🔘 Нажмите на кнопку для просмотра"
    )
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def giveaway_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о розыгрышах"""
    
    keyboard = [
        [InlineKeyboardButton("🫦 Полная информация", url="https://t.me/budapestpartners")],
        [InlineKeyboardButton("👅 Канал с розыгрышами", url="https://t.me/budapestpartners")],
        [InlineKeyboardButton("👄 Главное меню", callback_data="menu:back")]
    ]
    
    text = (
        "🔋 **СИСТЕМА РОЗЫГРЫШЕЙ TRIX**\n\n"
        "🤹‍♂️ **Ежедневно**\n"
        "• TopDayPost — топ пост дня **5$**\n"
        "• TopDayComment — топ коммент дня **5$**\n"
        "• TopDayTager — топ пост/сторис в котором упоминается Трикс также получит **5$**\n"
        
        "🤹 **Еженедельно**\n"
        "• WeeklyRoll — Три победителя по **5$**\n"
        "• NeedTryMore — Три победителя по **10$**\n"
        "• TopWeek — топ публикация недели **10$**\n"
        "• 7TT — раздача **7 🎫TrixTicket**\n"
        
        "🤹‍♀️ **Ежемесячно**\n"
        "• Member — 100$ просто за подписку\n"
        "• TrixTicket — розыгрыш среди обладателей TrixTicket\n"
        "• Catalog43X — случайный розыгрыш услуги мастера из каталога, победителю оплачивается сеанс/консультация\n\n"
        
        "🪁 **Награды за действия /trixmoney**\n"
        "Выполняйте задания и получайте денежные награды.\n"
        "**Актуальные**\n"
        "• Active3x — Оплата за активность в соцсетях **3$**\n"
        "• RaidTrix — рекламные сообщения, деньги за пиар  **1-5$**\n"
        "• Ref — регистрация и верификация, **5$ + 🎫TrixTicket**\n"
        "• Look — предлагайте свой контент, награды **до 10$**\n\n"
        "🟦**Используй каждый шанс!**\n"
        "🧏‍♂️ **Правила**\n"
        "• Быть участником Трикс комьюнити\n"
        "• Фейковые аккаунты исключаются\n"
        "• Выплаты — в **USDT** в течение 24 ч\n\n"
    )
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

__all__ = ['social_command', 'giveaway_command']
