from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from datetime import datetime, timedelta
from sqlalchemy import select
import json

from database.models import User, MealPlan, Goal
from database.connection import get_session
from bot.services.meal_generator import MealPlanGenerator  # НОВЫЙ СЕРВИС
from bot.keyboards.meal import get_meal_keyboard, get_day_keyboard  # НОВЫЕ КЛАВИАТУРЫ

router = Router()

@router.message(Command("meal_plan"))
async def show_meal_plan(message: Message):
    """Показать план питания на неделю"""
    async with get_session() as session:
        # Получаем пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user or not user.onboarding_completed:
            await message.answer(
                "❌ Вы еще не прошли регистрацию.\n"
                "Используйте /start для начала работы."
            )
            return
        
        # ========== НОВЫЙ КОД: Проверка существующего плана ==========
        # Проверяем, есть ли у пользователя план на текущую неделю
        current_week = datetime.utcnow().isocalendar()[1]
        result = await session.execute(
            select(MealPlan).where(
                MealPlan.user_id == user.id,
                MealPlan.week_number == current_week,
                MealPlan.is_active == True
            ).order_by(MealPlan.day_number)
        )
        meal_plans = result.scalars().all()
        
        if not meal_plans:
            # ========== НОВЫЙ КОД: Генерация плана через AI ==========
            await message.answer("🔄 Генерирую персональный план питания...")
            
            generator = MealPlanGenerator()
            try:
                # Генерируем план на неделю
                weekly_plan = await generator.generate_weekly_plan(user)
                
                # Сохраняем в БД
                for day_num, day_plan in enumerate(weekly_plan, 1):
                    meal_plan = MealPlan(
                        user_id=user.id,
                        week_number=current_week,
                        day_number=day_num,
                        breakfast=day_plan['breakfast'],
                        lunch=day_plan['lunch'],
                        dinner=day_plan['dinner'],
                        snack=day_plan.get('snack'),
                        total_calories=day_plan['total_calories'],
                        total_protein=day_plan['total_protein'],
                        total_fats=day_plan['total_fats'],
                        total_carbs=day_plan['total_carbs']
                    )
                    session.add(meal_plan)
                
                await session.commit()
                
                # Перезагружаем планы
                result = await session.execute(
                    select(MealPlan).where(
                        MealPlan.user_id == user.id,
                        MealPlan.week_number == current_week,
                        MealPlan.is_active == True
                    ).order_by(MealPlan.day_number)
                )
                meal_plans = result.scalars().all()
                
            except Exception as e:
                await message.answer(
                    "❌ Ошибка при генерации плана. Попробуйте позже.\n"
                    f"Детали: {str(e)}"
                )
                return
        
        # ========== НОВЫЙ КОД: Отображение плана с навигацией ==========
        # Показываем план на сегодня
        today = datetime.utcnow().weekday() + 1  # 1-7
        today_plan = next((p for p in meal_plans if p.day_number == today), meal_plans[0])
        
        await send_day_plan(message, today_plan, user)

