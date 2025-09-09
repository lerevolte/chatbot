from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from datetime import datetime, timedelta
from sqlalchemy import select

from database.models import User, Goal
from database.connection import get_session
from bot.utils.calculations import calculate_water_intake, calculate_weekly_progress

router = Router()

@router.message(Command("profile"))
async def show_profile(message: Message):
    """Показать профиль пользователя"""
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
        
        # Рассчитываем прогресс
        weight_diff = abs(user.target_weight - user.current_weight)
        weight_lost = 0
        
        if user.goal == Goal.LOSE_WEIGHT:
            weight_lost = user.current_weight - user.target_weight
            if weight_lost > 0:
                progress_percent = min(100, (weight_lost / weight_diff) * 100) if weight_diff > 0 else 0
            else:
                progress_percent = 0
        elif user.goal == Goal.GAIN_MUSCLE:
            weight_gained = user.current_weight - (user.target_weight - weight_diff)
            progress_percent = min(100, (weight_gained / weight_diff) * 100) if weight_diff > 0 else 0
        else:  # MAINTAIN
            progress_percent = 100
        
        # Определяем статус подписки
        subscription_status = "❌ Подписка не активна"
        days_left = 0
        
        if user.trial_started_at:
            trial_end = user.trial_started_at + timedelta(days=7)
            if datetime.utcnow() < trial_end:
                days_left = (trial_end - datetime.utcnow()).days
                subscription_status = f"🎁 Пробный период (осталось {days_left} дней)"
        elif user.subscription_until and user.subscription_until > datetime.utcnow():
            days_left = (user.subscription_until - datetime.utcnow()).days
            subscription_status = f"✅ Активна (осталось {days_left} дней)"
        
        # Рекомендации
        water_intake = calculate_water_intake(user.current_weight)
        weekly_progress = calculate_weekly_progress(
            user.current_weight, 
            user.target_weight, 
            user.goal
        )
        
        # Определяем эмодзи для цели
        goal_emoji = {
            Goal.LOSE_WEIGHT: "🔥",
            Goal.GAIN_MUSCLE: "💪",
            Goal.MAINTAIN: "⚖️"
        }
        
        # Формируем сообщение профиля
        profile_text = (
            "👤 **Твой профиль**\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"📊 **Основные параметры:**\n"
            f"├ Рост: {user.height} см\n"
            f"├ Текущий вес: {user.current_weight} кг\n"
            f"├ Целевой вес: {user.target_weight} кг\n"
            f"└ Прогресс: ▓{'▓' * int(progress_percent/10)}{'░' * (10-int(progress_percent/10))} {progress_percent:.1f}%\n\n"
            f"🎯 **План питания:**\n"
            f"├ Калории: {user.daily_calories} ккал\n"
            f"├ Белки: {user.daily_protein}г\n"
            f"├ Жиры: {user.daily_fats}г\n"
            f"└ Углеводы: {user.daily_carbs}г\n\n"
            f"💧 **Рекомендации на день:**\n"
            f"├ Вода: {water_intake/1000:.1f}л\n"
            f"├ Шаги: 8000-10000\n"
            f"└ Сон: 7-9 часов\n\n"
            f"{goal_emoji[user.goal]} **Цель на неделю:** "
            f"{'−' if user.goal == Goal.LOSE_WEIGHT else '+'}"
            f"{abs(weekly_progress):.2f} кг\n\n"
            f"💳 **Статус:** {subscription_status}\n\n"
            "━━━━━━━━━━━━━━━\n"
            "📱 **Доступные команды:**\n"
            "• /meal_plan - План питания\n"
            "• /checkin - Ежедневный чек-ин\n"
            "• /stats - Статистика прогресса\n"
            "• /settings - Настройки профиля"
        )
        
        await message.answer(profile_text, parse_mode="Markdown")

@router.message(Command("settings"))
async def settings_menu(message: Message):
    """Меню настроек"""
    async with get_session() as session:
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
        
        settings_text = (
            "⚙️ **Настройки профиля**\n"
            "━━━━━━━━━━━━━━━\n\n"
            "Доступные команды:\n\n"
            "📝 /update_weight - Обновить текущий вес\n"
            "🎯 /update_goal - Изменить цель\n"
            "🍽 /update_meals - Изменить план питания\n"
            "🔄 /reset - Пройти регистрацию заново\n"
            "❌ /delete_account - Удалить аккаунт\n\n"
            "Для изменения других параметров используйте /reset"
        )
        
        await message.answer(settings_text, parse_mode="Markdown")

@router.message(Command("update_weight"))
async def update_weight_start(message: Message):
    """Начало обновления веса"""
    await message.answer(
        "📝 Введите ваш новый вес в кг (например: 75.5)\n"
        "Или отправьте /cancel для отмены"
    )
    # В будущем здесь будет FSM состояние для обновления веса

@router.message(Command("stats"))
async def show_stats(message: Message):
    """Показать статистику"""
    async with get_session() as session:
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
        
        # Подсчет дней в программе
        days_in_program = 0
        if user.created_at:
            days_in_program = (datetime.utcnow() - user.created_at).days
        
        # В будущем здесь будет подсчет реальной статистики из чек-инов
        stats_text = (
            "📈 **Твоя статистика**\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"📅 Дней в программе: {days_in_program}\n"
            f"⚖️ Начальный вес: {user.current_weight} кг\n"
            f"🎯 Цель: {user.target_weight} кг\n\n"
            "📊 **За последнюю неделю:**\n"
            "├ Чек-инов: 0/7\n"
            "├ Средний вес: - кг\n"
            "├ Изменение: - кг\n"
            "└ Выполнено тренировок: 0\n\n"
            "🏆 **Достижения:**\n"
            "• 🔓 Первый день - ✅\n"
            "• 🔒 Неделя без пропусков\n"
            "• 🔒 Месяц в программе\n"
            "• 🔒 Достигнута цель\n\n"
            "Продолжай в том же духе! 💪"
        )
        
        await message.answer(stats_text, parse_mode="Markdown")