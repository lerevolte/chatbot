from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_day_keyboard(current_day: int, week_number: int) -> InlineKeyboardMarkup:
    """
    Клавиатура для навигации по дням недели
    ========== НОВЫЙ КОД: Навигация по дням ==========
    """
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    
    # Кнопки дней недели
    day_buttons = []
    for i in range(1, 8):
        if i == current_day:
            # Текущий день отмечен
            day_buttons.append(
                InlineKeyboardButton(
                    text=f"• {days[i-1]} •",
                    callback_data=f"day_{i}_{week_number}"
                )
            )
        else:
            day_buttons.append(
                InlineKeyboardButton(
                    text=days[i-1],
                    callback_data=f"day_{i}_{week_number}"
                )
            )
    
    # ========== НОВЫЙ КОД: Кнопки действий ==========
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        day_buttons[:4],  # Первые 4 дня
        day_buttons[4:],  # Остальные 3 дня
        [
            InlineKeyboardButton(text="🔄 Заменить завтрак", callback_data=f"replace_breakfast_{current_day}_{week_number}"),
            InlineKeyboardButton(text="🔄 Заменить обед", callback_data=f"replace_lunch_{current_day}_{week_number}")
        ],
        [
            InlineKeyboardButton(text="🔄 Заменить ужин", callback_data=f"replace_dinner_{current_day}_{week_number}"),
            InlineKeyboardButton(text="🛒 Список покупок", callback_data="shopping_list")
        ],
        [
            InlineKeyboardButton(text="📊 Мой профиль", callback_data="show_profile"),
            InlineKeyboardButton(text="✅ Чек-ин", callback_data="daily_checkin")
        ]
    ])
    
    return keyboard

def get_meal_keyboard() -> InlineKeyboardMarkup:
    """
    Основная клавиатура плана питания
    ========== НОВЫЙ КОД: Главное меню ==========
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 План на неделю", callback_data="week_plan"),
            InlineKeyboardButton(text="📅 План на сегодня", callback_data="today_plan")
        ],
        [
            InlineKeyboardButton(text="🛒 Список покупок", callback_data="shopping_list"),
            InlineKeyboardButton(text="📊 Калории и БЖУ", callback_data="nutrition_info")
        ],
        [
            InlineKeyboardButton(text="🔄 Обновить план", callback_data="regenerate_plan")
        ]
    ])
    
    return keyboard

def get_shopping_list_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для списка покупок
    ========== НОВЫЙ КОД: Действия со списком ==========
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📤 Экспорт в PDF", callback_data="export_shopping_pdf"),
            InlineKeyboardButton(text="📱 Поделиться", callback_data="share_shopping")
        ],
        [
            InlineKeyboardButton(text="◀️ Назад к плану", callback_data="back_to_plan")
        ]
    ])

    return keyboard
    