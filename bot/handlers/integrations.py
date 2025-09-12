from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, time
from sqlalchemy import select
import logging

from database.models import User
from database.connection import get_session
from bot.services.fitness_tracker_integration import FitnessIntegrationService
from bot.services.smart_reminder import SmartReminderService

router = Router()
logger = logging.getLogger(__name__)

# Состояния для настроек
class SettingsStates(StatesGroup):
    timezone = State()
    morning_reminder_time = State()
    evening_reminder_time = State()
    google_fit_auth = State()

# ============ ИНТЕГРАЦИИ ============
@router.message(Command("integrations"))
async def integrations_menu(message: Message):
    """Меню управления интеграциями"""
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer("❌ Пользователь не найден. Используйте /start")
            return
        
        connected = user.connected_services or []
        
        # Формируем клавиатуру
        keyboard_buttons = []
        
        # Google Fit
        if "google_fit" in connected:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text="✅ Google Fit (подключен)",
                    callback_data="sync_google_fit"
                ),
                InlineKeyboardButton(
                    text="❌ Отключить",
                    callback_data="disconnect_google_fit"
                )
            ])
        else:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text="🔗 Подключить Google Fit",
                    callback_data="connect_google_fit"
                )
            ])
        
        # Apple Health (заглушка)
        keyboard_buttons.append([
            InlineKeyboardButton(
                text="🍎 Apple Health (скоро)",
                callback_data="coming_soon"
            )
        ])
        
        # Fitbit (заглушка)
        keyboard_buttons.append([
            InlineKeyboardButton(
                text="⌚ Fitbit (скоро)",
                callback_data="coming_soon"
            )
        ])
        
        # Синхронизация всех
        if connected:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text="🔄 Синхронизировать все",
                    callback_data="sync_all"
                )
            ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        text = "🔗 **Интеграции с фитнес-трекерами**\n\n"
        
        if connected:
            text += "✅ Подключенные сервисы:\n"
            for service in connected:
                text += f"• {service.replace('_', ' ').title()}\n"
            text += "\nДанные синхронизируются автоматически каждый день."
        else:
            text += "У вас пока нет подключенных сервисов.\n"
            text += "Подключите фитнес-трекер для автоматического импорта данных!"
        
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data == "connect_google_fit")
async def connect_google_fit(callback: CallbackQuery, state: FSMContext):
    """Начало подключения Google Fit"""
    await callback.answer()
    
    # В реальном приложении здесь будет OAuth flow
    await callback.message.answer(
        "🔗 **Подключение Google Fit**\n\n"
        "Для подключения Google Fit:\n"
        "1. Перейдите по ссылке авторизации\n"
        "2. Войдите в свой Google аккаунт\n"
        "3. Разрешите доступ к данным фитнеса\n"
        "4. Скопируйте код авторизации\n"
        "5. Отправьте код сюда\n\n"
        "⚠️ В данной версии интеграция находится в разработке.\n"
        "Используйте /checkin для ручного ввода данных."
    )
    
    # В продакшене здесь будет реальная ссылка
    # integration_service = FitnessIntegrationService()
    # auth_url = await integration_service.connect_service(callback.from_user.id, "google_fit")
    # await callback.message.answer(f"Перейдите по ссылке: {auth_url}")
    # await state.set_state(SettingsStates.google_fit_auth)

@router.callback_query(F.data == "sync_google_fit")
async def sync_google_fit(callback: CallbackQuery):
    """Синхронизация данных из Google Fit"""
    await callback.answer("Синхронизация...")
    
    integration_service = FitnessIntegrationService()
    success = await integration_service.sync_all(callback.from_user.id)
    
    if success.get("google_fit"):
        await callback.message.answer(
            "✅ Данные из Google Fit успешно синхронизированы!\n\n"
            "Обновлены:\n"
            "• Шаги за последние 7 дней\n"
            "• Данные о весе\n"
            "• Активность и калории"
        )
    else:
        await callback.message.answer(
            "⚠️ Не удалось синхронизировать данные.\n"
            "Попробуйте позже или переподключите сервис."
        )

@router.callback_query(F.data == "sync_all")
async def sync_all_services(callback: CallbackQuery):
    """Синхронизация всех подключенных сервисов"""
    await callback.answer("Синхронизация всех сервисов...")
    
    integration_service = FitnessIntegrationService()
    results = await integration_service.sync_all(callback.from_user.id)
    
    if any(results.values()):
        success_services = [s for s, status in results.items() if status]
        text = "✅ Синхронизация завершена!\n\n"
        text += "Обновлены данные из:\n"
        for service in success_services:
            text += f"• {service.replace('_', ' ').title()}\n"
    else:
        text = "⚠️ Не удалось синхронизировать данные.\nПроверьте подключения."
    
    await callback.message.answer(text)

