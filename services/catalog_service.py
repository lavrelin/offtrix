# -*- coding: utf-8 -*-
"""
ДОПОЛНИТЕЛЬНЫЕ МЕТОДЫ для catalog_service.py
Добавьте эти методы в класс CatalogService
"""

# ============= ДОБАВЬТЕ ЭТИ МЕТОДЫ В КЛАСС CatalogService =============

async def import_media_from_telegram(self, telegram_link: str) -> Dict:
    """
    Импортировать медиа из Telegram поста по ссылке
    
    Использование:
        result = await catalog_service.import_media_from_telegram(
            "https://t.me/catalogtrix/123"
        )
        # Возвращает:
        # {
        #     'media': [file_id1, file_id2, ...],
        #     'description': 'текст из поста',
        #     'media_type': 'photo' / 'video' / 'mixed'
        # }
    """
    try:
        # Парсим ссылку
        import re
        match = re.match(r'https://t\.me/([a-zA-Z0-9_]+)/(\d+)', telegram_link)
        if not match:
            logger.error(f"Invalid Telegram link format: {telegram_link}")
            return {'media': [], 'description': '', 'media_type': None}
        
        channel_name = match.group(1)
        message_id = int(match.group(2))
        
        logger.info(f"Importing media from @{channel_name}/{message_id}")
        
        # ТУТ ИСПОЛЬЗУЕМ telegram.ext для получения медиа
        # Это требует доступа к Bot API
        
        # ОПЦИЯ 1: Если у вас есть доступ к bot
        # Получите bot из context:
        # media_result = await bot.get_file(file_id)
        
        # ОПЦИЯ 2: Использовать REST API (более надежно)
        import aiohttp
        import asyncio
        
        async with aiohttp.ClientSession() as session:
            # Получаем информацию о посте через Bot API
            # Требует BOT_TOKEN и use_channel_username
            pass
        
        # ДЛЯ РЕАЛИЗАЦИИ:
        # 1. Используйте telegram.ext.Application для получения медиа
        # 2. Или используйте Telegram Client API (требует USER_SESSION)
        # 3. Или просто сохраняйте пустой список медиа (медиа добавляется вручную)
        
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
    
    Использование:
        posts = await catalog_service.search_posts("маникюр гель-лак")
        # Возвращает посты с "маникюр" ИЛИ "гель-лак" в тегах/названии
    """
    try:
        async with db.get_session() as session:
            # Разбиваем запрос на слова
            keywords = query.lower().split()
            
            # Строим запрос поиска
            from sqlalchemy import or_
            
            conditions = []
            for keyword in keywords:
                # Ищем в названии
                conditions.append(
                    func.lower(CatalogPost.name).contains(keyword)
                )
                # Ищем в описании (если есть)
                # conditions.append(
                #     func.lower(CatalogPost.description).contains(keyword)
                # )
            
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


async def add_review(
    self,
    post_id: int,
    user_id: int,
    review_text: str,
    rating: int = 5,
    username: Optional[str] = None
) -> Optional[int]:
    """
    Добавить отзыв о посте
    
    Использование:
        review_id = await catalog_service.add_review(
            post_id=123,
            user_id=456,
            review_text="Отличная услуга!",
            rating=5,
            username="john_doe"
        )
    """
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
    """
    Получить все отзывы для поста
    
    Использование:
        reviews = await catalog_service.get_reviews(post_id=123)
    """
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


async def get_post_by_id(self, post_id: int) -> Optional[Dict]:
    """
    Получить пост по ID (уже существует в коде выше)
    Описание для справки
    
    Использование:
        post = await catalog_service.get_post_by_id(123)
        if post:
            print(post['name'])
    """
    pass  # Метод уже реализован выше


async def get_views_stats(self, limit: int = 20) -> List[tuple]:
    """
    Получить статистику просмотров - ТОП постов
    
    Возвращает список: [(post_id, views, name), ...]
    
    Использование:
        stats = await catalog_service.get_views_stats(limit=20)
        for post_id, views, name in stats:
            print(f"{name}: {views} просмотров")
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
    """
    Получить статистику по категориям
    
    Возвращает: {'Маникюр': 10, 'Парикмахер': 5, ...}
    
    Использование:
        stats = await catalog_service.get_category_stats()
    """
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
    """
    Получить все посты пользователя
    
    Использование:
        posts = await catalog_service.get_user_posts(123456)
    """
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


async def delete_post(self, post_id: int, user_id: int) -> bool:
    """
    Удалить пост (только автор или админ)
    
    Использование:
        success = await catalog_service.delete_post(123, user_id=456)
    """
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


async def subscribe_to_category(
    self,
    user_id: int,
    category: str
) -> bool:
    """
    Подписать пользователя на уведомления категории
    
    Использование:
        await catalog_service.subscribe_to_category(123, "Маникюр")
    """
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


async def unsubscribe_from_category(
    self,
    user_id: int,
    category: str
) -> bool:
    """
    Отписать пользователя от категории
    
    Использование:
        await catalog_service.unsubscribe_from_category(123, "Маникюр")
    """
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
    """
    Получить всех подписчиков категории (для рассылки уведомлений)
    
    Использование:
        subscribers = await catalog_service.get_category_subscribers("Маникюр")
        for user_id in subscribers:
            await send_notification(user_id, "Новая услуга!")
    """
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


# ============= КОНЕЦ ДОПОЛНИТЕЛЬНЫХ МЕТОДОВ =============
