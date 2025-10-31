# -*- coding: utf-8 -*-
"""
Start Handler v6.0 - SIMPLIFIED
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
import logging
import secrets
import string

logger = logging.getLogger(__name__)

# Import menu callbacks
from menu_handler_v6 import MENU_CALLBACKS

def generate_referral_code():
    """Generate unique referral code"""
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name
    chat_id = update.effective_chat.id
    
    # ✅ Игнорируем команду в Будапешт чате
    if chat_id == Config.BUDAPEST_CHAT_ID:
        try:
            await update.message.delete()
            logger.info(f"Deleted /start from Budapest chat, user {user_id}")
        except Exception as e:
            logger.error(f"Could not delete /start: {e}")
        return
    
    # Сохраняем пользователя в БД
    try:
        from services.db import db
        from models import User, Gender
        from sqlalchemy import select
        from datetime import datetime
        
        async with db.get_session() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            
            if not user:
                new_user = User(
                    id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    gender=Gender.UNKNOWN,
                    referral_code=generate_referral_code(),
                    created_at=datetime.utcnow()
                )
                session.add(new_user)
                await session.commit()
                logger.info(f"Created new user: {user_id}")
                
    except Exception as e:
        logger.warning(f"Could not save user to DB: {e}")
    
    # Показываем главное меню
    await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show simplified main menu v6.0"""
    
    # ✅ Не показываем меню в Будапешт чате
    chat_id = update.effective_chat.id
    if chat_id == Config.BUDAPEST_CHAT_ID:
        logger.info(f"Blocked main menu in Budapest chat")
        return
    
    # ✅ УПРОЩЕННОЕ МЕНЮ
    keyboard = [
        [InlineKeyboardButton("🙅‍♂️ Будапешт - канал", url="https://t.me/snghu")],
        [InlineKeyboardButton("🙅‍♀️ Будапешт - чат", url="https://t.me/tgchatxxx")],
        [InlineKeyboardButton("🙅 Каталог услуг", url="https://t.me/catalogtrix")],
        [InlineKeyboardButton("🕵️‍♂️ Барахолка", url="https://t.me/hungarytrade")],
        [InlineKeyboardButton("✍️ Создать публикацию", callback_data=MENU_CALLBACKS['write'])]
    ]
    
    text = (
        "🇭🇺 **Сообщество Будапешта Трикс**\n\n"
        
        "**Наши каналы:**\n"
        "🙅‍♂️ **Канал** — новости и информация\n"
        "🙅‍♀️ **Чат** — общение участников\n"
        "🙅 **Каталог** — мастера и услуги\n"
        "🕵️‍♂️ **Барахолка** — купля/продажа\n\n"
            
        "**Создать публикацию:**\n"
        "Нажмите ✍️ **Создать публикацию**\n\n"
        
        "📌 *Закрепите бота для быстрого доступа*"
    )
    
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.effective_message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Error showing main menu: {e}")
        # Fallback
        try:
            await update.effective_message.reply_text(
                "🇭🇺 TrixBot - Сообщество Будапешта\n\n"
                "Нажмите 'Создать публикацию' чтобы начать",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e2:
            logger.error(f"Fallback menu also failed: {e2}")

__all__ = ['start_command', 'show_main_menu']