@router.callback_query(F.data == "disconnect_google_fit")
async def disconnect_google_fit(callback: CallbackQuery):
    """Отключение Google Fit"""
    await callback.answer()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, отключить", callback_data="confirm_disconnect_gf"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_disconnect")
        ]
    ])
    
    await callback.message.answer(
        "⚠️ Вы уверены, что хотите отключить Google Fit?\n\n"
        "Автоматическая синхронизация данных будет остановлена.",
        reply_markup=keyboard
    )

# ============ НАСТРОЙКИ НАПОМИНАНИЙ ============
@router.message(Command("reminder_settings"))
async def reminder_settings_menu(message: Message):
    """Меню настроек напоминаний"""
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer("❌ Сначала нужно пройти регистрацию. Используйте /start")
            return
        
        settings = user.reminder_settings or {}
        timezone = user.timezone or "UTC"
        style = user.reminder_style or "friendly"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=f"🌍 Часовой пояс: {timezone}", callback_data="set_timezone"),
            ],
            [
                InlineKeyboardButton(text="⏰ Время утреннего напоминания", callback_data="set_morning_time"),
                InlineKeyboardButton(text="🌙 Время вечернего напоминания", callback_data="set_evening_time")
            ],
            [
                InlineKeyboardButton(text=f"💬 Стиль: {style}", callback_data="set_reminder_style"),
            ],
            [
                InlineKeyboardButton(text="💧 Напоминания о воде", callback_data="toggle_water_reminders"),
                InlineKeyboardButton(text="🔕 Отключить все", callback_data="disable_all_reminders")
            ]
        ])
        
        text = "⏰ **Настройки напоминаний**\n\n"
        text += f"🌍 Часовой пояс: {timezone}\n"
        text += f"🌅 Утреннее: {settings.get('morning_time', '08:00')}\n"
        text += f"🌙 Вечернее: {settings.get('evening_time', '20:00')}\n"
        text += f"💧 Напоминания о воде: {'✅ Вкл' if settings.get('water_reminders', True) else '❌ Выкл'}\n"
        text += f"💬 Стиль: {style}\n\n"
        
        style_descriptions = {
            "friendly": "Дружелюбный - мягкие и позитивные напоминания",
            "motivational": "Мотивирующий - вдохновляющие сообщения",
            "strict": "Строгий - четкие и краткие напоминания"
        }
        text += f"_{style_descriptions.get(style, '')}_"
        
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data == "set_timezone")
async def set_timezone(callback: CallbackQuery, state: FSMContext):
    """Установка часового пояса"""
    await callback.answer()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="UTC+0 (Лондон)", callback_data="tz_UTC"),
            InlineKeyboardButton(text="UTC+1 (Берлин)", callback_data="tz_UTC+1")
        ],
        [
            InlineKeyboardButton(text="UTC+2 (Киев)", callback_data="tz_UTC+2"),
            InlineKeyboardButton(text="UTC+3 (Москва)", callback_data="tz_UTC+3")
        ],
        [
            InlineKeyboardButton(text="UTC+4 (Дубай)", callback_data="tz_UTC+4"),
            InlineKeyboardButton(text="UTC+5 (Ташкент)", callback_data="tz_UTC+5")
        ],
        [
            InlineKeyboardButton(text="UTC+6 (Алматы)", callback_data="tz_UTC+6"),
            InlineKeyboardButton(text="UTC+7 (Бангкок)", callback_data="tz_UTC+7")
        ],
        [
            InlineKeyboardButton(text="UTC+8 (Пекин)", callback_data="tz_UTC+8"),
            InlineKeyboardButton(text="UTC+9 (Токио)", callback_data="tz_UTC+9")
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_reminder_settings")
        ]
    ])
    
    await callback.message.edit_text(
        "🌍 Выберите ваш часовой пояс:",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("tz_"))
async def save_timezone(callback: CallbackQuery):
    """Сохранение часового пояса"""
    timezone = callback.data.replace("tz_", "")
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        user.timezone = timezone
        await session.commit()
    
    await callback.answer(f"✅ Часовой пояс установлен: {timezone}")
    
    # Обновляем в сервисе напоминаний
    # reminder_service = SmartReminderService(callback.bot)
    # await reminder_service.set_user_timezone(callback.from_user.id, timezone)
    
    # Возвращаемся в меню
    await reminder_settings_menu(callback.message)

@router.callback_query(F.data == "set_morning_time")
async def set_morning_time(callback: CallbackQuery, state: FSMContext):
    """Установка времени утреннего напоминания"""
    await callback.answer()
    
    await callback.message.answer(
        "⏰ Введите время утреннего напоминания в формате ЧЧ:ММ\n"
        "Например: 08:00\n\n"
        "Или отправьте /cancel для отмены"
    )
    await state.set_state(SettingsStates.morning_reminder_time)

