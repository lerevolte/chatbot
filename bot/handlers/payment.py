from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton, PreCheckoutQuery, ContentType
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from datetime import datetime, timedelta
import logging

from database.models import User
from database.payment_models import SubscriptionPlan, PromoType
from database.connection import get_session
from bot.services.payment_service import PaymentService

router = Router()
logger = logging.getLogger(__name__)

# Состояния для промокода
class PromoCodeStates(StatesGroup):
    entering_code = State()
    creating_partner = State()

# ============ КОМАНДА ПОДПИСКИ ============
@router.message(Command("subscription"))
async def subscription_menu(message: Message):
    """Главное меню подписки"""
    # Получаем сервис платежей
    payment_service = PaymentService(message.bot)
    
    # Проверяем статус подписки
    status = await payment_service.check_subscription_status(message.from_user.id)
    
    if status["status"] == "active":
        # Активная подписка
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 История платежей", callback_data="payment_history"),
                InlineKeyboardButton(text="❌ Отменить автопродление", callback_data="cancel_subscription")
            ],
            [
                InlineKeyboardButton(text="🎁 Партнерская программа", callback_data="partner_program")
            ]
        ])
        
        text = f"✅ **Подписка активна**\n\n"
        text += f"📅 Действует до: {status['expires_at'].strftime('%d.%m.%Y')}\n"
        text += f"⏳ Осталось дней: {status['days_left']}\n"
        text += f"💳 План: {status['plan'].replace('_', ' ').title()}\n"
        
        if status.get('auto_renew'):
            text += f"🔄 Автопродление: ✅ Включено\n"
        else:
            text += f"🔄 Автопродление: ❌ Выключено\n"
        
        if status.get('features'):
            text += "\n**Доступные функции:**\n"
            feature_names = {
                "meal_plans": "• Персональные планы питания",
                "ai_coach": "• AI-коуч и анализ фото",
                "integrations": "• Интеграция с фитнес-трекерами",
                "priority_support": "• Приоритетная поддержка",
                "custom_programs": "• Индивидуальные программы"
            }
            for feature, enabled in status['features'].items():
                if enabled:
                    text += f"{feature_names.get(feature, feature)}\n"
    
    elif status["status"] == "trial":
        # Триальный период
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💳 Оформить подписку", callback_data="show_plans")
            ],
            [
                InlineKeyboardButton(text="🎁 У меня есть промокод", callback_data="enter_promo")
            ]
        ])
        
        text = f"🎁 **Пробный период**\n\n"
        text += f"📅 Действует до: {status['expires_at'].strftime('%d.%m.%Y')}\n"
        text += f"⏳ Осталось дней: {status['days_left']}\n\n"
        text += "После окончания пробного периода некоторые функции станут недоступны.\n"
        text += "Оформите подписку, чтобы продолжить пользоваться всеми возможностями!"
    
    else:
        # Подписка неактивна
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💳 Выбрать план", callback_data="show_plans")
            ],
            [
                InlineKeyboardButton(text="🎁 У меня есть промокод", callback_data="enter_promo"),
                InlineKeyboardButton(text="❓ Что дает подписка?", callback_data="subscription_info")
            ]
        ])
        
        text = "❌ **Подписка неактивна**\n\n"
        text += "Оформите подписку, чтобы получить доступ ко всем функциям:\n\n"
        text += "✅ Персональные планы питания с AI\n"
        text += "✅ Анализ фото еды и подсчет калорий\n"
        text += "✅ Интеграция с фитнес-трекерами\n"
        text += "✅ Умные напоминания\n"
        text += "✅ Приоритетная поддержка\n"
    
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

