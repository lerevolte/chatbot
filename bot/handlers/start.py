from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from bot.states.onboarding import OnboardingStates
from database.models import User, Gender, Goal, ActivityLevel, MealStyle
from database.connection import get_session
from bot.utils.calculations import calculate_calories_and_macros

router = Router()

# Клавиатуры
def get_gender_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👨 Мужской")],
            [KeyboardButton(text="👩 Женский")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_goal_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔥 Похудеть")],
            [KeyboardButton(text="💪 Набрать мышечную массу")],
            [KeyboardButton(text="⚖️ Поддерживать вес")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_activity_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🪑 Малоподвижный (офис, мало движения)")],
            [KeyboardButton(text="🚶 Легкая активность (1-3 тренировки/нед)")],
            [KeyboardButton(text="🏃 Умеренная (3-5 тренировок/нед)")],
            [KeyboardButton(text="⚡ Активный (6-7 тренировок/нед)")],
            [KeyboardButton(text="🔥 Очень активный (спортсмен)")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_meal_count_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="3️⃣ 3 приема пищи")],
            [KeyboardButton(text="4️⃣ 4 приема пищи")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_meal_style_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👁 На глаз (проще)")],
            [KeyboardButton(text="⚖️ Точные граммовки")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_budget_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Экономный")],
            [KeyboardButton(text="💳 Средний")],
            [KeyboardButton(text="💎 Без ограничений")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_skip_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⏭ Пропустить")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# Хендлеры
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    async with get_session() as session:
        # Проверяем, есть ли пользователь в БД
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if user and user.onboarding_completed:
            await message.answer(
                "С возвращением! 👋\n\n"
                "Используйте меню для навигации:\n"
                "📊 /profile - Ваш профиль\n"
                "🍽 /meal_plan - План питания\n"
                "✅ /checkin - Чек-ин\n"
                "💳 /subscription - Подписка"
            )
        else:
            await message.answer(
                "Привет! 👋 Я твой персональный фитнес-помощник.\n\n"
                "За 90 дней мы вместе:\n"
                "✅ Снизим вес или наберем мышечную массу\n"
                "✅ Создадим здоровые привычки\n"
                "✅ Научимся правильно питаться\n\n"
                "Давай начнем с нескольких вопросов, чтобы составить твой персональный план.\n\n"
                "Какой у тебя пол?",
                reply_markup=get_gender_keyboard()
            )
            await state.set_state(OnboardingStates.gender)

@router.message(OnboardingStates.gender)
async def process_gender(message: Message, state: FSMContext):
    if "Мужской" in message.text:
        gender = Gender.MALE
    elif "Женский" in message.text:
        gender = Gender.FEMALE
    else:
        await message.answer("Пожалуйста, выберите из предложенных вариантов", 
                           reply_markup=get_gender_keyboard())
        return
    
    await state.update_data(gender=gender.value)
    await message.answer("Сколько тебе лет? (напиши число)")
    await state.set_state(OnboardingStates.age)

@router.message(OnboardingStates.age)
async def process_age(message: Message, state: FSMContext):
    try:
        age = int(message.text)
        if age < 14 or age > 100:
            await message.answer("Пожалуйста, введите корректный возраст (14-100)")
            return
    except ValueError:
        await message.answer("Пожалуйста, введите число")
        return
    
    await state.update_data(age=age)
    await message.answer("Какой у тебя рост в см? (например: 175)")
    await state.set_state(OnboardingStates.height)

@router.message(OnboardingStates.height)
async def process_height(message: Message, state: FSMContext):
    try:
        height = float(message.text.replace(',', '.'))
        if height < 100 or height > 250:
            await message.answer("Пожалуйста, введите корректный рост в см (100-250)")
            return
    except ValueError:
        await message.answer("Пожалуйста, введите число")
        return
    
    await state.update_data(height=height)
    await message.answer("Какой у тебя текущий вес в кг? (например: 75.5)")
    await state.set_state(OnboardingStates.current_weight)

@router.message(OnboardingStates.current_weight)
async def process_current_weight(message: Message, state: FSMContext):
    try:
        weight = float(message.text.replace(',', '.'))
        if weight < 30 or weight > 300:
            await message.answer("Пожалуйста, введите корректный вес в кг (30-300)")
            return
    except ValueError:
        await message.answer("Пожалуйста, введите число")
        return
    
    await state.update_data(current_weight=weight)
    await message.answer("Какая у тебя цель?", reply_markup=get_goal_keyboard())
    await state.set_state(OnboardingStates.goal)

@router.message(OnboardingStates.goal)
async def process_goal(message: Message, state: FSMContext):
    if "Похудеть" in message.text:
        goal = Goal.LOSE_WEIGHT
    elif "Набрать" in message.text:
        goal = Goal.GAIN_MUSCLE
    elif "Поддерживать" in message.text:
        goal = Goal.MAINTAIN
    else:
        await message.answer("Пожалуйста, выберите из предложенных вариантов",
                           reply_markup=get_goal_keyboard())
        return
    
    await state.update_data(goal=goal.value)
    
    if goal != Goal.MAINTAIN:
        await message.answer("Какой целевой вес ты хочешь достичь? (в кг)")
        await state.set_state(OnboardingStates.target_weight)
    else:
        data = await state.get_data()
        await state.update_data(target_weight=data['current_weight'])
        await message.answer("Какой у тебя уровень активности?", 
                           reply_markup=get_activity_keyboard())
        await state.set_state(OnboardingStates.activity_level)

@router.message(OnboardingStates.target_weight)
async def process_target_weight(message: Message, state: FSMContext):
    try:
        weight = float(message.text.replace(',', '.'))
        if weight < 30 or weight > 300:
            await message.answer("Пожалуйста, введите корректный вес в кг (30-300)")
            return
    except ValueError:
        await message.answer("Пожалуйста, введите число")
        return
    
    await state.update_data(target_weight=weight)
    await message.answer("Какой у тебя уровень активности?", 
                       reply_markup=get_activity_keyboard())
    await state.set_state(OnboardingStates.activity_level)

@router.message(OnboardingStates.activity_level)
async def process_activity(message: Message, state: FSMContext):
    activity_map = {
        "Малоподвижный": ActivityLevel.SEDENTARY,
        "Легкая": ActivityLevel.LIGHT,
        "Умеренная": ActivityLevel.MODERATE,
        "Активный": ActivityLevel.ACTIVE,
        "Очень активный": ActivityLevel.VERY_ACTIVE
    }
    
    activity = None
    for key, value in activity_map.items():
        if key in message.text:
            activity = value
            break
    
    if not activity:
        await message.answer("Пожалуйста, выберите из предложенных вариантов",
                           reply_markup=get_activity_keyboard())
        return
    
    await state.update_data(activity_level=activity.value)
    await message.answer("Сколько раз в день ты предпочитаешь есть?",
                       reply_markup=get_meal_count_keyboard())
    await state.set_state(OnboardingStates.meal_count)

@router.message(OnboardingStates.meal_count)
async def process_meal_count(message: Message, state: FSMContext):
    if "3" in message.text:
        meal_count = 3
    elif "4" in message.text:
        meal_count = 4
    else:
        await message.answer("Пожалуйста, выберите из предложенных вариантов",
                           reply_markup=get_meal_count_keyboard())
        return
    
    await state.update_data(meal_count=meal_count)
    await message.answer("Как ты предпочитаешь следить за питанием?",
                       reply_markup=get_meal_style_keyboard())
    await state.set_state(OnboardingStates.meal_style)

@router.message(OnboardingStates.meal_style)
async def process_meal_style(message: Message, state: FSMContext):
    if "глаз" in message.text:
        style = MealStyle.VISUAL
    elif "граммовки" in message.text:
        style = MealStyle.PRECISE
    else:
        await message.answer("Пожалуйста, выберите из предложенных вариантов",
                           reply_markup=get_meal_style_keyboard())
        return
    
    await state.update_data(meal_style=style.value)
    await message.answer(
        "Есть ли у тебя аллергии или продукты, которые нужно исключить?\n"
        "(например: лактоза, глютен, орехи)\n\n"
        "Напиши через запятую или нажми 'Пропустить'",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(OnboardingStates.allergies)

@router.message(OnboardingStates.allergies)
async def process_allergies(message: Message, state: FSMContext):
    if "Пропустить" not in message.text:
        allergies = [a.strip() for a in message.text.split(',')]
        await state.update_data(allergies=allergies)
    else:
        await state.update_data(allergies=[])
    
    await message.answer("Какой у тебя бюджет на питание?",
                       reply_markup=get_budget_keyboard())
    await state.set_state(OnboardingStates.budget)

@router.message(OnboardingStates.budget)
async def process_budget(message: Message, state: FSMContext):
    budget_map = {
        "Экономный": "low",
        "Средний": "medium",
        "Без ограничений": "high"
    }
    
    budget = None
    for key, value in budget_map.items():
        if key in message.text:
            budget = value
            break
    
    if not budget:
        await message.answer("Пожалуйста, выберите из предложенных вариантов",
                           reply_markup=get_budget_keyboard())
        return
    
    await state.update_data(budget=budget)
    
    # Сохраняем пользователя и рассчитываем КБЖУ
    await save_user_and_calculate(message, state)

async def save_user_and_calculate(message: Message, state: FSMContext):
    data = await state.get_data()
    
    async with get_session() as session:
        # Ищем или создаем пользователя
        user = await session.get(User, {"telegram_id": message.from_user.id})
        if not user:
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name
            )
            session.add(user)
        
        # Обновляем данные пользователя
        user.gender = Gender(data['gender'])
        user.age = data['age']
        user.height = data['height']
        user.current_weight = data['current_weight']
        user.target_weight = data['target_weight']
        user.goal = Goal(data['goal'])
        user.activity_level = ActivityLevel(data['activity_level'])
        user.meal_count = data['meal_count']
        user.meal_style = MealStyle(data['meal_style'])
        user.food_preferences = {
            'allergies': data.get('allergies', []),
            'exclude': [],
            'cuisines': []
        }
        user.budget = data['budget']
        user.onboarding_completed = True
        
        # Рассчитываем КБЖУ
        calories, protein, fats, carbs = calculate_calories_and_macros(
            gender=user.gender,
            age=user.age,
            height=user.height,
            weight=user.current_weight,
            activity_level=user.activity_level,
            goal=user.goal
        )
        
        user.daily_calories = calories
        user.daily_protein = protein
        user.daily_fats = fats
        user.daily_carbs = carbs
        
        # Активируем триал
        user.trial_started_at = datetime.utcnow()
        user.is_premium = True
        
        await session.commit()
    
    # Формируем итоговое сообщение
    result_text = (
        "🎉 Отлично! Твой персональный план готов!\n\n"
        f"📊 Твои параметры:\n"
        f"• Калории: {calories} ккал/день\n"
        f"• Белки: {protein}г\n"
        f"• Жиры: {fats}г\n"
        f"• Углеводы: {carbs}г\n\n"
        f"🎯 Цель: {goal_text[user.goal]}\n"
        f"⚖️ Текущий вес: {user.current_weight} кг\n"
        f"🎯 Целевой вес: {user.target_weight} кг\n\n"
        "✅ У тебя активирован пробный период на 7 дней!\n\n"
        "Теперь доступны команды:\n"
        "📊 /profile - Твой профиль\n"
        "🍽 /meal_plan - План питания на неделю\n"
        "✅ /checkin - Ежедневный чек-ин\n"
        "💳 /subscription - Управление подпиской"
    )
    
    await message.answer(result_text, reply_markup=ReplyKeyboardRemove())
    await state.clear()

# Обработчик для повторного прохождения онбординга
@router.message(Command("reset"))
async def reset_onboarding(message: Message, state: FSMContext):
    """Сброс данных и повторный онбординг"""
    await state.clear()
    
    async with get_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.onboarding_completed = False
            await session.commit()
    
    await message.answer(
        "Данные сброшены. Давай начнем заново!\n\n"
        "Какой у тебя пол?",
        reply_markup=get_gender_keyboard()
    )
    await state.set_state(OnboardingStates.gender)

# Обработчик отмены
@router.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext):
    """Отмена текущего действия"""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нечего отменять.")
        return
    
    await state.clear()
    await message.answer(
        "Действие отменено.\n\n"
        "Используйте:\n"
        "/start - начать заново\n"
        "/profile - ваш профиль",
        reply_markup=ReplyKeyboardRemove()
    )