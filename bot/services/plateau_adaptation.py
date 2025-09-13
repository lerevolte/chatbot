import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import select, and_, func
import numpy as np

from database.models import User, CheckIn, MealPlan, Goal, ActivityLevel
from database.connection import get_session
from bot.utils.calculations import calculate_calories_and_macros, adjust_calories_for_plateau
from bot.services.meal_generator import MealPlanGenerator

logger = logging.getLogger(__name__)

class PlateauAdaptationService:
    """Сервис для автоматической адаптации при плато"""
    
    def __init__(self):
        self.plateau_threshold_days = 7  # Дней без изменений для определения плато
        self.weight_change_threshold = 0.5  # Минимальное изменение веса в кг
        self.adaptation_strategies = {
            Goal.LOSE_WEIGHT: self._adapt_for_weight_loss,
            Goal.GAIN_MUSCLE: self._adapt_for_muscle_gain,
            Goal.MAINTAIN: self._adapt_for_maintenance
        }