# ============ ПОКАЗ ПЛАНОВ ============
@router.callback_query(F.data == "show_plans")
async def show_subscription_plans(callback: CallbackQuery, state: FSMContext):
    """Показывает доступные планы подписки"""
    await callback.answer()
    
    # Сохраняем выбранную валюту (по умолчанию RUB)
    await state.update_data(currency="RUB")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        # Месячная подписка
        [
            InlineKeyboardButton(
                text="📅 Месяц - 299₽",
                callback_data="buy_monthly"
            )
        ],
        # Квартальная подписка (популярная)
        [
            InlineKeyboardButton(
                text="⭐ 3 месяца - 699₽ (экономия 22%)",
                callback_data="buy_quarterly"
            )
        ],
        # Годовая подписка
        [
            InlineKeyboardButton(
                text="🎯 Год - 1999₽ (экономия 44%)",
                callback_data="buy_yearly"
            )
        ],
        # Дополнительные опции
        [
            InlineKeyboardButton(text="🎁 Ввести промокод", callback_data="enter_promo"),
            InlineKeyboardButton(text="💱 Другая валюта", callback_data="change_currency")
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_subscription")
        ]
    ])
    
    text = "💳 **Выберите план подписки**\n\n"
    
    text += "**📅 Месячная** - 299₽/мес\n"
    text += "• Все базовые функции\n"
    text += "• Планы питания\n"
    text += "• Анализ фото\n\n"
    
    text += "**⭐ 3 месяца** - 699₽ (233₽/мес)\n"
    text += "• Все функции месячной\n"
    text += "• Приоритетная поддержка\n"
    text += "• Экономия 22%\n\n"
    
    text += "**🎯 Годовая** - 1999₽ (167₽/мес)\n"
    text += "• Все функции\n"
    text += "• Индивидуальные программы\n"
    text += "• Консультация диетолога\n"
    text += "• Экономия 44%\n\n"
    
    text += "💡 _Все планы включают 7 дней гарантии возврата_"
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

# ============ ПОКУПКА ПОДПИСКИ ============
@router.callback_query(F.data.startswith("buy_"))
async def process_subscription_purchase(callback: CallbackQuery, state: FSMContext):
    """Обработка покупки подписки"""
    plan_type = callback.data.replace("buy_", "")
    
    # Маппинг планов
    plan_map = {
        "monthly": SubscriptionPlan.MONTHLY,
        "quarterly": SubscriptionPlan.QUARTERLY,
        "yearly": SubscriptionPlan.YEARLY
    }
    
    plan = plan_map.get(plan_type)
    if not plan:
        await callback.answer("Неверный план", show_alert=True)
        return
    
    await callback.answer("Создаю счет на оплату...")
    
    # Получаем данные из состояния (промокод если есть)
    data = await state.get_data()
    promo_code = data.get("promo_code")
    
    # Создаем инвойс
    payment_service = PaymentService(callback.bot)
    invoice_link = await payment_service.create_invoice(
        user_id=callback.from_user.id,
        plan=plan,
        promo_code=promo_code
    )
    
    if invoice_link:
        await callback.message.answer(
            "💳 Счет на оплату создан!\n"
            "Нажмите кнопку оплаты выше ☝️\n\n"
            "_Оплата происходит через защищенную систему Telegram Payments_"
        )
    else:
        await callback.message.answer(
            "❌ Ошибка при создании счета.\n"
            "Попробуйте позже или обратитесь в поддержку."
        )
    
    await state.clear()

# ============ ОБРАБОТКА ПЛАТЕЖЕЙ ============
@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    """Обработка pre-checkout запроса"""
    payment_service = PaymentService(pre_checkout_query.bot)
    await payment_service.process_pre_checkout(pre_checkout_query)

@router.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def process_successful_payment(message: Message):
    """Обработка успешного платежа"""
    payment_service = PaymentService(message.bot)
    
    success = await payment_service.process_successful_payment(
        message=message,
        telegram_payment_charge_id=message.successful_payment.telegram_payment_charge_id,
        provider_payment_charge_id=message.successful_payment.provider_payment_charge_id
    )
    
    if not success:
        await message.answer(
            "⚠️ Платеж получен, но возникла ошибка при активации подписки.\n"
            "Обратитесь в поддержку с номером платежа: "
            f"`{message.successful_payment.telegram_payment_charge_id}`",
            parse_mode="Markdown"
        )

# ============ ПРОМОКОДЫ ============
@router.callback_query(F.data == "enter_promo")
async def enter_promo_code(callback: CallbackQuery, state: FSMContext):
    """Ввод промокода"""
    await callback.answer()
    
    await callback.message.answer(
        "🎁 **Введите промокод**\n\n"
        "Отправьте промокод в чат или нажмите /cancel для отмены",
        parse_mode="Markdown"
    )
    await state.set_state(PromoCodeStates.entering_code)

