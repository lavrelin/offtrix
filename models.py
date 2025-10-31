from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Boolean, Text, JSON, Enum as SQLEnum, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum

Base = declarative_base()

# ✅ ИСПРАВЛЕНО: Правильное определение enum с заглавными буквами
class Gender(str, Enum):
    MALE = 'MALE'
    FEMALE = 'FEMALE'
    UNKNOWN = 'UNKNOWN'

class PostStatus(str, Enum):
    PENDING = 'PENDING'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'

class User(Base):
    __tablename__ = 'users'
    
    id = Column(BigInteger, primary_key=True)
    username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255))
    gender = Column(SQLEnum(Gender), default=Gender.UNKNOWN)
    referral_code = Column(String(255), unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Post(Base):
    __tablename__ = 'posts'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False)
    category = Column(String(255))
    subcategory = Column(String(255))
    text = Column(Text)
    media = Column(JSON, default=list)
    hashtags = Column(JSON, default=list)
    media_type = Column(String(50), nullable=True)
    media_file_id = Column(String(500), nullable=True)
    media_group_id = Column(String(255), nullable=True)
    media_json = Column(JSON, default=list, nullable=True)
    anonymous = Column(Boolean, default=False)
    status = Column(SQLEnum(PostStatus), default=PostStatus.PENDING)
    moderation_message_id = Column(BigInteger)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Piar specific fields
    is_piar = Column(Boolean, default=False)
    piar_name = Column(String(255), nullable=True)
    piar_profession = Column(String(255), nullable=True)
    piar_districts = Column(JSON, default=list, nullable=True)
    piar_phone = Column(String(255), nullable=True)
    piar_instagram = Column(String(255), nullable=True)
    piar_telegram = Column(String(255), nullable=True)
    piar_price = Column(String(255), nullable=True)
    piar_description = Column(Text, nullable=True)


# ============= РЕЙТИНГ ЛЮДЕЙ (TOPPEOPLE) =============

class RatingPost(Base):
    """Анкета для рейтинга людей"""
    __tablename__ = 'rating_posts'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False)
    
    # Основные данные
    gender = Column(String(10), nullable=False)  # 'boy' или 'girl'
    age = Column(Integer, nullable=False)
    name = Column(String(100), nullable=False)
    about = Column(String(500), nullable=True)
    profile_url = Column(String(500), nullable=True)
    photo_file_id = Column(String(500), nullable=False)
    
    # Статистика голосов
    total_score = Column(Integer, default=0)
    vote_count = Column(Integer, default=0)
    vote_counts = Column(JSON, default=dict)  # {-2: 0, -1: 0, 0: 0, 1: 0, 2: 0}
    user_votes = Column(JSON, default=dict)  # {user_id: vote_value}
    
    # Статус и модерация
    status = Column(String(20), default='pending')  # pending, approved, rejected
    moderation_message_id = Column(BigInteger, nullable=True)
    channel_message_id = Column(BigInteger, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============= КАТАЛОГ УСЛУГ - ВЕРСИЯ 4.0 =============

class CatalogPost(Base):
    """Запись в каталоге услуг"""
    __tablename__ = 'catalog_posts'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False)
    catalog_link = Column(String(500), nullable=False)
    category = Column(String(100), nullable=False)
    name = Column(String(255))
    tags = Column(JSON, default=list)
    
    # ============= УНИКАЛЬНЫЙ НОМЕР ПОСТА =============
    catalog_number = Column(Integer, unique=True, nullable=True)
    
    # ============= СТАТУС =============
    status = Column(String(20), default='approved')  # pending, approved, rejected
    
    # ============= ПОЛЯ ДЛЯ АВТОРА - НОВОЕ В v4.0 =============
    author_username = Column(String(255), nullable=True)  # @username автора услуги
    author_id = Column(BigInteger, nullable=True)  # Telegram ID автора (если доступен)
    
    # ============= ПОЛЯ ДЛЯ МЕДИА =============
    media_type = Column(String(50), nullable=True)
    media_file_id = Column(String(500), nullable=True)
    media_group_id = Column(String(255), nullable=True)
    media_json = Column(JSON, default=list, nullable=True)
    
    # ============= СЧЁТЧИКИ =============
    review_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    clicks = Column(Integer, default=0)
    views = Column(Integer, default=0)
    
    is_priority = Column(Boolean, default=False)
    is_ad = Column(Boolean, default=False)
    ad_frequency = Column(Integer, default=10)


class CatalogReview(Base):
    """Отзывы о специалистах"""
    __tablename__ = 'catalog_reviews'
    
    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey('catalog_posts.id'))  # ИСПРАВЛЕНО: было catalog_post_id
    user_id = Column(BigInteger, nullable=False)
    username = Column(String(255))
    text = Column(Text)  # ИСПРАВЛЕНО: было review_text
    rating = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class CatalogSubscription(Base):
    """Подписки на уведомления"""
    __tablename__ = 'catalog_subscriptions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False)
    subscription_type = Column(String(50))
    subscription_value = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)


class CatalogSession(Base):
    __tablename__ = 'catalog_sessions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False, unique=True)
    viewed_posts = Column(JSON, default=[])
    favorites = Column(JSON, default=[])
    last_activity = Column(DateTime, default=datetime.utcnow)
    session_active = Column(Boolean, default=True)
