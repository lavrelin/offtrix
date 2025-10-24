# -*- coding: utf-8 -*-
"""
Сервис для работы с каталогом услуг - ИСПРАВЛЕННАЯ ВЕРСИЯ 3.1

Изменения v3.1:
- ✅ Добавлена генерация уникальных номеров постов (1-9999)
- ✅ Добавлен метод get_post_by_number()
- ✅ Добавлен метод change_catalog_number()
- ✅ Добавлен расчет рейтинга для постов (среднее из отзывов)
- ✅ Обновлены методы статистики для работы с catalog_number
- ✅ Добавлены методы get_unique_viewers() и get_unique_clickers()

Версия: 3.1.0
Дата: 24.10.2025
"""
import logging
import random
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_, func, text, desc
from services.db import db
from models import CatalogPost, CatalogReview, CatalogSubscription, CatalogSession

logger = logging.getLogger(__name__)

# ============= КАТЕГОРИИ КАТАЛОГА =============
CATALOG_CATEGORIES = {
    '💇‍♀️ Красота и уход': [
        'Барбер', 'БьютиПроцедуры', 'Волосы', 'Косметолог',
        'Депиляция', 'Эпиляция', 'Маникюр', 'Педикюр',
        'Ресницы и брови', 'Тату', 'Пирсинг'
    ],
    '🩺 Здоровье и тело': [
        'Ветеринар', 'Врач', 'Массажист', 'Психолог',
        'Стоматолог', 'Спорт', 'Йога', 'Фитнес', 'Диетолог'
    ],
    '🛠️ Услуги и помощь': [
        'Автомеханик', 'Грузчик', 'Клининг', 'Мастер по дому',
        'Перевозчик', 'Ремонт техники', 'Няня', 'Юрист',
        'Бухгалтер', 'IT-специалист'
    ],
    '📚 Обучение и развитие': [
        'Каналы по изучению венгерского', 'Каналы по изучению английского',
        'Курсы', 'Переводчик', 'Репетитор', 'Музыка', 'Риелтор',
        'Языковые школы', 'Онлайн-курсы'
    ],
    '🎭 Досуг и впечатления': [
        'Еда', 'Фотограф', 'Экскурсии', 'Для детей', 'Ремонт',
        'Швея', 'Цветы', 'Видеограф', 'Аниматоры', 'Организация праздников'
    ]
}


