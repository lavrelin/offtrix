# -*- coding: utf-8 -*-
"""
Сервис для работы с каталогом услуг - С ПОДДЕРЖКОЙ МЕДИА
"""
import logging
import random
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy import select, and_, or_, func
from services.db import db
from models import CatalogPost, CatalogReview, CatalogSubscription, CatalogSession

logger = logging.getLogger(__name__)

# Категории каталога
CATALOG_CATEGORIES = {
    '💇‍♀️ Красота и уход': [
        'Барбер', 'БьютиПроцедуры', 'Волосы', 'Косметолог',
        'Депиляция', 'Эпиляция', 'Маникюр', 'Ресницы и брови', 'Тату'
    ],
    '🩺 Здоровье и тело': [
        'Ветеринар', 'Врач', 'Массажист', 'Психолог', 'Стоматолог', 'Спорт'
    ],
    '🛠️ Услуги и помощь': [
        'Автомеханик', 'Грузчик', 'Клининг', 'Мастер по дому',
        'Перевозчик', 'Ремонт техники', 'Няня', 'Юрист'
    ],
    '📚 Обучение и развитие': [
        'Каналы по изучению венгерского', 'Каналы по изучению английского',
        'Курсы', 'Переводчик', 'Репетитор', 'Музыка', 'Риелтор'
    ],
    '🎭 Досуг и впечатления': [
        'Еда', 'Фотограф', 'Экскурсии', 'Для детей', 'Ремонт', 'Швея', 'Цветы'
    ]
}