async def send_day_plan(message_or_query, meal_plan: MealPlan, user: User):
    """Отправить план на день"""
    # ========== НОВЫЙ КОД: Форматирование плана дня ==========
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    day_name = days[meal_plan.day_number - 1]
    
    text = f"📅 **{day_name}**\n"
    text += f"📊 Всего: {meal_plan.total_calories} ккал | "
    text += f"Б: {meal_plan.total_protein}г | "
    text += f"Ж: {meal_plan.total_fats}г | "
    text += f"У: {meal_plan.total_carbs}г\n"
    text += "━━━━━━━━━━━━━━━\n\n"
    
    # Завтрак
    text += "🌅 **Завтрак**\n"
    text += f"{meal_plan.breakfast['name']}\n"
    text += f"├ Калории: {meal_plan.breakfast['calories']} ккал\n"
    text += f"├ БЖУ: {meal_plan.breakfast['protein']}г/{meal_plan.breakfast['fats']}г/{meal_plan.breakfast['carbs']}г\n"
    if meal_plan.breakfast.get('ingredients'):
        text += f"└ Состав: {', '.join(meal_plan.breakfast['ingredients'])}\n"
    text += "\n"
    
    # Обед
    text += "☀️ **Обед**\n"
    text += f"{meal_plan.lunch['name']}\n"
    text += f"├ Калории: {meal_plan.lunch['calories']} ккал\n"
    text += f"├ БЖУ: {meal_plan.lunch['protein']}г/{meal_plan.lunch['fats']}г/{meal_plan.lunch['carbs']}г\n"
    if meal_plan.lunch.get('ingredients'):
        text += f"└ Состав: {', '.join(meal_plan.lunch['ingredients'])}\n"
    text += "\n"
    
    # Ужин
    text += "🌙 **Ужин**\n"
    text += f"{meal_plan.dinner['name']}\n"
    text += f"├ Калории: {meal_plan.dinner['calories']} ккал\n"
    text += f"├ БЖУ: {meal_plan.dinner['protein']}г/{meal_plan.dinner['fats']}г/{meal_plan.dinner['carbs']}г\n"
    if meal_plan.dinner.get('ingredients'):
        text += f"└ Состав: {', '.join(meal_plan.dinner['ingredients'])}\n"
    
    # Перекус (если есть)
    if meal_plan.snack:
        text += "\n🍎 **Перекус**\n"
        text += f"{meal_plan.snack['name']}\n"
        text += f"└ {meal_plan.snack['calories']} ккал\n"
    
    # ========== НОВЫЙ КОД: Клавиатура навигации ==========
    keyboard = get_day_keyboard(meal_plan.day_number, meal_plan.week_number)
    
    if isinstance(message_or_query, CallbackQuery):
        await message_or_query.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await message_or_query.answer(text, reply_markup=keyboard, parse_mode="Markdown")

# ========== НОВЫЙ КОД: Обработчики callback для навигации ==========
@router.callback_query(F.data.startswith("day_"))
async def navigate_days(callback: CallbackQuery):
    """Навигация по дням недели"""
    _, day_num, week_num = callback.data.split("_")
    day_num = int(day_num)
    week_num = int(week_num)
    
    async with get_session() as session:
        # Получаем пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        # Получаем план на выбранный день
        result = await session.execute(
            select(MealPlan).where(
                MealPlan.user_id == user.id,
                MealPlan.week_number == week_num,
                MealPlan.day_number == day_num,
                MealPlan.is_active == True
            )
        )
        meal_plan = result.scalar_one_or_none()
        
        if meal_plan:
            await send_day_plan(callback, meal_plan, user)
        else:
            await callback.answer("План на этот день не найден", show_alert=True)

# ========== НОВЫЙ КОД: Замена блюда ==========
@router.callback_query(F.data.startswith("replace_"))
async def replace_meal(callback: CallbackQuery):
    """Замена блюда в плане"""
    _, meal_type, day_num, week_num = callback.data.split("_")
    
    await callback.answer("🔄 Генерирую альтернативу...")
    
    async with get_session() as session:
        # Получаем пользователя и план
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        result = await session.execute(
            select(MealPlan).where(
                MealPlan.user_id == user.id,
                MealPlan.week_number == int(week_num),
                MealPlan.day_number == int(day_num)
            )
        )
        meal_plan = result.scalar_one_or_none()
        
        # Генерируем замену через AI
        generator = MealPlanGenerator()
        new_meal = await generator.generate_meal_replacement(
            user, meal_type, meal_plan
        )
        
        # Обновляем план
        if meal_type == "breakfast":
            meal_plan.breakfast = new_meal
        elif meal_type == "lunch":
            meal_plan.lunch = new_meal
        elif meal_type == "dinner":
            meal_plan.dinner = new_meal
        
        # Пересчитываем итоги
        meal_plan.total_calories = (
            meal_plan.breakfast['calories'] + 
            meal_plan.lunch['calories'] + 
            meal_plan.dinner['calories'] +
            (meal_plan.snack['calories'] if meal_plan.snack else 0)
        )
        
        await session.commit()
        await send_day_plan(callback, meal_plan, user)

