import asyncio
import logging
from datetime import datetime, timedelta
from telegram import Bot
from telegram.error import TelegramError
from config import Config
from data.user_data import db

logger = logging.getLogger(__name__)

class StatsScheduler:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.running = False
        self.task = None
        self.next_update = None

    async def get_unique_users_count(self, period: str) -> int:
        try:
            now = datetime.now()
            if period == 'day':
                start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == 'week':
                start_time = now - timedelta(days=now.weekday())
                start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == 'month':
                start_time = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                return 0

            query = """
                SELECT COUNT(DISTINCT user_id) 
                FROM user_activity 
                WHERE last_activity >= ?
            """
            result = await db.execute_query(query, (start_time.isoformat(),))
            return result[0][0] if result else 0
        except Exception as e:
            logger.error(f"Error getting unique users for {period}: {e}")
            return 0

    async def get_command_stats(self) -> dict:
        try:
            now = datetime.now()
            week_start = now - timedelta(days=now.weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            weekly_query = """
                SELECT command, COUNT(*) as count 
                FROM command_usage 
                WHERE timestamp >= ? 
                GROUP BY command 
                ORDER BY count DESC 
                LIMIT 5
            """
            weekly_results = await db.execute_query(weekly_query, (week_start.isoformat(),))
            
            monthly_query = """
                SELECT command, COUNT(*) as count 
                FROM command_usage 
                WHERE timestamp >= ? 
                GROUP BY command 
                ORDER BY count DESC 
                LIMIT 5
            """
            monthly_results = await db.execute_query(monthly_query, (month_start.isoformat(),))

            weekly_total = sum(row[1] for row in weekly_results) if weekly_results else 0
            monthly_total = sum(row[1] for row in monthly_results) if monthly_results else 0

            return {
                'week': {'total': weekly_total, 'top': weekly_results or []},
                'month': {'total': monthly_total, 'top': monthly_results or []}
            }
        except Exception as e:
            logger.error(f"Error getting command stats: {e}")
            return {'week': {'total': 0, 'top': []}, 'month': {'total': 0, 'top': []}}

    async def get_channel_stats(self, channel_id: int) -> dict:
        try:
            now = datetime.now()
            day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = now - timedelta(days=now.weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            query = """
                SELECT 
                    SUM(CASE WHEN date >= ? THEN member_count ELSE 0 END) as day_count,
                    SUM(CASE WHEN date >= ? THEN member_count ELSE 0 END) as week_count,
                    SUM(CASE WHEN date >= ? THEN member_count ELSE 0 END) as month_count
                FROM channel_stats 
                WHERE channel_id = ?
            """
            result = await db.execute_query(
                query, 
                (day_start.isoformat(), week_start.isoformat(), month_start.isoformat(), channel_id)
            )
            
            if result and result[0]:
                return {
                    'day': result[0][0] or 0,
                    'week': result[0][1] or 0,
                    'month': result[0][2] or 0
                }
            return {'day': 0, 'week': 0, 'month': 0}
        except Exception as e:
            logger.error(f"Error getting channel stats for {channel_id}: {e}")
            return {'day': 0, 'week': 0, 'month': 0}

    async def format_stats_message(self) -> str:
        now = datetime.now()
        budapest_time = now.strftime('%H:%M')
        
        unique_day = await self.get_unique_users_count('day')
        unique_week = await self.get_unique_users_count('week')
        unique_month = await self.get_unique_users_count('month')
        
        command_stats = await self.get_command_stats()
        
        channels = {
            '🌑 Каталог Услуг': -1002601716810,
            '🌒 Marketplace': -1003033694255,
            '🌓 Будапешт': -1002743668534,
            '🌔 Чат': -1002883770818,
            '🌕 Партнерс': -1002919380244,
            '🌖 TopPeople': -1003088023508,
            '🌗 🦄Budapest': -1003114019170
        }
        
        channel_stats_text = ""
        for name, channel_id in channels.items():
            stats = await self.get_channel_stats(channel_id)
            channel_stats_text += f"{name}\n"
            channel_stats_text += f"  Day: {stats['day']} | Week: {stats['week']} | Month: {stats['month']}\n"
        
        message = f"""🌘 TrixBot - статистика бота @Trixlivebot

⚡️ Обновлено {budapest_time} (Будапешт)

🔘 Уникальные пользователи Трикс бота:
  Day: {unique_day}
  Week: {unique_week}
  Month: {unique_month}

Week: {command_stats['week']['total']} - старт недели в пн {budapest_time}
Month: {command_stats['month']['total']} - старт месяца 1го числа {budapest_time}

📏🏆 TOP ✋FIVE:
"""
        
        medals = ['🥇', '🥈', '🥉', '⚡️', '💥']
        for i, (command, count) in enumerate(command_stats['month']['top'][:5]):
            medal = medals[i] if i < len(medals) else '▫️'
            message += f"▫️ {medal} /{command} — {count} раз\n"
        
        message += f"\n📊 КАНАЛЫ:\n{channel_stats_text}"
        
        return message

    async def update_stats(self):
        try:
            message = await self.format_stats_message()
            
            if Config.STATS_MESSAGE_ID and Config.STATS_CHANNEL_ID:
                try:
                    await self.bot.edit_message_text(
                        chat_id=Config.STATS_CHANNEL_ID,
                        message_id=Config.STATS_MESSAGE_ID,
                        text=message
                    )
                    logger.info(f"Stats updated at {datetime.now().strftime('%H:%M')}")
                except TelegramError as e:
                    logger.error(f"Failed to update stats message: {e}")
            else:
                logger.warning("STATS_MESSAGE_ID or STATS_CHANNEL_ID not configured")
                
        except Exception as e:
            logger.error(f"Error updating stats: {e}", exc_info=True)

    def calculate_next_update(self) -> datetime:
        now = datetime.now()
        next_hour = (now + timedelta(hours=1)).replace(minute=18, second=0, microsecond=0)
        if next_hour <= now:
            next_hour += timedelta(hours=1)
        return next_hour

    async def start(self):
        if self.running:
            logger.warning("Stats scheduler already running")
            return
        
        self.running = True
        logger.info("Stats scheduler started")
        
        while self.running:
            try:
                self.next_update = self.calculate_next_update()
                wait_seconds = (self.next_update - datetime.now()).total_seconds()
                
                if wait_seconds > 0:
                    logger.info(f"Next stats update at {self.next_update.strftime('%H:%M')}")
                    await asyncio.sleep(wait_seconds)
                
                if self.running:
                    await self.update_stats()
                    
            except asyncio.CancelledError:
                logger.info("Stats scheduler task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in stats scheduler: {e}", exc_info=True)
                await asyncio.sleep(300)

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Stats scheduler stopped")
