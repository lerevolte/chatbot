import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
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
    
    async def check_and_adapt(self, telegram_id: int) -> Dict:
        """Проверяет наличие плато и адаптирует план"""
        async with get_session() as session:
            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return {"success": False, "error": "User not found"}
            
            # Анализируем прогресс
            plateau_data = await self._detect_plateau(user.id)
            
            if not plateau_data['is_plateau']:
                return {
                    "success": True,
                    "is_plateau": False,
                    "message": "Progress is on track"
                }
            
            # Применяем адаптацию
            adaptation_strategy = self.adaptation_strategies.get(user.goal)
            if adaptation_strategy:
                adaptations = await adaptation_strategy(user, plateau_data)
                
                # Сохраняем изменения
                await self._apply_adaptations(user, adaptations, session)
                
                return {
                    "success": True,
                    "is_plateau": True,
                    "plateau_days": plateau_data['plateau_days'],
                    "adaptations": adaptations
                }
            
            return {"success": False, "error": "No adaptation strategy"}
    
    async def _detect_plateau(self, user_id: int) -> Dict:
        """Определяет наличие плато"""
        async with get_session() as session:
            # Получаем последние чек-ины с весом
            two_weeks_ago = datetime.now() - timedelta(days=14)
            result = await session.execute(
                select(CheckIn).where(
                    and_(
                        CheckIn.user_id == user_id,
                        CheckIn.date >= two_weeks_ago,
                        CheckIn.weight.isnot(None)
                    )
                ).order_by(CheckIn.date)
            )
            checkins = result.scalars().all()
            
            if len(checkins) < self.plateau_threshold_days:
                return {"is_plateau": False, "plateau_days": 0}
            
            # Анализируем последние N дней
            recent_weights = [c.weight for c in checkins[-self.plateau_threshold_days:]]
            weight_range = max(recent_weights) - min(recent_weights)
            
            # Плато, если изменение веса меньше порога
            is_plateau = weight_range <= self.weight_change_threshold
            
            # Подсчитываем дни плато
            plateau_days = 0
            if is_plateau:
                for i in range(len(checkins) - 1, 0, -1):
                    if abs(checkins[i].weight - checkins[i-1].weight) <= self.weight_change_threshold:
                        plateau_days += 1
                    else:
                        break
            
            return {
                "is_plateau": is_plateau,
                "plateau_days": plateau_days,
                "weight_range": weight_range,
                "recent_weights": recent_weights
            }
    
    async def _adapt_for_weight_loss(self, user: User, plateau_data: Dict) -> Dict:
        """Адаптация для снижения веса"""
        adaptations = {
            "calorie_adjustment": 0,
            "macro_adjustment": {},
            "activity_changes": {},
            "strategies": []
        }
        
        # Стратегия 1: Уменьшение калорий
        if plateau_data['plateau_days'] >= 7:
            adaptations['calorie_adjustment'] = -100  # -100 ккал
            adaptations['strategies'].append("Снижение калорийности на 100 ккал")
        
        if plateau_data['plateau_days'] >= 14:
            adaptations['calorie_adjustment'] = -200  # -200 ккал
            adaptations['strategies'].append("Значительное снижение калорийности")
            
            # Увеличиваем белок для сохранения мышц
            adaptations['macro_adjustment']['protein'] = user.current_weight * 2.0  # 2г на кг
            adaptations['strategies'].append("Увеличение белка до 2г/кг веса")
        
        # Стратегия 2: Изменение активности
        adaptations['activity_changes']['cardio'] = "Добавить 2 кардио-сессии по 30 мин"
        adaptations['activity_changes']['steps'] = "Увеличить до 10,000 шагов/день"
        
        # Стратегия 3: Циклирование калорий
        if plateau_data['plateau_days'] >= 10:
            adaptations['strategies'].append("Циклирование калорий (дни с высокими и низкими калориями)")
            adaptations['calorie_cycling'] = {
                "high_days": 2,  # 2 дня в неделю с обычными калориями
                "low_days": 5,   # 5 дней с дефицитом
                "high_day_calories": user.daily_calories,
                "low_day_calories": user.daily_calories - 300
            }
        
        # Стратегия 4: Рефид
        if plateau_data['plateau_days'] >= 21:
            adaptations['strategies'].append("Рефид день раз в неделю")
            adaptations['refeed'] = {
                "frequency": "weekly",
                "calories": user.daily_calories + 500,
                "carbs_increase": True
            }
        
        return adaptations
    
    async def _adapt_for_muscle_gain(self, user: User, plateau_data: Dict) -> Dict:
        """Адаптация для набора мышечной массы"""
        adaptations = {
            "calorie_adjustment": 0,
            "macro_adjustment": {},
            "activity_changes": {},
            "strategies": []
        }
        
        # Увеличиваем калории
        if plateau_data['plateau_days'] >= 7:
            adaptations['calorie_adjustment'] = 150  # +150 ккал
            adaptations['strategies'].append("Увеличение калорийности на 150 ккал")
        
        if plateau_data['plateau_days'] >= 14:
            adaptations['calorie_adjustment'] = 250  # +250 ккал
            adaptations['strategies'].append("Значительное увеличение калорийности")
            
            # Увеличиваем углеводы для энергии
            adaptations['macro_adjustment']['carbs'] = user.current_weight * 5  # 5г на кг
            adaptations['strategies'].append("Увеличение углеводов до 5г/кг")
        
        # Изменение тренировок
        adaptations['activity_changes']['strength'] = "Увеличить объем силовых тренировок"
        adaptations['activity_changes']['rest'] = "Добавить день отдыха для восстановления"
        adaptations['strategies'].append("Прогрессивная перегрузка в тренировках")
        
        return adaptations
    
    async def _adapt_for_maintenance(self, user: User, plateau_data: Dict) -> Dict:
        """Адаптация для поддержания веса"""
        return {
            "calorie_adjustment": 0,
            "macro_adjustment": {},
            "activity_changes": {
                "variety": "Добавить разнообразие в тренировки"
            },
            "strategies": ["Поддержание текущего режима"]
        }
    
    async def _apply_adaptations(self, user: User, adaptations: Dict, session):
        """Применяет адаптации к профилю пользователя"""
        # Корректируем калории
        if adaptations.get('calorie_adjustment'):
            user.daily_calories += adaptations['calorie_adjustment']
            
            # Пересчитываем макросы пропорционально
            calorie_ratio = (user.daily_calories + adaptations['calorie_adjustment']) / user.daily_calories
            user.daily_protein *= calorie_ratio
            user.daily_fats *= calorie_ratio
            user.daily_carbs *= calorie_ratio
        
        # Применяем изменения макросов
        if adaptations.get('macro_adjustment'):
            for macro, value in adaptations['macro_adjustment'].items():
                if macro == 'protein':
                    user.daily_protein = value
                elif macro == 'fats':
                    user.daily_fats = value
                elif macro == 'carbs':
                    user.daily_carbs = value
        
        await session.commit()
    
    async def generate_breakthrough_plan(self, telegram_id: int) -> Dict:
        """Генерирует специальный план для прорыва плато"""
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return {"success": False}
            
            plan = {
                "days": [],
                "recommendations": []
            }
            
            # 7-дневный план с чередованием
            if user.goal == Goal.LOSE_WEIGHT:
                # План для похудения: чередование калорий и нагрузок
                for day in range(1, 8):
                    day_plan = {
                        "day": day,
                        "calories": 0,
                        "type": ""
                    }
                    
                    if day in [1, 3, 5]:  # Низкокалорийные дни
                        day_plan["calories"] = user.daily_calories - 300
                        day_plan["type"] = "Низкокалорийный"
                        day_plan["cardio"] = "30 мин кардио средней интенсивности"
                    elif day in [2, 4, 6]:  # Умеренные дни
                        day_plan["calories"] = user.daily_calories - 100
                        day_plan["type"] = "Умеренный"
                        day_plan["strength"] = "Силовая тренировка на все тело"
                    else:  # День 7 - рефид
                        day_plan["calories"] = user.daily_calories + 200
                        day_plan["type"] = "Рефид"
                        day_plan["rest"] = True
                    
                    plan["days"].append(day_plan)
                
                plan["recommendations"] = [
                    "Пейте минимум 2.5л воды в день",
                    "Спите 7-9 часов",
                    "Взвешивайтесь только раз в неделю",
                    "Делайте фото для отслеживания визуальных изменений",
                    "Не снижайте калории ниже базового метаболизма"
                ]
            
            elif user.goal == Goal.GAIN_MUSCLE:
                # План для набора массы
                for day in range(1, 8):
                    day_plan = {
                        "day": day,
                        "calories": 0,
                        "type": ""
                    }
                    
                    if day in [1, 3, 5]:  # Тренировочные дни
                        day_plan["calories"] = user.daily_calories + 300
                        day_plan["type"] = "Тренировочный"
                        day_plan["strength"] = "Тяжелая силовая тренировка"
                    elif day in [2, 4, 6]:  # Дни восстановления
                        day_plan["calories"] = user.daily_calories + 100
                        day_plan["type"] = "Восстановление"
                        day_plan["cardio"] = "Легкая активность 20 мин"
                    else:  # День 7 - полный отдых
                        day_plan["calories"] = user.daily_calories
                        day_plan["type"] = "Отдых"
                        day_plan["rest"] = True
                    
                    plan["days"].append(day_plan)
                
                plan["recommendations"] = [
                    "Употребляйте белок каждые 3-4 часа",
                    "Добавьте креатин моногидрат 5г в день",
                    "Увеличивайте рабочие веса на 2.5-5% еженедельно",
                    "Спите минимум 8 часов",
                    "Делайте массаж или растяжку для восстановления"
                ]
            
            return {
                "success": True,
                "plan": plan,
                "duration": 7
            }
    
    async def suggest_diet_break(self, telegram_id: int) -> bool:
        """Определяет, нужен ли диетический перерыв"""
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            
            if not user or user.goal != Goal.LOSE_WEIGHT:
                return False
            
            # Проверяем, как долго пользователь на дефиците
            three_months_ago = datetime.now() - timedelta(days=90)
            result = await session.execute(
                select(CheckIn).where(
                    and_(
                        CheckIn.user_id == user.id,
                        CheckIn.date >= three_months_ago,
                        CheckIn.weight.isnot(None)
                    )
                ).order_by(CheckIn.date)
            )
            checkins = result.scalars().all()
            
            if len(checkins) < 30:
                return False
            
            # Если вес снижался 3 месяца подряд - рекомендуем перерыв
            first_weight = checkins[0].weight
            last_weight = checkins[-1].weight
            total_lost = first_weight - last_weight
            
            # Если потеряно больше 10% веса - нужен перерыв
            if total_lost > first_weight * 0.1:
                return True
            
            # Если на плато больше 3 недель - тоже перерыв
            plateau_data = await self._detect_plateau(user.id)
            if plateau_data['plateau_days'] >= 21:
                return True
            
            return False
    
    async def calculate_reverse_diet(self, user: User) -> Dict:
        """Рассчитывает план обратной диеты после похудения"""
        return {
            "weeks": 4,
            "weekly_calorie_increase": 50,
            "focus": "Постепенное увеличение калорий для восстановления метаболизма",
            "week_1": user.daily_calories + 50,
            "week_2": user.daily_calories + 100,
            "week_3": user.daily_calories + 150,
            "week_4": user.daily_calories + 200,
            "final_maintenance": user.daily_calories + 200
        }
    
    async def get_plateau_strategies(self, goal: Goal) -> List[str]:
        """Возвращает список стратегий для прорыва плато"""
        strategies = {
            Goal.LOSE_WEIGHT: [
                "🔄 Циклирование калорий (2 дня высокие, 5 дней низкие)",
                "⚡ HIIT тренировки 2-3 раза в неделю",
                "🧘 Управление стрессом и кортизолом",
                "💧 Увеличение потребления воды до 3л",
                "🛌 Улучшение качества сна (7-9 часов)",
                "🥗 Увеличение клетчатки и овощей",
                "🏃 Добавление утреннего кардио натощак",
                "📝 Точный подсчет калорий в течение недели",
                "🧂 Контроль потребления соли",
                "☕ Временное исключение кофеина"
            ],
            Goal.GAIN_MUSCLE: [
                "💪 Изменение программы тренировок",
                "🍽 Увеличение калорий на 200-300",
                "😴 Добавление дневного сна 20-30 мин",
                "🥩 Увеличение белка до 2.5г/кг",
                "💊 Добавление креатина и витамина D",
                "🏋️ Техника прогрессивной перегрузки",
                "📉 Уменьшение объема кардио",
                "🗓 Периодизация тренировок",
                "🧘 Добавление йоги для восстановления",
                "⏰ Изменение времени тренировок"
            ],
            Goal.MAINTAIN: [
                "🔄 Изменение типа активности",
                "🎯 Постановка новых фитнес-целей",
                "🏃 Подготовка к соревнованиям",
                "🧠 Фокус на ментальном здоровье",
                "👥 Групповые тренировки",
                "🏊 Добавление плавания",
                "🚴 Велосипедные прогулки",
                "🥋 Единоборства или танцы",
                "🧗 Скалолазание или новый спорт",
                "📚 Изучение новых рецептов"
            ]
        }
        
        return strategies.get(goal, [])