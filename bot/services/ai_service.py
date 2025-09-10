import json
import logging
from typing import Dict, List, Optional
from openai import AsyncOpenAI
from bot.config import settings
from database.models import User, Goal

logger = logging.getLogger(__name__)

class AIService:
    """Сервис для работы с AI API"""
    
    def __init__(self):
        # ========== ИНИЦИАЛИЗАЦИЯ AI КЛИЕНТА ==========
        if settings.OPENAI_API_KEY:
            self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            self.enabled = True
            logger.info("AI сервис инициализирован с OpenAI")
        else:
            self.client = None
            self.enabled = False
            logger.warning("AI сервис отключен - нет API ключа")
    
    async def generate_meal_plan(self, user: User) -> Dict:
        """
        Генерирует план питания через AI
        ========== ОСНОВНАЯ ЛОГИКА ГЕНЕРАЦИИ ЧЕРЕЗ AI ==========
        """
        if not self.enabled:
            logger.warning("AI сервис отключен, используется базовая генерация")
            return None
        
        # Формируем промпт
        prompt = self._create_meal_prompt(user)
        
        try:
            # ========== ЗАПРОС К AI ==========
            response = await self.client.chat.completions.create(
                model=settings.AI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": """Ты профессиональный диетолог и фитнес-тренер. 
                        Создавай персонализированные планы питания на основе параметров клиента.
                        Отвечай ТОЛЬКО в формате JSON без дополнительного текста."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=settings.AI_TEMPERATURE,
                max_tokens=settings.AI_MAX_TOKENS,
                response_format={"type": "json_object"}  # Форсируем JSON ответ
            )
            
            # Парсим ответ
            result = response.choices[0].message.content
            meal_data = json.loads(result)
            
            logger.info(f"AI успешно сгенерировал план для пользователя {user.telegram_id}")
            return meal_data
            
        except Exception as e:
            logger.error(f"Ошибка при генерации через AI: {e}")
            return None
    
    def _create_meal_prompt(self, user: User) -> str:
        """
        Создает промпт для генерации плана питания
        ========== ФОРМИРОВАНИЕ ПРОМПТА ==========
        """
        goal_text = {
            Goal.LOSE_WEIGHT: "снижение веса",
            Goal.GAIN_MUSCLE: "набор мышечной массы",
            Goal.MAINTAIN: "поддержание веса"
        }.get(user.goal, "поддержание веса")
        
        budget_text = {
            "low": "экономный",
            "medium": "средний",
            "high": "без ограничений"
        }.get(user.budget, "средний")
        
        allergies = ""
        if user.food_preferences and user.food_preferences.get('allergies'):
            allergies = f"Исключить: {', '.join(user.food_preferences['allergies'])}"
        
        prompt = f"""
        Создай план питания на ОДИН день для клиента со следующими параметрами:
        
        - Пол: {'мужской' if user.gender.value == 'male' else 'женский'}
        - Возраст: {user.age} лет
        - Текущий вес: {user.current_weight} кг
        - Рост: {user.height} см
        - Цель: {goal_text}
        - Целевые калории: {user.daily_calories} ккал
        - Белки: {user.daily_protein}г
        - Жиры: {user.daily_fats}г  
        - Углеводы: {user.daily_carbs}г
        - Количество приемов пищи: {user.meal_count}
        - Бюджет: {budget_text}
        {allergies}
        
        Верни JSON объект со следующей структурой:
        {{
            "breakfast": {{
                "name": "Название блюда",
                "calories": число,
                "protein": число,
                "fats": число,
                "carbs": число,
                "ingredients": ["Ингредиент 1 - количество", "Ингредиент 2 - количество"],
                "recipe": "Краткий рецепт приготовления"
            }},
            "lunch": {{ ... }},
            "dinner": {{ ... }},
            "snack": {{ ... }} // только если meal_count = 4
        }}
        
        Важно:
        1. Блюда должны быть простыми в приготовлении
        2. Ингредиенты доступные в обычном магазине
        3. Соответствовать бюджету
        4. Общая калорийность должна быть близка к целевой ({user.daily_calories} ккал)
        5. Используй русские названия блюд и ингредиентов
        """
        
        return prompt
    
    async def generate_meal_replacement(
        self, 
        user: User, 
        meal_type: str, 
        current_meal: Dict,
        reason: str = "user_request"
    ) -> Optional[Dict]:
        """
        Генерирует замену для конкретного блюда
        ========== ЗАМЕНА БЛЮДА ЧЕРЕЗ AI ==========
        """
        if not self.enabled:
            return None
        
        reason_text = {
            "user_request": "пользователь хочет другое блюдо",
            "allergy": "обнаружена аллергия",
            "not_available": "продукты недоступны",
            "too_expensive": "слишком дорого"
        }.get(reason, "пользователь хочет другое блюдо")
        
        meal_type_text = {
            "breakfast": "завтрак",
            "lunch": "обед",
            "dinner": "ужин",
            "snack": "перекус"
        }.get(meal_type, meal_type)
        
        prompt = f"""
        Нужно заменить {meal_type_text}.
        
        Текущее блюдо: {current_meal['name']}
        Калории: {current_meal['calories']} ккал
        БЖУ: {current_meal['protein']}г/{current_meal['fats']}г/{current_meal['carbs']}г
        
        Причина замены: {reason_text}
        
        Параметры клиента:
        - Цель: {user.goal.value}
        - Бюджет: {user.budget}
        - Аллергии: {user.food_preferences.get('allergies', [])}
        
        Предложи ДРУГОЕ блюдо с похожими калориями и БЖУ.
        
        Верни JSON:
        {{
            "name": "Название блюда",
            "calories": число (±50 ккал от текущего),
            "protein": число,
            "fats": число,
            "carbs": число,
            "ingredients": ["Ингредиент - количество"],
            "recipe": "Краткий рецепт"
        }}
        """
        
        try:
            response = await self.client.chat.completions.create(
                model=settings.AI_MODEL,
                messages=[
                    {"role": "system", "content": "Ты диетолог. Отвечай только JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,  # Больше вариативности
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при генерации замены: {e}")
            return None
    
    async def analyze_food_photo(self, photo_path: str) -> Optional[Dict]:
        """
        Анализирует фото еды (заготовка для будущего)
        ========== АНАЛИЗ ФОТО (ТРЕБУЕТ VISION API) ==========
        """
        # Это требует модель с поддержкой изображений (GPT-4 Vision)
        # Пока возвращаем заглушку
        logger.info(f"Анализ фото пока не реализован: {photo_path}")
        return {
            "description": "Анализ фото будет доступен в следующей версии",
            "estimated_calories": 0
        }