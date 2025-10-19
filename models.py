from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Boolean, Text, JSON, Enum as SQLEnum, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum

Base = declarative_base()

# ✅ ИСПРАВЛЕНО: Правильное определение enum с заглавными буквами
class Gender(str, Enum):
    MALE = 'MALE'           # ← Было 'male', стало 'MALE'
    FEMALE = 'FEMALE'       # ← Было 'female', стало 'FEMALE'
    UNKNOWN = 'UNKNOWN'     # ← Было 'unknown', стало 'UNKNOWN'

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
   # ============= КАТАЛОГ УСЛУГ =============

class CatalogPost(Base):
    """Запись в каталоге услуг"""
    __tablename__ = 'catalog_posts'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False)
    catalog_link = Column(String(500), nullable=False)
    category = Column(String(100), nullable=False)
    name = Column(String(255))
    tags = Column(JSON, default=list)
    
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
    catalog_post_id = Column(Integer, ForeignKey('catalog_posts.id'))
    user_id = Column(BigInteger, nullable=False)
    username = Column(String(255))
    review_text = Column(Text)
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
    """Сессии просмотра каталога"""
    __tablename__ = 'catalog_sessions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False)
    viewed_posts = Column(JSON, default=list)
    last_activity = Column(DateTime, default=datetime.utcnow)
    session_active = Column(Boolean, default=True) 
