# -*- coding: utf-8 -*-
"""
Сервис для работы с каталогом услуг - С ПОЛНОЙ ПОДДЕРЖКОЙ МЕДИА И НОВЫХ ФУНКЦИЙ
Версия 2.0.0 с поддержкой:
- Импорта медиа из Telegram
- Поиска по ключевым словам
- Сохранения отзывов в БД
- Статистики просмотров
"""
import logging
import random
import re
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy import select, and_, or_, func, text
from services.db import db
from models import CatalogPost, CatalogReview, CatalogSubscription, CatalogSession

logger = logging.getLogger(__name__)

# ============= КАТЕГОРИИ КАТАЛОГА =============
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
    """Сервис для работы с каталогом услуг - ПОЛНАЯ ВЕРСИЯ"""
    
    def __init__(self):
        self.max_posts_per_page = 5
        self.max_priority_posts = 10
        self.ad_frequency = 10
    
    # ============= ОСНОВНЫЕ МЕТОДЫ =============
    
    async def add_post(
        self,
        user_id: int,
        catalog_link: str,
        category: str,
        name: str,
        tags: List[str],
        media_files: Optional[List[str]] = None,
        telegram_description: Optional[str] = None,
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
                    media_json=media_json or media_files or []
                )
                
                session.add(post)
                await session.commit()
                await session.refresh(post)
                
                media_info = f"with media ({len(media_files or [])} files)" if media_files else "without media"
                logger.info(f"Added catalog post {post.id} by user {user_id} {media_info}")
                return post.id
                
        except Exception as e:
            logger.error(f"Error adding catalog post: {e}")
            return None
    
    async def get_random_posts(self, user_id: int, count: int = 5) -> List[Dict]:
        """Получить случайные посты без повторов с медиа"""
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
                
                # Конвертируем в dict с медиа
                return [
                    {
                        'id': p.id,
                        'catalog_link': p.catalog_link,
                        'category': p.category,
                        'name': p.name,
                        'tags': p.tags or [],
                        'views': p.views,
                        'clicks': p.clicks,
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
    
    # ============= НОВЫЕ МЕТОДЫ - ПОИСК И ИМПОРТ =============
    
    async def import_media_from_telegram(self, telegram_link: str) -> Dict:
        """
        Импортировать медиа из Telegram поста по ссылке
        
        Возвращает:
        {
            'media': [file_id1, file_id2, ...],
            'description': 'текст из поста',
            'media_type': 'photo' / 'video' / 'mixed'
        }
        """
        try:
            # Парсим ссылку
            match = re.match(r'https://t\.me/([a-zA-Z0-9_]+)/(\d+)', telegram_link)
            if not match:
                logger.error(f"Invalid Telegram link format: {telegram_link}")
                return {'media': [], 'description': '', 'media_type': None}
            
            channel_name = match.group(1)
            message_id = int(match.group(2))
            
            logger.info(f"Importing media from @{channel_name}/{message_id}")
            
            # ВНИМАНИЕ: Для реального импорта нужно использовать:
            # 1. telegram.ext.Application для получения медиа
            # 2. Или Telegram Client API
            # 3. Или просто пустой результат для ручного добавления
            
            # Сейчас возвращаем заглушку - медиа добавляется вручную
            return {
                'media': [],  # Список file_id медиа файлов
                'description': '',  # Текст из поста
                'media_type': None  # 'photo', 'video', 'mixed'
            }
            
        except Exception as e:
            logger.error(f"Error importing media from Telegram: {e}")
            return {'media': [], 'description': '', 'media_type': None}
    
    async def search_posts(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Поиск постов по ключевым словам и тегам
        
        Ищет в названиях и тегах постов
        Использование: search_posts("маникюр гель-лак")
        """
        try:
            async with db.get_session() as session:
                # Разбиваем запрос на слова
                keywords = query.lower().split()
                
                conditions = []
                for keyword in keywords:
                    # Ищем в названии
                    conditions.append(
                        func.lower(CatalogPost.name).contains(keyword)
                    )
                
                # Ищем в тегах
                for keyword in keywords:
                    conditions.append(
                        CatalogPost.tags.contains([keyword])
                    )
                
                query_obj = select(CatalogPost).where(
                    and_(
                        CatalogPost.is_active == True,
                        or_(*conditions) if conditions else True
                    )
                ).limit(limit)
                
                result = await session.execute(query_obj)
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
    
    # ============= МЕТОДЫ ОТЗЫВОВ =============
    
    async def add_review(
        self,
        post_id: int,
        user_id: int,
        review_text: str,
        rating: int = 5,
        username: Optional[str] = None
    ) -> Optional[int]:
        """Добавить отзыв о посте"""
        try:
            async with db.get_session() as session:
                # Проверяем существует ли пост
                post_result = await session.execute(
                    select(CatalogPost).where(CatalogPost.id == post_id)
                )
                post = post_result.scalar_one_or_none()
                
                if not post:
                    logger.warning(f"Post {post_id} not found for review")
                    return None
                
                # Создаём отзыв
                review = CatalogReview(
                    catalog_post_id=post_id,
                    user_id=user_id,
                    username=username,
                    review_text=review_text[:500],  # Макс 500 символов
                    rating=max(1, min(5, rating))  # 1-5
                )
                
                session.add(review)
                await session.commit()
                await session.refresh(review)
                
                logger.info(f"Added review {review.id} for post {post_id} by user {user_id}")
                return review.id
                
        except Exception as e:
            logger.error(f"Error adding review: {e}")
            return None
    
    async def get_reviews(self, post_id: int, limit: int = 10) -> List[Dict]:
        """Получить все отзывы для поста"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(CatalogReview)
                    .where(CatalogReview.catalog_post_id == post_id)
                    .order_by(CatalogReview.created_at.desc())
                    .limit(limit)
                )
                reviews = result.scalars().all()
                
                return [
                    {
                        'id': r.id,
                        'user_id': r.user_id,
                        'username': r.username,
                        'review_text': r.review_text,
                        'rating': r.rating,
                        'created_at': r.created_at.isoformat() if r.created_at else None
                    }
                    for r in reviews
                ]
                
        except Exception as e:
            logger.error(f"Error getting reviews: {e}")
            return []
    
    # ============= МЕТОДЫ ПОЛУЧЕНИЯ ДАННЫХ =============
    
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
    
    async def get_views_stats(self, limit: int = 20) -> List[tuple]:
        """
        Получить статистику просмотров - ТОП постов
        Возвращает список: [(post_id, views, name), ...]
        """
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(
                        CatalogPost.id,
                        CatalogPost.views,
                        CatalogPost.name
                    ).where(CatalogPost.is_active == True)
                    .order_by(CatalogPost.views.desc())
                    .limit(limit)
                )
                
                stats = result.all()
                logger.info(f"Retrieved views stats for {len(stats)} posts")
                return stats
                
        except Exception as e:
            logger.error(f"Error getting views stats: {e}")
            return []
    
    async def get_category_stats(self) -> Dict[str, int]:
        """Получить статистику по категориям"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(
                        CatalogPost.category,
                        func.count(CatalogPost.id).label('count')
                    ).where(CatalogPost.is_active == True)
                    .group_by(CatalogPost.category)
                    .order_by(func.count(CatalogPost.id).desc())
                )
                
                stats = {}
                for category, count in result.all():
                    stats[category] = count
                
                logger.info(f"Category stats: {stats}")
                return stats
                
        except Exception as e:
            logger.error(f"Error getting category stats: {e}")
            return {}
    
    async def get_user_posts(self, user_id: int) -> List[Dict]:
        """Получить все посты пользователя"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(CatalogPost)
                    .where(CatalogPost.user_id == user_id)
                    .order_by(CatalogPost.created_at.desc())
                )
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
                        'is_active': p.is_active,
                        'created_at': p.created_at.isoformat() if p.created_at else None
                    }
                    for p in posts
                ]
                
        except Exception as e:
            logger.error(f"Error getting user posts: {e}")
            return []
    
    # ============= МЕТОДЫ РЕДАКТИРОВАНИЯ =============
    
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
    
    async def delete_post(self, post_id: int, user_id: int) -> bool:
        """Удалить пост (только автор или админ)"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(CatalogPost).where(CatalogPost.id == post_id)
                )
                post = result.scalar_one_or_none()
                
                if not post:
                    logger.warning(f"Post {post_id} not found")
                    return False
                
                # Проверяем авторство
                if post.user_id != user_id:
                    logger.warning(f"User {user_id} not authorized to delete post {post_id}")
                    return False
                
                post.is_active = False
                await session.commit()
                
                logger.info(f"Deleted post {post_id} by user {user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error deleting post: {e}")
            return False
    
    # ============= МЕТОДЫ СТАТИСТИКИ =============
    
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
    
    # ============= МЕТОДЫ СЕССИЙ =============
    
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
    
    # ============= МЕТОДЫ ПРИОРИТЕТА И РЕКЛАМЫ =============
    
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
    
    # ============= МЕТОДЫ ПОДПИСОК =============
    
    async def subscribe_to_category(self, user_id: int, category: str) -> bool:
        """Подписать пользователя на уведомления категории"""
        try:
            async with db.get_session() as session:
                # Проверяем не подписан ли уже
                result = await session.execute(
                    select(CatalogSubscription).where(
                        and_(
                            CatalogSubscription.user_id == user_id,
                            CatalogSubscription.subscription_value == category
                        )
                    )
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    logger.info(f"User {user_id} already subscribed to {category}")
                    return True
                
                # Добавляем подписку
                subscription = CatalogSubscription(
                    user_id=user_id,
                    subscription_type='category',
                    subscription_value=category
                )
                
                session.add(subscription)
                await session.commit()
                
                logger.info(f"User {user_id} subscribed to {category}")
                return True
                
        except Exception as e:
            logger.error(f"Error subscribing to category: {e}")
            return False
    
    async def unsubscribe_from_category(self, user_id: int, category: str) -> bool:
        """Отписать пользователя от категории"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(CatalogSubscription).where(
                        and_(
                            CatalogSubscription.user_id == user_id,
                            CatalogSubscription.subscription_value == category
                        )
                    )
                )
                subscription = result.scalar_one_or_none()
                
                if subscription:
                    await session.delete(subscription)
                    await session.commit()
                    logger.info(f"User {user_id} unsubscribed from {category}")
                    return True
                
                return False
                
        except Exception as e:
            logger.error(f"Error unsubscribing from category: {e}")
            return False
    
    async def get_category_subscribers(self, category: str) -> List[int]:
        """Получить всех подписчиков категории для рассылки уведомлений"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(CatalogSubscription.user_id).where(
                        and_(
                            CatalogSubscription.subscription_type == 'category',
                            CatalogSubscription.subscription_value == category
                        )
                    )
                )
                
                user_ids = [row[0] for row in result.all()]
                logger.info(f"Found {len(user_ids)} subscribers for category {category}")
                return user_ids
                
        except Exception as e:
            logger.error(f"Error getting category subscribers: {e}")
            return []
    
    # ============= МЕТОДЫ АНАЛИТИКИ =============
    
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
        """Получить полную статистику каталога"""
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
                
                # Количество отзывов
                reviews_result = await session.execute(
                    select(func.count(CatalogReview.id))
                )
                total_reviews = reviews_result.scalar() or 0
                
                return {
                    'total_posts': total_posts,
                    'posts_with_media': posts_with_media,
                    'posts_without_media': total_posts - posts_with_media,
                    'media_percentage': round((posts_with_media / total_posts * 100), 1) if total_posts > 0 else 0,
                    'total_views': total_views,
                    'total_clicks': total_clicks,
                    'ctr': round((total_clicks / total_views * 100), 2) if total_views > 0 else 0,
                    'active_sessions': active_sessions,
                    'total_reviews': total_reviews
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
                'active_sessions': 0,
                'total_reviews': 0
            }


# ============= ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР =============

catalog_service = CatalogService()

__all__ = [
    'catalog_service',
    'CatalogService',
    'CATALOG_CATEGORIES'
]
