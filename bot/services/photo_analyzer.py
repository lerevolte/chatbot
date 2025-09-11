import logging
import base64
from typing import Optional, Dict
import google.generativeai as genai
from PIL import Image

from bot.config import settings

logger = logging.getLogger(__name__)

class PhotoAnalyzer:
    """Анализатор фото еды через AI"""
    
    def __init__(self):
        """
        Инициализация анализатора
        ========== НАСТРОЙКА GEMINI ДЛЯ VISION ==========
        """
        self.enabled = False
        if settings.GEMINI_API_KEY:
            try:
                genai.configure(api_key=settings.GEMINI_API_KEY)
                # Используем модель с поддержкой изображений
                self.model = genai.GenerativeModel('gemini-1.5-flash')
                self.enabled = True
                logger.info("Анализатор фото инициализирован с Gemini Vision")
            except Exception as e:
                logger.error(f"Ошибка инициализации анализатора фото: {e}")
        else:
            logger.warning("Анализатор фото отключен - нет API ключа")
    
    async def analyze_food_photo(self, photo_path: str) -> Optional[Dict]:
        """
        Анализирует фото еды и возвращает информацию о блюде
        ========== ОСНОВНАЯ ЛОГИКА АНАЛИЗА ==========
        """
        if not self.enabled:
            logger.warning("Анализатор фото отключен")
            return None
        
        try:
            # Открываем изображение
            img = Image.open(photo_path)
            
            # Формируем промпт для анализа
            prompt = """
            Проанализируй это фото еды и определи:
            1. Что это за блюдо (название и описание)
            2. Примерный размер порции
            3. Примерную калорийность
            4. Примерное содержание БЖУ
            
            Ответь в формате JSON:
            {
                "description": "Описание блюда на русском",
                "portion_size": "размер порции",
                "estimated_calories": число,
                "protein": число,
                "fats": число,
                "carbs": число,
                "ingredients": ["основные ингредиенты"],
                "healthiness": "оценка полезности от 1 до 10"
            }
            
            Если на фото не еда, верни {"error": "Это не еда"}
            """
            
            # Отправляем запрос к Gemini
            response = await self.model.generate_content_async([prompt, img])
            
            # Парсим ответ
            try:
                # Убираем markdown если есть
                text = response.text.strip()
                if text.startswith("```json"):
                    text = text[7:]
                if text.endswith("```"):
                    text = text[:-3]
                
                import json
                result = json.loads(text)
                
                logger.info(f"Фото успешно проанализировано: {result.get('description', 'Unknown')}")
                return result
                
            except json.JSONDecodeError:
                # Если не удалось распарсить JSON, пробуем извлечь информацию из текста
                logger.warning("Не удалось распарсить JSON ответ от Gemini")
                return {
                    "description": response.text[:200],
                    "estimated_calories": 0,
                    "protein": 0,
                    "fats": 0,
                    "carbs": 0
                }
                
        except Exception as e:
            logger.error(f"Ошибка при анализе фото: {e}")
            return None
    
    async def compare_with_plan(self, photo_path: str, planned_meal: Dict) -> Dict:
        """
        Сравнивает фото еды с запланированным приемом пищи
        ========== СРАВНЕНИЕ С ПЛАНОМ ==========
        """
        if not self.enabled:
            return {"match": False, "comment": "Анализ недоступен"}
        
        try:
            # Анализируем фото
            analysis = await self.analyze_food_photo(photo_path)
            if not analysis:
                return {"match": False, "comment": "Не удалось проанализировать фото"}
            
            # Сравниваем калории
            planned_calories = planned_meal.get('calories', 0)
            actual_calories = analysis.get('estimated_calories', 0)
            
            if actual_calories == 0:
                return {"match": False, "comment": "Не удалось определить калории"}
            
            difference_percent = abs(actual_calories - planned_calories) / planned_calories * 100
            
            # Формируем результат
            if difference_percent <= 20:
                match_level = "good"
                comment = "✅ Отлично! Блюдо соответствует плану."
            elif difference_percent <= 40:
                match_level = "moderate"
                comment = "⚠️ Есть небольшие отклонения от плана."
            else:
                match_level = "poor"
                comment = "❌ Значительное отклонение от плана."
            
            return {
                "match": match_level != "poor",
                "match_level": match_level,
                "comment": comment,
                "planned_calories": planned_calories,
                "actual_calories": actual_calories,
                "difference_percent": difference_percent,
                "analysis": analysis
            }
            
        except Exception as e:
            logger.error(f"Ошибка при сравнении с планом: {e}")
            return {"match": False, "comment": f"Ошибка анализа: {str(e)}"}