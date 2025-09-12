import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, DateTime, Boolean, 
    Text, JSON, ForeignKey, Enum as SQLEnum, Numeric
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

# --- Enums from original models.py ---

class Gender(enum.Enum):
    MALE = "male"
    FEMALE = "female"

class ActivityLevel(enum.Enum):
    SEDENTARY = "sedentary"  # Малоподвижный
    LIGHT = "light"          # Легкая активность
    MODERATE = "moderate"    # Умеренная активность
    ACTIVE = "active"        # Активный
    VERY_ACTIVE = "very_active"  # Очень активный

class Goal(enum.Enum):
    LOSE_WEIGHT = "lose_weight"
    MAINTAIN = "maintain"
    GAIN_MUSCLE = "gain_muscle"

class MealStyle(enum.Enum):
    VISUAL = "visual"  # На глаз
    PRECISE = "precise"  # Точные граммовки

# --- Enums from original payment_models.py ---

class SubscriptionPlan(enum.Enum):
    TRIAL = "trial"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    LIFETIME = "lifetime"

class PaymentStatus(enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"

class PaymentProvider(enum.Enum):
    TELEGRAM = "telegram"
    YOOKASSA = "yookassa"
    STRIPE = "stripe"
    CRYPTOBOT = "cryptobot"

class PromoType(enum.Enum):
    DISCOUNT_PERCENT = "discount_percent"
    DISCOUNT_FIXED = "discount_fixed"
    TRIAL_EXTENSION = "trial_extension"
    FREE_PERIOD = "free_period"

# --- Main User Model ---

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    
    gender = Column(SQLEnum(Gender), nullable=True)
    age = Column(Integer, nullable=True)
    height = Column(Float, nullable=True)
    current_weight = Column(Float, nullable=True)
    target_weight = Column(Float, nullable=True)
    goal = Column(SQLEnum(Goal), nullable=True)
    activity_level = Column(SQLEnum(ActivityLevel), nullable=True)
    
    meal_count = Column(Integer, default=3)
    meal_style = Column(SQLEnum(MealStyle), default=MealStyle.VISUAL)
    food_preferences = Column(JSON, default=dict)
    budget = Column(String(50), nullable=True)
    
    daily_calories = Column(Integer, nullable=True)
    daily_protein = Column(Float, nullable=True)
    daily_fats = Column(Float, nullable=True)
    daily_carbs = Column(Float, nullable=True)
    
    is_premium = Column(Boolean, default=False)
    trial_started_at = Column(DateTime, nullable=True)
    subscription_until = Column(DateTime, nullable=True)
    
    timezone = Column(String(50), default="UTC")
    reminder_settings = Column(JSON, default=dict)
    reminder_style = Column(String(20), default="friendly")
    
    connected_services = Column(JSON, default=list)
    fitness_tokens = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    onboarding_completed = Column(Boolean, default=False)
    
    # Relationships
    check_ins = relationship("CheckIn", back_populates="user", cascade="all, delete-orphan")
    meal_plans = relationship("MealPlan", back_populates="user", cascade="all, delete-orphan")
    user_patterns = relationship("UserPattern", back_populates="user", cascade="all, delete-orphan")
    
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")
    promo_codes_created = relationship("PromoCode", back_populates="created_by_user", foreign_keys="PromoCode.created_by_user_id")
    promo_code_uses = relationship("PromoCodeUse", back_populates="user", cascade="all, delete-orphan")

# --- Other Main Models ---

class CheckIn(Base):
    __tablename__ = "check_ins"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    date = Column(DateTime, default=datetime.utcnow)
    weight = Column(Float, nullable=True)
    sleep_hours = Column(Float, nullable=True)
    mood = Column(String(20), nullable=True)
    steps = Column(Integer, nullable=True)
    water_ml = Column(Integer, nullable=True)
    
    breakfast_photo = Column(String(255), nullable=True)
    lunch_photo = Column(String(255), nullable=True)
    dinner_photo = Column(String(255), nullable=True)
    snack_photo = Column(String(255), nullable=True)
    
    breakfast_analysis = Column(JSON, nullable=True)
    lunch_analysis = Column(JSON, nullable=True)
    dinner_analysis = Column(JSON, nullable=True)
    snack_analysis = Column(JSON, nullable=True)
    
    tracker_data = Column(JSON, nullable=True)
    calories_burned = Column(Integer, nullable=True)
    active_minutes = Column(Integer, nullable=True)
    heart_rate_avg = Column(Integer, nullable=True)
    distance_km = Column(Float, nullable=True)
    
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="check_ins")

