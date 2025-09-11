from aiogram.fsm.state import State, StatesGroup

class MorningCheckInStates(StatesGroup):
    """Состояния для утреннего чек-ина"""
    weight = State()
    sleep = State()
    mood = State()
    
class EveningCheckInStates(StatesGroup):
    """Состояния для вечернего чек-ина"""
    steps = State()
    water = State()
    meals_review = State()
    notes = State()

class FoodPhotoStates(StatesGroup):
    """Состояния для фото еды"""
    meal_type = State()  # breakfast/lunch/dinner/snack
    photo = State()
    description = State()