# ========== НОВЫЙ КОД: Список покупок ==========
@router.callback_query(F.data == "shopping_list")
async def show_shopping_list(callback: CallbackQuery):
    """Показать список покупок на неделю"""
    await callback.answer()
    
    async with get_session() as session:
        # Получаем пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        # Получаем план на неделю
        current_week = datetime.utcnow().isocalendar()[1]
        result = await session.execute(
            select(MealPlan).where(
                MealPlan.user_id == user.id,
                MealPlan.week_number == current_week,
                MealPlan.is_active == True
            )
        )
        meal_plans = result.scalars().all()
        
        # Собираем все ингредиенты
        shopping_list = {}
        for plan in meal_plans:
            for meal in [plan.breakfast, plan.lunch, plan.dinner]:
                if meal and meal.get('ingredients'):
                    for ingredient in meal['ingredients']:
                        # Парсим ингредиент (название и количество)
                        parts = ingredient.split(' - ')
                        name = parts[0]
                        amount = parts[1] if len(parts) > 1 else "по вкусу"
                        
                        if name in shopping_list:
                            shopping_list[name].append(amount)
                        else:
                            shopping_list[name] = [amount]
        
        # Форматируем список
        text = "🛒 **Список покупок на неделю**\n"
        text += "━━━━━━━━━━━━━━━\n\n"
        
        categories = {
            "Мясо и птица": ["курица", "говядина", "свинина", "индейка", "рыба"],
            "Молочные продукты": ["молоко", "творог", "сыр", "йогурт", "кефир"],
            "Овощи": ["помидор", "огурец", "капуста", "морковь", "лук", "картофель"],
            "Фрукты": ["яблоко", "банан", "апельсин", "груша"],
            "Крупы": ["рис", "гречка", "овсянка", "макароны"],
            "Другое": []
        }
        
        categorized = {cat: {} for cat in categories}
        
        for item, amounts in shopping_list.items():
            placed = False
            for category, keywords in categories.items():
                if any(kw in item.lower() for kw in keywords):
                    categorized[category][item] = amounts
                    placed = True
                    break
            if not placed:
                categorized["Другое"][item] = amounts
        
        for category, items in categorized.items():
            if items:
                text += f"**{category}:**\n"
                for item, amounts in items.items():
                    text += f"• {item}: {', '.join(set(amounts))}\n"
                text += "\n"
        
        # ========== ДОБАВЛЕНА КНОПКА ЭКСПОРТА В PDF ==========
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📄 Скачать PDF", callback_data="export_shopping_pdf"),
                InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_plan")
            ]
        ])
        
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

# ========== НОВЫЙ ОБРАБОТЧИК: ЭКСПОРТ В PDF ==========
@router.callback_query(F.data == "export_shopping_pdf")
async def export_shopping_pdf(callback: CallbackQuery):
    """Экспорт списка покупок в PDF"""
    await callback.answer("📄 Генерирую PDF...")
    
    async with get_session() as session:
        # Получаем пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        # Получаем план на неделю
        current_week = datetime.utcnow().isocalendar()[1]
        result = await session.execute(
            select(MealPlan).where(
                MealPlan.user_id == user.id,
                MealPlan.week_number == current_week,
                MealPlan.is_active == True
            )
        )
        meal_plans = result.scalars().all()
        
        if not meal_plans:
            await callback.message.answer("❌ План питания не найден")
            return
        
        # Генерируем PDF
        pdf_generator = PDFGenerator()
        try:
            pdf_path = await pdf_generator.generate_shopping_list_pdf(user, meal_plans)
            
            # Отправляем файл
            pdf_file = FSInputFile(pdf_path, filename=f"shopping_list_{current_week}.pdf")
            await callback.message.answer_document(
                pdf_file,
                caption="📄 Ваш список покупок на неделю\n\n"
                       "Можете распечатать и взять с собой в магазин!"
            )
            
            # Удаляем временный файл
            os.remove(pdf_path)
            
        except Exception as e:
            logger.error(f"Ошибка при генерации PDF: {e}")
            await callback.message.answer(
                "❌ Ошибка при создании PDF. Попробуйте позже."
            )

