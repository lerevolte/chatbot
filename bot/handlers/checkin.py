from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove, PhotoSize
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta, date
from sqlalchemy import select, and_
import logging
import os

from database.models import User, CheckIn
from database.connection import get_session
from bot.states.checkin import MorningCheckInStates, EveningCheckInStates, FoodPhotoStates
from bot.keyboards.checkin import get_mood_keyboard, get_meal_type_keyboard, get_water_keyboard, get_quick_weight_keyboard
from bot.services.ai_service import AIService
from bot.config import settings

router = Router()
logger = logging.getLogger(__name__)

# ============ КОМАНДА СТАРТА ЧЕК-ИНА ============
@router.message(Command("checkin"))
async def checkin_menu(message: Message):
    """Главное меню чек-ина"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌅 Утренний чек-ин", callback_data="morning_checkin"),
            InlineKeyboardButton(text="🌙 Вечерний чек-ин", callback_data="evening_checkin")
        ],
        [
            InlineKeyboardButton(text="📸 Фото еды", callback_data="food_photo"),
            InlineKeyboardButton(text="💧 Вода", callback_data="quick_water")
        ],
        [
            InlineKeyboardButton(text="📊 Сегодняшний прогресс", callback_data="today_progress"),
            InlineKeyboardButton(text="📈 История", callback_data="checkin_history")
        ]
    ])
    
    await message.answer(
        "📝 **Чек-ин на сегодня**\n\n"
        "Выберите, что хотите записать:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# ============ УТРЕННИЙ ЧЕК-ИН ============
@router.callback_query(F.data == "morning_checkin")
async def start_morning_checkin(callback: CallbackQuery, state: FSMContext):
    """Начало утреннего чек-ина"""
    await callback.answer()
    
    keyboard = get_quick_weight_keyboard()
    
    await callback.message.answer(
        "🌅 **Утренний чек-ин**\n\n"
        "Какой у тебя вес сегодня утром? (в кг)\n"
        "Можешь выбрать из быстрых вариантов или написать точное значение:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await state.set_state(MorningCheckInStates.weight)

@router.message(MorningCheckInStates.weight)
async def process_morning_weight(message: Message, state: FSMContext):
    """Обработка утреннего веса"""
    try:
        if "вчера" in message.text.lower():
            async with get_session() as session:
                result = await session.execute(
                    select(User).where(User.telegram_id == message.from_user.id)
                )
                user = result.scalar_one_or_none()
                weight = user.current_weight if user else 0
        elif "пропустить" in message.text.lower():
            weight = None
        else:
            weight_str = message.text.replace('кг', '').replace(',', '.').strip()
            weight = float(weight_str)
            if weight < 30 or weight > 300:
                await message.answer("Пожалуйста, введите корректный вес (30-300 кг)")
                return
    except ValueError:
        await message.answer("Пожалуйста, введите число или выберите из предложенных вариантов")
        return
    
    await state.update_data(weight=weight)
    
    if weight:
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == message.from_user.id)
            )
            user = result.scalar_one_or_none()
            if user:
                user.current_weight = weight
                await session.commit()
    
    await message.answer(
        "💤 Сколько часов ты спал(а) этой ночью?\n"
        "(введи число от 0 до 24)",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(MorningCheckInStates.sleep)

@router.message(MorningCheckInStates.sleep)
async def process_sleep(message: Message, state: FSMContext):
    """Обработка сна"""
    try:
        sleep_hours = float(message.text.replace(',', '.'))
        if sleep_hours < 0 or sleep_hours > 24:
            await message.answer("Пожалуйста, введите корректное количество часов (0-24)")
            return
    except ValueError:
        await message.answer("Пожалуйста, введите число")
        return
    
    await state.update_data(sleep_hours=sleep_hours)
    
    keyboard = get_mood_keyboard()
    await message.answer(
        "😊 Как твое самочувствие сегодня?",
        reply_markup=keyboard
    )
    await state.set_state(MorningCheckInStates.mood)

@router.message(MorningCheckInStates.mood)
async def process_mood(message: Message, state: FSMContext):
    """Обработка настроения и сохранение утреннего чек-ина"""
    mood_map = {
        "😊 Отлично": "good",
        "😐 Нормально": "normal",
        "😔 Плохо": "bad"
    }
    
    mood = mood_map.get(message.text, "normal")
    data = await state.get_data()
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer("Пользователь не найден. Используйте /start")
            await state.clear()
            return
        
        today = date.today()
        result = await session.execute(
            select(CheckIn).where(
                and_(
                    CheckIn.user_id == user.id,
                    CheckIn.date >= datetime.combine(today, datetime.min.time()),
                    CheckIn.date <= datetime.combine(today, datetime.max.time())
                )
            )
        )
        checkin = result.scalar_one_or_none()
        
        if not checkin:
            checkin = CheckIn(user_id=user.id)
            session.add(checkin)
        
        checkin.weight = data.get('weight')
        checkin.sleep_hours = data.get('sleep_hours')
        checkin.mood = mood
        
        await session.commit()
    
    response = "✅ **Утренний чек-ин сохранен!**\n\n"
    
    if data.get('weight'):
        response += f"⚖️ Вес: {data['weight']} кг\n"
    
    response += f"💤 Сон: {data['sleep_hours']} часов\n"
    response += f"😊 Самочувствие: {message.text}\n\n"
    
    if data['sleep_hours'] < 7:
        response += "💡 *Совет:* Старайся спать минимум 7-8 часов для лучшего восстановления.\n"
    elif data['sleep_hours'] > 9:
        response += "💡 *Совет:* Избыток сна может вызывать вялость. Попробуй придерживаться 7-9 часов.\n"
    else:
        response += "👍 Отличная продолжительность сна!\n"
    
    response += "\nНе забудь сегодня:\n"
    response += "• 💧 Выпить достаточно воды\n"
    response += "• 🚶 Сделать минимум 8000 шагов\n"
    response += "• 📸 Сфотографировать еду для контроля\n"
    
    await message.answer(response, reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")
    await state.clear()

# ============ ВЕЧЕРНИЙ ЧЕК-ИН ============
@router.callback_query(F.data == "evening_checkin")
async def start_evening_checkin(callback: CallbackQuery, state: FSMContext):
    """Начало вечернего чек-ина"""
    await callback.answer()
    
    await callback.message.answer(
        "🌙 **Вечерний чек-ин**\n\n"
        "🚶 Сколько шагов ты сделал(а) сегодня?\n"
        "(введи число или пропусти)",
        parse_mode="Markdown"
    )
    await state.set_state(EveningCheckInStates.steps)

@router.message(EveningCheckInStates.steps)
async def process_steps(message: Message, state: FSMContext):
    """Обработка шагов"""
    if "пропус" in message.text.lower():
        steps = None
    else:
        try:
            steps = int(message.text.replace(' ', ''))
            if steps < 0 or steps > 100000:
                await message.answer("Пожалуйста, введите корректное количество шагов")
                return
        except ValueError:
            await message.answer("Пожалуйста, введите число или напишите 'пропустить'")
            return
    
    await state.update_data(steps=steps)
    
    keyboard = get_water_keyboard()
    await message.answer(
        "💧 Сколько воды ты выпил(а) сегодня?",
        reply_markup=keyboard
    )
    await state.set_state(EveningCheckInStates.water)

@router.message(EveningCheckInStates.water)
async def process_water(message: Message, state: FSMContext):
    """Обработка воды"""
    water_map = {
        "< 1л": 500,
        "1-1.5л": 1250,
        "1.5-2л": 1750,
        "2-2.5л": 2250,
        "> 2.5л": 3000
    }
    
    water = water_map.get(message.text)
    if not water:
        try:
            water_str = message.text.lower().replace('л', '').replace('мл', '').replace(',', '.').strip()
            water_float = float(water_str)
            water = int(water_float * 1000) if water_float < 10 else int(water_float)
        except:
            water = 0
    
    await state.update_data(water_ml=water)
    
    await message.answer(
        "📝 Есть ли какие-то заметки о сегодняшнем дне?\n"
        "(питание, тренировки, самочувствие)\n\n"
        "Напиши или нажми 'Пропустить'",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Пропустить")]],
            resize_keyboard=True
        )
    )
    await state.set_state(EveningCheckInStates.notes)

@router.message(EveningCheckInStates.notes)
async def process_notes(message: Message, state: FSMContext):
    """Обработка заметок и сохранение вечернего чек-ина"""
    notes = None if "пропустить" in message.text.lower() else message.text
    data = await state.get_data()
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        today = date.today()
        result = await session.execute(
            select(CheckIn).where(
                and_(
                    CheckIn.user_id == user.id,
                    CheckIn.date >= datetime.combine(today, datetime.min.time()),
                    CheckIn.date <= datetime.combine(today, datetime.max.time())
                )
            )
        )
        checkin = result.scalar_one_or_none()
        
        if not checkin:
            checkin = CheckIn(user_id=user.id)
            session.add(checkin)
        
        checkin.steps = data.get('steps')
        checkin.water_ml = data.get('water_ml')
        checkin.notes = notes
        
        await session.commit()
    
    response = "✅ **Вечерний чек-ин сохранен!**\n\n"
    response += "📊 **Итоги дня:**\n"
    
    if data.get('steps'):
        steps_emoji = "🎯" if data['steps'] >= 8000 else "📈"
        response += f"{steps_emoji} Шаги: {data['steps']:,}\n"
        if data['steps'] < 8000:
            response += f"   _Осталось до цели: {8000 - data['steps']:,}_\n"
    
    if data.get('water_ml'):
        water_l = data['water_ml'] / 1000
        water_emoji = "💧" if water_l >= 2 else "💦"
        response += f"{water_emoji} Вода: {water_l:.1f}л\n"
    
    if notes:
        response += f"\n📝 Заметки: {notes[:100]}...\n" if len(notes) > 100 else f"\n📝 Заметки: {notes}\n"
    
    response += "\n**Отличная работа сегодня!** 💪\n"
    response += "Завтра утром не забудь сделать утренний чек-ин!"
    
    await message.answer(response, reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")
    await state.clear()

# ============ ФОТО ЕДЫ ============
@router.callback_query(F.data == "food_photo")
async def start_food_photo(callback: CallbackQuery, state: FSMContext):
    """Начало загрузки фото еды"""
    await callback.answer()
    
    keyboard = get_meal_type_keyboard()
    
    await callback.message.answer(
        "📸 **Фото еды**\n\n"
        "Какой прием пищи ты хочешь зафиксировать?",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await state.set_state(FoodPhotoStates.meal_type)

@router.message(FoodPhotoStates.meal_type)
async def process_meal_type(message: Message, state: FSMContext):
    """Обработка типа приема пищи"""
    meal_map = {
        "🌅 Завтрак": "breakfast",
        "☀️ Обед": "lunch",
        "🌙 Ужин": "dinner",
        "🍎 Перекус": "snack"
    }
    
    meal_type = meal_map.get(message.text)
    if not meal_type:
        await message.answer("Пожалуйста, выберите из предложенных вариантов")
        return
    
    await state.update_data(meal_type=meal_type)
    
    await message.answer(
        "📷 Отправь фото блюда\n\n"
        "_Я попробую определить, что это за блюдо и примерную калорийность_",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    await state.set_state(FoodPhotoStates.photo)

@router.message(FoodPhotoStates.photo, F.photo)
async def process_food_photo(message: Message, state: FSMContext):
    """Обработка фото еды с детальным анализом"""
    data = await state.get_data()
    
    photo: PhotoSize = message.photo[-1]
    file_id = photo.file_id
    
    upload_dir = os.path.join(settings.UPLOAD_DIR, str(message.from_user.id))
    os.makedirs(upload_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{data['meal_type']}_{timestamp}.jpg"
    filepath = os.path.join(upload_dir, filename)
    
    bot = message.bot
    try:
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, filepath)
    except Exception as e:
        logger.error(f"Ошибка при сохранении фото: {e}")
        await message.answer("❌ Ошибка при сохранении фото")
        await state.clear()
        return
    
    await message.answer("🤖 Анализирую фото... Это займет несколько секунд")
    
    # Используем улучшенный Vision Service
    from bot.services.vision_service import VisionService
    vision_service = VisionService()
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        # Анализируем фото с учетом данных пользователя
        analysis = await vision_service.analyze_food_photo(filepath, user)
        
        if not analysis.get('success'):
            await message.answer(
                "⚠️ Не удалось точно определить блюдо, но фото сохранено.\n"
                "Вы можете добавить описание вручную."
            )
        
        # Получаем план питания для сравнения
        today = date.today()
        current_week = datetime.utcnow().isocalendar()[1]
        day_number = datetime.utcnow().weekday() + 1
        
        result = await session.execute(
            select(MealPlan).where(
                and_(
                    MealPlan.user_id == user.id,
                    MealPlan.week_number == current_week,
                    MealPlan.day_number == day_number
                )
            )
        )
        meal_plan = result.scalar_one_or_none()
        
        # Сравниваем с планом, если он есть
        comparison = None
        if meal_plan and analysis.get('success'):
            planned_meal = getattr(meal_plan, data['meal_type'], None)
            if planned_meal:
                comparison = await vision_service.compare_with_plan(filepath, planned_meal, user)
        
        # Сохраняем чек-ин
        result = await session.execute(
            select(CheckIn).where(
                and_(
                    CheckIn.user_id == user.id,
                    CheckIn.date >= datetime.combine(today, datetime.min.time()),
                    CheckIn.date <= datetime.combine(today, datetime.max.time())
                )
            )
        )
        checkin = result.scalar_one_or_none()
        
        if not checkin:
            checkin = CheckIn(user_id=user.id)
            session.add(checkin)
        
        # Сохраняем путь к фото и данные анализа
        if data['meal_type'] == 'breakfast':
            checkin.breakfast_photo = filepath
            checkin.breakfast_analysis = analysis if analysis.get('success') else None
        elif data['meal_type'] == 'lunch':
            checkin.lunch_photo = filepath
            checkin.lunch_analysis = analysis if analysis.get('success') else None
        elif data['meal_type'] == 'dinner':
            checkin.dinner_photo = filepath
            checkin.dinner_analysis = analysis if analysis.get('success') else None
        else:
            checkin.snack_photo = filepath
            checkin.snack_analysis = analysis if analysis.get('success') else None
        
        await session.commit()
    
    # Формируем ответ
    meal_names = {
        "breakfast": "Завтрак",
        "lunch": "Обед",
        "dinner": "Ужин",
        "snack": "Перекус"
    }
    
    response = f"✅ **{meal_names[data['meal_type']]} сохранен!**\n\n"
    
    if analysis.get('success'):
        response += f"🍽 **Распознано:** {analysis.get('dish_name', 'Неизвестное блюдо')}\n"
        response += f"📊 **Пищевая ценность:**\n"
        response += f"• Калории: {analysis.get('calories', 0)} ккал\n"
        response += f"• Белки: {analysis.get('protein', 0)}г\n"
        response += f"• Жиры: {analysis.get('fats', 0)}г\n"
        response += f"• Углеводы: {analysis.get('carbs', 0)}г\n"
        
        # Добавляем оценку полезности
        healthiness = analysis.get('healthiness_score', 0)
        if healthiness >= 8:
            response += f"\n🌟 Полезность: {healthiness}/10 - Отличный выбор!\n"
        elif healthiness >= 6:
            response += f"\n⭐ Полезность: {healthiness}/10 - Хорошее блюдо\n"
        else:
            response += f"\n⚠️ Полезность: {healthiness}/10 - Можно найти более полезную альтернативу\n"
        
        # Добавляем сравнение с планом
        if comparison and comparison.get('success'):
            response += f"\n**Соответствие плану:** {comparison['match_emoji']} {comparison['match_text']}\n"
            
            if comparison.get('daily_adjustments'):
                response += "\n**Рекомендации на день:**\n"
                for adjustment in comparison['daily_adjustments']:
                    response += f"• {adjustment}\n"
        
        # Персональные рекомендации
        if analysis.get('personal_recommendations'):
            recs = analysis['personal_recommendations']
            if recs.get('warnings'):
                response += "\n**Предупреждения:**\n"
                for warning in recs['warnings']:
                    response += f"{warning}\n"
            if recs.get('suggestions'):
                response += "\n**Советы:**\n"
                for suggestion in recs['suggestions']:
                    response += f"{suggestion}\n"
    else:
        response += "📸 Фото сохранено для истории\n"
        response += "⚠️ Автоматический анализ временно недоступен\n"
    
    await message.answer(response, parse_mode="Markdown")
    await state.clear()

# ============ БЫСТРЫЕ ФУНКЦИИ ============
@router.callback_query(F.data == "quick_water")
async def quick_water(callback: CallbackQuery):
    """Быстрое добавление воды"""
    await callback.answer()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🥤 +250мл", callback_data="add_water_250"),
            InlineKeyboardButton(text="🥤 +500мл", callback_data="add_water_500"),
            InlineKeyboardButton(text="🥤 +1л", callback_data="add_water_1000")
        ]
    ])
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        today = date.today()
        result = await session.execute(
            select(CheckIn).where(
                and_(
                    CheckIn.user_id == user.id,
                    CheckIn.date >= datetime.combine(today, datetime.min.time()),
                    CheckIn.date <= datetime.combine(today, datetime.max.time())
                )
            )
        )
        checkin = result.scalar_one_or_none()
        
        current_water = checkin.water_ml if checkin and checkin.water_ml else 0
    
    await callback.message.edit_text(
        f"💧 **Трекер воды**\n\n"
        f"Сегодня выпито: {current_water/1000:.1f}л\n\n"
        f"Добавить:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("add_water_"))
async def add_water(callback: CallbackQuery):
    """Добавление воды"""
    amount = int(callback.data.split("_")[2])
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        today = date.today()
        result = await session.execute(
            select(CheckIn).where(
                and_(
                    CheckIn.user_id == user.id,
                    CheckIn.date >= datetime.combine(today, datetime.min.time()),
                    CheckIn.date <= datetime.combine(today, datetime.max.time())
                )
            )
        )
        checkin = result.scalar_one_or_none()
        
        if not checkin:
            checkin = CheckIn(user_id=user.id, water_ml=0)
            session.add(checkin)
        
        checkin.water_ml = (checkin.water_ml or 0) + amount
        await session.commit()
        
        total_water = checkin.water_ml
    
    await callback.answer(f"✅ Добавлено {amount}мл воды!")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🥤 +250мл", callback_data="add_water_250"),
            InlineKeyboardButton(text="🥤 +500мл", callback_data="add_water_500"),
            InlineKeyboardButton(text="🥤 +1л", callback_data="add_water_1000")
        ]
    ])
    
    emoji = "💧" if total_water < 2000 else "💦" if total_water < 3000 else "🌊"
    
    await callback.message.edit_text(
        f"{emoji} **Трекер воды**\n\n"
        f"Сегодня выпито: {total_water/1000:.1f}л\n\n"
        f"{'Отлично! Продолжай в том же духе!' if total_water >= 2000 else 'Добавить:'}",
        reply_markup=keyboard if total_water < 3000 else None,
        parse_mode="Markdown"
    )

# ============ ПРОГРЕСС И ИСТОРИЯ ============
@router.callback_query(F.data == "today_progress")
async def show_today_progress(callback: CallbackQuery):
    """Показать прогресс за сегодня"""
    await callback.answer()
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        today = date.today()
        result = await session.execute(
            select(CheckIn).where(
                and_(
                    CheckIn.user_id == user.id,
                    CheckIn.date >= datetime.combine(today, datetime.min.time()),
                    CheckIn.date <= datetime.combine(today, datetime.max.time())
                )
            )
        )
        checkin = result.scalar_one_or_none()
    
    if not checkin:
        await callback.message.answer(
            "📊 **Прогресс за сегодня**\n\n"
            "Пока нет данных за сегодня.\n"
            "Начните с утреннего чек-ина!",
            parse_mode="Markdown"
        )
        return
    
    response = f"📊 **Прогресс за {today.strftime('%d.%m.%Y')}**\n\n"
    
    if checkin.weight or checkin.sleep_hours or checkin.mood:
        response += "**🌅 Утро:**\n"
        if checkin.weight:
            response += f"• Вес: {checkin.weight} кг\n"
        if checkin.sleep_hours:
            response += f"• Сон: {checkin.sleep_hours} часов\n"
        if checkin.mood:
            mood_emoji = {"good": "😊", "normal": "😐", "bad": "😔"}.get(checkin.mood, "😐")
            response += f"• Самочувствие: {mood_emoji}\n"
        response += "\n"
    
    response += "**📈 Активность:**\n"
    response += f"• Шаги: {checkin.steps:,} / 8,000 🎯\n" if checkin.steps else "• Шаги: не записано\n"
    response += f"• Вода: {checkin.water_ml/1000:.1f}л / 2л 💧\n" if checkin.water_ml else "• Вода: не записано\n"
    response += "\n"
    
    response += "**🍽 Питание:**\n"
    meals_recorded = []
    if checkin.breakfast_photo:
        meals_recorded.append("Завтрак ✅")
    if checkin.lunch_photo:
        meals_recorded.append("Обед ✅")
    if checkin.dinner_photo:
        meals_recorded.append("Ужин ✅")
    if checkin.snack_photo:
        meals_recorded.append("Перекус ✅")
    
    if meals_recorded:
        response += "• " + ", ".join(meals_recorded) + "\n"
    else:
        response += "• Фото еды не загружены\n"
    
    if checkin.notes:
        response += f"\n**📝 Заметки:**\n{checkin.notes}\n"
    
    await callback.message.answer(response, parse_mode="Markdown")

@router.callback_query(F.data == "checkin_history")
async def show_checkin_history(callback: CallbackQuery):
    """Показать историю чек-инов за неделю"""
    await callback.answer()
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        week_ago = datetime.now() - timedelta(days=7)
        result = await session.execute(
            select(CheckIn).where(
                and_(
                    CheckIn.user_id == user.id,
                    CheckIn.date >= week_ago
                )
            ).order_by(CheckIn.date.desc())
        )
        checkins = result.scalars().all()
    
    if not checkins:
        await callback.message.answer(
            "📈 **История за неделю**\n\n"
            "Пока нет данных. Начните делать чек-ины!",
            parse_mode="Markdown"
        )
        return
    
    response = "📈 **История за последние 7 дней**\n\n"
    
    for checkin in checkins:
        date_str = checkin.date.strftime('%d.%m')
        response += f"**{date_str}:**"
        
        if checkin.weight:
            response += f" {checkin.weight}кг"
        if checkin.steps:
            response += f" | {checkin.steps//1000}k шагов"
        if checkin.water_ml:
            response += f" | {checkin.water_ml/1000:.1f}л"
        
        response += "\n"
    
    weights = [c.weight for c in checkins if c.weight]
    if len(weights) > 1:
        weight_change = weights[0] - weights[-1]
        response += f"\n**Изменение веса:** {weight_change:+.1f} кг"
    
    await callback.message.answer(response, parse_mode="Markdown")

# ============ ОБРАБОТЧИКИ ДЛЯ НАПОМИНАНИЙ ============
@router.callback_query(F.data == "start_checkin")
async def start_checkin_from_reminder(callback: CallbackQuery):
    """Начать чек-ин из напоминания"""
    await callback.answer()
    await checkin_menu(callback.message)

@router.callback_query(F.data == "remind_later")
async def remind_later(callback: CallbackQuery):
    """Отложить напоминание"""
    await callback.answer("⏰ Хорошо, напомню позже!")
    await callback.message.edit_text(
        "Напоминание отложено.\n"
        "Используйте /checkin когда будете готовы."
    )

@router.callback_query(F.data == "disable_reminders")
async def disable_reminders(callback: CallbackQuery):
    """Отключить напоминания (заглушка)"""
    await callback.answer()
    await callback.message.edit_text(
        "🔕 Функция отключения напоминаний будет доступна в следующей версии.\n\n"
        "Пока что напоминания можно игнорировать."
    )