@router.message(SettingsStates.morning_reminder_time)
async def save_morning_time(message: Message, state: FSMContext):
    """Сохранение времени утреннего напоминания"""
    try:
        # Проверяем формат времени
        time_parts = message.text.split(":")
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            time_str = f"{hour:02d}:{minute:02d}"
            
            async with get_session() as session:
                result = await session.execute(
                    select(User).where(User.telegram_id == message.from_user.id)
                )
                user = result.scalar_one_or_none()
                
                if not user.reminder_settings:
                    user.reminder_settings = {}
                user.reminder_settings["morning_time"] = time_str
                await session.commit()
            
            await message.answer(f"✅ Время утреннего напоминания установлено: {time_str}")
            
            # Обновляем в сервисе
            # reminder_service = SmartReminderService(message.bot)
            # await reminder_service.set_custom_reminder_time(
            #     message.from_user.id, "morning", time(hour, minute)
            # )
        else:
            await message.answer("❌ Неверный формат времени. Попробуйте еще раз.")
            return
            
    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат. Используйте формат ЧЧ:ММ (например, 08:00)")
        return
    
    await state.clear()

@router.callback_query(F.data == "set_reminder_style")
async def set_reminder_style(callback: CallbackQuery):
    """Выбор стиля напоминаний"""
    await callback.answer()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="😊 Дружелюбный", callback_data="style_friendly")
        ],
        [
            InlineKeyboardButton(text="💪 Мотивирующий", callback_data="style_motivational")
        ],
        [
            InlineKeyboardButton(text="📊 Строгий", callback_data="style_strict")
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_reminder_settings")
        ]
    ])
    
    await callback.message.edit_text(
        "💬 **Выберите стиль напоминаний:**\n\n"
        "😊 **Дружелюбный** - мягкие и позитивные сообщения\n"
        "💪 **Мотивирующий** - вдохновляющие и энергичные\n"
        "📊 **Строгий** - четкие и по делу\n",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("style_"))
async def save_reminder_style(callback: CallbackQuery):
    """Сохранение стиля напоминаний"""
    style = callback.data.replace("style_", "")
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        user.reminder_style = style
        await session.commit()
    
    style_names = {
        "friendly": "Дружелюбный",
        "motivational": "Мотивирующий",
        "strict": "Строгий"
    }
    
    await callback.answer(f"✅ Стиль установлен: {style_names.get(style, style)}")
    await reminder_settings_menu(callback.message)

@router.callback_query(F.data == "toggle_water_reminders")
async def toggle_water_reminders(callback: CallbackQuery):
    """Переключение напоминаний о воде"""
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user.reminder_settings:
            user.reminder_settings = {}
        
        current = user.reminder_settings.get("water_reminders", True)
        user.reminder_settings["water_reminders"] = not current
        await session.commit()
        
        status = "включены" if not current else "выключены"
        await callback.answer(f"💧 Напоминания о воде {status}")
    
    await reminder_settings_menu(callback.message)

@router.callback_query(F.data == "disable_all_reminders")
async def disable_all_reminders(callback: CallbackQuery):
    """Отключение всех напоминаний"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, отключить все", callback_data="confirm_disable_all"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_reminder_settings")
        ]
    ])
    
    await callback.message.edit_text(
        "⚠️ Вы уверены, что хотите отключить все напоминания?\n\n"
        "Вы не будете получать:\n"
        "• Утренние напоминания о чек-ине\n"
        "• Вечерние напоминания\n"
        "• Напоминания о воде\n",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "confirm_disable_all")
async def confirm_disable_all_reminders(callback: CallbackQuery):
    """Подтверждение отключения всех напоминаний"""
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user.reminder_settings:
            user.reminder_settings = {}
        
        user.reminder_settings["all_disabled"] = True
        user.reminder_settings["water_reminders"] = False
        await session.commit()
    
    await callback.answer("✅ Все напоминания отключены")
    
    # Отключаем в сервисе
    # reminder_service = SmartReminderService(callback.bot)
    # await reminder_service.disable_reminders(callback.from_user.id)
    
    await callback.message.edit_text(
        "🔕 Все напоминания отключены.\n\n"
        "Вы можете включить их снова в любое время через /reminder_settings"
    )

@router.callback_query(F.data == "back_to_reminder_settings")
async def back_to_reminder_settings(callback: CallbackQuery):
    """Возврат в меню настроек напоминаний"""
    await callback.answer()
    await reminder_settings_menu(callback.message)

@router.callback_query(F.data == "coming_soon")
async def coming_soon(callback: CallbackQuery):
    """Заглушка для функций в разработке"""
    await callback.answer("🚧 Эта функция скоро будет доступна!", show_alert=True)