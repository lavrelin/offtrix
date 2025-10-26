import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import Config
from services.join_stats_db import (
    register_join_user, has_user_joined, get_all_unique_counts
)

logger = logging.getLogger(__name__)

# ... ваш существующий код (GROUPS, команды и т.д.) ...

# ====== CALLBACK HANDLER ДЛЯ ПОДТВЕРЖДЕНИЯ ВСТУПЛЕНИЯ ======
async def handle_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback для подтверждения вступления в группы"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Извлекаем данные из callback: join_ack:group_key:user_id
        data = query.data
        if not data.startswith('join_ack:'):
            return
            
        parts = data.split(':')
        if len(parts) != 3:
            return
            
        group_key = parts[1]
        user_id = int(parts[2])
        
        # Проверяем, что callback нажал тот же пользователь
        if query.from_user.id != user_id:
            await query.edit_message_text("❌ Это подтверждение предназначено другому пользователю")
            return
        
        # Проверяем существование группы
        if group_key not in GROUPS:
            await query.edit_message_text("❌ Группа не найдена")
            return
        
        group = GROUPS[group_key]
        
        # Регистрируем переход
        already_joined = await has_user_joined(group_key, user_id)
        if already_joined:
            await query.edit_message_text(
                f"✅ Вы уже вступили в {group['title']}!\n\n"
                f"Ссылка: https://t.me/{group['link']}"
            )
        else:
            success = await register_join_user(group_key, user_id)
            if success:
                await query.edit_message_text(
                    f"🎉 Спасибо за вступление в {group['title']}!\n\n"
                    f"✅ Ваш переход засчитан.\n"
                    f"Ссылка: https://t.me/{group['link']}"
                )
            else:
                await query.edit_message_text("❌ Ошибка при регистрации перехода")
                
    except Exception as e:
        logger.error(f"Error in handle_join_callback: {e}")
        await query.edit_message_text("❌ Произошла ошибка при обработке подтверждения")

# ====== АЛЬТЕРНАТИВНАЯ ВЕРСИЯ join_menu С КНОПКАМИ ПОДТВЕРЖДЕНИЯ ======
async def join_menu_with_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню /join с кнопками подтверждения вступления"""
    user_id = update.effective_user.id
    stats = await get_all_unique_counts()
    
    text = "💬 Выберите группу для вступления:\n\n"
    for key, group in GROUPS.items():
        count = stats.get(key, 0)
        text += f"• <b>{group['title']}</b> — <i>{count} уникальных участников</i>\n"
    
    keyboard = []
    for key, group in GROUPS.items():
        # Кнопка для перехода в группу
        join_btn = InlineKeyboardButton(
            f"🔗 Перейти в {group['title']}", 
            url=f"https://t.me/{group['link']}"
        )
        # Кнопка подтверждения вступления
        confirm_btn = InlineKeyboardButton(
            "✅ Я вступил(а)", 
            callback_data=f"join_ack:{key}:{user_id}"
        )
        keyboard.append([join_btn])
        keyboard.append([confirm_btn])
    
    markup = InlineKeyboardMarkup(keyboard)
    await update.effective_message.reply_text(
        text,
        reply_markup=markup,
        parse_mode="HTML"
    )
