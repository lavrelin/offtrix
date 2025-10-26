# services/join_stats_db.py
# Асинхронный сервис для хранения/получения статистики переходов через базу данных (JoinStat model)
import logging
from datetime import datetime
from typing import Dict

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from services.db import db
from models import JoinStat

logger = logging.getLogger(__name__)

async def increment(key: str) -> int:
    """
    Увеличить счётчик для ключа и вернуть новое значение.
    Создаёт запись если не существует.
    """
    try:
        # Убедимся, что DB инициализирован
        await db.init()
        async with db.get_session() as session:
            # Попробуем получить запись
            result = await session.execute(select(JoinStat).where(JoinStat.key == key))
            stat = result.scalar_one_or_none()
            if stat:
                stat.count = (stat.count or 0) + 1
                stat.last_updated = datetime.utcnow()
                session.add(stat)
                await session.commit()
                return int(stat.count)
            else:
                stat = JoinStat(key=key, count=1, last_updated=datetime.utcnow())
                session.add(stat)
                await session.commit()
                # refresh to load generated fields
                try:
                    await session.refresh(stat)
                except Exception:
                    pass
                return int(stat.count)
    except SQLAlchemyError as e:
        logger.error(f"DB error in join_stats.increment: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error in join_stats.increment: {e}", exc_info=True)
        raise

async def get(key: str) -> int:
    """Вернуть текущее значение счётчика для ключа (0 если нет)"""
    try:
        await db.init()
        async with db.get_session() as session:
            result = await session.execute(select(JoinStat).where(JoinStat.key == key))
            stat = result.scalar_one_or_none()
            return int(stat.count) if stat else 0
    except Exception as e:
        logger.error(f"Error getting join_stat for key={key}: {e}", exc_info=True)
        return 0

async def get_all() -> Dict[str, int]:
    """Вернуть словарь {key: count} для всех записей"""
    try:
        await db.init()
        async with db.get_session() as session:
            result = await session.execute(select(JoinStat))
            rows = result.scalars().all()
            return {row.key: int(row.count or 0) for row in rows}
    except Exception as e:
        logger.error(f"Error getting all join_stats: {e}", exc_info=True)
        return {}
