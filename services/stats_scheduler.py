# -*- coding: utf-8 -*-
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from config import Config
import pytz

logger = logging.getLogger(__name__)

# Timezone Будапешта
BUDAPEST_TZ = pytz.timezone('Europe/Budapest')

# Времена отправки статистики (Будапешт)
STATS_TIMES_BUDAPEST = [
    (9, 6),      # 09:06
    (15, 16),    # 15:16
    (23, 23),    # 23:23
    (21, 11),    # 21:11
    (3, 45),     # 03:45
    (11, 18),    # 11:18
]

class StatsScheduler:
    """Планировщик автоматической статистики с фиксированными временами"""
    
    def __init__(self):
        self.task: Optional[asyncio.Task] = None
        self.running = False
        self.admin_notifications = None
        self._stop_event = asyncio.Event()
    
    def set_admin_notifications(self, admin_notifications):
        """Устанавливает сервис уведомлений"""
        self.admin_notifications = admin_notifications
        logger.info("Admin notifications service set for stats scheduler")
    
    async def start(self):
        """Запустить планировщик статистики"""
        if self.task and not self.task.done():
            logger.warning("Stats scheduler already running")
            return
        
        if not self.admin_notifications:
            logger.error("Admin notifications service not set")
            return
        
        self.running = True
        self._stop_event.clear()
        self.task = asyncio.create_task(self._stats_loop())
        logger.info("Stats scheduler started")
        
        # Логируем расписание
        logger.info(f"📅 Statistics schedule (Budapest timezone):")
        for hour, minute in STATS_TIMES_BUDAPEST:
            logger.info(f"  ⏰ {hour:02d}:{minute:02d}")
    
    async def stop(self):
        """Остановить планировщик корректно"""
        logger.info("Stopping stats scheduler...")
        self.running = False
        self._stop_event.set()
        
        if self.task:
            try:
                # Даём задаче 5 секунд на завершение
                await asyncio.wait_for(self.task, timeout=5.0)
                logger.info("Stats scheduler task completed")
            except asyncio.TimeoutError:
                logger.warning("Stats scheduler task timeout, cancelling...")
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    logger.info("Stats scheduler task cancelled")
            except asyncio.CancelledError:
                logger.info("Stats scheduler task was cancelled")
            except Exception as e:
                logger.error(f"Error stopping stats scheduler: {e}")
            finally:
                self.task = None
        
        logger.info("Stats scheduler stopped")
    
    async def _stats_loop(self):
        """Основной цикл отправки статистики"""
        logger.info("Stats loop started")
        
        try:
            while self.running:
                try:
                    # Получаем текущее время в Будапеште
                    budapest_now = datetime.now(BUDAPEST_TZ)
                    current_hour = budapest_now.hour
                    current_minute = budapest_now.minute
                    
                    # Проверяем, совпадает ли текущее время с расписанием
                    should_send = False
                    for scheduled_hour, scheduled_minute in STATS_TIMES_BUDAPEST:
                        if current_hour == scheduled_hour and current_minute == scheduled_minute:
                            should_send = True
                            break
                    
                    if should_send and self.running:
                        logger.info(f"⏰ Stats time reached: {current_hour:02d}:{current_minute:02d} Budapest")
                        try:
                            await self.admin_notifications.send_statistics()
                            logger.info("✅ Statistics sent successfully")
                        except Exception as e:
                            logger.error(f"Error sending statistics: {e}")
                        
                        # Ждём 2 минуты чтобы не отправить статистику дважды
                        await asyncio.sleep(120)
                    
                    # Проверяем каждые 30 секунд
                    try:
                        await asyncio.wait_for(
                            self._stop_event.wait(),
                            timeout=30
                        )
                        # Если stop event сработал - выходим
                        if not self.running:
                            logger.info("Stats loop received stop signal")
                            break
                    except asyncio.TimeoutError:
                        # Timeout - нормально, продолжаем
                        pass
                    
                except asyncio.CancelledError:
                    logger.info("Stats loop cancelled")
                    raise
                except Exception as e:
                    logger.error(f"Error in stats loop: {e}")
                    await asyncio.sleep(60)
                    
        except asyncio.CancelledError:
            logger.info("Stats loop cancelled (outer)")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in stats loop: {e}", exc_info=True)
        finally:
            logger.info("Stats loop finished")
    
    def is_running(self) -> bool:
        """Проверить, запущен ли планировщик"""
        return self.running and self.task and not self.task.done()
    
    async def send_stats_now(self):
        """Отправить статистику немедленно (для команды)"""
        if not self.admin_notifications:
            logger.error("Admin notifications service not set")
            return False
        
        try:
            await self.admin_notifications.send_statistics()
            logger.info("Statistics sent manually")
            return True
        except Exception as e:
            logger.error(f"Error sending stats: {e}")
            return False
    
    def get_next_stats_time(self) -> str:
        """Получить время следующей статистики"""
        budapest_now = datetime.now(BUDAPEST_TZ)
        current_hour = budapest_now.hour
        current_minute = budapest_now.minute
        
        # Находим следующее время из расписания
        next_time = None
        for hour, minute in sorted(STATS_TIMES_BUDAPEST):
            if (hour > current_hour) or (hour == current_hour and minute > current_minute):
                next_time = (hour, minute)
                break
        
        # Если нет времени сегодня, берём первое время завтра
        if not next_time:
            next_time = sorted(STATS_TIMES_BUDAPEST)[0]
            return f"Завтра в {next_time[0]:02d}:{next_time[1]:02d}"
        
        return f"Сегодня в {next_time[0]:02d}:{next_time[1]:02d}"

# Глобальный экземпляр планировщика
stats_scheduler = StatsScheduler()
