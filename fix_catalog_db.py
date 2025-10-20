#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Быстрое исправление базы данных каталога
Использование: python fix_catalog_db.py
"""

import asyncio
import logging
from services.db import db
from models import Base, CatalogPost, CatalogReview, CatalogSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fix_catalog_db():
    """Исправить базу данных каталога"""
    try:
        logger.info("🔧 Исправляю базу данных каталога...")
        
        # Инициализируем БД
        await db.init()
        
        if not db.engine:
            logger.error("❌ Не удалось подключиться к БД")
            return False
        
        logger.info("✅ Подключение к БД установлено")
        
        # Создаём таблицы каталога
        logger.info("📋 Создаю таблицы каталога...")
        
        async with db.engine.begin() as conn:
            # Создаём только таблицы каталога
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("✅ Таблицы созданы")
        
        # Проверяем таблицы
        from sqlalchemy import text
        
        async with db.get_session() as session:
            result = await session.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'catalog_%'")
            )
            
            tables = [row[0] for row in result.fetchall()]
            logger.info(f"📊 Таблицы каталога: {tables}")
            
            required = {'catalog_posts', 'catalog_reviews', 'catalog_subscriptions', 'catalog_sessions'}
            missing = required - set(tables)
            
            if missing:
                logger.error(f"❌ Отсутствуют таблицы: {missing}")
                return False
            
            logger.info("✅ Все таблицы на месте")
        
        # Добавляем тестовые данные
        logger.info("🧪 Добавляю тестовую запись...")
        
        async with db.get_session() as session:
            # Проверяем есть ли уже записи
            result = await session.execute(
                text("SELECT COUNT(*) FROM catalog_posts")
            )
            count = result.scalar()
            
            if count == 0:
                # Добавляем тестовую запись
                test_post = CatalogPost(
                    user_id=123456789,
                    catalog_link="https://t.me/catalogtrix/1",
                    category="Маникюр",
                    name="Тестовая услуга",
                    tags=["тест", "маникюр"],
                    is_active=True
                )
                
                session.add(test_post)
                await session.commit()
                
                logger.info("✅ Тестовая запись добавлена")
            else:
                logger.info(f"ℹ️  В каталоге уже есть {count} записей")
        
        await db.close()
        
        logger.info("\n" + "="*60)
        logger.info("✅ БАЗА ДАННЫХ КАТАЛОГА ИСПРАВЛЕНА!")
        logger.info("="*60)
        logger.info("\n🚀 Можете запускать бота: python main.py\n")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = asyncio.run(fix_catalog_db())
    exit(0 if success else 1)
