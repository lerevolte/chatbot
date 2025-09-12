import base64
import logging
from typing import Dict, Optional
import google.generativeai as genai
from PIL import Image
import io

from bot.config import settings
from database.models import User

logger = logging.getLogger(__name__)

class VisionService:
    """Сервис для анализа фото еды через Vision API"""
    
    def __init__(self):
        self.enabled = False
        if settings.GEMINI_API_KEY:
            try:
                genai.configure(api_key=settings.GEMINI_API_KEY)
                # Используем модель с поддержкой изображений
                self.model = genai.GenerativeModel('gemini-1.5-flash')
                self.enabled = True
                logger.info("Vision сервис инициализирован с Gemini")
            except Exception as e:
                logger.error(f"Ошибка инициализации Vision: {e}")
        else:
            logger.warning("Vision сервис отключен - нет API ключа")
    
    async def analyze_food_photo(self, photo_path: str, user: Optional[User] = None) -> Dict:
        """
        Анализирует фото еды и возвращает информацию о блюде
        """
        if not self.enabled:
            return {
                "success": False,
                "description": "Анализ фото временно недоступен",
                "estimated_calories": 0
            }
        
        try:
            # Открываем изображение
            with Image.open(photo_path) as img:
                # Конвертируем в RGB если нужно
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Создаем промпт для анализа
                prompt = self._create_food_analysis_prompt(user)
                
                # Отправляем запрос к Gemini
                response = await self.model.generate_content_async([prompt, img])
                
                # Парсим ответ
                result = self._parse_food_response(response.text)
                
                logger.info(f"Успешно проанализировано фото: {photo_path}")
                return result
                
        except Exception as e:
            logger.error(f"Ошибка при анализе фото: {e}")
            return {
                "success": False,
                "description": "Ошибка при анализе изображения",
                "estimated_calories": 0
            }
    
    def _create_food_analysis_prompt(self, user: Optional[User] = None) -> str:
        """Создает промпт для анализа фото еды"""
        
        user_context = ""
        if user:
            user_context = f"""
            Учти параметры пользователя:
            - Дневная норма калорий: {user.daily_calories} ккал
            - Цель по белкам: {user.daily_protein}г
            - Цель по жирам: {user.daily_fats}г
            - Цель по углеводам: {user.daily_carbs}г
            """
        
        prompt = f"""
        Проанализируй это фото еды. Определи:
        1. Что изображено на фото (название блюда/продуктов)
        2. Примерный размер порции
        3. Оценку калорийности
        4. Примерное содержание БЖУ
        5. Полезность блюда (по шкале 1-10)
        
        {user_context}
        
        Ответь в формате:
        БЛЮДО: [название]
        ПОРЦИЯ: [размер в граммах]
        КАЛОРИИ: [число]
        БЕЛКИ: [число]г
        ЖИРЫ: [число]г
        УГЛЕВОДЫ: [число]г
        ПОЛЕЗНОСТЬ: [оценка]/10
        СОСТАВ: [основные ингредиенты]
        РЕКОМЕНДАЦИЯ: [короткий совет]
        """
        
        return prompt
    
    def _parse_food_response(self, response_text: str) -> Dict:
        """Парсит ответ от AI"""
        result = {
            "success": True,
            "dish_name": "",
            "portion_size": "",
            "estimated_calories": 0,
            "protein": 0,
            "fats": 0,
            "carbs": 0,
            "healthiness": 0,
            "ingredients": [],
            "recommendation": "",
            "description": ""
        }
        
        try:
            lines = response_text.strip().split('\n')
            
            for line in lines:
                if 'БЛЮДО:' in line:
                    result['dish_name'] = line.split(':', 1)[1].strip()
                elif 'ПОРЦИЯ:' in line:
                    result['portion_size'] = line.split(':', 1)[1].strip()
                elif 'КАЛОРИИ:' in line:
                    calories_str = line.split(':', 1)[1].strip()
                    result['estimated_calories'] = int(''.join(filter(str.isdigit, calories_str)))
                elif 'БЕЛКИ:' in line:
                    protein_str = line.split(':', 1)[1].strip()
                    result['protein'] = float(''.join(filter(lambda x: x.isdigit() or x == '.', protein_str)))
                elif 'ЖИРЫ:' in line:
                    fats_str = line.split(':', 1)[1].strip()
                    result['fats'] = float(''.join(filter(lambda x: x.isdigit() or x == '.', fats_str)))
                elif 'УГЛЕВОДЫ:' in line:
                    carbs_str = line.split(':', 1)[1].strip()
                    result['carbs'] = float(''.join(filter(lambda x: x.isdigit() or x == '.', carbs_str)))
                elif 'ПОЛЕЗНОСТЬ:' in line:
                    health_str = line.split(':', 1)[1].strip()
                    result['healthiness'] = int(''.join(filter(str.isdigit, health_str.split('/')[0])))
                elif 'СОСТАВ:' in line:
                    ingredients_str = line.split(':', 1)[1].strip()
                    result['ingredients'] = [i.strip() for i in ingredients_str.split(',')]
                elif 'РЕКОМЕНДАЦИЯ:' in line:
                    result['recommendation'] = line.split(':', 1)[1].strip()
            
            # Формируем описание
            result['description'] = (
                f"Распознано: {result['dish_name']} ({result['portion_size']})\n"
                f"Примерно {result['estimated_calories']} ккал\n"
                f"БЖУ: {result['protein']}/{result['fats']}/{result['carbs']}г"
            )
            
        except Exception as e:
            logger.error(f"Ошибка парсинга ответа: {e}")
            result['description'] = "Обнаружена еда, но не удалось точно определить параметры"
        
        return result

    async def compare_with_plan(self, food_data: Dict, planned_meal: Dict) -> Dict:
        """
        Сравнивает распознанную еду с запланированным приемом пищи и возвращает
        структуру, ожидаемую хендлером.
        """
        deviation = {
            "calories": food_data.get('estimated_calories', 0) - planned_meal.get('calories', 0),
            "protein": food_data.get('protein', 0) - planned_meal.get('protein', 0),
            "fats": food_data.get('fats', 0) - planned_meal.get('fats', 0),
            "carbs": food_data.get('carbs', 0) - planned_meal.get('carbs', 0)
        }
        
        # Оценка соответствия плану
        total_deviation = abs(deviation['calories'])
        
        if total_deviation < 75:
            match_text = "Полностью соответствует плану"
            match_emoji = "✅"
        elif total_deviation < 150:
            match_text = "Небольшое отклонение от плана"
            match_emoji = "⚠️"
        else:
            match_text = "Значительное отклонение от плана"
            match_emoji = "❌"
        
        suggestions = self._get_meal_suggestions(deviation)
        
        return {
            "success": True,
            "match_text": match_text,
            "match_emoji": match_emoji,
            "daily_adjustments": suggestions,
            "deviation": deviation
        }
    
    def _get_meal_suggestions(self, deviation: Dict) -> list:
        """Генерирует рекомендации на основе отклонений"""
        suggestions = []
        
        if deviation['calories'] > 200:
            suggestions.append("Порция больше запланированной, можно уменьшить следующий прием пищи")
        elif deviation['calories'] < -200:
            suggestions.append("Порция меньше запланированной, можно добавить полезный перекус")
        
        if deviation['protein'] < -10:
            suggestions.append("Недостаточно белка - добавьте творог или яйцо")
        
        if deviation['carbs'] > 30:
            suggestions.append("Много углеводов - следующий прием пищи сделайте более белковым")
        
        return suggestions