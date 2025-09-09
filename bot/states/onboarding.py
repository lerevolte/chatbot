from aiogram.fsm.state import State, StatesGroup

class OnboardingStates(StatesGroup):
    # Базовая информация
    gender = State()
    age = State()
    height = State()
    current_weight = State()
    
    # Цели
    goal = State()
    target_weight = State()
    activity_level = State()
    
    # Питание
    meal_count = State()
    meal_style = State()
    food_preferences = State()
    allergies = State()
    budget = State()
    
    # Подтверждение
    confirmation = State()