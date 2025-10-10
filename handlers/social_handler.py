# -*- coding: utf-8 -*-
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)

async def social_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать социальные сети TRIX"""
    
    keyboard = [
        [InlineKeyboardButton("🧢 Instagram", url="https://www.instagram.com/budapesttrix?igsh=ZXlrNmo4NDdyN2Vz&utm_source=qr")],
        [InlineKeyboardButton("🔷 Facebook Group", url="https://www.facebook.com/share/g/1EKwURtZ13/?mibextid=wwXIfr")],
        [InlineKeyboardButton("🌀 Threads", url="https://www.threads.com/@budapesttrix?igshid=NTc4MTIwNjQ2YQ==")],
        [InlineKeyboardButton("🫆 Telegram DM", url="https://t.me/trixilvebot")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="menu:back")]
    ]
    
    text = (
        "📱 **СОЦИАЛЬНЫЕ СЕТИ TRIX**\n\n"
        "Присоединяйтесь к нам в социальных сетях:\n\n"
        
        "🧢 **Instagram**\n"
        "Фото, stories, актуальные новости\n"
        "@budapesttrix\n\n"
        
        "🔷 **Facebook Group**\n"
        "Обсуждения, мероприятия, знакомства\n\n"
        
        "🌀 **Threads**\n"
        "Короткие посты и общение\n"
        "@budapesttrix\n\n"
        
        "🫆 **Telegram DM**\n"
        "Личная связь с администрацией\n\n"
        
        "👆 Нажмите на кнопку чтобы перейти"
    )
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def giveaway_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о розыгрышах"""
    
    keyboard = [
        [InlineKeyboardButton("🎁 Участвовать в розыгрыше", url="https://t.me/trixvault")],
        [InlineKeyboardButton("📢 Канал с розыгрышами", url="https://t.me/trixvault")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="menu:back")]
    ]
    
    text = (
        "🎁 **РОЗЫГРЫШИ TRIX**\n\n"
        "🎉 Регулярно проводим розыгрыши призов для участников нашего сообщества!\n\n"
        
        "🎯 **Как участвовать:**\n"
        "1️⃣ Подпишитесь на наш канал\n"
        "2️⃣ Следите за объявлениями о розыгрышах\n"
        "3️⃣ Выполняйте условия участия\n"
        "4️⃣ Ждите результатов!\n\n"
        
        "🏆 **Призы:**\n"
        "• Подарочные сертификаты\n"
        "• Бесплатные услуги от партнеров\n"
        "• Эксклюзивные товары\n"
        "• И многое другое!\n\n"
        
        "📢 **Текущие розыгрыши:**\n"
        "Смотрите актуальную информацию в нашем канале\n\n"
        
        "💡 Больше участвуешь в жизни сообщества = больше шансов выиграть!\n\n"
        
        "🍀 Удачи!"
    )
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

__all__ = ['social_command', 'giveaway_command']