class MealPlan(Base):
    __tablename__ = "meal_plans"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    week_number = Column(Integer, nullable=False)
    day_number = Column(Integer, nullable=False)
    
    breakfast = Column(JSON, nullable=True)
    lunch = Column(JSON, nullable=True)
    dinner = Column(JSON, nullable=True)
    snack = Column(JSON, nullable=True)
    
    total_calories = Column(Integer, nullable=True)
    total_protein = Column(Float, nullable=True)
    total_fats = Column(Float, nullable=True)
    total_carbs = Column(Float, nullable=True)
    
    adherence_score = Column(Float, nullable=True)
    actual_calories = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    user = relationship("User", back_populates="meal_plans")

class UserPattern(Base):
    __tablename__ = "user_patterns"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    avg_checkin_time_morning = Column(String(5), nullable=True)
    avg_checkin_time_evening = Column(String(5), nullable=True)
    most_active_hour = Column(Integer, nullable=True)
    avg_steps_weekday = Column(Integer, nullable=True)
    avg_steps_weekend = Column(Integer, nullable=True)
    avg_water_consumption = Column(Integer, nullable=True)
    avg_sleep_duration = Column(Float, nullable=True)
    typical_breakfast_calories = Column(Integer, nullable=True)
    typical_lunch_calories = Column(Integer, nullable=True)
    typical_dinner_calories = Column(Integer, nullable=True)
    most_common_foods = Column(JSON, nullable=True)
    reminder_response_rate = Column(Float, nullable=True)
    best_reminder_time = Column(String(5), nullable=True)
    preferred_reminder_frequency = Column(String(20), nullable=True)
    weight_trend = Column(String(20), nullable=True)
    consistency_score = Column(Float, nullable=True)
    streak_days = Column(Integer, default=0)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="user_patterns")

# --- Payment Models ---

class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan = Column(SQLEnum(SubscriptionPlan), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    auto_renew = Column(Boolean, default=True)
    price = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="RUB")
    promo_code_id = Column(Integer, ForeignKey("promo_codes.id"), nullable=True)
    discount_amount = Column(Numeric(10, 2), default=0)
    features = Column(JSON, nullable=True)
    subscription_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="subscriptions")
    payments = relationship("Payment", back_populates="subscription")
    promo_code = relationship("PromoCode", back_populates="subscriptions")

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    provider = Column(SQLEnum(PaymentProvider), nullable=False)
    provider_payment_id = Column(String(255), nullable=True)
    invoice_payload = Column(String(255), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="RUB")
    status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING)
    description = Column(Text, nullable=True)
    provider_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)
    refunded_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="payments")
    subscription = relationship("Subscription", back_populates="payments")

class PromoCode(Base):
    __tablename__ = "promo_codes"
    
    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    promo_type = Column(SQLEnum(PromoType), nullable=False)
    value = Column(Numeric(10, 2), nullable=False)
    max_uses = Column(Integer, nullable=True)
    uses_count = Column(Integer, default=0)
    max_uses_per_user = Column(Integer, default=1)
    applicable_plans = Column(JSON, nullable=True)
    min_amount = Column(Numeric(10, 2), nullable=True)
    valid_from = Column(DateTime, default=datetime.utcnow)
    valid_until = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    commission_percent = Column(Numeric(5, 2), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    subscriptions = relationship("Subscription", back_populates="promo_code")
    uses = relationship("PromoCodeUse", back_populates="promo_code")
    created_by_user = relationship("User", back_populates="promo_codes_created")

class PromoCodeUse(Base):
    __tablename__ = "promo_code_uses"
    
    id = Column(Integer, primary_key=True)
    promo_code_id = Column(Integer, ForeignKey("promo_codes.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    used_at = Column(DateTime, default=datetime.utcnow)
    discount_applied = Column(Numeric(10, 2), nullable=True)
    
    promo_code = relationship("PromoCode", back_populates="uses")
    user = relationship("User", back_populates="promo_code_uses")
    payment = relationship("Payment")

class PricingPlan(Base):
    __tablename__ = "pricing_plans"
    
    id = Column(Integer, primary_key=True)
    plan = Column(SQLEnum(SubscriptionPlan), nullable=False)
    currency = Column(String(3), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    original_price = Column(Numeric(10, 2), nullable=True)
    features = Column(JSON, nullable=False)
    duration_days = Column(Integer, nullable=False)
    trial_days = Column(Integer, default=0)
    is_popular = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)