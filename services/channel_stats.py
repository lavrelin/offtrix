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
            Config.STATS_CHANNELS.get('gambling_chat'): "🌑 Catalog",
            Config.STATS_CHANNELS.get('catalog'): "🌒 Marketplace",
            Config.STATS_CHANNELS.get('trade'): "🌓 Main",
            Config.STATS_CHANNELS.get('budapest_main'): "🌔 Chat",
            Config.STATS_CHANNELS.get('budapest_chat'): "🌕 Partners",
            Config.STATS_CHANNELS.get('partners'): "🌖 Social",
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
    
    class ChannelStatsService:
    def format_stats_message(self, stats):
        timestamp = stats['timestamp'].strftime('%d.%m.%Y %H:%M')
        message = f"📊 **РАСШИРЕННАЯ СТАТИСТИКА**\n\n"
        message += f"🕓 Обновлено {timestamp} (Будапешт)\n\n"
        channel_names = {
            'gambling_chat': '🌑 Catalog',
            'catalog': '🌒 Marketplace',
            'trade': '🌓 Main',
            'budapest_main': '🌔 Chat',
            'budapest_chat': '🌕 Partners',
            'partners': '🌖 Social',
            'budapest_people': '🌗 Instagram',
            'budapesocial': '🌘 Social2',
        }
        if stats.get('channels'):
            message += "📢 **СТАТИСТИКА КАНАЛОВ**\n\n"
            for channel in stats['channels']:
                if 'error' in channel: continue
                name = channel_names.get(channel['name'], channel['name'])
                count = channel.get('member_count', 'N/A')
                day_change = channel.get('day_change', 0)
                week_change = channel.get('week_change', 0)
                month_change = channel.get('month_change', 0)
                message += f"{name} — {count} участников.\n"
                message += f"День: {day_change:+d}\n"
                message += f"Неделя: {week_change:+d}\n"
                message += f"Месяц: {month_change:+d}\n\n"
        from data.user_data import user_data, get_banned_users
        total_users = len(user_data)
        active_24h = sum(1 for d in user_data.values() if datetime.now() - d['last_activity'] <= timedelta(days=1))
        active_week = sum(1 for d in user_data.values() if datetime.now() - d['last_activity'] <= timedelta(days=7))
        active_month = sum(1 for d in user_data.values() if datetime.now() - d['last_activity'] <= timedelta(days=30))
        total_commands = sum(d.get('command_count', 0) for d in user_data.values())
        banned_count = len(get_banned_users())
        total_messages = sum(d.get('message_count', 0) for d in user_data.values())
        avg_messages = round(total_messages / total_users, 1) if total_users else 0
        message += f"⌨️ Всего команд: {total_commands}\n"
        message += f"👥 Уникальные пользователи:\nDay: {active_24h}\nWeek: {active_week}\nMonth: {active_month}\n"
        message += f"• Забанено: {banned_count}\n"
        message += f"💬 Сообщения:\n• Всего: {total_messages}\n• Среднее на пользователя: {avg_messages}\n"
        from data.user_data import get_top_commands
        top_commands = [c for c in get_top_commands(5) if c[0] not in ['needadd', 'tryadd', 'moreadd']]
        if top_commands:
            medals = ['🥇', '🥈', '🥉', '⚡️', '💥']
            for i, (cmd, count) in enumerate(top_commands):
                medal = medals[i] if i < len(medals) else '▫️'
                message += f"{medal} /{cmd} — {count}\n"
        return message
            
        except Exception as e:
            logger.error(f"Error formatting stats message: {e}")
            return f"❌ Ошибка форматирования статистики: {e}"

# Глобальный экземпляр сервиса
channel_stats = ChannelStatsService()
