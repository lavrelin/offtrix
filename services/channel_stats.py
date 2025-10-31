import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from config import Config
import pytz

logger = logging.getLogger(__name__)

BUDAPEST_TZ = pytz.timezone('Europe/Budapest')

class ChannelStatsService:
    
    def __init__(self):
        self.bot = None
        self.stats_history = {}
        self.chat_messages = {}
        self.hourly_activity = {}
    
    def set_bot(self, bot):
        self.bot = bot
        logger.info("Bot instance set for channel stats service")
    
    async def get_channel_stats(self, channel_id: int, channel_name: str) -> Dict[str, Any]:
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
            
            if channel_name not in self.stats_history:
                self.stats_history[channel_name] = {}
            
            now = datetime.now(BUDAPEST_TZ)
            today_key = now.strftime('%Y-%m-%d')
            
            self.stats_history[channel_name][today_key] = member_count
            
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
        history = self.stats_history.get(channel_name, {})
        
        day_ago_key = (now - timedelta(days=1)).strftime('%Y-%m-%d')
        day_prev = history.get(day_ago_key, current_count)
        day_change = current_count - day_prev if day_prev else 0
        
        days_to_monday = now.weekday()
        week_start = now - timedelta(days=days_to_monday)
        week_ago_key = week_start.strftime('%Y-%m-%d')
        week_prev = history.get(week_ago_key, current_count)
        week_change = current_count - week_prev if week_prev else 0
        
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
        if chat_id not in self.chat_messages:
            self.chat_messages[chat_id] = {
                'count': 0,
                'last_reset': datetime.now(BUDAPEST_TZ)
            }
        
        self.chat_messages[chat_id]['count'] += 1
        
        current_hour = datetime.now(BUDAPEST_TZ).hour
        chat_name = self._get_chat_name_by_id(chat_id)
        
        if chat_name not in self.hourly_activity:
            self.hourly_activity[chat_name] = {f"{h:02d}:00": 0 for h in range(24)}
        
        self.hourly_activity[chat_name][f"{current_hour:02d}:00"] += 1
    
    def reset_message_count(self, chat_id: int):
        self.chat_messages[chat_id] = {
            'count': 0,
            'last_reset': datetime.now(BUDAPEST_TZ)
        }
    
    def _get_chat_name_by_id(self, chat_id: int) -> str:
        chat_map = {
            Config.STATS_CHANNELS.get('catalog'): "Catalog",
            Config.STATS_CHANNELS.get('trade'): "Marketplace",
            Config.STATS_CHANNELS.get('budapest_main'): "Main",
            Config.STATS_CHANNELS.get('budapest_chat'): "Chat",
            Config.STATS_CHANNELS.get('partners'): "Partners",
            Config.STATS_CHANNELS.get('budapest_people'): "TopPeople",
            Config.STATS_CHANNELS.get('budapest_unicorn'): "Budapest Unicorn",
        }
        return chat_map.get(chat_id, f"chat_{chat_id}")
    
    async def get_all_stats(self) -> Dict[str, Any]:
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
            
            for name, channel_id in Config.STATS_CHANNELS.items():
                try:
                    stats = await self.get_channel_stats(channel_id, name)
                    if stats and 'error' not in stats:
                        all_stats['channels'].append(stats)
                        
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
        try:
            timestamp = stats['timestamp'].strftime('%d.%m.%Y %H:%M')
            
            message = f"Расширенная статистика\n\n"
            message += f"Обновлено {timestamp} (Будапешт)\n\n"
            
            channel_names = {
                'catalog': 'Каталог Услуг',
                'trade': 'Marketplace',
                'budapest_main': 'Будапешт',
                'budapest_chat': 'Чат',
                'partners': 'Партнерс',
                'budapest_people': 'TopPeople',
                'budapest_unicorn': 'Budapest',
            }
            
            if stats.get('channels'):
                message += "Статистика каналов сообщества\n\n"
                
                for channel in stats['channels']:
                    if 'error' in channel:
                        continue
                    
                    name = channel_names.get(channel['name'], channel['name'])
                    count = channel.get('member_count', 'N/A')
                    
                    week_change = channel.get('week_change', 0)
                    week_prev = channel.get('week_prev', 0)
                    
                    month_change = channel.get('month_change', 0)
                    month_prev = channel.get('month_prev', 0)
                    
                    message += f"{name} — {count} участников\n"
                    message += f"Week: {week_change:+d} ({week_prev})\n"
                    message += f"Month: {month_change:+d} ({month_prev})\n\n"
            
            from data.user_data import get_user_stats, get_top_commands, get_active_users_by_period
            
            message += "Статистика команд бота\n\n"
            
            stats_data = get_user_stats()
            total_commands = stats_data['total_commands']
            
            message += f"Всего вызовов команд: {total_commands}\n\n"
            
            active_day = get_active_users_by_period(1)
            active_week = get_active_users_by_period(7)
            active_month = get_active_users_by_period(30)
            
            message += f"Уникальные пользователи Трикс бота:\n"
            message += f"Day: {active_day}\n"
            message += f"Week: {active_week}\n"
            message += f"Month: {active_month}\n\n"
            
            top_commands = get_top_commands(5)
            
            if top_commands:
                message += "TOP FIVE:\n"
                medals = ['', '', '', '', '']
                for i, (cmd, count) in enumerate(top_commands):
                    medal = medals[i] if i < len(medals) else ''
                    message += f"{medal} /{cmd} — {count} раз\n"
            
            return message
            
        except Exception as e:
            logger.error(f"Error formatting stats message: {e}")
            return f"Ошибка форматирования статистики: {e}"

channel_stats = ChannelStatsService()
