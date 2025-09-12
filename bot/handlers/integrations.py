from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Union
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, time
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
import logging
import re # Добавлен импорт

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


async def _display_reminder_settings(target: Union[Message, CallbackQuery]):
    """
    Отображает меню настроек напоминаний, корректно обрабатывая
    и сообщения, и callback-запросы.
    """
    user_id = target.from_user.id
    
    async with get_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == user_id))

        # ИСПРАВЛЕНИЕ 3: Улучшенная проверка наличия пользователя
        if not user or not user.onboarding_completed:
            text = "❌ Сначала нужно пройти регистрацию. Используйте /start"
            chat_id = target.chat.id if isinstance(target, Message) else target.message.chat.id
            await target.bot.send_message(chat_id, text)
            if isinstance(target, CallbackQuery):
                await target.answer()
            return

        settings = user.reminder_settings or {}
        timezone = user.timezone or "UTC"
        style = user.reminder_style or "friendly"
        all_disabled = settings.get("all_disabled", False)
        water_reminders_on = settings.get("water_reminders", True) and not all_disabled

        # ИСПРАВЛЕНИЕ 4: Корректная кнопка включения/выключения
        if all_disabled:
            toggle_all_button = InlineKeyboardButton(
                text="✅ Включить все напоминания",
                callback_data="enable_all_reminders"
            )
        else:
            toggle_all_button = InlineKeyboardButton(
                text="🔕 Отключить все напоминания",
                callback_data="disable_all_reminders"
            )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🌍 Часовой пояс: {timezone}", callback_data="set_timezone")],
            [
                InlineKeyboardButton(text="🌅 Утро: " + settings.get('morning_time', '08:00'), callback_data="set_morning_time"),
                InlineKeyboardButton(text="🌙 Вечер: " + settings.get('evening_time', '20:00'), callback_data="set_evening_time")
            ],
            [InlineKeyboardButton(text=f"💬 Стиль: {style.capitalize()}", callback_data="set_reminder_style")],
            [InlineKeyboardButton(
                text=f"💧 Вода: {'✅ Вкл' if water_reminders_on else '❌ Выкл'}",
                callback_data="toggle_water_reminders"
            )],
            [toggle_all_button],
            [InlineKeyboardButton(text="◀️ Назад в главное меню", callback_data="back_to_main_menu")] # Добавлена кнопка Назад
        ])
        
        text = "⏰ **Настройки напоминаний**\n\n"
        style_descriptions = {
            "friendly": "Дружелюбный - мягкие и позитивные",
            "motivational": "Мотивирующий - вдохновляющие сообщения",
            "strict": "Строгий - четкие и по делу"
        }
        text += f"Здесь вы можете настроить, как и когда бот будет напоминать вам о важных действиях.\n\n"
        text += f"Текущий стиль: _{style_descriptions.get(style, '')}_"
        
        if isinstance(target, CallbackQuery):
            try:
                await target.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
                await target.answer()
            except Exception as e:
                logger.debug(f"Could not edit message: {e}")
        else:
            await target.answer(text, reply_markup=keyboard, parse_mode="Markdown")

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
        keyboard_buttons = []
        if "google_fit" in connected:
            keyboard_buttons.append([
                InlineKeyboardButton(text="✅ Google Fit (подключен)", callback_data="sync_google_fit"),
                InlineKeyboardButton(text="❌ Отключить", callback_data="disconnect_google_fit")
            ])
        else:
            keyboard_buttons.append([InlineKeyboardButton(text="🔗 Подключить Google Fit", callback_data="connect_google_fit")])
        
        keyboard_buttons.append([InlineKeyboardButton(text="🍎 Apple Health (скоро)", callback_data="coming_soon")])
        
        if connected:
            keyboard_buttons.append([InlineKeyboardButton(text="🔄 Синхронизировать все", callback_data="sync_all")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        text = "🔗 **Интеграции с фитнес-трекерами**\n\n"
        text += "Подключите фитнес-трекер для автоматического импорта данных о шагах, весе и активности."
        
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
    await _display_reminder_settings(message)

@router.callback_query(F.data == "back_to_reminder_settings")
async def back_to_reminder_settings(callback: CallbackQuery):
    await _display_reminder_settings(callback)

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
    timezone = callback.data.replace("tz_", "")
    async with get_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
        if user:
            user.timezone = timezone
            await session.commit()
    await callback.answer(f"✅ Часовой пояс установлен: {timezone}")
    await _display_reminder_settings(callback)

@router.callback_query(F.data == "set_morning_time")
async def set_morning_time(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        "⏰ Введите время утреннего напоминания в формате ЧЧ:ММ (например: 08:30)",
    )
    await state.set_state(SettingsStates.morning_reminder_time)

@router.message(SettingsStates.morning_reminder_time)
async def save_morning_time(message: Message, state: FSMContext):
    try:
        # ИСПРАВЛЕНИЕ: Улучшенная проверка формата времени с помощью регулярного выражения
        cleaned_text = message.text.strip()
        match = re.fullmatch(r"(\d{1,2}):(\d{2})", cleaned_text)

        if not match:
            raise ValueError(f"Input '{cleaned_text}' does not match HH:MM format")

        hour, minute = int(match.group(1)), int(match.group(2))
        
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"Time out of range: {hour}:{minute}")

        time_str = f"{hour:02d}:{minute:02d}"
        async with get_session() as session:
            user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
            if user:
                user.reminder_settings = user.reminder_settings or {}
                user.reminder_settings["morning_time"] = time_str
                flag_modified(user, "reminder_settings")
                await session.commit()
        await message.answer(f"✅ Утреннее напоминание установлено на {time_str}")
        await state.clear()
        await _display_reminder_settings(message)
    except ValueError as e:
        logger.warning(f"Invalid time format from user {message.from_user.id}: {e}")
        await message.answer("❌ Неверный формат. Используйте ЧЧ:ММ (например, 08:30).")
    except Exception as e:
        logger.error(f"Unexpected error in save_morning_time: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте снова.")
        await state.clear()

@router.callback_query(F.data == "set_evening_time")
async def set_evening_time(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("⏰ Введите время вечернего напоминания в формате ЧЧ:ММ (например: 20:00)")
    await state.set_state(SettingsStates.evening_reminder_time)

@router.message(SettingsStates.evening_reminder_time)
async def save_evening_time(message: Message, state: FSMContext):
    try:
        # ИСПРАВЛЕНИЕ: Улучшенная проверка формата времени с помощью регулярного выражения
        cleaned_text = message.text.strip()
        match = re.fullmatch(r"(\d{1,2}):(\d{2})", cleaned_text)

        if not match:
            raise ValueError(f"Input '{cleaned_text}' does not match HH:MM format")
            
        hour, minute = int(match.group(1)), int(match.group(2))

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"Time out of range: {hour}:{minute}")

        time_str = f"{hour:02d}:{minute:02d}"
        async with get_session() as session:
            user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
            if user:
                user.reminder_settings = user.reminder_settings or {}
                user.reminder_settings["evening_time"] = time_str
                flag_modified(user, "reminder_settings")
                await session.commit()
        await message.answer(f"✅ Вечернее напоминание установлено на {time_str}")
        await state.clear()
        await _display_reminder_settings(message)
    except ValueError as e:
        logger.warning(f"Invalid time format from user {message.from_user.id}: {e}")
        await message.answer("❌ Неверный формат. Используйте ЧЧ:ММ (например, 20:00).")
    except Exception as e:
        logger.error(f"Unexpected error in save_evening_time: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте снова.")
        await state.clear()

@router.callback_query(F.data == "set_reminder_style")
async def set_reminder_style(callback: CallbackQuery):
    await callback.answer()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="😊 Дружелюбный", callback_data="style_friendly")],
        [InlineKeyboardButton(text="💪 Мотивирующий", callback_data="style_motivational")],
        [InlineKeyboardButton(text="📊 Строгий", callback_data="style_strict")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_reminder_settings")]
    ])
    await callback.message.edit_text("💬 **Выберите стиль напоминаний:**", reply_markup=keyboard, parse_mode="Markdown")


