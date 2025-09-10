import json
import logging
from typing import Dict, List, Optional
import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from bot.config import settings
from database.models import User, Goal

logger = logging.getLogger(__name__)

class AIService:
    """Сервис для работы с Gemini API"""
    
    def __init__(self):
        self.enabled = False
        if settings.GEMINI_API_KEY:
            try:
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self.model = genai.GenerativeModel(settings.AI_MODEL)
                self.enabled = True
                logger.info("AI сервис инициализирован с Google Gemini")
            except Exception as e:
                logger.error(f"Ошибка инициализации Gemini: {e}")
        else:
            logger.warning("AI сервис отключен - нет GEMINI_API_KEY")

    async def generate_meal_plan(self, user: User) -> Optional[Dict]:
        """Генерирует план питания через Gemini"""
        if not self.enabled:
            logger.warning("AI сервис отключен, генерация невозможна")
            return None
        
        prompt = self._create_meal_prompt(user)
        generation_config = GenerationConfig(
            temperature=settings.AI_TEMPERATURE,
            max_output_tokens=settings.AI_MAX_TOKENS,
            response_mime_type="application/json", # Указываем, что ждем JSON
        )
        
        try:
            response = await self.model.generate_content_async(
                contents=prompt,
                generation_config=generation_config
            )
            
            # API возвращает JSON-строку, ее нужно распарсить
            meal_data = json.loads(response.text)
            logger.info(f"Gemini успешно сгенерировал план для пользователя {user.telegram_id}")
            return meal_data
            
        except Exception as e:
            logger.error(f"Ошибка при генерации через Gemini: {e}")
            return None
    
    def _create_meal_prompt(self, user: User) -> str:
        """Создает промпт для генерации плана питания"""
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
        
        # Системный промпт + пользовательский запрос в одном
        prompt = f"""
        Ты — профессиональный диетолог. Твоя задача — создать персонализированный план питания на ОДИН день.
        Ответ должен быть СТРОГО в формате JSON без какого-либо дополнительного текста или markdown-разметки.

        Параметры клиента:
        - Пол: {'мужской' if user.gender.value == 'male' else 'женский'}
        - Возраст: {user.age} лет
        - Вес: {user.current_weight} кг
        - Рост: {user.height} см
        - Цель: {goal_text}
        - Калории: ~{user.daily_calories} ккал
        - БЖУ: ~{user.daily_protein}г белка, ~{user.daily_fats}г жиров, ~{user.daily_carbs}г углеводов
        - Приемы пищи: {user.meal_count}
        - Бюджет: {budget_text}
        {allergies}
        
        Требования к плану:
        1. Блюда должны быть простыми в приготовлении.
        2. Ингредиенты должны быть доступны в обычных магазинах.
        3. Общая калорийность и БЖУ должны быть максимально близки к целевым.
        4. Используй русские названия блюд и ингредиентов.

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
            "snack": {{ ... }} // это поле должно быть null или отсутствовать, если meal_count = 3
        }}
        """
        
        return prompt
    
    async def generate_meal_replacement(
        self, 
        user: User, 
        meal_type: str, 
        current_meal: Dict,
    ) -> Optional[Dict]:
        """Генерирует замену для конкретного блюда через Gemini"""
        if not self.enabled:
            return None

        meal_type_text = {
            "breakfast": "завтрак", "lunch": "обед", "dinner": "ужин", "snack": "перекус"
        }.get(meal_type, meal_type)

        prompt = f"""
        Ты — диетолог. Замени блюдо, потому что оно не понравилось пользователю.
        Ответ должен быть СТРОГО в формате JSON.
        
        Текущее блюдо ({meal_type_text}):
        - Название: {current_meal['name']}
        - Калории: {current_meal['calories']} ккал
        
        Параметры клиента:
        - Цель: {user.goal.value}
        - Бюджет: {user.budget}
        - Аллергии: {user.food_preferences.get('allergies', [])}
        
        Предложи ДРУГОЕ блюдо с похожей калорийностью (±10%).
        
        Верни JSON:
        {{
            "name": "Название блюда",
            "calories": число,
            "protein": число,
            "fats": число,
            "carbs": число,
            "ingredients": ["Ингредиент - количество"],
            "recipe": "Краткий рецепт"
        }}
        """

        generation_config = GenerationConfig(
            temperature=0.8, # Больше вариативности
            max_output_tokens=500,
            response_mime_type="application/json",
        )

        try:
            response = await self.model.generate_content_async(prompt, generation_config=generation_config)
            result = json.loads(response.text)
            return result
        except Exception as e:
            logger.error(f"Ошибка при генерации замены: {e}")
            return None

    async def categorize_shopping_list(self, items: List[str]) -> Optional[Dict]:
        """
        Категоризирует список покупок с помощью Gemini.
        """
        if not self.enabled:
            logger.warning("AI сервис отключен, используется базовая категоризация")
            return None

        # Преобразуем список в строку для промпта
        items_str = "\n".join(f"- {item}" for item in items)

        prompt = f"""
        Ты — помощник по закупкам. Твоя задача — сгруппировать список продуктов по категориям для удобного похода в магазин.
        Ответ должен быть СТРОГО в формате JSON без какого-либо дополнительного текста или markdown-разметки.

        Вот список продуктов:
        {items_str}

        Сгруппируй их по стандартным категориям, таким как "Мясо и птица", "Рыба и морепродукты", "Молочные продукты", "Овощи", "Фрукты", "Бакалея" (для круп, макарон, муки), "Напитки", "Другое".
        Используй только те категории, для которых есть продукты.

        Верни JSON объект, где ключ — это название категории, а значение — список продуктов (строк) из этой категории.
        
        Пример формата ответа:
        {{
          "Молочные продукты": [
            "Творог 5% - 200 г",
            "Сыр - 30 г"
          ],
          "Овощи": [
            "Помидоры - 100г",
            "Шпинат - 50г"
          ]
        }}
        """

        generation_config = GenerationConfig(
            temperature=0.2, # Низкая температура для точности
            response_mime_type="application/json",
        )

        try:
            response = await self.model.generate_content_async(prompt, generation_config=generation_config)
            categorized_list = json.loads(response.text)
            logger.info("Gemini успешно категоризировал список покупок")
            return categorized_list
        except Exception as e:
            logger.error(f"Ошибка при категоризации списка покупок: {e}")
            return None # Возвращаем None, чтобы можно было откатиться к ручному методу
    
    # Метод analyze_food_photo остается без изменений, так как это заготовка
    async def analyze_food_photo(self, photo_path: str) -> Optional[Dict]:
        """Анализирует фото еды (заготовка для будущего)"""
        logger.info(f"Анализ фото пока не реализован: {photo_path}")
        return {
            "description": "Анализ фото будет доступен в следующей версии",
            "estimated_calories": 0
        }