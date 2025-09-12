import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, 
    Text, JSON, ForeignKey, Enum as SQLEnum, Numeric
)
from sqlalchemy.orm import relationship
from database.models import Base

class SubscriptionPlan(enum.Enum):
    TRIAL = "trial"          # 7 дней бесплатно
    MONTHLY = "monthly"      # Месячная подписка
    QUARTERLY = "quarterly"  # 3 месяца
    YEARLY = "yearly"        # Годовая подписка
    LIFETIME = "lifetime"    # Пожизненная

class PaymentStatus(enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"

class PaymentProvider(enum.Enum):
    TELEGRAM = "telegram"    # Telegram Payments
    YOOKASSA = "yookassa"    # ЮKassa (для России)
    STRIPE = "stripe"        # Stripe (международные платежи)
    CRYPTOBOT = "cryptobot"  # Крипто платежи

class PromoType(enum.Enum):
    DISCOUNT_PERCENT = "discount_percent"  # Скидка в процентах
    DISCOUNT_FIXED = "discount_fixed"      # Фиксированная скидка
    TRIAL_EXTENSION = "trial_extension"    # Продление триала
    FREE_PERIOD = "free_period"            # Бесплатный период

# Таблица подписок
class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    plan = Column(SQLEnum(SubscriptionPlan), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    auto_renew = Column(Boolean, default=True)
    
    # Цена на момент покупки
    price = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="RUB")
    
    # Если использовался промокод
    promo_code_id = Column(Integer, ForeignKey("promo_codes.id"), nullable=True)
    discount_amount = Column(Numeric(10, 2), default=0)
    
    # Дополнительная информация
    features = Column(JSON, nullable=True)  # Доступные функции
    metadata = Column(JSON, nullable=True)  # Дополнительные данные
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    user = relationship("User", back_populates="subscriptions")
    payments = relationship("Payment", back_populates="subscription")
    promo_code = relationship("PromoCode", back_populates="subscriptions")

# Таблица платежей
class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    
    # Информация о платеже
    provider = Column(SQLEnum(PaymentProvider), nullable=False)
    provider_payment_id = Column(String(255), nullable=True)  # ID платежа в системе провайдера
    invoice_payload = Column(String(255), nullable=True)  # Payload для Telegram
    
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="RUB")
    status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING)
    
    # Детали платежа
    description = Column(Text, nullable=True)
    provider_data = Column(JSON, nullable=True)  # Данные от провайдера
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)
    refunded_at = Column(DateTime, nullable=True)
    
    # Связи
    user = relationship("User", back_populates="payments")
    subscription = relationship("Subscription", back_populates="payments")

# Таблица промокодов
class PromoCode(Base):
    __tablename__ = "promo_codes"
    
    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    
    # Тип и значение промокода
    promo_type = Column(SQLEnum(PromoType), nullable=False)
    value = Column(Numeric(10, 2), nullable=False)  # Процент, сумма или дни
    
    # Ограничения
    max_uses = Column(Integer, nullable=True)  # Максимальное количество использований
    uses_count = Column(Integer, default=0)  # Сколько раз использован
    max_uses_per_user = Column(Integer, default=1)  # Максимум на пользователя
    
    # Применимость
    applicable_plans = Column(JSON, nullable=True)  # ["monthly", "yearly"] или null для всех
    min_amount = Column(Numeric(10, 2), nullable=True)  # Минимальная сумма заказа
    
    # Период действия
    valid_from = Column(DateTime, default=datetime.utcnow)
    valid_until = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Создатель промокода (для партнерской программы)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    commission_percent = Column(Numeric(5, 2), nullable=True)  # Процент партнеру
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    subscriptions = relationship("Subscription", back_populates="promo_code")
    uses = relationship("PromoCodeUse", back_populates="promo_code")

# Таблица использования промокодов
class PromoCodeUse(Base):
    __tablename__ = "promo_code_uses"
    
    id = Column(Integer, primary_key=True)
    promo_code_id = Column(Integer, ForeignKey("promo_codes.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    
    used_at = Column(DateTime, default=datetime.utcnow)
    discount_applied = Column(Numeric(10, 2), nullable=True)
    
    # Связи
    promo_code = relationship("PromoCode", back_populates="uses")
    user = relationship("User")
    payment = relationship("Payment")

# Таблица цен (для разных регионов/валют)
class PricingPlan(Base):
    __tablename__ = "pricing_plans"
    
    id = Column(Integer, primary_key=True)
    plan = Column(SQLEnum(SubscriptionPlan), nullable=False)
    currency = Column(String(3), nullable=False)
    
    price = Column(Numeric(10, 2), nullable=False)
    original_price = Column(Numeric(10, 2), nullable=True)  # Для отображения скидки
    
    # Что включено в план
    features = Column(JSON, nullable=False)
    # {
    #   "meal_plans": true,
    #   "ai_coach": true,
    #   "integrations": true,
    #   "priority_support": false,
    #   "custom_programs": false
    # }
    
    duration_days = Column(Integer, nullable=False)  # Длительность в днях
    trial_days = Column(Integer, default=0)  # Дни триала
    
    is_popular = Column(Boolean, default=False)  # Отметка "Популярный"
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)