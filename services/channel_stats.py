# -*- coding: utf-8 -*-
"""
Channel Stats Service v2.0
Отслеживание изменений пользователей за Day/Week/Month
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from config import Config
import pytz

logger = logging.getLogger(__name__)

BUDAPEST_TZ = pytz.timezone('Europe/Budapest')

class ChannelStatsService:
    """Сервис для сбора статистики каналов с отслеживанием изменений"""
    
    def __init__(self):
        self.bot = None
        self.stats_history = {}  # История статистики: {channel: {date: count}}
        self.chat_messages = {}
        self.hourly_activity = {}
    
    def set_bot(self, bot):
        """Устанавливает экземпляр бота"""
        self.bot = bot
        logger.info("Bot instance set for channel stats service")
    
    async def get_channel_stats(self, channel_id: int, channel_name: str) -> Dict[str, Any]:
        """Получить статистику канала с изменениями"""
        try:
            if not self.bot:
                logger.warning("Bot instance not set")
                return None
            
            chat = await self.bot.get_chat(channel_id)
            
            try:
                member_count = await self.bot.get_chat_member_count(channel_id)
            except Exception as e:
                logger.warning(f"Could not get member count for {channel_name}: {e}")
                member_count = None
            
            # Инициализируем историю если нет
            if channel_name not in self.stats_history:
                self.stats_history[channel_name] = {}
            
            now = datetime.now(BUDAPEST_TZ)
            today_key = now.strftime('%Y-%m-%d')
            
            # Сохраняем текущее значение
            self.stats_history[channel_name][today_key] = member_count
            
            # Вычисляем изменения
            changes = self._calculate_changes(channel_name, member_count, now)
            
            stats = {
                'name': channel_name,
                'title': chat.title,
                'member_count': member_count,
                'day_change': changes['day_change'],
                'day_prev': changes['day_prev'],
                'week_change': changes['week_change'],
                'week_prev': changes['week_prev'],
                'month_change': changes['month_change'],
                'month_prev': changes['month_prev'],
                'type': chat.type,
                'timestamp': now
            }
            
            logger.info(f"Stats collected for {channel_name}: {member_count} members")
            return stats
            
        except Exception as e:
            logger.error(f"Error getting stats for {channel_name} ({channel_id}): {e}")
            return {
                'name': channel_name,
                'error': str(e),
                'timestamp': datetime.now(BUDAPEST_TZ)
            }
    
    def _calculate_changes(self, channel_name: str, current_count: int, now: datetime) -> Dict[str, Any]:
        """Вычислить изменения за день, неделю, месяц"""
        history = self.stats_history.get(channel_name, {})
        
        # День назад
        day_ago_key = (now - timedelta(days=1)).strftime('%Y-%m-%d')
        day_prev = history.get(day_ago_key, current_count)
        day_change = current_count - day_prev if day_prev else 0
        
        # Неделя назад (понедельник)
        days_to_monday = now.weekday()  # 0 = Monday
        week_start = now - timedelta(days=days_to_monday)
        week_ago_key = week_start.strftime('%Y-%m-%d')
        week_prev = history.get(week_ago_key, current_count)
        week_change = current_count - week_prev if week_prev else 0
        
        # Месяц назад (1-е число)
        month_start = now.replace(day=1)
        month_ago_key = month_start.strftime('%Y-%m-%d')
        month_prev = history.get(month_ago_key, current_count)
        month_change = current_count - month_prev if month_prev else 0
        
        return {
            'day_change': day_change,
            'day_prev': day_prev,
            'week_change': week_change,
            'week_prev': week_prev,
            'month_change': month_change,
            'month_prev': month_prev,
        }
    
    def increment_message_count(self, chat_id: int):
        """Увеличить счетчик сообщений для чата"""
        if chat_id not in self.chat_messages:
            self.chat_messages[chat_id] = {
                'count': 0,
                'last_reset': datetime.now(BUDAPEST_TZ)
            }
        
        self.chat_messages[chat_id]['count'] += 1
        
        # Добавляем в heatmap активности
        current_hour = datetime.now(BUDAPEST_TZ).hour
        chat_name = self._get_chat_name_by_id(chat_id)
        
        if chat_name not in self.hourly_activity:
            self.hourly_activity[chat_name] = {f"{h:02d}:00": 0 for h in range(24)}
        
        self.hourly_activity[chat_name][f"{current_hour:02d}:00"] += 1
    
    def reset_message_count(self, chat_id: int):
        """Сбросить счетчик сообщений для чата"""
        self.chat_messages[chat_id] = {
            'count': 0,
            'last_reset': datetime.now(BUDAPEST_TZ)
        }
    
    def _get_chat_name_by_id(self, chat_id: int) -> str:
        """Получить название чата по ID"""
        chat_map = {
            Config.STATS_CHANNELS.get('catalog'): "🌑 Catalog",
            Config.STATS_CHANNELS.get('trade'): "🌒 Marketplace",
            Config.STATS_CHANNELS.get('budapest_main'): "🌓 Budapest",
            Config.STATS_CHANNELS.get('budapest_chat'): "🌔 Chat",
            Config.STATS_CHANNELS.get('partners'): "🌕 Partners",
            Config.STATS_CHANNELS.get('budapest_people'): "🌖 TopPeople",
            Config.STATS_CHANNELS.get('budapes'): "🌗 🦄Budapest",
        }
        return chat_map.get(chat_id, f"chat_{chat_id}")
    
    async def get_all_stats(self) -> Dict[str, Any]:
        """Собрать статистику по всем каналам"""
        try:
            all_stats = {
                'timestamp': datetime.now(BUDAPEST_TZ),
                'channels': [],
                'total_changes': {
                    'day': 0,
                    'week': 0,
                    'month': 0
                }
            }
            
            # Собираем статистику по каналам
            for name, channel_id in Config.STATS_CHANNELS.items():
                try:
                    stats = await self.get_channel_stats(channel_id, name)
                    if stats and 'error' not in stats:
                        all_stats['channels'].append(stats)
                        
                        # Суммируем изменения
                        all_stats['total_changes']['day'] += stats.get('day_change', 0)
                        all_stats['total_changes']['week'] += stats.get('week_change', 0)
                        all_stats['total_changes']['month'] += stats.get('month_change', 0)
                        
                except Exception as e:
                    logger.error(f"Error collecting stats for {name}: {e}")
            
            return all_stats
            
        except Exception as e:
            logger.error(f"Error collecting all stats: {e}")
            return {
                'timestamp': datetime.now(BUDAPEST_TZ),
                'error': str(e),
                'channels': []
            }
    
    def format_stats_message(self, stats: Dict[str, Any]) -> str:
        """Форматировать статистику в красивое сообщение"""
        try:
            from data.user_data import user_data, get_top_commands
            
            now = stats['timestamp']
            timestamp = now.strftime('%H:%M')
            
            # Начало недели (понедельник)
            days_to_monday = now.weekday()
            week_start = now - timedelta(days=days_to_monday)
            week_start_str = week_start.strftime('%d.%m')
            
            # Начало месяца
            month_start = now.replace(day=1)
            month_start_str = month_start.strftime('%d.%m')
            
            message = ""
            
            # Названия каналов
            channel_names = {
                'catalog': '🌑 Каталог Услуг',
                'trade': '🌒 Marketplace',
                'budapest_main': '🌓 Будапешт',
                'budapest_chat': '🌔 Чат',
                'partners': '🌕 Партнерс',
                'budapest_people': '🌖 TopPeople',
                'budapes': '🌗 🦄Budapest',
            }
            
            # Список каналов
            for key in channel_names:
                channel_id = Config.STATS_CHANNELS.get(key)
                if channel_id:
                    message += f"{channel_names[key]} —{channel_id}\n"
            
            message += f"🌘 TrixBot - статистика бота @Trixlivebot\n\n"
            message += f"⚡️ Обновлено {timestamp} (Будапешт)\n"
            
            # Вычисляем изменения для Week и Month
            total_week = 0
            total_month = 0
            if stats.get('channels'):
                for channel in stats['channels']:
                    if 'error' not in channel:
                        total_week += channel.get('week_change', 0)
                        total_month += channel.get('month_change', 0)
            
            message += f"Week : {total_week} - старт недели в пн {timestamp}\n"
            message += f"Month: {total_month} - старт месяца 1го числа {timestamp}\n\n"
            
            # TOP FIVE команд
            top_commands = get_top_commands(5)
            if top_commands:
                message += "📏🏆 **TOP ✋FIVE:**\n"
                medals = ['🥇', '🥈', '🥉', '⚡️', '💥']
                for i, (cmd, count) in enumerate(top_commands):
                    medal = medals[i] if i < len(medals) else '▫️'
                    message += f"▫️ {medal}/{cmd} — {count} раз\n"
            
            # Уникальные пользователи
            message += f"\n🔘 Уникальные пользователи Трикс бота:\n"
            active_day = sum(
                1 for d in user_data.values() 
                if datetime.now() - d['last_activity'] <= timedelta(days=1)
            )
            active_week = sum(
                1 for d in user_data.values() 
                if datetime.now() - d['last_activity'] <= timedelta(days=7)
            )
            active_month = sum(
                1 for d in user_data.values() 
                if datetime.now() - d['last_activity'] <= timedelta(days=30)
            )
            
            message += f"Day: {active_day}\n"
            message += f"Week: {active_week}\n"
            message += f"Month: {active_month}\n"
            
            return message
            
        except Exception as e:
            logger.error(f"Error formatting stats message: {e}")
            return f"❌ Ошибка форматирования статистики: {e}"

# Глобальный экземпляр сервиса
channel_stats = ChannelStatsService()
