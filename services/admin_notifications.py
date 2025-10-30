# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from typing import Optional
from config import Config

logger = logging.getLogger(__name__)

class AdminNotificationService:
    """Сервис уведомлений для администраторов"""
    
    def __init__(self):
        self.bot = None
    
    def set_bot(self, bot):
        """Устанавливает экземпляр бота"""
        self.bot = bot
        logger.info("Bot instance set for admin notifications")
    
    async def send_notification(self, message: str, parse_mode: str = None):
        """Отправить уведомление в админскую группу"""
        if not self.bot:
            logger.warning("Bot instance not set, cannot send notification")
            return False
        
        try:
            await self.bot.send_message(
                chat_id=Config.ADMIN_GROUP_ID,
                text=message,
                parse_mode=parse_mode
            )
            logger.info("Admin notification sent successfully")
            return True
        except Exception as e:
            logger.error(f"Error sending admin notification: {e}")
            return False
    
    async def notify_ban(self, username: str, user_id: int, reason: str, moderator: str):
        """Уведомление о бане пользователя"""
        message = (
            f"🚫 БЛОКИРОВКА ПОЛЬЗОВАТЕЛЯ\n\n"
            f"👤 Пользователь: @{username}\n"
            f"🆔 ID: {user_id}\n"
            f"📝 Причина: {reason}\n"
            f"👮 Модератор: @{moderator}\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        await self.send_notification(message)
    
    async def notify_unban(self, username: str, user_id: int, moderator: str):
        """Уведомление о разбане пользователя"""
        message = (
            f"✅ РАЗБЛОКИРОВКА ПОЛЬЗОВАТЕЛЯ\n\n"
            f"👤 Пользователь: @{username}\n"
            f"🆔 ID: {user_id}\n"
            f"👮 Модератор: @{moderator}\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        await self.send_notification(message)
    
    async def notify_mute(self, username: str, user_id: int, duration: str, moderator: str):
        """Уведомление о муте пользователя"""
        message = (
            f"🔇 МУТ ПОЛЬЗОВАТЕЛЯ\n\n"
            f"👤 Пользователь: @{username}\n"
            f"🆔 ID: {user_id}\n"
            f"⏱️ Длительность: {duration}\n"
            f"👮 Модератор: @{moderator}\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        await self.send_notification(message)
    
    async def notify_unmute(self, username: str, user_id: int, moderator: str):
        """Уведомление о размуте пользователя"""
        message = (
            f"🔊 РАЗМУТ ПОЛЬЗОВАТЕЛЯ\n\n"
            f"👤 Пользователь: @{username}\n"
            f"🆔 ID: {user_id}\n"
            f"👮 Модератор: @{moderator}\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        await self.send_notification(message)
    
    async def notify_report(self, reporter: str, reporter_id: int, target: str, reason: str):
        """Уведомление о жалобе"""
        message = (
            f"🚨 НОВАЯ ЖАЛОБА\n\n"
            f"👤 От: @{reporter} (ID: {reporter_id})\n"
            f"🎯 На: {target}\n"
            f"📝 Причина: {reason}\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        await self.send_notification(message)
    
    async def notify_game_winner(self, game_version: str, username: str, user_id: int, word: str):
        """Уведомление о победителе в игре"""
        message = (
            f"🏆 ПОБЕДИТЕЛЬ В ИГРЕ {game_version.upper()}!\n\n"
            f"👤 Победитель: @{username}\n"
            f"🆔 ID: {user_id}\n"
            f"🎯 Угадал слово: {word}\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"📞 Свяжитесь с победителем для вручения приза!"
        )
        await self.send_notification(message)
    
    async def notify_roll_winner(self, game_version: str, winners: list):
        """Уведомление о победителях розыгрыша"""
        winners_text = "\n".join([f"{i+1}. @{w['username']} (номер: {w['number']})" for i, w in enumerate(winners)])
        
        message = (
            f"🎲 РОЗЫГРЫШ {game_version.upper()} ЗАВЕРШЕН!\n\n"
            f"🏆 Победители:\n{winners_text}\n\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"📞 Свяжитесь с победителями для вручения призов!"
        )
        await self.send_notification(message)
    
    async def notify_new_user(self, username: str, user_id: int, first_name: str):
        """Уведомление о новом пользователе"""
        message = (
            f"👋 НОВЫЙ ПОЛЬЗОВАТЕЛЬ\n\n"
            f"👤 Имя: {first_name}\n"
            f"📧 Username: @{username if username else 'не указан'}\n"
            f"🆔 ID: {user_id}\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        await self.send_notification(message)
    
    async def send_statistics(self):
        """Отправить расширенную статистику в админскую группу"""
        from services.channel_stats import channel_stats
        
        try:
            channel_statistics = await channel_stats.get_all_stats()
            channel_stats_text = channel_stats.format_stats_message(channel_statistics)
        except Exception as e:
            logger.error(f"Error collecting channel stats: {e}")
            channel_stats_text = "❌ Ошибка сбора статистики"
        
        message = channel_stats_text
        
        await self.send_notification(message)
        
        # Сбрасываем счетчики сообщений в чатах после отправки статистики
        for chat_id in Config.STATS_CHANNELS.values():
            channel_stats.reset_message_count(chat_id)
        
        logger.info("Statistics sent to admin group")
    
    async def notify_error(self, error_type: str, error_message: str, user_id: Optional[int] = None):
        """Уведомление об ошибке"""
        message = (
            f"⚠️ ОШИБКА В БОТЕ\n\n"
            f"🔴 Тип: {error_type}\n"
            f"📝 Сообщение: {error_message[:200]}\n"
        )
        
        if user_id:
            message += f"👤 User ID: {user_id}\n"
        
        message += f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        
        await self.send_notification(message)
    
    async def notify_lockdown(self, chat_id: int, duration: str, moderator: str):
        """Уведомление о блокировке чата"""
        message = (
            f"🔒 ЧАТ ЗАБЛОКИРОВАН\n\n"
            f"💬 Chat ID: {chat_id}\n"
            f"⏱️ Длительность: {duration}\n"
            f"👮 Модератор: @{moderator}\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        await self.send_notification(message)
    
    async def notify_broadcast(self, sent: int, failed: int, moderator: str):
        """Уведомление о рассылке"""
        message = (
            f"📢 РАССЫЛКА ЗАВЕРШЕНА\n\n"
            f"✅ Отправлено: {sent}\n"
            f"❌ Не удалось: {failed}\n"
            f"👮 Инициатор: @{moderator}\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        await self.send_notification(message)

# Глобальный экземпляр сервиса
admin_notifications = AdminNotificationService()