@router.message(PromoCodeStates.entering_code)
async def process_promo_code(message: Message, state: FSMContext):
    """Обработка введенного промокода"""
    code = message.text.strip().upper()
    
    # Проверяем промокод
    payment_service = PaymentService(message.bot)
    promo = await payment_service.validate_promo_code(
        code=code,
        user_id=message.from_user.id,
        plan=SubscriptionPlan.MONTHLY  # Проверяем для базового плана
    )
    
    if promo:
        await state.update_data(promo_code=code)
        
        discount_text = ""
        if promo.promo_type == PromoType.DISCOUNT_PERCENT:
            discount_text = f"{int(promo.value)}%"
        elif promo.promo_type == PromoType.DISCOUNT_FIXED:
            discount_text = f"{int(promo.value)}₽"
        
        await message.answer(
            f"✅ **Промокод принят!**\n\n"
            f"Код: `{code}`\n"
            f"Скидка: {discount_text}\n\n"
            f"Теперь выберите план подписки:",
            parse_mode="Markdown"
        )
        
        # Показываем планы
        # Создаем фейковый callback для вызова функции
        class FakeCallback:
            def __init__(self, message):
                self.message = message
            async def answer(self):
                pass
        
        fake_callback = FakeCallback(message)
        await show_subscription_plans(fake_callback, state)
    else:
        await message.answer(
            "❌ **Неверный промокод**\n\n"
            "Промокод недействителен, уже использован или истек срок его действия.\n\n"
            "Попробуйте другой код или продолжите без промокода.",
            parse_mode="Markdown"
        )
    
    await state.set_state(None)

# ============ ПАРТНЕРСКАЯ ПРОГРАММА ============
@router.callback_query(F.data == "partner_program")
async def show_partner_program(callback: CallbackQuery):
    """Показывает информацию о партнерской программе"""
    await callback.answer()
    
    # Проверяем, есть ли у пользователя партнерский код
    payment_service = PaymentService(callback.bot)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎟 Получить партнерский код", callback_data="generate_partner_code")
        ],
        [
            InlineKeyboardButton(text="📊 Моя статистика", callback_data="partner_stats"),
            InlineKeyboardButton(text="💰 Вывести средства", callback_data="partner_withdraw")
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_subscription")
        ]
    ])
    
    text = "🤝 **Партнерская программа**\n\n"
    text += "Приглашайте друзей и получайте бонусы!\n\n"
    text += "**Как это работает:**\n"
    text += "1️⃣ Получите персональный промокод\n"
    text += "2️⃣ Поделитесь им с друзьями\n"
    text += "3️⃣ Друг получает скидку 20%\n"
    text += "4️⃣ Вы получаете 10% от платежа\n\n"
    text += "**Условия:**\n"
    text += "• Промокод действует 90 дней\n"
    text += "• Максимум 100 использований\n"
    text += "• Выплаты от 500₽\n"
    text += "• Вывод на карту или криптокошелек\n"
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data == "generate_partner_code")
async def generate_partner_code(callback: CallbackQuery):
    """Генерирует партнерский промокод"""
    await callback.answer("Генерирую код...")
    
    payment_service = PaymentService(callback.bot)
    code = await payment_service.generate_partner_promo_code(callback.from_user.id)
    
    if code:
        text = f"✅ **Ваш партнерский код создан!**\n\n"
        text += f"🎟 Код: `{code}`\n\n"
        text += f"**Поделитесь этим сообщением:**\n"
        text += f"_Получи скидку 20% на подписку FitnessBot!_\n"
        text += f"_Используй промокод:_ `{code}`\n"
        text += f"_Начни путь к идеальной форме:_ @YourBotName\n\n"
        text += "💡 Код скопирован в буфер обмена"
        
        await callback.message.answer(text, parse_mode="Markdown")
    else:
        await callback.message.answer("❌ Ошибка при создании кода. Попробуйте позже.")

# ============ ИСТОРИЯ ПЛАТЕЖЕЙ ============
@router.callback_query(F.data == "payment_history")
async def show_payment_history(callback: CallbackQuery):
    """Показывает историю платежей"""
    await callback.answer()
    
    payment_service = PaymentService(callback.bot)
    payments = await payment_service.get_payment_history(callback.from_user.id)
    
    if not payments:
        await callback.message.answer("У вас пока нет платежей")
        return
    
    text = "💳 **История платежей**\n\n"
    
    for payment in payments[:10]:  # Последние 10 платежей
        status_emoji = "✅" if payment.status.value == "success" else "❌"
        text += f"{status_emoji} {payment.created_at.strftime('%d.%m.%Y')} - "
        text += f"{payment.amount} {payment.currency}\n"
        if payment.description:
            text += f"   _{payment.description}_\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_subscription")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

