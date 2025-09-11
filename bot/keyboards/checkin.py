from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_mood_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для выбора настроения"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="😊 Отлично")],
            [KeyboardButton(text="😐 Нормально")],
            [KeyboardButton(text="😔 Плохо")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_meal_type_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для выбора типа приема пищи"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌅 Завтрак"), KeyboardButton(text="☀️ Обед")],
            [KeyboardButton(text="🌙 Ужин"), KeyboardButton(text="🍎 Перекус")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_water_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для быстрого выбора количества воды"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="< 1л"), KeyboardButton(text="1-1.5л")],
            [KeyboardButton(text="1.5-2л"), KeyboardButton(text="2-2.5л")],
            [KeyboardButton(text="> 2.5л")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_quick_weight_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для быстрого ввода веса"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Как вчера")],
            [KeyboardButton(text="Пропустить")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_checkin_reminder_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для напоминаний о чек-ине"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Сделать чек-ин", callback_data="start_checkin"),
            InlineKeyboardButton(text="⏰ Напомнить позже", callback_data="remind_later")
        ],
        [
            InlineKeyboardButton(text="🔕 Отключить напоминания", callback_data="disable_reminders")
        ]
    ])

def get_progress_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для просмотра прогресса"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Сегодня", callback_data="today_progress"),
            InlineKeyboardButton(text="📈 Неделя", callback_data="week_progress")
        ],
        [
            InlineKeyboardButton(text="📅 Месяц", callback_data="month_progress"),
            InlineKeyboardButton(text="🎯 Цели", callback_data="goals_progress")
        ]
    ])