class CatalogService:
    """Сервис для работы с каталогом услуг - ВЕРСИЯ 3.1"""
    
    def __init__(self):
        self.max_posts_per_page = 5
        self.max_priority_posts = 10
        self.ad_frequency = 10
    
    # ============= НОВЫЙ МЕТОД: ГЕНЕРАЦИЯ УНИКАЛЬНОГО НОМЕРА =============
    
    async def _generate_unique_catalog_number(self, session) -> int:
        """Генерировать уникальный номер для нового поста (1-9999)"""
        max_attempts = 100
        for _ in range(max_attempts):
            number = random.randint(1, 9999)
            
            # Проверяем что номер свободен
            result = await session.execute(
                select(CatalogPost.id).where(CatalogPost.catalog_number == number)
            )
            
            if not result.scalar_one_or_none():
                return number
        
        raise Exception("Could not generate unique catalog number after 100 attempts")
    
    # ============= БАЗОВЫЕ МЕТОДЫ =============
    
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
        """Добавить пост в каталог с медиа и уникальным номером"""
        try:
            async with db.get_session() as session:
                # ✅ НОВОЕ: Генерируем уникальный номер
                catalog_number = await self._generate_unique_catalog_number(session)
                
                post = CatalogPost(
                    user_id=user_id,
                    catalog_link=catalog_link,
                    category=category,
                    name=name,
                    tags=tags,
                    catalog_number=catalog_number,  # ✅ НОВОЕ
                    is_active=True,
                    clicks=0,
                    views=0,
                    media_type=media_type,
                    media_file_id=media_file_id,
                    media_group_id=media_group_id,
                    media_json=media_json or media_files or []
                )
                
                session.add(post)
                await session.commit()
                await session.refresh(post)
                
                media_info = f"with media ({len(media_files or [])} files)" if media_files else "without media"
                logger.info(f"Added catalog post #{catalog_number} (ID: {post.id}) by user {user_id} {media_info}")
                return post.id
                
        except Exception as e:
            logger.error(f"Error adding catalog post: {e}")
            return None
    
    async def get_random_posts(self, user_id: int, count: int = 5) -> List[Dict]:
        """Получить случайные посты без повторов с рейтингом"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(CatalogSession).where(
                        and_(
                            CatalogSession.user_id == user_id,
                            CatalogSession.session_active == True
                        )
                    )
                )
                user_session = result.scalar_one_or_none()
                
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
                
                # ✅ НОВОЕ: Добавляем рейтинг для каждого поста
                result_posts = []
                for post in posts:
                    # Добавляем ID в просмотренные
                    viewed_ids.append(post.id)
                    
                    post_dict = self._post_to_dict(post)
                    
                    # Получаем рейтинг
                    reviews_result = await session.execute(
                        select(
                            func.avg(CatalogReview.rating).label('avg_rating'),
                            func.count(CatalogReview.id).label('review_count')
                        ).where(CatalogReview.catalog_post_id == post.id)
                    )
                    rating_data = reviews_result.first()
                    
                    post_dict['rating'] = round(rating_data.avg_rating, 1) if rating_data.avg_rating else 0
                    post_dict['review_count'] = rating_data.review_count or 0
                    
                    result_posts.append(post_dict)
                
                user_session.viewed_posts = viewed_ids
                user_session.last_activity = datetime.utcnow()
                await session.commit()
                
                return result_posts
                
        except Exception as e:
            logger.error(f"Error getting random posts: {e}")
            return []
    
    async def search_posts(self, query: str, limit: int = 10) -> List[Dict]:
        """Поиск постов по ключевым словам и тегам"""
        try:
            async with db.get_session() as session:
                keywords = query.lower().split()
                
                conditions = []
                for keyword in keywords:
                    conditions.append(func.lower(CatalogPost.name).contains(keyword))
                    conditions.append(CatalogPost.tags.contains([keyword]))
                
                query_obj = select(CatalogPost).where(
                    and_(
                        CatalogPost.is_active == True,
                        or_(*conditions) if conditions else True
                    )
                ).limit(limit)
                
                result = await session.execute(query_obj)
                posts = result.scalars().all()
                
                # Добавляем рейтинг
                result_posts = []
                for post in posts:
                    post_dict = self._post_to_dict(post)
                    
                    reviews_result = await session.execute(
                        select(
                            func.avg(CatalogReview.rating).label('avg_rating'),
                            func.count(CatalogReview.id).label('review_count')
                        ).where(CatalogReview.catalog_post_id == post.id)
                    )
                    rating_data = reviews_result.first()
                    
                    post_dict['rating'] = round(rating_data.avg_rating, 1) if rating_data.avg_rating else 0
                    post_dict['review_count'] = rating_data.review_count or 0
                    
                    result_posts.append(post_dict)
                
                return result_posts
                
        except Exception as e:
            logger.error(f"Error searching posts: {e}")
            return []
    
    async def get_post_by_id(self, post_id: int) -> Optional[Dict]:
        """Получить пост по ID с рейтингом"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(CatalogPost).where(CatalogPost.id == post_id)
                )
                post = result.scalar_one_or_none()
                
                if not post:
                    return None
                
                post_dict = self._post_to_dict(post)
                
                # Получаем рейтинг
                reviews_result = await session.execute(
                    select(
                        func.avg(CatalogReview.rating).label('avg_rating'),
                        func.count(CatalogReview.id).label('review_count')
                    ).where(CatalogReview.catalog_post_id == post.id)
                )
                rating_data = reviews_result.first()
                
                post_dict['rating'] = round(rating_data.avg_rating, 1) if rating_data.avg_rating else 0
                post_dict['review_count'] = rating_data.review_count or 0
                
                return post_dict
                
        except Exception as e:
            logger.error(f"Error getting post {post_id}: {e}")
            return None
    
    # ============= НОВЫЙ МЕТОД: ПОЛУЧЕНИЕ ПОСТА ПО НОМЕРУ =============
    
    async def get_post_by_number(self, catalog_number: int) -> Optional[Dict]:
        """Получить пост по уникальному номеру"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(CatalogPost).where(CatalogPost.catalog_number == catalog_number)
                )
                post = result.scalar_one_or_none()
                
                if not post:
                    return None
                
                post_dict = self._post_to_dict(post)
                
                # Получаем средний рейтинг и количество отзывов
                reviews_result = await session.execute(
                    select(
                        func.avg(CatalogReview.rating).label('avg_rating'),
                        func.count(CatalogReview.id).label('review_count')
                    ).where(CatalogReview.catalog_post_id == post.id)
                )
                rating_data = reviews_result.first()
                
                post_dict['rating'] = round(rating_data.avg_rating, 1) if rating_data.avg_rating else 0
                post_dict['review_count'] = rating_data.review_count or 0
                
                return post_dict
                
        except Exception as e:
            logger.error(f"Error getting post by number {catalog_number}: {e}")
            return None
    
    # ============= НОВЫЙ МЕТОД: ИЗМЕНЕНИЕ НОМЕРА ПОСТА =============
    
    async def change_catalog_number(self, old_number: int, new_number: int) -> bool:
        """Изменить номер поста"""
        try:
            async with db.get_session() as session:
                # Проверяем что новый номер свободен
                check_result = await session.execute(
                    select(CatalogPost.id).where(CatalogPost.catalog_number == new_number)
                )
                if check_result.scalar_one_or_none():
                    logger.warning(f"Catalog number {new_number} already taken")
                    return False
                
                # Находим пост со старым номером
                result = await session.execute(
                    select(CatalogPost).where(CatalogPost.catalog_number == old_number)
                )
                post = result.scalar_one_or_none()
                
                if not post:
                    logger.warning(f"Post with number {old_number} not found")
                    return False
                
                # Меняем номер
                post.catalog_number = new_number
                post.updated_at = datetime.utcnow()
                await session.commit()
                
                logger.info(f"Changed catalog number from {old_number} to {new_number} (post ID: {post.id})")
                return True
                
        except Exception as e:
            logger.error(f"Error changing catalog number: {e}")
            return False
    
    async def increment_views(self, post_id: int, user_id: Optional[int] = None):
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
    
    async def increment_clicks(self, post_id: int, user_id: Optional[int] = None):
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
    
    # ============= ОТЗЫВЫ =============
    
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
                post_result = await session.execute(
                    select(CatalogPost).where(CatalogPost.id == post_id)
                )
                post = post_result.scalar_one_or_none()
                
                if not post:
                    logger.warning(f"Post {post_id} not found for review")
                    return None
                
                review = CatalogReview(
                    catalog_post_id=post_id,
                    user_id=user_id,
                    username=username,
                    review_text=review_text[:500],
                    rating=max(1, min(5, rating))
                )
                
                session.add(review)
                await session.commit()
                await session.refresh(review)
                
                logger.info(f"Added review {review.id} for post {post_id} by user {user_id} (rating: {rating})")
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
    
    # ============= ПОДПИСКИ =============
    
    async def subscribe_to_category(self, user_id: int, category: str) -> bool:
        """Подписать пользователя на уведомления категории"""
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
                existing = result.scalar_one_or_none()
                
                if existing:
                    logger.info(f"User {user_id} already subscribed to {category}")
                    return False
                
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
        """Получить всех подписчиков категории"""
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
    
    async def get_user_subscriptions(self, user_id: int) -> List[Dict]:
        """Получить все подписки пользователя"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(CatalogSubscription).where(
                        CatalogSubscription.user_id == user_id
                    )
                )
                subscriptions = result.scalars().all()
                
                subs_data = []
                for sub in subscriptions:
                    subs_data.append({
                        'category': sub.subscription_value,
                        'subscribed_at': sub.created_at.isoformat() if sub.created_at else None
                    })
                
                return subs_data
                
        except Exception as e:
            logger.error(f"Error getting user subscriptions: {e}")
            return []
    
    async def unsubscribe_from_all(self, user_id: int) -> int:
        """Отписаться от всех категорий"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(CatalogSubscription).where(
                        CatalogSubscription.user_id == user_id
                    )
                )
                subscriptions = result.scalars().all()
                count = len(subscriptions)
                
                for sub in subscriptions:
                    await session.delete(sub)
                
                await session.commit()
                logger.info(f"User {user_id} unsubscribed from {count} categories")
                return count
                
        except Exception as e:
            logger.error(f"Error unsubscribing from all: {e}")
            return 0
    
    # ============= РЕДАКТИРОВАНИЕ =============
    
    async def update_post_field(self, post_id: int, field: str, value: any) -> bool:
        """Обновить конкретное поле поста"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(CatalogPost).where(CatalogPost.id == post_id)
                )
                post = result.scalar_one_or_none()
                
                if not post:
                    logger.warning(f"Post {post_id} not found for update")
                    return False
                
                # Если меняем catalog_number, проверяем уникальность
                if field == 'catalog_number':
                    check_result = await session.execute(
                        select(CatalogPost.id).where(CatalogPost.catalog_number == value)
                    )
                    if check_result.scalar_one_or_none():
                        logger.warning(f"Catalog number {value} already taken")
                        return False
                
                setattr(post, field, value)
                post.updated_at = datetime.utcnow()
                
                await session.commit()
                logger.info(f"Updated post {post_id} field '{field}'")
                return True
                
        except Exception as e:
            logger.error(f"Error updating post field: {e}")
            return False
    
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
        """Удалить пост (деактивировать)"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(CatalogPost).where(CatalogPost.id == post_id)
                )
                post = result.scalar_one_or_none()
                
                if not post:
                    logger.warning(f"Post {post_id} not found")
                    return False
                
                post.is_active = False
                post.updated_at = datetime.utcnow()
                await session.commit()
                
                logger.info(f"Deleted post {post_id} (catalog #{post.catalog_number}) by user {user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error deleting post: {e}")
            return False
    
    # ============= СТАТИСТИКА =============
    
    async def get_views_stats(self, limit: int = 20) -> List[tuple]:
        """Получить статистику просмотров - ТОП постов"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(
                        CatalogPost.id,
                        CatalogPost.views,
                        CatalogPost.name,
                        CatalogPost.catalog_number  # ✅ ДОБАВЛЕНО
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
    
    async def get_priority_stats(self) -> Dict:
        """Статистика по приоритетным постам"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(CatalogPost).where(
                        and_(
                            CatalogPost.is_priority == True,
                            CatalogPost.is_active == True
                        )
                    ).order_by(CatalogPost.views.desc())
                )
                priority_posts = result.scalars().all()
                
                priority_views = sum(p.views for p in priority_posts)
                priority_clicks = sum(p.clicks for p in priority_posts)
                priority_ctr = (priority_clicks / priority_views * 100) if priority_views > 0 else 0
                
                result = await session.execute(
                    select(CatalogPost).where(
                        and_(
                            CatalogPost.is_priority == False,
                            CatalogPost.is_active == True
                        )
                    )
                )
                normal_posts = result.scalars().all()
                normal_views = sum(p.views for p in normal_posts)
                normal_clicks = sum(p.clicks for p in normal_posts)
                normal_ctr = (normal_clicks / normal_views * 100) if normal_views > 0 else 0
                
                improvement = ((priority_ctr - normal_ctr) / normal_ctr * 100) if normal_ctr > 0 else 0
                
                return {
                    'posts': [
                        {
                            'id': p.id,
                            'catalog_number': p.catalog_number,  # ✅ ДОБАВЛЕНО
                            'name': p.name,
                            'views': p.views,
                            'clicks': p.clicks
                        }
                        for p in priority_posts
                    ],
                    'avg_ctr': priority_ctr,
                    'normal_ctr': normal_ctr,
                    'improvement': improvement
                }
                
        except Exception as e:
            logger.error(f"Error getting priority stats: {e}")
            return {'posts': [], 'avg_ctr': 0, 'normal_ctr': 0, 'improvement': 0}
    
    async def get_ad_stats(self) -> Dict:
        """Статистика по рекламным постам"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(CatalogPost).where(
                        and_(
                            CatalogPost.is_ad == True,
                            CatalogPost.is_active == True
                        )
                    )
                )
                ads = result.scalars().all()
                
                total_views = sum(ad.views for ad in ads)
                total_clicks = sum(ad.clicks for ad in ads)
                avg_ctr = (total_clicks / total_views * 100) if total_views > 0 else 0
                
                return {
                    'ads': [
                        {
                            'id': ad.id,
                            'catalog_number': ad.catalog_number,  # ✅ ДОБАВЛЕНО
                            'name': ad.name,
                            'views': ad.views,
                            'clicks': ad.clicks
                        }
                        for ad in ads
                    ],
                    'total_views': total_views,
                    'total_clicks': total_clicks,
                    'avg_ctr': avg_ctr
                }
                
        except Exception as e:
            logger.error(f"Error getting ad stats: {e}")
            return {'ads': [], 'total_views': 0, 'total_clicks': 0, 'avg_ctr': 0}
    
    async def get_catalog_stats(self) -> Dict:
        """Получить полную статистику каталога"""
        try:
            async with db.get_session() as session:
                total_result = await session.execute(
                    select(func.count(CatalogPost.id)).where(CatalogPost.is_active == True)
                )
                total_posts = total_result.scalar()
                
                media_result = await session.execute(
                    select(func.count(CatalogPost.id)).where(
                        and_(
                            CatalogPost.is_active == True,
                            CatalogPost.media_type.isnot(None)
                        )
                    )
                )
                posts_with_media = media_result.scalar()
                
                views_result = await session.execute(
                    select(func.sum(CatalogPost.views)).where(CatalogPost.is_active == True)
                )
                total_views = views_result.scalar() or 0
                
                clicks_result = await session.execute(
                    select(func.sum(CatalogPost.clicks)).where(CatalogPost.is_active == True)
                )
                total_clicks = clicks_result.scalar() or 0
                
                sessions_result = await session.execute(
                    select(func.count(CatalogSession.id)).where(CatalogSession.session_active == True)
                )
                active_sessions = sessions_result.scalar()
                
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
    
    # ============= НОВЫЕ МЕТОДЫ v3.1 =============
    
    async def get_unique_viewers(self) -> int:
        """Количество уникальных пользователей с просмотрами"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(func.count(func.distinct(CatalogSession.user_id))).where(
                        func.json_array_length(CatalogSession.viewed_posts) > 0
                    )
                )
                return result.scalar() or 0
        except Exception as e:
            logger.error(f"Error getting unique viewers: {e}")
            return 0
    
    async def get_unique_clickers(self) -> int:
        """Количество уникальных пользователей с переходами"""
        try:
            async with db.get_session() as session:
                # Считаем уникальных пользователей среди постов с кликами
                result = await session.execute(
                    select(func.count(func.distinct(CatalogPost.user_id))).where(
                        CatalogPost.clicks > 0
                    )
                )
                return result.scalar() or 0
        except Exception as e:
            logger.error(f"Error getting unique clickers: {e}")
            return 0
    
    async def get_top_posts_with_clicks(self, limit: int = 20) -> List[tuple]:
        """ТОП постов с просмотрами и переходами"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(
                        CatalogPost.id,
                        CatalogPost.views,
                        CatalogPost.clicks,
                        CatalogPost.name,
                        CatalogPost.catalog_number  # ✅ ДОБАВЛЕНО
                    ).where(CatalogPost.is_active == True)
                    .order_by(CatalogPost.views.desc())
                    .limit(limit)
                )
                
                stats = result.all()
                return stats
                
        except Exception as e:
            logger.error(f"Error getting top posts: {e}")
            return []
    
    # ============= ПРИОРИТЕТЫ И РЕКЛАМА =============
    
    async def set_priority_posts(self, links: List[str]) -> int:
        """Установить приоритетные посты по ссылкам"""
        try:
            count = 0
            async with db.get_session() as session:
                posts_to_reset = (await session.execute(
                    select(CatalogPost).where(CatalogPost.is_priority == True)
                )).scalars().all()
                
                for post in posts_to_reset:
                    post.is_priority = False
                
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
                # Генерируем уникальный номер
                catalog_number = await self._generate_unique_catalog_number(session)
                
                post = CatalogPost(
                    user_id=0,
                    catalog_link=catalog_link,
                    category='Реклама',
                    name=description,
                    tags=[],
                    catalog_number=catalog_number,  # ✅ ДОБАВЛЕНО
                    is_active=True,
                    is_ad=True,
                    ad_frequency=self.ad_frequency
                )
                
                session.add(post)
                await session.commit()
                await session.refresh(post)
                
                logger.info(f"Added ad post #{catalog_number} (ID: {post.id})")
                return post.id
                
        except Exception as e:
            logger.error(f"Error adding ad post: {e}")
            return None
    
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
                        'catalog_number': p.catalog_number,  # ✅ ДОБАВЛЕНО
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
    
    # ============= ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ =============
    
    def _post_to_dict(self, post: CatalogPost) -> Dict:
        """Конвертировать пост в словарь"""
        return {
            'id': post.id,
            'catalog_number': post.catalog_number,  # ✅ ДОБАВЛЕНО
            'catalog_link': post.catalog_link,
            'category': post.category,
            'name': post.name,
            'tags': post.tags or [],
            'views': post.views,
            'clicks': post.clicks,
            'media_type': post.media_type,
            'media_file_id': post.media_file_id,
            'media_group_id': post.media_group_id,
            'media_json': post.media_json or [],
            'created_at': post.created_at.isoformat() if post.created_at else None,
            'is_priority': post.is_priority,
            'is_ad': post.is_ad
        }


# ============= ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР =============

catalog_service = CatalogService()

__all__ = [
    'catalog_service',
    'CatalogService',
    'CATALOG_CATEGORIES'
]
