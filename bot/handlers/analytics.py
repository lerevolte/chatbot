from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, BufferedInputFile
from aiogram.filters import Command
from datetime import datetime
import logging
import os

from database.models import User
from database.connection import get_session
from bot.services.analytics_service import AnalyticsService
from bot.services.plateau_adaptation import PlateauAdaptationService
from bot.services.motivation_service import MotivationService
from sqlalchemy import select

router = Router()
logger = logging.getLogger(__name__)

# ============ КОМАНДА АНАЛИТИКИ ============
@router.message(Command("analytics"))
async def analytics_menu(message: Message):
    """Главное меню аналитики"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Полный отчет", callback_data="full_report"),
            InlineKeyboardButton(text="📈 Проверить плато", callback_data="check_plateau")
        ],
        [
            InlineKeyboardButton(text="💪 Мотивация дня", callback_data="daily_motivation"),
            InlineKeyboardButton(text="📅 Недельный отчет", callback_data="weekly_report")
        ],
        [
            InlineKeyboardButton(text="🎯 Новый челлендж", callback_data="new_challenge"),
            InlineKeyboardButton(text="🏆 Мои достижения", callback_data="my_achievements")
        ],
        [
            InlineKeyboardButton(text="🔄 Адаптировать план", callback_data="adapt_plan"),
            InlineKeyboardButton(text="💡 Рекомендации", callback_data="get_recommendations")
        ]
    ])
    
    await message.answer(
        "📊 **Аналитика и адаптация**\n\n"
        "Здесь вы можете получить детальный анализ вашего прогресса, "
        "проверить наличие плато и получить персональные рекомендации.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# ============ ПОЛНЫЙ ОТЧЕТ ============
@router.callback_query(F.data == "full_report")
async def generate_full_report(callback: CallbackQuery):
    """Генерирует полный отчет с графиками"""
    await callback.answer("Генерирую отчет...")
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.message.answer("❌ Пользователь не найден")
            return
        
        # Генерируем отчет
        analytics_service = AnalyticsService()
        try:
            report_data = await analytics_service.generate_comprehensive_report(user.id)
            
            if report_data:
                # Отправляем график как фото
                photo_file = BufferedInputFile(report_data, filename="report.png")
                await callback.message.answer_photo(
                    photo=photo_file,
                    caption="📊 **Ваш комплексный отчет готов!**\n\n"
                           "Отчет включает:\n"
                           "• График веса с прогнозом\n"
                           "• Карту активности\n"
                           "• Анализ питания и сна\n"
                           "• Прогресс к цели\n"
                           "• Персональные рекомендации\n\n"
                           "_Сохраните отчет для отслеживания прогресса_",
                    parse_mode="Markdown"
                )
            else:
                await callback.message.answer(
                    "❌ Недостаточно данных для генерации отчета.\n"
                    "Продолжайте делать чек-ины!"
                )
        except Exception as e:
            logger.error(f"Ошибка при генерации отчета: {e}")
            await callback.message.answer("❌ Ошибка при генерации отчета")

# ============ ПРОВЕРКА ПЛАТО ============
@router.callback_query(F.data == "check_plateau")
async def check_plateau(callback: CallbackQuery):
    """Проверяет наличие плато"""
    await callback.answer("Анализирую данные...")
    
    plateau_service = PlateauAdaptationService()
    result = await plateau_service.check_and_adapt(callback.from_user.id)
    
    if not result['success']:
        await callback.message.answer("❌ Ошибка при проверке плато")
        return
    
    if result['is_plateau']:
        text = f"⚠️ **Обнаружено плато!**\n\n"
        text += f"Ваш вес не меняется уже {result['plateau_days']} дней.\n\n"
        text += "**Адаптации:**\n"
        
        adaptations = result.get('adaptations', {})
        
        if adaptations.get('calorie_adjustment'):
            adj = adaptations['calorie_adjustment']
            text += f"• Калории: {adj:+d} ккал\n"
        
        if adaptations.get('strategies'):
            text += "\n**Стратегии:**\n"
            for strategy in adaptations['strategies']:
                text += f"• {strategy}\n"
        
        if adaptations.get('activity_changes'):
            text += "\n**Изменения активности:**\n"
            for key, value in adaptations['activity_changes'].items():
                text += f"• {key}: {value}\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🚀 План прорыва", callback_data="breakthrough_plan"),
                InlineKeyboardButton(text="💡 Советы", callback_data="plateau_tips")
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_analytics")
            ]
        ])
        
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await callback.message.answer(
            "✅ **Плато не обнаружено!**\n\n"
            "Ваш прогресс идет по плану. Продолжайте в том же духе!\n\n"
            "💡 Совет: Следите за регулярностью и не забывайте про:\n"
            "• Достаточное потребление воды\n"
            "• Качественный сон 7-9 часов\n"
            "• Регулярную активность",
            parse_mode="Markdown"
        )

# ============ ПЛАН ПРОРЫВА ПЛАТО ============
@router.callback_query(F.data == "breakthrough_plan")
async def breakthrough_plan(callback: CallbackQuery):
    """Генерирует план прорыва плато"""
    await callback.answer("Создаю план прорыва...")
    
    plateau_service = PlateauAdaptationService()
    plan = await plateau_service.generate_breakthrough_plan(callback.from_user.id)
    
    if plan['success']:
        text = "🚀 **План прорыва плато (7 дней)**\n\n"
        
        for day_plan in plan['plan']['days']:
            text += f"**День {day_plan['day']}:**\n"
            text += f"• Калории: {day_plan['calories']} ккал ({day_plan['type']})\n"
            
            if 'cardio' in day_plan:
                text += f"• Кардио: {day_plan['cardio']}\n"
            if 'strength' in day_plan:
                text += f"• Силовая: {day_plan['strength']}\n"
            if 'hiit' in day_plan:
                text += f"• HIIT: {day_plan['hiit']}\n"
            if 'rest' in day_plan:
                text += f"• День отдыха\n"
            text += "\n"
        
        text += "**Важные правила:**\n"
        for rec in plan['plan']['recommendations']:
            text += f"• {rec}\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Начать план", callback_data="start_breakthrough"),
                InlineKeyboardButton(text="📥 Скачать PDF", callback_data="download_breakthrough")
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="check_plateau")
            ]
        ])
        
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await callback.message.answer("❌ Не удалось создать план прорыва")

# ============ МОТИВАЦИЯ ============
@router.callback_query(F.data == "daily_motivation")
async def daily_motivation(callback: CallbackQuery):
    """Показывает мотивацию дня"""
    await callback.answer()
    
    motivation_service = MotivationService()
    motivation = await motivation_service.get_daily_motivation(callback.from_user.id)
    
    if motivation['success']:
        text = "🌟 **Мотивация дня**\n\n"
        text += f"_{motivation['quote']}_\n\n"
        
        if motivation['streak'] > 0:
            text += f"🔥 Твоя серия: {motivation['streak']} дней\n\n"
        
        text += f"{motivation['tip']}\n\n"
        
        if motivation['achievements']:
            text += "🏆 **Новые достижения:**\n"
            for achievement in motivation['achievements']:
                text += f"{achievement['emoji']} {achievement['text']}\n"
            text += "\n"
        
        if motivation['challenge']:
            text += f"🎯 **Челлендж дня:**\n"
            text += f"{motivation['challenge']['name']}\n"
            text += f"Задание: {motivation['challenge']['task']}\n"
            text += f"Награда: {motivation['challenge']['reward']}\n"
        
        await callback.message.answer(text, parse_mode="Markdown")
    else:
        await callback.message.answer("❌ Не удалось получить мотивацию")

# ============ НЕДЕЛЬНЫЙ ОТЧЕТ ============
@router.callback_query(F.data == "weekly_report")
async def weekly_report(callback: CallbackQuery):
    """Генерирует недельный отчет"""
    await callback.answer("Готовлю отчет...")
    
    motivation_service = MotivationService()
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            report = await motivation_service.generate_weekly_report(user.id)
            await callback.message.answer(report, parse_mode="Markdown")
        else:
            await callback.message.answer("❌ Пользователь не найден")

# ============ АДАПТАЦИЯ ПЛАНА ============
@router.callback_query(F.data == "adapt_plan")
async def adapt_plan(callback: CallbackQuery):
    """Адаптирует план питания и тренировок"""
    await callback.answer("Анализирую и адаптирую...")
    
    plateau_service = PlateauAdaptationService()
    
    # Проверяем, нужен ли диетический перерыв
    needs_break = await plateau_service.suggest_diet_break(callback.from_user.id)
    
    if needs_break:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Начать диет-перерыв", callback_data="start_diet_break"),
                InlineKeyboardButton(text="❌ Продолжить план", callback_data="continue_plan")
            ]
        ])
        
        await callback.message.answer(
            "🔄 **Рекомендуется диетический перерыв!**\n\n"
            "Вы находитесь на дефиците калорий длительное время.\n"
            "Диет-перерыв на 7-14 дней поможет:\n"
            "• Восстановить метаболизм\n"
            "• Снизить стресс\n"
            "• Подготовиться к новому этапу\n\n"
            "Во время перерыва:\n"
            "• Калории на уровне поддержки\n"
            "• Сохранение тренировок\n"
            "• Фокус на восстановлении",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    else:
        # Обычная адаптация
        result = await plateau_service.check_and_adapt(callback.from_user.id)
        
        if result['success'] and result.get('is_plateau'):
            text = "✅ **План успешно адаптирован!**\n\n"
            
            if result.get('adaptations'):
                adaptations = result['adaptations']
                
                if adaptations.get('calorie_adjustment'):
                    adj = adaptations['calorie_adjustment']
                    text += f"📊 Калории: {adj:+d} ккал\n"
                
                if adaptations.get('strategies'):
                    text += "\n**Применены стратегии:**\n"
                    for strategy in adaptations['strategies']:
                        text += f"• {strategy}\n"
                
                if adaptations.get('activity_changes'):
                    text += "\n**Рекомендации по активности:**\n"
                    for key, value in adaptations['activity_changes'].items():
                        text += f"• {value}\n"
            
            text += "\nИзменения вступят в силу со следующего дня.\n"
            text += "Используйте /meal_plan для просмотра обновленного плана питания."
            
            await callback.message.answer(text, parse_mode="Markdown")
        elif result['success']:
            await callback.message.answer(
                "✅ **Анализ завершен**\n\n"
                "Ваш прогресс идет по плану!\n"
                "Адаптация пока не требуется.\n\n"
                "Продолжайте следовать текущему плану.",
                parse_mode="Markdown"
            )
        else:
            await callback.message.answer("❌ Произошла ошибка при анализе")


@router.callback_query(F.data == "start_diet_break")
async def start_diet_break(callback: CallbackQuery):
    """Начинает диетический перерыв"""
    await callback.answer("Активирую диет-перерыв...")
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Увеличиваем калории до уровня поддержки
            calories, protein, fats, carbs = calculate_calories_and_macros(
                gender=user.gender,
                age=user.age,
                height=user.height,
                weight=user.current_weight,
                activity_level=user.activity_level,
                goal=Goal.MAINTAIN  # Временно переключаем на поддержание
            )
            
            # Сохраняем старые значения для возврата
            old_calories = user.daily_calories
            old_goal = user.goal
            
            user.daily_calories = calories
            user.daily_protein = protein
            user.daily_fats = fats
            user.daily_carbs = carbs
            
            # Сохраняем информацию о диет-перерыве
            user.reminder_settings = user.reminder_settings or {}
            user.reminder_settings['diet_break'] = {
                'started': datetime.now().isoformat(),
                'old_calories': old_calories,
                'old_goal': old_goal.value,
                'duration': 14  # дней
            }
            
            await session.commit()
            
            await callback.message.answer(
                "✅ **Диет-перерыв активирован!**\n\n"
                f"📊 Новые параметры на 14 дней:\n"
                f"• Калории: {calories} ккал (поддержание)\n"
                f"• Белки: {protein}г\n"
                f"• Жиры: {fats}г\n"
                f"• Углеводы: {carbs}г\n\n"
                "**Рекомендации:**\n"
                "• Продолжайте тренировки\n"
                "• Фокус на восстановлении\n"
                "• Не беспокойтесь о небольшом увеличении веса\n"
                "• Это восстановление, а не откат!\n\n"
                "Через 14 дней вернемся к работе над целью 💪",
                parse_mode="Markdown"
            )

@router.callback_query(F.data == "continue_plan")
async def continue_plan(callback: CallbackQuery):
    """Продолжает текущий план без изменений"""
    await callback.answer()
    await callback.message.answer(
        "👍 **План продолжается без изменений**\n\n"
        "Вы решили продолжить без диет-перерыва.\n"
        "Следите за самочувствием и при необходимости используйте /analytics",
        parse_mode="Markdown"
    )

# ============ СКАЧИВАНИЕ PDF ПЛАНА ПРОРЫВА ============
@router.callback_query(F.data == "download_breakthrough")
async def download_breakthrough_pdf(callback: CallbackQuery):
    """Скачивает PDF с планом прорыва плато"""
    await callback.answer("Генерирую PDF...")
    
    from bot.services.pdf_generator import PDFGenerator
    from aiogram.types import FSInputFile
    
    plateau_service = PlateauAdaptationService()
    pdf_generator = PDFGenerator()
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Получаем план прорыва
            breakthrough_plan = await plateau_service.generate_breakthrough_plan(callback.from_user.id)
            
            if breakthrough_plan['success']:
                # Генерируем PDF
                pdf_path = await pdf_generator.generate_breakthrough_pdf(user, breakthrough_plan['plan'])
                
                # Отправляем файл
                pdf_file = FSInputFile(pdf_path, filename=f"breakthrough_plan_{datetime.now().strftime('%Y%m%d')}.pdf")
                await callback.message.answer_document(
                    pdf_file,
                    caption="📄 **План прорыва плато на 7 дней**\n\n"
                           "Следуйте этому плану для преодоления застоя.\n"
                           "Включает:\n"
                           "• Циклирование калорий\n"
                           "• План тренировок\n"
                           "• Важные рекомендации",
                    parse_mode="Markdown"
                )
                
                # Удаляем временный файл
                os.remove(pdf_path)
            else:
                await callback.message.answer("❌ Ошибка при генерации PDF")

# ============ НАЧАТЬ ПЛАН ПРОРЫВА ============
@router.callback_query(F.data == "start_breakthrough")
async def start_breakthrough(callback: CallbackQuery):
    """Активирует план прорыва плато"""
    await callback.answer("Активирую план прорыва...")
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Сохраняем информацию о начале плана прорыва
            user.reminder_settings = user.reminder_settings or {}
            user.reminder_settings['breakthrough_plan'] = {
                'started': datetime.now().isoformat(),
                'day': 1,
                'total_days': 7
            }
            
            await session.commit()
            
            await callback.message.answer(
                "🚀 **План прорыва активирован!**\n\n"
                "Следующие 7 дней будут интенсивными:\n"
                "• Циклирование калорий\n"
                "• Чередование нагрузок\n"
                "• Фокус на результате\n\n"
                "Я буду напоминать о плане каждый день.\n"
                "Используйте /checkin для отслеживания прогресса.\n\n"
                "Вместе прорвем это плато! 💪",
                parse_mode="Markdown"
            )

# ============ НОВЫЙ ЧЕЛЛЕНДЖ ============
@router.callback_query(F.data == "new_challenge")
async def new_challenge(callback: CallbackQuery):
    """Предлагает новый челлендж"""
    await callback.answer()
    
    motivation_service = MotivationService()
    challenge = await motivation_service._get_active_challenge(callback.from_user.id)
    
    if challenge:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять челлендж", callback_data="accept_challenge"),
                InlineKeyboardButton(text="🔄 Другой", callback_data="new_challenge")
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_analytics")
            ]
        ])
        
        await callback.message.answer(
            f"🎯 **Челлендж дня**\n\n"
            f"**{challenge['name']}**\n"
            f"Задание: {challenge['task']}\n"
            f"Награда: {challenge['reward']}\n\n"
            f"Принимаете вызов?",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

@router.callback_query(F.data == "accept_challenge")
async def accept_challenge(callback: CallbackQuery):
    """Принимает челлендж"""
    await callback.answer("Челлендж принят!")
    
    await callback.message.answer(
        "✅ **Челлендж принят!**\n\n"
        "Отлично! Покажи на что способен!\n"
        "Выполни задание и отметься в вечернем чек-ине.\n\n"
        "Удачи! 🔥",
        parse_mode="Markdown"
    )

# ============ МОИ ДОСТИЖЕНИЯ ============
@router.callback_query(F.data == "my_achievements")
async def my_achievements(callback: CallbackQuery):
    """Показывает достижения пользователя"""
    await callback.answer()
    
    motivation_service = MotivationService()
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            stats = await motivation_service._get_user_stats(user.id)
            achievements = await motivation_service._check_achievements(user.id)
            
            text = "🏆 **Твои достижения**\n\n"
            
            # Основные достижения
            if stats['total_checkins'] >= 1:
                text += "✅ Первый чек-ин\n"
            if stats['total_checkins'] >= 7:
                text += "🔥 Неделя активности\n"
            if stats['total_checkins'] >= 30:
                text += "⭐ Месяц дисциплины\n"
            if stats['total_checkins'] >= 90:
                text += "👑 Легенда (90 дней)\n"
            
            # Достижения по весу
            if stats.get('weight_change', 0) <= -5:
                text += "🏅 Минус 5 кг\n"
            if stats.get('weight_change', 0) <= -10:
                text += "🏆 Минус 10 кг\n"
            
            # Серии
            if stats.get('streak_days', 0) >= 7:
                text += f"🔥 Серия {stats['streak_days']} дней\n"
            
            text += f"\n**Статистика:**\n"
            text += f"• Всего чек-инов: {stats['total_checkins']}\n"
            text += f"• Текущая серия: {stats.get('streak_days', 0)} дней\n"
            
            if stats.get('weight_change'):
                text += f"• Изменение веса: {stats['weight_change']:.1f} кг\n"
            
            text += f"\n_Продолжай в том же духе!_ 💪"
            
            await callback.message.answer(text, parse_mode="Markdown")
            
# ============ РЕКОМЕНДАЦИИ ============
@router.callback_query(F.data == "get_recommendations")
async def get_recommendations(callback: CallbackQuery):
    """Показывает персональные рекомендации"""
    await callback.answer("Анализирую данные...")
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.message.answer("❌ Пользователь не найден")
            return
        
        analytics_service = AnalyticsService()
        analysis = await analytics_service.analyze_user_progress(user.id)
        
        text = "💡 **Персональные рекомендации**\n\n"
        
        if analysis['is_plateau']:
            text += f"⚠️ Обнаружено плато ({analysis['plateau_days']} дней)\n"
            text += f"Рекомендуем изменить подход к питанию и тренировкам\n\n"
        
        if analysis.get('calorie_adjustment'):
            adj = analysis['calorie_adjustment']
            if adj > 0:
                text += f"📈 **Питание:** Увеличьте калории на {adj} ккал\n\n"
            else:
                text += f"📉 **Питание:** Уменьшите калории на {abs(adj)} ккал\n\n"
        
        if analysis.get('activity_recommendation'):
            text += f"🏃 **Активность:** {analysis['activity_recommendation']}\n\n"
        
        if analysis.get('sleep_recommendation'):
            text += f"😴 **Сон:** {analysis['sleep_recommendation']}\n\n"
        
        text += f"💪 {analysis.get('motivation', 'Продолжайте в том же духе!')}"
        
        await callback.message.answer(text, parse_mode="Markdown")

# ============ ВСПОМОГАТЕЛЬНЫЕ CALLBACK ============
@router.callback_query(F.data == "back_to_analytics")
async def back_to_analytics(callback: CallbackQuery):
    """Возврат в меню аналитики"""
    await analytics_menu(callback.message)

@router.callback_query(F.data == "plateau_tips")
async def plateau_tips(callback: CallbackQuery):
    """Показывает советы при плато"""
    motivation_service = MotivationService()
    tips = await motivation_service.get_plateau_motivation(callback.from_user.id)
    await callback.message.answer(tips, parse_mode="Markdown")