# ========== НОВЫЙ ОБРАБОТЧИК: ЭКСПОРТ ПЛАНА В PDF ==========
@router.callback_query(F.data == "export_plan_pdf")
async def export_plan_pdf(callback: CallbackQuery):
    """Экспорт полного плана питания в PDF"""
    await callback.answer("📄 Генерирую PDF с планом питания...")
    
    async with get_session() as session:
        # Получаем пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        # Получаем план на неделю
        current_week = datetime.utcnow().isocalendar()[1]
        result = await session.execute(
            select(MealPlan).where(
                MealPlan.user_id == user.id,
                MealPlan.week_number == current_week,
                MealPlan.is_active == True
            ).order_by(MealPlan.day_number)
        )
        meal_plans = result.scalars().all()
        
        if not meal_plans:
            await callback.message.answer("❌ План питания не найден")
            return
        
        # Генерируем PDF
        pdf_generator = PDFGenerator()
        try:
            pdf_path = await pdf_generator.generate_meal_plan_pdf(user, meal_plans)
            
            # Отправляем файл
            pdf_file = FSInputFile(pdf_path, filename=f"meal_plan_week_{current_week}.pdf")
            await callback.message.answer_document(
                pdf_file,
                caption="📄 Ваш план питания на неделю\n\n"
                       "✅ Все блюда с калориями и БЖУ\n"
                       "✅ Список покупок в конце документа\n"
                       "✅ Можете распечатать для удобства"
            )
            
            # Удаляем временный файл
            os.remove(pdf_path)
            
        except Exception as e:
            logger.error(f"Ошибка при генерации PDF: {e}")
            await callback.message.answer(
                "❌ Ошибка при создании PDF. Попробуйте позже."
            )

# ========== НОВЫЙ ОБРАБОТЧИК: РЕГЕНЕРАЦИЯ ПЛАНА ЧЕРЕЗ AI ==========
@router.callback_query(F.data == "regenerate_plan")
async def regenerate_plan(callback: CallbackQuery):
    """Полная регенерация плана питания"""
    await callback.answer()
    
    confirmation_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, создать новый", callback_data="confirm_regenerate"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_regenerate")
        ]
    ])
    
    await callback.message.answer(
        "⚠️ Вы уверены, что хотите создать новый план?\n\n"
        "Текущий план будет полностью заменен новым.",
        reply_markup=confirmation_keyboard
    )

@router.callback_query(F.data == "confirm_regenerate")
async def confirm_regenerate(callback: CallbackQuery):
    """Подтверждение регенерации плана"""
    await callback.answer("🔄 Генерирую новый план...")
    await callback.message.edit_text("🔄 Генерирую новый план питания...\nЭто может занять несколько секунд...")
    
    async with get_session() as session:
        # Получаем пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        # Деактивируем старый план
        current_week = datetime.utcnow().isocalendar()[1]
        result = await session.execute(
            select(MealPlan).where(
                MealPlan.user_id == user.id,
                MealPlan.week_number == current_week
            )
        )
        old_plans = result.scalars().all()
        for plan in old_plans:
            plan.is_active = False
        
        # Генерируем новый план
        generator = MealPlanGenerator()
        try:
            weekly_plan = await generator.generate_weekly_plan(user)
            
            # Сохраняем в БД
            for day_num, day_plan in enumerate(weekly_plan, 1):
                meal_plan = MealPlan(
                    user_id=user.id,
                    week_number=current_week,
                    day_number=day_num,
                    breakfast=day_plan['breakfast'],
                    lunch=day_plan['lunch'],
                    dinner=day_plan['dinner'],
                    snack=day_plan.get('snack'),
                    total_calories=day_plan['total_calories'],
                    total_protein=day_plan['total_protein'],
                    total_fats=day_plan['total_fats'],
                    total_carbs=day_plan['total_carbs']
                )
                session.add(meal_plan)
            
            await session.commit()
            
            await callback.message.edit_text(
                "✅ Новый план питания успешно создан!\n\n"
                "Используйте /meal_plan для просмотра"
            )
            
        except Exception as e:
            logger.error(f"Ошибка при регенерации плана: {e}")
            await callback.message.edit_text(
                "❌ Ошибка при генерации плана. Попробуйте позже."
            )

@router.callback_query(F.data == "cancel_regenerate")
async def cancel_regenerate(callback: CallbackQuery):
    """Отмена регенерации"""
    await callback.answer("Отменено")
    await callback.message.edit_text("План питания не был изменен.")

# ========== ДОБАВЛЯЕМ ЛОГГЕР ==========
import logging
logger = logging.getLogger(__name__)