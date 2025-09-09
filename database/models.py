import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, 
    Text, JSON, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

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

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    
    # Онбординг данные
    gender = Column(SQLEnum(Gender), nullable=True)
    age = Column(Integer, nullable=True)
    height = Column(Float, nullable=True)  # в см
    current_weight = Column(Float, nullable=True)  # в кг
    target_weight = Column(Float, nullable=True)  # в кг
    goal = Column(SQLEnum(Goal), nullable=True)
    activity_level = Column(SQLEnum(ActivityLevel), nullable=True)
    
    # Предпочтения питания
    meal_count = Column(Integer, default=3)  # 3 или 4 приема пищи
    meal_style = Column(SQLEnum(MealStyle), default=MealStyle.VISUAL)
    food_preferences = Column(JSON, default=dict)  # {cuisines: [], exclude: [], allergies: []}
    budget = Column(String(50), nullable=True)  # low/medium/high
    
    # Расчетные данные
    daily_calories = Column(Integer, nullable=True)
    daily_protein = Column(Float, nullable=True)  # в граммах
    daily_fats = Column(Float, nullable=True)
    daily_carbs = Column(Float, nullable=True)
    
    # Подписка
    is_premium = Column(Boolean, default=False)
    trial_started_at = Column(DateTime, nullable=True)
    subscription_until = Column(DateTime, nullable=True)
    
    # Системные поля
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    onboarding_completed = Column(Boolean, default=False)
    
    # Связи
    check_ins = relationship("CheckIn", back_populates="user", cascade="all, delete-orphan")
    meal_plans = relationship("MealPlan", back_populates="user", cascade="all, delete-orphan")

class CheckIn(Base):
    __tablename__ = "check_ins"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    date = Column(DateTime, default=datetime.utcnow)
    weight = Column(Float, nullable=True)  # Утренний вес
    sleep_hours = Column(Float, nullable=True)
    mood = Column(String(20), nullable=True)  # good/normal/bad
    steps = Column(Integer, nullable=True)
    water_ml = Column(Integer, nullable=True)
    
    # Фото еды (путь к файлу)
    breakfast_photo = Column(String(255), nullable=True)
    lunch_photo = Column(String(255), nullable=True)
    dinner_photo = Column(String(255), nullable=True)
    snack_photo = Column(String(255), nullable=True)
    
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="check_ins")

class MealPlan(Base):
    __tablename__ = "meal_plans"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    week_number = Column(Integer, nullable=False)  # Номер недели программы
    day_number = Column(Integer, nullable=False)  # День недели (1-7)
    
    breakfast = Column(JSON, nullable=True)  # {name, ingredients, calories, protein, fats, carbs}
    lunch = Column(JSON, nullable=True)
    dinner = Column(JSON, nullable=True)
    snack = Column(JSON, nullable=True)
    
    total_calories = Column(Integer, nullable=True)
    total_protein = Column(Float, nullable=True)
    total_fats = Column(Float, nullable=True)
    total_carbs = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    user = relationship("User", back_populates="meal_plans")