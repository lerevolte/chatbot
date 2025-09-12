# ИСПРАВЛЕНО: Импортируем все модели из обоих файлов, чтобы SQLAlchemy мог их обнаружить
from .models import User, CheckIn, MealPlan, Gender, Goal, ActivityLevel, MealStyle, UserPattern, Subscription, Payment, PromoCode, PromoCodeUse, PricingPlan, SubscriptionPlan, PaymentStatus, PaymentProvider, PromoType
from .connection import get_session, init_db, close_db

__all__ = [
    # from models
    "User", "CheckIn", "MealPlan", "UserPattern",
    "Gender", "Goal", "ActivityLevel", "MealStyle",
    # from payment_models
    "Subscription", "Payment", "PromoCode", "PromoCodeUse", "PricingPlan",
    "SubscriptionPlan", "PaymentStatus", "PaymentProvider", "PromoType",
    # from connection
    "get_session", "init_db", "close_db"
]