# ============ ОТМЕНА ПОДПИСКИ ============
@router.callback_query(F.data == "cancel_subscription")
async def cancel_subscription(callback: CallbackQuery):
    """Отмена автопродления подписки"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, отменить", callback_data="confirm_cancel_subscription"),
            InlineKeyboardButton(text="❌ Нет, оставить", callback_data="back_to_subscription")
        ]
    ])
    
    await callback.message.edit_text(
        "⚠️ **Отмена автопродления**\n\n"
        "Вы уверены, что хотите отменить автопродление?\n\n"
        "Подписка будет активна до конца оплаченного периода, "
        "но не будет продлеваться автоматически.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "confirm_cancel_subscription")
async def confirm_cancel_subscription(callback: CallbackQuery):
    """Подтверждение отмены подписки"""
    await callback.answer()
    
    payment_service = PaymentService(callback.bot)
    success = await payment_service.cancel_subscription(callback.from_user.id)
    
    if success:
        await callback.message.edit_text(
            "✅ Автопродление отменено.\n\n"
            "Подписка будет активна до конца оплаченного периода.\n"
            "Вы всегда можете возобновить подписку через /subscription"
        )
    else:
        await callback.message.edit_text("❌ Ошибка при отмене подписки")

# ============ ИНФОРМАЦИЯ О ПОДПИСКЕ ============
@router.callback_query(F.data == "subscription_info")
async def show_subscription_info(callback: CallbackQuery):
    """Показывает информацию о преимуществах подписки"""
    await callback.answer()
    
    text = "💎 **Преимущества подписки**\n\n"
    
    text += "**🍽 Персональные планы питания**\n"
    text += "• Адаптированы под ваши цели\n"
    text += "• Учитывают предпочтения и аллергии\n"
    text += "• Обновляются еженедельно\n\n"
    
    text += "**🤖 AI-коуч**\n"
    text += "• Анализ фото еды\n"
    text += "• Подсчет калорий и БЖУ\n"
    text += "• Персональные рекомендации\n\n"
    
    text += "**📊 Расширенная аналитика**\n"
    text += "• Детальные графики прогресса\n"
    text += "• Прогнозы достижения целей\n"
    text += "• Еженедельные отчеты\n\n"
    
    text += "**🔗 Интеграции**\n"
    text += "• Google Fit\n"
    text += "• Apple Health (скоро)\n"
    text += "• Fitbit (скоро)\n\n"
    
    text += "**🎯 Дополнительно**\n"
    text += "• Приоритетная поддержка\n"
    text += "• Ранний доступ к новым функциям\n"
    text += "• Эксклюзивные материалы\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Выбрать план", callback_data="show_plans")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_subscription")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data == "back_to_subscription")
async def back_to_subscription(callback: CallbackQuery):
    """Возврат в меню подписки"""
    await subscription_menu(callback.message)

# ============ СМЕНА ВАЛЮТЫ ============
@router.callback_query(F.data == "change_currency")
async def change_currency(callback: CallbackQuery, state: FSMContext):
    """Смена валюты для оплаты"""
    await callback.answer()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 RUB (₽)", callback_data="currency_RUB"),
            InlineKeyboardButton(text="🇺🇸 USD ($)", callback_data="currency_USD")
        ],
        [
            InlineKeyboardButton(text="🇪🇺 EUR (€)", callback_data="currency_EUR"),
            InlineKeyboardButton(text="🇰🇿 KZT (₸)", callback_data="currency_KZT")
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="show_plans")
        ]
    ])
    
    await callback.message.edit_text(
        "💱 **Выберите валюту**\n\n"
        "Цены будут автоматически пересчитаны в выбранную валюту",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("currency_"))
async def set_currency(callback: CallbackQuery, state: FSMContext):
    """Установка выбранной валюты"""
    currency = callback.data.replace("currency_", "")
    await state.update_data(currency=currency)
    await callback.answer(f"Валюта изменена на {currency}")
    await show_subscription_plans(callback, state)

# ============ СТАТИСТИКА ПАРТНЕРА ============
@router.callback_query(F.data == "partner_stats")
async def show_partner_stats(callback: CallbackQuery):
    """Показывает статистику партнера"""
    await callback.answer()
    
    # Здесь должна быть логика получения статистики из БД
    # Пока заглушка
    text = "📊 **Статистика партнера**\n\n"
    text += "Использований кода: 0\n"
    text += "Заработано: 0₽\n"
    text += "Доступно к выводу: 0₽\n\n"
    text += "_Статистика обновляется раз в час_"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="partner_program")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data == "partner_withdraw")
async def partner_withdraw(callback: CallbackQuery):
    """Вывод средств партнера"""
    await callback.answer("Функция в разработке", show_alert=True)