# Настройка платежей в Telegram Bot

## 1. Получение Payment Token от BotFather

### Шаг 1: Откройте BotFather
```
https://t.me/BotFather
```

### Шаг 2: Настройте платежного провайдера
```
/mybots → Выберите вашего бота → Payments

Выберите провайдера:
- Stripe (международные платежи)
- ЮKassa (для России)
- Telegram Stars (внутренняя валюта)
```

### Шаг 3: Настройка Stripe (рекомендуется для тестов)
1. Зарегистрируйтесь на https://stripe.com
2. Получите тестовые ключи в Dashboard
3. В BotFather выберите Stripe
4. Вставьте Publishable Key и Secret Key
5. Выберите валюты
6. Получите Payment Token

### Шаг 4: Настройка ЮKassa (для России)
1. Зарегистрируйтесь на https://yookassa.ru
2. Создайте магазин
3. Получите Shop ID и Secret Key
4. В BotFather выберите ЮKassa
5. Введите данные
6. Получите Payment Token

## 2. Добавление токена в .env

```env
# Telegram Payments
TELEGRAM_PAYMENT_TOKEN=YOUR_TOKEN_FROM_BOTFATHER

# Для ЮKassa (опционально)
YOOKASSA_TOKEN=YOUR_YOOKASSA_TOKEN
YOOKASSA_SHOP_ID=YOUR_SHOP_ID

# Для CryptoBot (опционально)
CRYPTOBOT_TOKEN=YOUR_CRYPTOBOT_TOKEN
```

## 3. Тестирование платежей

### Тестовые карты для Stripe:
```
Успешный платеж: 4242 4242 4242 4242
Отклонение: 4000 0000 0000 0002
3D Secure: 4000 0000 0000 3220

Любая дата в будущем
Любой CVV (например, 123)
```

### Тестовые карты для ЮKassa:
```
Успешный платеж: 5555 5555 5555 4444
Недостаточно средств: 5555 5555 5555 4446

Дата: любая в будущем
CVV: любой трехзначный
```

## 4. Команды для тестирования

```
/subscription - Меню подписки
/subscription → Выбрать план → Оплатить

Промокоды для тестов:
- WELCOME20 - скидка 20%
- TRIAL30 - продление триала на 30 дней
```

## 5. Создание промокодов

### Через админ-панель (будущая функция):
```python
# Создание промокода через код
from bot.services.payment_service import PaymentService
from database.payment_models import PromoType

# Создать промокод на 50% скидку
await payment_service.create_promo_code(
    code="NEWYEAR50",
    promo_type=PromoType.DISCOUNT_PERCENT,
    value=50,
    max_uses=100,
    valid_days=30
)
```

### Типы промокодов:
- **DISCOUNT_PERCENT** - процентная скидка
- **DISCOUNT_FIXED** - фиксированная скидка в рублях
- **TRIAL_EXTENSION** - продление триала
- **FREE_PERIOD** - бесплатный период

## 6. Партнерская программа

### Как работает:
1. Пользователь с активной подпиской может стать партнером
2. Получает уникальный промокод
3. Друзья получают 20% скидку
4. Партнер получает 10% комиссию

### Активация:
```
/subscription → Партнерская программа → Получить код
```

## 7. Обработка платежей

### Процесс оплаты:
1. Пользователь выбирает план
2. Бот создает invoice через Telegram API
3. Пользователь оплачивает в Telegram
4. Telegram отправляет pre_checkout_query
5. Бот подтверждает платеж
6. Telegram списывает деньги
7. Telegram отправляет successful_payment
8. Бот активирует подписку

### Безопасность:
- Бот НЕ хранит данные карт
- Все платежи проходят через Telegram
- Токены хранятся зашифрованными
- Используется HTTPS для webhooks

## 8. Webhook для уведомлений (опционально)

Для продакшена настройте webhook:

```python
# В main.py
from aiogram import types

@dp.message(content_type=types.ContentType.SUCCESSFUL_PAYMENT)
async def got_payment(message: types.Message):
    # Обработка успешного платежа
    pass
```

## 9. Отчетность

### Где смотреть платежи:
- **Stripe**: https://dashboard.stripe.com/payments
- **ЮKassa**: https://yookassa.ru/my/payments
- **В боте**: /admin → Платежи (будущая функция)

## 10. Частые проблемы

### "Payment failed"
- Проверьте токен в .env
- Проверьте настройки в BotFather
- Убедитесь, что провайдер активен

### "Currency not supported"
- Проверьте поддерживаемые валюты провайдера
- Измените валюту в pricing_plans

### "Invoice expired"
- Invoice действителен 60 минут
- Создайте новый через /subscription

## 11. Продакшен чеклист

- [ ] Получить боевые токены от провайдера
- [ ] Настроить webhook для уведомлений
- [ ] Включить логирование платежей
- [ ] Настроить автоматические отчеты
- [ ] Добавить уведомления администратору
- [ ] Настроить автопродление (recurring payments)
- [ ] Добавить обработку refund
- [ ] Настроить антифрод проверки