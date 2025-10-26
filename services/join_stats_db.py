import logging
from datetime import datetime
from sqlalchemy import select
from services.db import db
from models import JoinStat, JoinStatUser

logger = logging.getLogger(__name__)

async def register_join_user(key: str, user_id: int) -> bool:
    """
    Засчитать уникальный переход user_id к группе key.
    Возвращает True, если засчитан впервые; False, если уже был.
    """
    await db.init()
    async with db.get_session() as session:
        exists = await session.execute(
            select(JoinStatUser).where(
                JoinStatUser.key == key,
                JoinStatUser.user_id == user_id
            )
        )
        row = exists.scalar_one_or_none()
        if row:
            return False  # Уже был

        session.add(JoinStatUser(key=key, user_id=user_id, created_at=datetime.utcnow()))
        stat = await session.execute(select(JoinStat).where(JoinStat.key == key))
        stat_obj = stat.scalar_one_or_none()
        if stat_obj:
            stat_obj.count = (stat_obj.count or 0) + 1
            stat_obj.last_updated = datetime.utcnow()
            session.add(stat_obj)
        else:
            session.add(JoinStat(key=key, count=1, last_updated=datetime.utcnow()))
        await session.commit()
        return True

async def has_user_joined(key: str, user_id: int) -> bool:
    """
    Проверяет, был ли user_id уже засчитан для данной группы key.
    """
    await db.init()
    async with db.get_session() as session:
        result = await session.execute(
            select(JoinStatUser).where(
                JoinStatUser.key == key,
                JoinStatUser.user_id == user_id
            )
        )
        return bool(result.scalar_one_or_none())

async def get_join_count(key: str) -> int:
    """
    Сколько уникальных пользователей засчитано для группы key.
    """
    await db.init()
    async with db.get_session() as session:
        result = await session.execute(
            select(JoinStatUser).where(JoinStatUser.key == key)
        )
        return len(result.scalars().all())

async def get_all_unique_counts() -> dict:
    """
    Словарь {key: count} для всех групп (уникальные пользователи).
    """
    await db.init()
    async with db.get_session() as session:
        result = await session.execute(select(JoinStatUser))
        rows = result.scalars().all()
        stats = {}
        for row in rows:
            stats.setdefault(row.key, set()).add(row.user_id)
        return {k: len(v) for k, v in stats.items()}
