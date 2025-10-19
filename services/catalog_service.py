# -*- coding: utf-8 -*-
"""
Модели для каталога услуг
Добавить в models.py или использовать отдельно
"""
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Boolean, Text, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class CatalogPost(Base):
    """Запись в каталоге услуг"""
    __tablename__ = 'catalog_posts'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False)  # Кто добавил
    catalog_link = Column(String(500), nullable=False)  # Ссылка на пост в канале
    category = Column(String(100), nullable=False)  # Категория
    name = Column(String(255))  # Имя/описание
    tags = Column(JSON, default=list)  # Теги (до 10)
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    clicks = Column(Integer, default=0)  # Количество кликов
    views = Column(Integer, default=0)  # Количество просмотров
    
    # Приоритет и реклама
    is_priority = Column(Boolean, default=False)  # Приоритетный пост
    is_ad = Column(Boolean, default=False)  # Рекламный пост
    ad_frequency = Column(Integer, default=10)  # Показывать каждые N постов


class CatalogReview(Base):
    """Отзывы о специалистах"""
    __tablename__ = 'catalog_reviews'
    
    id = Column(Integer, primary_key=True)
    catalog_post_id = Column(Integer, ForeignKey('catalog_posts.id'))
    user_id = Column(BigInteger, nullable=False)
    username = Column(String(255))
    review_text = Column(Text)  # Короткий отзыв
    rating = Column(Integer)  # 1-5 звезд (опционально)
    created_at = Column(DateTime, default=datetime.utcnow)


class CatalogSubscription(Base):
    """Подписки на уведомления"""
    __tablename__ = 'catalog_subscriptions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False)
    subscription_type = Column(String(50))  # 'category' или 'tag'
    subscription_value = Column(String(255))  # Название категории или тега
    created_at = Column(DateTime, default=datetime.utcnow)


class CatalogSession(Base):
    """Сессии просмотра каталога"""
    __tablename__ = 'catalog_sessions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False)
    viewed_posts = Column(JSON, default=list)  # ID просмотренных постов
    last_activity = Column(DateTime, default=datetime.utcnow)
    session_active = Column(Boolean, default=True)
