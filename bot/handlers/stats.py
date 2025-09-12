from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command
from datetime import datetime, timedelta
from sqlalchemy import select, and_, func
import logging
import os

from database.models import User, CheckIn
from database.connection import get_session
from bot.services.charts_service import ChartsService
from bot.config import settings

router = Router()
logger = logging.getLogger(__name__)

@router.message(Command("stats"))
async def stats_menu(message: Message):
    """Меню статистики с графиками"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 График веса", callback_data="chart_weight"),
            InlineKeyboardButton(text="🚶 Активность", callback_data="chart_activity")
        ],
        [
            InlineKeyboardButton(text="💤 Сон и настроение", callback_data="chart_sleep"),
            InlineKeyboardButton(text="📈 Общая сводка", callback_data="chart_summary")
        ],
        [
            InlineKeyboardButton(text="🎯 Прогресс к цели", callback_data="goal_progress"),
            InlineKeyboardButton(text="📅 Статистика месяца", callback_data="month_stats")
        ]
    ])
    
    await message.answer(
        "📊 **Статистика и аналитика**\n\n"
        "Выберите, какую статистику хотите посмотреть:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "chart_weight")
async def show_weight_chart(callback: CallbackQuery):
    """Показать график веса"""
    await callback.answer("Генерирую график веса...")
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.message.answer("❌ Пользователь не найден")
            return
        
        # Генерируем график
        charts_service = ChartsService()
        chart_data = await charts_service.generate_weight_chart(user.id, days=30)
        
        if not chart_data:
            await callback.message.answer(
                "📊 Недостаточно данных для построения графика веса.\n"
                "Нужно минимум 2 записи веса за последние 30 дней."
            )
            return
        
        # Отправляем график
        await callback.message.answer_photo(
            photo=chart_data,
            caption="📊 **График изменения веса за 30 дней**\n\n"
                    "🔵 Синяя линия - ваш вес\n"
                    "🔴 Красная линия - целевой вес\n"
                    "➖ Пунктир - линия тренда"
        )

@router.callback_query(F.data == "chart_activity")
async def show_activity_chart(callback: CallbackQuery):
    """Показать график активности"""
    await callback.answer("Генерирую график активности...")
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        charts_service = ChartsService()
        chart_data = await charts_service.generate_activity_chart(user.id, days=7)
        
        if not chart_data:
            await callback.message.answer(
                "📊 Недостаточно данных для графика активности.\n"
                "Начните записывать шаги и потребление воды!"
            )
            return
        
        await callback.message.answer_photo(
            photo=chart_data,
            caption="📊 **График активности за неделю**\n\n"
                    "📊 Столбцы - количество шагов\n"
                    "💧 Синие столбцы - потребление воды\n"
                    "🎯 Пунктирные линии - целевые значения"
        )

@router.callback_query(F.data == "chart_sleep")
async def show_sleep_chart(callback: CallbackQuery):
    """Показать график сна и настроения"""
    await callback.answer("Генерирую график сна...")
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        charts_service = ChartsService()
        chart_data = await charts_service.generate_sleep_chart(user.id, days=14)
        
        if not chart_data:
            await callback.message.answer(
                "📊 Недостаточно данных о сне.\n"
                "Записывайте часы сна в утреннем чек-ине!"
            )
            return
        
        await callback.message.answer_photo(
            photo=chart_data,
            caption="💤 **График сна и настроения за 2 недели**\n\n"
                    "📊 Верхний график - часы сна\n"
                    "😊 Нижний график - настроение\n"
                    "➖ Пунктир - рекомендуемые границы сна (7-9 часов)"
        )

@router.callback_query(F.data == "chart_summary")
async def show_summary_chart(callback: CallbackQuery):
    """Показать общую сводку"""
    await callback.answer("Генерирую общую сводку...")
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        charts_service = ChartsService()
        chart_data = await charts_service.generate_progress_summary(user.id)
        
        if not chart_data:
            await callback.message.answer(
                "📊 Недостаточно данных для сводки.\n"
                "Продолжайте вести чек-ины!"
            )
            return
        
        await callback.message.answer_photo(
            photo=chart_data,
            caption="📊 **Общая сводка прогресса**\n\n"
                    "Все ключевые метрики в одном месте:\n"
                    "• Динамика веса\n"
                    "• Активность за неделю\n"
                    "• Потребление воды\n"
                    "• Общая статистика"
        )

@router.callback_query(F.data == "goal_progress")
async def show_goal_progress(callback: CallbackQuery):
    """Показать прогресс к цели"""
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        # Получаем первый и последний вес
        result = await session.execute(
            select(CheckIn).where(
                and_(
                    CheckIn.user_id == user.id,
                    CheckIn.weight.isnot(None)
                )
            ).order_by(CheckIn.date)
        )
        checkins = result.scalars().all()
        
        if len(checkins) < 2:
            await callback.message.answer(
                "📊 Недостаточно данных для оценки прогресса.\n"
                "Нужно минимум 2 записи веса."
            )
            return
        
        start_weight = checkins[0].weight
        current_weight = checkins[-1].weight
        target_weight = user.target_weight
        
        # Рассчитываем прогресс
        total_to_lose = abs(start_weight - target_weight)
        lost = abs(start_weight - current_weight)
        progress_percent = (lost / total_to_lose * 100) if total_to_lose > 0 else 0
        
        # Прогноз достижения цели
        days_passed = (checkins[-1].date - checkins[0].date).days
        if days_passed > 0 and lost > 0:
            rate_per_day = lost / days_passed
            days_to_goal = abs(current_weight - target_weight) / rate_per_day if rate_per_day > 0 else 999
            estimated_date = datetime.now() + timedelta(days=int(days_to_goal))
        else:
            estimated_date = None
        
        # Формируем сообщение
        progress_bar = "▓" * int(progress_percent/10) + "░" * (10-int(progress_percent/10))
        
        response = f"🎯 **Прогресс к цели**\n\n"
        response += f"📊 Начальный вес: {start_weight} кг\n"
        response += f"⚖️ Текущий вес: {current_weight} кг\n"
        response += f"🎯 Целевой вес: {target_weight} кг\n\n"
        response += f"Прогресс: {progress_bar} {progress_percent:.1f}%\n\n"
        
        if user.goal == "lose_weight":
            response += f"✅ Сброшено: {lost:.1f} кг\n"
            response += f"📉 Осталось: {abs(current_weight - target_weight):.1f} кг\n"
        elif user.goal == "gain_muscle":
            response += f"✅ Набрано: {lost:.1f} кг\n"
            response += f"📈 Осталось: {abs(target_weight - current_weight):.1f} кг\n"
        
        if estimated_date and days_to_goal < 365:
            response += f"\n📅 Прогноз достижения цели: {estimated_date.strftime('%d.%m.%Y')}\n"
            response += f"⏱ Осталось дней: {int(days_to_goal)}\n"
        
        # Рекомендации
        if progress_percent < 25:
            response += "\n💡 Вы в начале пути! Продолжайте следовать плану."
        elif progress_percent < 50:
            response += "\n💪 Отличный прогресс! Вы на правильном пути."
        elif progress_percent < 75:
            response += "\n🔥 Вы уже прошли больше половины! Не сдавайтесь!"
        else:
            response += "\n🏆 Вы почти у цели! Последний рывок!"
        
        await callback.message.answer(response, parse_mode="Markdown")

@router.callback_query(F.data == "month_stats")
async def show_month_stats(callback: CallbackQuery):
    """Показать статистику за месяц"""
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        # Получаем данные за последние 30 дней
        month_ago = datetime.now() - timedelta(days=30)
        result = await session.execute(
            select(CheckIn).where(
                and_(
                    CheckIn.user_id == user.id,
                    CheckIn.date >= month_ago
                )
            )
        )
        checkins = result.scalars().all()
        
        if not checkins:
            await callback.message.answer(
                "📊 Нет данных за последний месяц.\n"
                "Начните делать чек-ины!"
            )
            return
        
        # Подсчитываем статистику
        total_checkins = len(checkins)
        weights = [c.weight for c in checkins if c.weight]
        steps = [c.steps for c in checkins if c.steps]
        water = [c.water_ml for c in checkins if c.water_ml]
        sleep_hours = [c.sleep_hours for c in checkins if c.sleep_hours]
        
        # Подсчет выполнения целей
        days_8k_steps = sum(1 for s in steps if s >= 8000)
        days_2l_water = sum(1 for w in water if w >= 2000)
        days_good_sleep = sum(1 for s in sleep_hours if 7 <= s <= 9)
        
        # Изменение веса
        weight_change = 0
        if len(weights) >= 2:
            weight_change = weights[-1] - weights[0]
        
        # Подсчет фото еды
        meal_photos = sum(1 for c in checkins if any([
            c.breakfast_photo, c.lunch_photo, c.dinner_photo, c.snack_photo
        ]))
        
        response = "📊 **Статистика за последние 30 дней**\n\n"
        
        response += f"📝 **Чек-ины:** {total_checkins}/30 ({total_checkins/30*100:.0f}%)\n\n"
        
        if weights:
            response += f"⚖️ **Вес:**\n"
            response += f"• Изменение: {weight_change:+.1f} кг\n"
            response += f"• Средний: {sum(weights)/len(weights):.1f} кг\n"
            response += f"• Мин/Макс: {min(weights):.1f}/{max(weights):.1f} кг\n\n"
        
        if steps:
            response += f"🚶 **Шаги:**\n"
            response += f"• Среднее: {sum(steps)/len(steps):.0f} шагов/день\n"
            response += f"• Дней с 8000+: {days_8k_steps} ({days_8k_steps/30*100:.0f}%)\n"
            response += f"• Всего: {sum(steps):,} шагов\n\n"
        
        if water:
            response += f"💧 **Вода:**\n"
            response += f"• Среднее: {sum(water)/len(water)/1000:.1f} л/день\n"
            response += f"• Дней с 2л+: {days_2l_water} ({days_2l_water/30*100:.0f}%)\n\n"
        
        if sleep_hours:
            response += f"💤 **Сон:**\n"
            response += f"• Среднее: {sum(sleep_hours)/len(sleep_hours):.1f} часов\n"
            response += f"• Дней с 7-9ч: {days_good_sleep} ({days_good_sleep/30*100:.0f}%)\n\n"
        
        response += f"📸 **Фото еды:** {meal_photos} записей\n\n"
        
        # Оценка общего прогресса
        completion_rate = total_checkins / 30
        if completion_rate >= 0.9:
            response += "🏆 **Отличная дисциплина!** Вы делаете чек-ины почти каждый день!"
        elif completion_rate >= 0.7:
            response += "✅ **Хороший результат!** Старайтесь не пропускать чек-ины."
        elif completion_rate >= 0.5:
            response += "📈 **Есть прогресс!** Попробуйте делать чек-ины регулярнее."
        else:
            response += "💡 **Совет:** Регулярные чек-ины помогут лучше отслеживать прогресс!"
        
        await callback.message.answer(response, parse_mode="Markdown")