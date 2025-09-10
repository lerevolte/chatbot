import json
import random
from typing import Dict, List, Optional
from database.models import User, Goal, MealStyle
from bot.services.ai_service import AIService

class MealPlanGenerator:
    """Генератор планов питания на основе параметров пользователя"""
    
    def __init__(self):
        # ========== ИНИЦИАЛИЗАЦИЯ AI СЕРВИСА ==========
        self.ai_service = AIService()
        
        # ========== НОВЫЙ КОД: База данных блюд ==========
        # В реальном проекте это должно быть в отдельной БД
        self.meal_database = {
            "breakfast": {
                "lose_weight": [
                    {
                        "name": "Овсянка с ягодами и орехами",
                        "calories": 320,
                        "protein": 12,
                        "fats": 8,
                        "carbs": 45,
                        "ingredients": ["Овсяные хлопья - 50г", "Черника - 100г", "Миндаль - 20г", "Мед - 1 ч.л."],
                        "budget": "low"
                    },
                    {
                        "name": "Творожная запеканка с яблоком",
                        "calories": 280,
                        "protein": 25,
                        "fats": 5,
                        "carbs": 35,
                        "ingredients": ["Творог 2% - 150г", "Яблоко - 1 шт", "Яйцо - 1 шт", "Овсяная мука - 30г"],
                        "budget": "low"
                    },
                    {
                        "name": "Омлет с овощами",
                        "calories": 250,
                        "protein": 20,
                        "fats": 12,
                        "carbs": 15,
                        "ingredients": ["Яйца - 2 шт", "Помидоры - 100г", "Шпинат - 50г", "Сыр - 30г"],
                        "budget": "medium"
                    },
                    {
                        "name": "Греческий йогурт с гранолой",
                        "calories": 290,
                        "protein": 18,
                        "fats": 10,
                        "carbs": 35,
                        "ingredients": ["Греческий йогурт - 150г", "Гранола - 40г", "Мед - 1 ч.л.", "Банан - 0.5 шт"],
                        "budget": "medium"
                    }
                ],
                "gain_muscle": [
                    {
                        "name": "Овсяные панкейки с арахисовой пастой",
                        "calories": 450,
                        "protein": 25,
                        "fats": 15,
                        "carbs": 55,
                        "ingredients": ["Овсяная мука - 80г", "Яйца - 2 шт", "Банан - 1 шт", "Арахисовая паста - 30г"],
                        "budget": "medium"
                    },
                    {
                        "name": "Творог с бананом и орехами",
                        "calories": 420,
                        "protein": 30,
                        "fats": 12,
                        "carbs": 45,
                        "ingredients": ["Творог 5% - 200г", "Банан - 1 шт", "Грецкие орехи - 30г", "Мед - 1 ст.л."],
                        "budget": "low"
                    }
                ],
                "maintain": [
                    {
                        "name": "Сырники с ягодным соусом",
                        "calories": 350,
                        "protein": 22,
                        "fats": 10,
                        "carbs": 40,
                        "ingredients": ["Творог - 150г", "Яйцо - 1 шт", "Мука - 30г", "Ягоды - 100г"],
                        "budget": "medium"
                    }
                ]
            },
            "lunch": {
                "lose_weight": [
                    {
                        "name": "Куриная грудка с овощами на гриле",
                        "calories": 380,
                        "protein": 40,
                        "fats": 8,
                        "carbs": 35,
                        "ingredients": ["Куриная грудка - 150г", "Брокколи - 150г", "Морковь - 100г", "Рис - 50г"],
                        "budget": "medium"
                    },
                    {
                        "name": "Салат с тунцом и киноа",
                        "calories": 350,
                        "protein": 30,
                        "fats": 12,
                        "carbs": 30,
                        "ingredients": ["Тунец консерв. - 120г", "Киноа - 60г", "Салат микс - 100г", "Оливковое масло - 1 ст.л."],
                        "budget": "high"
                    },
                    {
                        "name": "Индейка с гречкой и овощами",
                        "calories": 400,
                        "protein": 35,
                        "fats": 10,
                        "carbs": 40,
                        "ingredients": ["Индейка филе - 150г", "Гречка - 60г", "Кабачок - 100г", "Перец - 100г"],
                        "budget": "medium"
                    }
                ],
                "gain_muscle": [
                    {
                        "name": "Говядина с картофелем и салатом",
                        "calories": 550,
                        "protein": 40,
                        "fats": 20,
                        "carbs": 50,
                        "ingredients": ["Говядина - 180г", "Картофель - 150г", "Салат - 100г", "Сметана - 30г"],
                        "budget": "high"
                    },
                    {
                        "name": "Лосось с рисом и брокколи",
                        "calories": 520,
                        "protein": 38,
                        "fats": 18,
                        "carbs": 48,
                        "ingredients": ["Лосось - 150г", "Рис - 80г", "Брокколи - 150г", "Оливковое масло - 1 ст.л."],
                        "budget": "high"
                    }
                ],
                "maintain": [
                    {
                        "name": "Паста с курицей и овощами",
                        "calories": 450,
                        "protein": 32,
                        "fats": 12,
                        "carbs": 50,
                        "ingredients": ["Паста - 70г", "Куриная грудка - 120г", "Помидоры - 100г", "Базилик - 10г"],
                        "budget": "medium"
                    }
                ]
            },
            "dinner": {
                "lose_weight": [
                    {
                        "name": "Запеченная рыба с овощами",
                        "calories": 320,
                        "protein": 35,
                        "fats": 10,
                        "carbs": 20,
                        "ingredients": ["Треска - 180г", "Цветная капуста - 150г", "Морковь - 100г", "Лимон - 0.5 шт"],
                        "budget": "medium"
                    },
                    {
                        "name": "Салат с креветками",
                        "calories": 280,
                        "protein": 25,
                        "fats": 12,
                        "carbs": 18,
                        "ingredients": ["Креветки - 150г", "Авокадо - 0.5 шт", "Салат микс - 150г", "Оливковое масло - 1 ст.л."],
                        "budget": "high"
                    },
                    {
                        "name": "Куриные котлеты с салатом",
                        "calories": 350,
                        "protein": 32,
                        "fats": 12,
                        "carbs": 25,
                        "ingredients": ["Куриный фарш - 150г", "Яйцо - 1 шт", "Овощной салат - 200г"],
                        "budget": "low"
                    }
                ],
                "gain_muscle": [
                    {
                        "name": "Стейк с овощами гриль",
                        "calories": 480,
                        "protein": 42,
                        "fats": 22,
                        "carbs": 25,
                        "ingredients": ["Говяжий стейк - 180г", "Баклажан - 100г", "Перец - 100г", "Помидоры - 100г"],
                        "budget": "high"
                    }
                ],
                "maintain": [
                    {
                        "name": "Рыбные котлеты с овощным рагу",
                        "calories": 380,
                        "protein": 28,
                        "fats": 14,
                        "carbs": 32,
                        "ingredients": ["Рыбный фарш - 150г", "Кабачок - 100г", "Морковь - 100г", "Лук - 50г"],
                        "budget": "medium"
                    }
                ]
            },
            "snack": [
                {
                    "name": "Протеиновый батончик",
                    "calories": 180,
                    "protein": 15,
                    "fats": 6,
                    "carbs": 18,
                    "ingredients": ["Протеиновый батончик - 1 шт"],
                    "budget": "medium"
                },
                {
                    "name": "Яблоко с арахисовой пастой",
                    "calories": 200,
                    "protein": 6,
                    "fats": 10,
                    "carbs": 25,
                    "ingredients": ["Яблоко - 1 шт", "Арахисовая паста - 20г"],
                    "budget": "low"
                },
                {
                    "name": "Греческий йогурт",
                    "calories": 150,
                    "protein": 15,
                    "fats": 5,
                    "carbs": 12,
                    "ingredients": ["Греческий йогурт - 150г"],
                    "budget": "medium"
                }
            ]
        }
    
    async def generate_weekly_plan(self, user: User) -> List[Dict]:
        """
        Генерирует план питания на неделю
        ========== НОВЫЙ КОД: Основная логика генерации ==========
        """
        weekly_plan = []
        
        for day in range(1, 8):  # 7 дней
            day_plan = await self.generate_day_plan(user)
            weekly_plan.append(day_plan)
        
        return weekly_plan
    
    async def generate_day_plan(self, user: User) -> Dict:
        """
        Генерирует план на один день
        ========== НОВЫЙ КОД: Подбор блюд по параметрам ==========
        """
        # ========== СНАЧАЛА ПРОБУЕМ AI ==========
        if self.ai_service.enabled:
            try:
                ai_plan = await self.ai_service.generate_meal_plan(user)
                if ai_plan:
                    # Добавляем итоговые подсчеты
                    total_calories = 0
                    total_protein = 0
                    total_fats = 0
                    total_carbs = 0
                    
                    for meal_key in ['breakfast', 'lunch', 'dinner', 'snack']:
                        if meal_key in ai_plan and ai_plan[meal_key]:
                            total_calories += ai_plan[meal_key]['calories']
                            total_protein += ai_plan[meal_key]['protein']
                            total_fats += ai_plan[meal_key]['fats']
                            total_carbs += ai_plan[meal_key]['carbs']
                    
                    return {
                        'breakfast': ai_plan.get('breakfast'),
                        'lunch': ai_plan.get('lunch'),
                        'dinner': ai_plan.get('dinner'),
                        'snack': ai_plan.get('snack') if user.meal_count == 4 else None,
                        'total_calories': total_calories,
                        'total_protein': total_protein,
                        'total_fats': total_fats,
                        'total_carbs': total_carbs
                    }
            except Exception as e:
                logger.error(f"Ошибка при генерации через AI: {e}")
        
        # ========== FALLBACK: ИСПОЛЬЗУЕМ БАЗОВУЮ ГЕНЕРАЦИЮ ==========
        # Определяем категорию по цели
        goal_key = {
            Goal.LOSE_WEIGHT: "lose_weight",
            Goal.GAIN_MUSCLE: "gain_muscle",
            Goal.MAINTAIN: "maintain"
        }[user.goal]
        
        # Фильтруем по бюджету
        budget_priority = ["low", "medium", "high"]
        if user.budget == "low":
            budget_priority = ["low", "medium"]
        elif user.budget == "high":
            budget_priority = ["high", "medium", "low"]
        
        # Подбираем блюда
        breakfast_options = self.meal_database["breakfast"].get(goal_key, [])
        lunch_options = self.meal_database["lunch"].get(goal_key, [])
        dinner_options = self.meal_database["dinner"].get(goal_key, [])
        
        # Фильтруем по аллергиям
        if user.food_preferences and user.food_preferences.get('allergies'):
            allergies = [a.lower() for a in user.food_preferences['allergies']]
            breakfast_options = [m for m in breakfast_options 
                                if not any(allergy in str(m['ingredients']).lower() 
                                         for allergy in allergies)]
            lunch_options = [m for m in lunch_options 
                           if not any(allergy in str(m['ingredients']).lower() 
                                    for allergy in allergies)]
            dinner_options = [m for m in dinner_options 
                            if not any(allergy in str(m['ingredients']).lower() 
                                     for allergy in allergies)]
        
        # Выбираем случайные блюда
        breakfast = random.choice(breakfast_options) if breakfast_options else self.get_default_meal("breakfast")
        lunch = random.choice(lunch_options) if lunch_options else self.get_default_meal("lunch")
        dinner = random.choice(dinner_options) if dinner_options else self.get_default_meal("dinner")
        
        # Добавляем перекус если нужно 4 приема пищи
        snack = None
        if user.meal_count == 4:
            snack = random.choice(self.meal_database["snack"])
        
        # Подсчитываем итоги
        total_calories = breakfast['calories'] + lunch['calories'] + dinner['calories']
        total_protein = breakfast['protein'] + lunch['protein'] + dinner['protein']
        total_fats = breakfast['fats'] + lunch['fats'] + dinner['fats']
        total_carbs = breakfast['carbs'] + lunch['carbs'] + dinner['carbs']
        
        if snack:
            total_calories += snack['calories']
            total_protein += snack['protein']
            total_fats += snack['fats']
            total_carbs += snack['carbs']
        
        # ========== НОВЫЙ КОД: Корректировка под целевые КБЖУ ==========
        # Проверяем соответствие целевым значениям
        target_calories = user.daily_calories
        if abs(total_calories - target_calories) > 200:
            # Корректируем порции
            adjustment_factor = target_calories / total_calories
            breakfast['calories'] = int(breakfast['calories'] * adjustment_factor)
            lunch['calories'] = int(lunch['calories'] * adjustment_factor)
            dinner['calories'] = int(dinner['calories'] * adjustment_factor)
            total_calories = target_calories
            
            # Корректируем БЖУ пропорционально
            breakfast['protein'] = int(breakfast['protein'] * adjustment_factor)
            breakfast['fats'] = int(breakfast['fats'] * adjustment_factor)
            breakfast['carbs'] = int(breakfast['carbs'] * adjustment_factor)
            
            lunch['protein'] = int(lunch['protein'] * adjustment_factor)
            lunch['fats'] = int(lunch['fats'] * adjustment_factor)
            lunch['carbs'] = int(lunch['carbs'] * adjustment_factor)
            
            dinner['protein'] = int(dinner['protein'] * adjustment_factor)
            dinner['fats'] = int(dinner['fats'] * adjustment_factor)
            dinner['carbs'] = int(dinner['carbs'] * adjustment_factor)
            
            if snack:
                snack['calories'] = int(snack['calories'] * adjustment_factor)
                snack['protein'] = int(snack['protein'] * adjustment_factor)
                snack['fats'] = int(snack['fats'] * adjustment_factor)
                snack['carbs'] = int(snack['carbs'] * adjustment_factor)
        
        return {
            'breakfast': breakfast,
            'lunch': lunch,
            'dinner': dinner,
            'snack': snack,
            'total_calories': total_calories,
            'total_protein': total_protein,
            'total_fats': total_fats,
            'total_carbs': total_carbs
        }
    
    async def generate_meal_replacement(self, user: User, meal_type: str, current_plan: 'MealPlan') -> Dict:
        """
        Генерирует замену для конкретного блюда
        ========== НОВЫЙ КОД: Логика замены блюд ==========
        """
        goal_key = {
            Goal.LOSE_WEIGHT: "lose_weight",
            Goal.GAIN_MUSCLE: "gain_muscle",
            Goal.MAINTAIN: "maintain"
        }[user.goal]
        
        # Получаем текущее блюдо
        if meal_type == "breakfast":
            current_meal = current_plan.breakfast
            options = self.meal_database["breakfast"].get(goal_key, [])
        elif meal_type == "lunch":
            current_meal = current_plan.lunch
            options = self.meal_database["lunch"].get(goal_key, [])
        elif meal_type == "dinner":
            current_meal = current_plan.dinner
            options = self.meal_database["dinner"].get(goal_key, [])
        else:
            return current_meal
        
        # Фильтруем, чтобы не предложить то же самое
        options = [m for m in options if m['name'] != current_meal['name']]
        
        # Фильтруем по аллергиям
        if user.food_preferences and user.food_preferences.get('allergies'):
            allergies = [a.lower() for a in user.food_preferences['allergies']]
            options = [m for m in options 
                      if not any(allergy in str(m['ingredients']).lower() 
                               for allergy in allergies)]
        
        if options:
            # Выбираем блюдо с похожими калориями
            target_calories = current_meal['calories']
            options.sort(key=lambda x: abs(x['calories'] - target_calories))
            return options[0]
        
        return self.get_default_meal(meal_type)
    
    def get_default_meal(self, meal_type: str) -> Dict:
        """
        Возвращает блюдо по умолчанию
        ========== НОВЫЙ КОД: Запасные варианты ==========
        """
        defaults = {
            "breakfast": {
                "name": "Овсяная каша с фруктами",
                "calories": 300,
                "protein": 10,
                "fats": 8,
                "carbs": 45,
                "ingredients": ["Овсянка - 60г", "Банан - 1 шт", "Мед - 1 ч.л."]
            },
            "lunch": {
                "name": "Куриная грудка с рисом",
                "calories": 400,
                "protein": 35,
                "fats": 10,
                "carbs": 40,
                "ingredients": ["Куриная грудка - 150г", "Рис - 70г", "Овощи - 150г"]
            },
            "dinner": {
                "name": "Рыба с овощами",
                "calories": 350,
                "protein": 30,
                "fats": 12,
                "carbs": 25,
                "ingredients": ["Рыба - 150г", "Овощи - 200г", "Оливковое масло - 1 ст.л."]
            }
        }
        return defaults.get(meal_type, defaults["lunch"])