class CatalogService:
    """Сервис для работы с каталогом услуг"""
    
    def __init__(self):
        self.max_posts_per_page = 5
        self.max_priority_posts = 10
        self.ad_frequency = 10
    
    async def add_post(
        self,
        user_id: int,
        catalog_link: str,
        category: str,
        name: str,
        tags: List[str],
        media_type: Optional[str] = None,
        media_file_id: Optional[str] = None,
        media_group_id: Optional[str] = None,
        media_json: Optional[List[str]] = None
    ) -> Optional[int]:
        """Добавить пост в каталог с медиа"""
        try:
            async with db.get_session() as session:
                post = CatalogPost(
                    user_id=user_id,
                    catalog_link=catalog_link,
                    category=category,
                    name=name,
                    tags=tags,
                    is_active=True,
                    clicks=0,
                    views=0,
                    # Медиа-поля
                    media_type=media_type,
                    media_file_id=media_file_id,
                    media_group_id=media_group_id,
                    media_json=media_json or []
                )
                
                session.add(post)
                await session.commit()
                await session.refresh(post)
                
                media_info = f"with media ({media_type})" if media_type else "without media"
                logger.info(f"Added catalog post {post.id} by user {user_id} {media_info}")
                return post.id
                
        except Exception as e:
            logger.error(f"Error adding catalog post: {e}")
            return None
    
    async def get_random_posts(self, user_id: int, count: int = 5) -> List[Dict]:
        """Получить случайные посты без повторов С МЕДИА"""
        try:
            async with db.get_session() as session:
                # Получаем сессию пользователя
                result = await session.execute(
                    select(CatalogSession).where(
                        and_(
                            CatalogSession.user_id == user_id,
                            CatalogSession.session_active == True
                        )
                    )
                )
                user_session = result.scalar_one_or_none()
                
                # Создаём сессию если нет
                if not user_session:
                    user_session = CatalogSession(
                        user_id=user_id,
                        viewed_posts=[],
                        session_active=True
                    )
                    session.add(user_session)
                    await session.commit()
                    await session.refresh(user_session)
                
                viewed_ids = user_session.viewed_posts or []
                
                # Получаем непросмотренные активные посты
                result = await session.execute(
                    select(CatalogPost).where(
                        and_(
                            CatalogPost.is_active == True,
                            ~CatalogPost.id.in_(viewed_ids) if viewed_ids else True
                        )
                    ).order_by(func.random()).limit(count)
                )
                posts = result.scalars().all()
                
                if not posts:
                    return []
                
                # Обновляем сессию
                for post in posts:
                    viewed_ids.append(post.id)
                
                user_session.viewed_posts = viewed_ids
                user_session.last_activity = datetime.utcnow()
                await session.commit()
                
                # Конвертируем в dict С МЕДИА
                return [
                    {
                        'id': p.id,
                        'catalog_link': p.catalog_link,
                        'category': p.category,
                        'name': p.name,
                        'tags': p.tags or [],
                        'views': p.views,
                        'clicks': p.clicks,
                        # Медиа-поля
                        'media_type': p.media_type,
                        'media_file_id': p.media_file_id,
                        'media_group_id': p.media_group_id,
                        'media_json': p.media_json or []
                    }
                    for p in posts
                ]
                
        except Exception as e:
            logger.error(f"Error getting random posts: {e}")
            return []
    
    async def search_posts(
        self,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Dict]:
        """Поиск постов по категории и тегам С МЕДИА"""
        try:
            async with db.get_session() as session:
                query = select(CatalogPost).where(CatalogPost.is_active == True)
                
                if category:
                    query = query.where(CatalogPost.category == category)
                
                if tags:
                    # Поиск по тегам (JSON contains)
                    for tag in tags:
                        query = query.where(
                            CatalogPost.tags.contains([tag])
                        )
                
                query = query.limit(limit)
                
                result = await session.execute(query)
                posts = result.scalars().all()
                
                return [
                    {
                        'id': p.id,
                        'catalog_link': p.catalog_link,
                        'category': p.category,
                        'name': p.name,
                        'tags': p.tags or [],
                        'views': p.views,
                        'clicks': p.clicks,
                        # Медиа-поля
                        'media_type': p.media_type,
                        'media_file_id': p.media_file_id,
                        'media_group_id': p.media_group_id,
                        'media_json': p.media_json or []
                    }
                    for p in posts
                ]
                
        except Exception as e:
            logger.error(f"Error searching posts: {e}")
            return []
    
    async def get_post_by_id(self, post_id: int) -> Optional[Dict]:
        """Получить пост по ID с медиа"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(CatalogPost).where(CatalogPost.id == post_id)
                )
                post = result.scalar_one_or_none()
                
                if not post:
                    return None
                
                return {
                    'id': post.id,
                    'catalog_link': post.catalog_link,
                    'category': post.category,
                    'name': post.name,
                    'tags': post.tags or [],
                    'views': post.views,
                    'clicks': post.clicks,
                    'media_type': post.media_type,
                    'media_file_id': post.media_file_id,
                    'media_group_id': post.media_group_id,
                    'media_json': post.media_json or []
                }
                
        except Exception as e:
            logger.error(f"Error getting post {post_id}: {e}")
            return None
    
    async def update_post_media(
        self,
        post_id: int,
        media_type: str,
        media_file_id: str,
        media_group_id: Optional[str] = None,
        media_json: Optional[List[str]] = None
    ) -> bool:
        """Обновить медиа для существующего поста"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(CatalogPost).where(CatalogPost.id == post_id)
                )
                post = result.scalar_one_or_none()
                
                if not post:
                    logger.warning(f"Post {post_id} not found")
                    return False
                
                post.media_type = media_type
                post.media_file_id = media_file_id
                post.media_group_id = media_group_id
                post.media_json = media_json or []
                post.updated_at = datetime.utcnow()
                
                await session.commit()
                logger.info(f"Updated media for post {post_id}: {media_type}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating post media: {e}")
            return False
    
    async def increment_views(self, post_id: int):
        """Увеличить счётчик просмотров"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(CatalogPost).where(CatalogPost.id == post_id)
                )
                post = result.scalar_one_or_none()
                
                if post:
                    post.views += 1
                    await session.commit()
                    
        except Exception as e:
            logger.error(f"Error incrementing views: {e}")
    
    async def increment_clicks(self, post_id: int):
        """Увеличить счётчик кликов"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(CatalogPost).where(CatalogPost.id == post_id)
                )
                post = result.scalar_one_or_none()
                
                if post:
                    post.clicks += 1
                    await session.commit()
                    
        except Exception as e:
            logger.error(f"Error incrementing clicks: {e}")
    
    async def reset_session(self, user_id: int):
        """Сбросить сессию пользователя"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(CatalogSession).where(CatalogSession.user_id == user_id)
                )
                user_session = result.scalar_one_or_none()
                
                if user_session:
                    user_session.viewed_posts = []
                    user_session.last_activity = datetime.utcnow()
                    await session.commit()
                    logger.info(f"Reset session for user {user_id}")
                    
        except Exception as e:
            logger.error(f"Error resetting session: {e}")
    
    async def set_priority_posts(self, links: List[str]) -> int:
        """Установить приоритетные посты по ссылкам"""
        try:
            count = 0
            async with db.get_session() as session:
                # Сбрасываем все приоритеты
                posts_to_reset = (await session.execute(
                    select(CatalogPost).where(CatalogPost.is_priority == True)
                )).scalars().all()
                
                for post in posts_to_reset:
                    post.is_priority = False
                
                # Устанавливаем новые приоритеты
                for link in links[:self.max_priority_posts]:
                    result = await session.execute(
                        select(CatalogPost).where(CatalogPost.catalog_link == link)
                    )
                    post = result.scalar_one_or_none()
                    
                    if post:
                        post.is_priority = True
                        count += 1
                
                await session.commit()
                logger.info(f"Set {count} priority posts")
                return count
                
        except Exception as e:
            logger.error(f"Error setting priority posts: {e}")
            return 0
    
    async def add_ad_post(self, catalog_link: str, description: str) -> Optional[int]:
        """Добавить рекламный пост"""
        try:
            async with db.get_session() as session:
                post = CatalogPost(
                    user_id=0,  # Системный пост
                    catalog_link=catalog_link,
                    category='Реклама',
                    name=description,
                    tags=[],
                    is_active=True,
                    is_ad=True,
                    ad_frequency=self.ad_frequency
                )
                
                session.add(post)
                await session.commit()
                await session.refresh(post)
                
                logger.info(f"Added ad post {post.id}")
                return post.id
                
        except Exception as e:
            logger.error(f"Error adding ad post: {e}")
            return None
    
    async def get_posts_with_media(self, limit: int = 50) -> List[Dict]:
        """Получить все посты с медиа (для статистики)"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(CatalogPost).where(
                        and_(
                            CatalogPost.is_active == True,
                            CatalogPost.media_type.isnot(None)
                        )
                    ).limit(limit)
                )
                posts = result.scalars().all()
                
                return [
                    {
                        'id': p.id,
                        'category': p.category,
                        'name': p.name,
                        'media_type': p.media_type,
                        'views': p.views,
                        'clicks': p.clicks
                    }
                    for p in posts
                ]
                
        except Exception as e:
            logger.error(f"Error getting posts with media: {e}")
            return []
    
    async def get_posts_without_media(self, limit: int = 50) -> List[Dict]:
        """Получить все посты без медиа (для напоминания добавить)"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(CatalogPost).where(
                        and_(
                            CatalogPost.is_active == True,
                            CatalogPost.media_type.is_(None)
                        )
                    ).limit(limit)
                )
                posts = result.scalars().all()
                
                return [
                    {
                        'id': p.id,
                        'user_id': p.user_id,
                        'category': p.category,
                        'name': p.name,
                        'catalog_link': p.catalog_link
                    }
                    for p in posts
                ]
                
        except Exception as e:
            logger.error(f"Error getting posts without media: {e}")
            return []
    
    async def get_catalog_stats(self) -> Dict:
        """Получить статистику каталога"""
        try:
            async with db.get_session() as session:
                # Общее количество постов
                total_result = await session.execute(
                    select(func.count(CatalogPost.id)).where(CatalogPost.is_active == True)
                )
                total_posts = total_result.scalar()
                
                # Посты с медиа
                media_result = await session.execute(
                    select(func.count(CatalogPost.id)).where(
                        and_(
                            CatalogPost.is_active == True,
                            CatalogPost.media_type.isnot(None)
                        )
                    )
                )
                posts_with_media = media_result.scalar()
                
                # Общие просмотры и клики
                views_result = await session.execute(
                    select(func.sum(CatalogPost.views)).where(CatalogPost.is_active == True)
                )
                total_views = views_result.scalar() or 0
                
                clicks_result = await session.execute(
                    select(func.sum(CatalogPost.clicks)).where(CatalogPost.is_active == True)
                )
                total_clicks = clicks_result.scalar() or 0
                
                # Активные сессии
                sessions_result = await session.execute(
                    select(func.count(CatalogSession.id)).where(CatalogSession.session_active == True)
                )
                active_sessions = sessions_result.scalar()
                
                return {
                    'total_posts': total_posts,
                    'posts_with_media': posts_with_media,
                    'posts_without_media': total_posts - posts_with_media,
                    'media_percentage': round((posts_with_media / total_posts * 100), 1) if total_posts > 0 else 0,
                    'total_views': total_views,
                    'total_clicks': total_clicks,
                    'ctr': round((total_clicks / total_views * 100), 2) if total_views > 0 else 0,
                    'active_sessions': active_sessions
                }
                
        except Exception as e:
            logger.error(f"Error getting catalog stats: {e}")
            return {
                'total_posts': 0,
                'posts_with_media': 0,
                'posts_without_media': 0,
                'media_percentage': 0,
                'total_views': 0,
                'total_clicks': 0,
                'ctr': 0,
                'active_sessions': 0
            }


# Глобальный экземпляр сервиса
catalog_service = CatalogService()

__all__ = ['catalog_service', 'CatalogService', 'CATALOG_CATEGORIES']