@router.callback_query(F.data.startswith("style_"))
async def save_reminder_style(callback: CallbackQuery):
    style = callback.data.replace("style_", "")
    async with get_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
        if user:
            user.reminder_style = style
            await session.commit()
    await callback.answer(f"✅ Стиль изменен")
    await _display_reminder_settings(callback)

@router.callback_query(F.data == "toggle_water_reminders")
async def toggle_water_reminders(callback: CallbackQuery):
    async with get_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
        if user:
            user.reminder_settings = user.reminder_settings or {}
            current_status = user.reminder_settings.get("water_reminders", True)
            user.reminder_settings["water_reminders"] = not current_status
            flag_modified(user, "reminder_settings")
            await session.commit()
            await callback.answer(f"💧 Напоминания о воде {'выключены' if current_status else 'включены'}")
    await _display_reminder_settings(callback)

@router.callback_query(F.data == "disable_all_reminders")
async def disable_all_reminders(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, отключить", callback_data="confirm_disable_all"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_reminder_settings")
        ]
    ])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Да, отключить", callback_data="confirm_disable_all"), InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_reminder_settings")]])
    await callback.message.edit_text("⚠️ Вы уверены, что хотите отключить все напоминания?", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "confirm_disable_all")
async def confirm_disable_all_reminders(callback: CallbackQuery):
    async with get_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
        if user:
            user.reminder_settings = user.reminder_settings or {}
            user.reminder_settings["all_disabled"] = True
            flag_modified(user, "reminder_settings")
            await session.commit()
    await callback.answer("🔕 Все напоминания отключены", show_alert=True)
    await _display_reminder_settings(callback)

@router.callback_query(F.data == "enable_all_reminders")
async def enable_all_reminders(callback: CallbackQuery):
    async with get_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
        if user:
            user.reminder_settings = user.reminder_settings or {}
            user.reminder_settings["all_disabled"] = False
            flag_modified(user, "reminder_settings")
            await session.commit()
    await callback.answer("✅ Все напоминания включены", show_alert=True)
    await _display_reminder_settings(callback)

@router.callback_query(F.data == "coming_soon")
async def coming_soon(callback: CallbackQuery):
    await callback.answer("🚧 Эта функция скоро будет доступна!", show_alert=True)