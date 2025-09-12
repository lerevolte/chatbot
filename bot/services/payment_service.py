import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import secrets
from aiogram import Bot
from aiogram.types import LabeledPrice, PreCheckoutQuery, Message
from sqlalchemy import select, and_, or_

from database.models import User
from database.payment_models import (
    Subscription, Payment, PromoCode, PromoCodeUse, 
    PricingPlan, SubscriptionPlan, PaymentStatus, 
    PaymentProvider, PromoType
)
from database.connection import get_session
from bot.config import settings

logger = logging.getLogger(__name__)

class PaymentService:
    """Сервис для работы с платежами и подписками"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        # Токены провайдеров платежей из настроек
        self.telegram_token = getattr(settings, 'TELEGRAM_PAYMENT_TOKEN', None)
        self.yookassa_token = getattr(settings, 'YOOKASSA_TOKEN', None)
        self.cryptobot_token = getattr(settings, 'CRYPTOBOT_TOKEN', None)
        
        # Инициализация планов подписки
        self.init_pricing_plans()
    
    def init_pricing_plans(self):
        """Инициализация планов подписки (выполняется при первом запуске)"""
        self.default_plans = {
            SubscriptionPlan.MONTHLY: {
                "RUB": {"price": 299, "duration": 30, "name": "Месячная подписка"},
                "USD": {"price": 3.99, "duration": 30, "name": "Monthly subscription"},
                "EUR": {"price": 3.49, "duration": 30, "name": "Monthly subscription"}
            },
            SubscriptionPlan.QUARTERLY: {
                "RUB": {"price": 699, "original": 897, "duration": 90, "name": "3 месяца (-22%)"},
                "USD": {"price": 9.99, "original": 11.97, "duration": 90, "name": "3 months (-22%)"},
                "EUR": {"price": 8.99, "original": 10.47, "duration": 90, "name": "3 months (-22%)"}
            },
            SubscriptionPlan.YEARLY: {
                "RUB": {"price": 1999, "original": 3588, "duration": 365, "name": "Год (-44%)"},
                "USD": {"price": 29.99, "original": 47.88, "duration": 365, "name": "Year (-44%)"},
                "EUR": {"price": 26.99, "original": 41.88, "duration": 365, "name": "Year (-44%)"}
            }
        }
    
    async def create_invoice(
        self,
        user_id: int,
        plan: SubscriptionPlan,
        promo_code: Optional[str] = None,
        provider: PaymentProvider = PaymentProvider.TELEGRAM
    ) -> Optional[str]:
        """Создает инвойс для оплаты"""
        
        async with get_session() as session:
            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return None
            
            # Получаем план подписки
            result = await session.execute(
                select(PricingPlan).where(
                    and_(
                        PricingPlan.plan == plan,
                        PricingPlan.currency == "RUB",  # TODO: определять валюту пользователя
                        PricingPlan.is_active == True
                    )
                )
            )
            pricing = result.scalar_one_or_none()
            
            if not pricing:
                # Создаем план из дефолтных значений
                plan_data = self.default_plans[plan]["RUB"]
                pricing = PricingPlan(
                    plan=plan,
                    currency="RUB",
                    price=plan_data["price"],
                    original_price=plan_data.get("original"),
                    duration_days=plan_data["duration"],
                    features={
                        "meal_plans": True,
                        "ai_coach": True,
                        "integrations": True,
                        "priority_support": plan in [SubscriptionPlan.QUARTERLY, SubscriptionPlan.YEARLY],
                        "custom_programs": plan == SubscriptionPlan.YEARLY
                    }
                )
                session.add(pricing)
                await session.commit()
            
            # Проверяем промокод
            discount = Decimal(0)
            promo = None
            if promo_code:
                promo = await self.validate_promo_code(promo_code, user.id, plan)
                if promo:
                    discount = await self.calculate_discount(promo, pricing.price)
            
            # Рассчитываем финальную цену
            final_price = pricing.price - discount
            if final_price <= 0:
                final_price = Decimal(1)  # Минимальная цена
            
            # Создаем запись о платеже
            payment = Payment(
                user_id=user.id,
                provider=provider,
                amount=final_price,
                currency=pricing.currency,
                status=PaymentStatus.PENDING,
                description=f"Подписка: {self.default_plans[plan]['RUB']['name']}"
            )
            session.add(payment)
            await session.commit()
            
            # Генерируем инвойс в зависимости от провайдера
            if provider == PaymentProvider.TELEGRAM:
                invoice_link = await self._create_telegram_invoice(
                    user_id=user_id,
                    payment=payment,
                    pricing=pricing,
                    discount=discount,
                    promo=promo
                )
            else:
                # Для других провайдеров
                invoice_link = None
            
            return invoice_link
    
    async def _create_telegram_invoice(
        self,
        user_id: int,
        payment: Payment,
        pricing: PricingPlan,
        discount: Decimal,
        promo: Optional[PromoCode]
    ) -> str:
        """Создает инвойс через Telegram Payments"""
        
        if not self.telegram_token:
            logger.error("Telegram payment token not configured")
            return None
        
        # Формируем список цен
        prices = []
        
        # Основная цена
        prices.append(
            LabeledPrice(
                label=self.default_plans[pricing.plan]["RUB"]["name"],
                amount=int(pricing.price * 100)  # В копейках
            )
        )
        
        # Скидка (если есть)
        if discount > 0:
            prices.append(
                LabeledPrice(
                    label=f"Скидка ({promo.code})" if promo else "Скидка",
                    amount=-int(discount * 100)  # Отрицательное значение для скидки
                )
            )
        
        # Payload для идентификации платежа
        payload = f"payment_{payment.id}_{user_id}"
        payment.invoice_payload = payload
        
        # Создаем инвойс
        try:
            # Отправляем инвойс пользователю
            message = await self.bot.send_invoice(
                chat_id=user_id,
                title=f"Подписка FitnessBot",
                description=f"Получите полный доступ ко всем функциям на {pricing.duration_days} дней",
                payload=payload,
                provider_token=self.telegram_token,
                currency=pricing.currency,
                prices=prices,
                start_parameter=f"sub_{pricing.plan.value}",
                photo_url="https://example.com/subscription.jpg",  # TODO: добавить картинку
                photo_size=512,
                photo_width=512,
                photo_height=512,
                need_name=False,
                need_phone_number=False,
                need_email=True,
                need_shipping_address=False,
                is_flexible=False,
                protect_content=True
            )
            
            return f"invoice_{message.message_id}"
            
        except Exception as e:
            logger.error(f"Error creating Telegram invoice: {e}")
            return None
    
    async def process_pre_checkout(self, pre_checkout_query: PreCheckoutQuery) -> bool:
        """Обработка pre-checkout запроса от Telegram"""
        
        # Извлекаем ID платежа из payload
        try:
            payload_parts = pre_checkout_query.invoice_payload.split("_")
            payment_id = int(payload_parts[1])
            user_telegram_id = int(payload_parts[2])
        except:
            await pre_checkout_query.answer(ok=False, error_message="Неверный формат платежа")
            return False
        
        async with get_session() as session:
            # Проверяем платеж
            result = await session.execute(
                select(Payment).where(Payment.id == payment_id)
            )
            payment = result.scalar_one_or_none()
            
            if not payment:
                await pre_checkout_query.answer(ok=False, error_message="Платеж не найден")
                return False
            
            if payment.status != PaymentStatus.PENDING:
                await pre_checkout_query.answer(ok=False, error_message="Платеж уже обработан")
                return False
            
            # Проверяем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == user_telegram_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                await pre_checkout_query.answer(ok=False, error_message="Пользователь не найден")
                return False
            
            # Все проверки пройдены
            await pre_checkout_query.answer(ok=True)
            return True
    
    async def process_successful_payment(
        self,
        message: Message,
        telegram_payment_charge_id: str,
        provider_payment_charge_id: str
    ) -> bool:
        """Обработка успешного платежа"""
        
        # Извлекаем ID платежа из payload
        try:
            payload_parts = message.successful_payment.invoice_payload.split("_")
            payment_id = int(payload_parts[1])
            user_telegram_id = int(payload_parts[2])
        except:
            logger.error("Invalid payment payload")
            return False
        
        async with get_session() as session:
            # Получаем платеж
            result = await session.execute(
                select(Payment).where(Payment.id == payment_id)
            )
            payment = result.scalar_one_or_none()
            
            if not payment:
                logger.error(f"Payment {payment_id} not found")
                return False
            
            # Обновляем статус платежа
            payment.status = PaymentStatus.SUCCESS
            payment.paid_at = datetime.utcnow()
            payment.provider_payment_id = provider_payment_charge_id
            payment.provider_data = {
                "telegram_payment_charge_id": telegram_payment_charge_id,
                "total_amount": message.successful_payment.total_amount,
                "currency": message.successful_payment.currency
            }
            
            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == user_telegram_id)
            )
            user = result.scalar_one_or_none()
            
            # Определяем план подписки по сумме
            amount = Decimal(message.successful_payment.total_amount) / 100
            plan = await self._determine_plan_by_amount(amount, message.successful_payment.currency)
            
            if not plan:
                logger.error(f"Cannot determine plan for amount {amount}")
                return False
            
            # Создаем или продлеваем подписку
            subscription = await self._activate_subscription(
                session=session,
                user=user,
                plan=plan,
                payment=payment
            )
            
            payment.subscription_id = subscription.id
            
            # Если использовался промокод, отмечаем его использование
            if subscription.promo_code_id:
                await self._mark_promo_used(
                    session=session,
                    promo_code_id=subscription.promo_code_id,
                    user_id=user.id,
                    payment_id=payment.id
                )
            
            await session.commit()
            
            # Отправляем подтверждение пользователю
            await self._send_payment_confirmation(user_telegram_id, subscription)
            
            return True
    
    async def _activate_subscription(
        self,
        session,
        user: User,
        plan: SubscriptionPlan,
        payment: Payment
    ) -> Subscription:
        """Активирует или продлевает подписку"""
        
        # Проверяем текущую подписку
        result = await session.execute(
            select(Subscription).where(
                and_(
                    Subscription.user_id == user.id,
                    Subscription.is_active == True,
                    Subscription.expires_at > datetime.utcnow()
                )
            ).order_by(Subscription.expires_at.desc())
        )
        current_sub = result.scalar_one_or_none()
        
        # Получаем информацию о плане
        result = await session.execute(
            select(PricingPlan).where(
                and_(
                    PricingPlan.plan == plan,
                    PricingPlan.currency == payment.currency
                )
            )
        )
        pricing = result.scalar_one_or_none()
        
        if current_sub and current_sub.expires_at > datetime.utcnow():
            # Продлеваем существующую подписку
            current_sub.expires_at += timedelta(days=pricing.duration_days)
            subscription = current_sub
        else:
            # Создаем новую подписку
            subscription = Subscription(
                user_id=user.id,
                plan=plan,
                started_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=pricing.duration_days),
                is_active=True,
                auto_renew=False,  # По умолчанию без автопродления
                price=payment.amount,
                currency=payment.currency,
                features=pricing.features
            )
            session.add(subscription)
        
        # Обновляем статус премиума у пользователя
        user.is_premium = True
        user.subscription_until = subscription.expires_at
        
        return subscription
    
    async def validate_promo_code(
        self,
        code: str,
        user_id: int,
        plan: SubscriptionPlan
    ) -> Optional[PromoCode]:
        """Проверяет валидность промокода"""
        
        async with get_session() as session:
            # Получаем промокод
            result = await session.execute(
                select(PromoCode).where(
                    and_(
                        PromoCode.code == code.upper(),
                        PromoCode.is_active == True
                    )
                )
            )
            promo = result.scalar_one_or_none()
            
            if not promo:
                return None
            
            # Проверяем срок действия
            now = datetime.utcnow()
            if promo.valid_from > now or (promo.valid_until and promo.valid_until < now):
                return None
            
            # Проверяем количество использований
            if promo.max_uses and promo.uses_count >= promo.max_uses:
                return None
            
            # Проверяем использование пользователем
            result = await session.execute(
                select(PromoCodeUse).where(
                    and_(
                        PromoCodeUse.promo_code_id == promo.id,
                        PromoCodeUse.user_id == user_id
                    )
                )
            )
            user_uses = result.scalars().all()
            
            if len(user_uses) >= promo.max_uses_per_user:
                return None
            
            # Проверяем применимость к плану
            if promo.applicable_plans and plan.value not in promo.applicable_plans:
                return None
            
            return promo
    
    async def calculate_discount(
        self,
        promo: PromoCode,
        original_price: Decimal
    ) -> Decimal:
        """Рассчитывает размер скидки"""
        
        if promo.promo_type == PromoType.DISCOUNT_PERCENT:
            # Процентная скидка
            discount = original_price * (promo.value / 100)
        elif promo.promo_type == PromoType.DISCOUNT_FIXED:
            # Фиксированная скидка
            discount = promo.value
        else:
            discount = Decimal(0)
        
        # Скидка не может быть больше цены
        if discount > original_price:
            discount = original_price - 1  # Оставляем минимум 1 рубль
        
        return discount
    
    async def _mark_promo_used(
        self,
        session,
        promo_code_id: int,
        user_id: int,
        payment_id: int
    ):
        """Отмечает использование промокода"""
        
        # Создаем запись об использовании
        promo_use = PromoCodeUse(
            promo_code_id=promo_code_id,
            user_id=user_id,
            payment_id=payment_id
        )
        session.add(promo_use)
        
        # Увеличиваем счетчик использований
        result = await session.execute(
            select(PromoCode).where(PromoCode.id == promo_code_id)
        )
        promo = result.scalar_one_or_none()
        if promo:
            promo.uses_count += 1
    
    async def _send_payment_confirmation(
        self,
        user_telegram_id: int,
        subscription: Subscription
    ):
        """Отправляет подтверждение об оплате"""
        
        features_text = ""
        if subscription.features:
            features_text = "\n\n✅ Доступные функции:\n"
            feature_names = {
                "meal_plans": "• Персональные планы питания",
                "ai_coach": "• AI-коуч и анализ фото",
                "integrations": "• Интеграция с фитнес-трекерами",
                "priority_support": "• Приоритетная поддержка",
                "custom_programs": "• Индивидуальные программы"
            }
            for feature, enabled in subscription.features.items():
                if enabled:
                    features_text += f"{feature_names.get(feature, feature)}\n"
        
        await self.bot.send_message(
            chat_id=user_telegram_id,
            text=f"✅ **Оплата успешно получена!**\n\n"
                 f"🎉 Ваша подписка активна до: {subscription.expires_at.strftime('%d.%m.%Y')}\n"
                 f"{features_text}\n"
                 f"Спасибо за доверие! 💪\n\n"
                 f"Используйте /profile для просмотра статуса подписки.",
            parse_mode="Markdown"
        )
    
    async def _determine_plan_by_amount(
        self,
        amount: Decimal,
        currency: str
    ) -> Optional[SubscriptionPlan]:
        """Определяет план подписки по сумме платежа"""
        
        async with get_session() as session:
            result = await session.execute(
                select(PricingPlan).where(
                    and_(
                        PricingPlan.price <= amount + 10,  # Допуск на скидки
                        PricingPlan.price >= amount - 10,
                        PricingPlan.currency == currency
                    )
                )
            )
            pricing = result.scalar_one_or_none()
            
            return pricing.plan if pricing else None
    
    async def check_subscription_status(self, user_id: int) -> Dict:
        """Проверяет статус подписки пользователя"""
        
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return {"status": "not_found"}
            
            # Проверяем активную подписку
            result = await session.execute(
                select(Subscription).where(
                    and_(
                        Subscription.user_id == user.id,
                        Subscription.is_active == True,
                        Subscription.expires_at > datetime.utcnow()
                    )
                ).order_by(Subscription.expires_at.desc())
            )
            subscription = result.scalar_one_or_none()
            
            if subscription:
                days_left = (subscription.expires_at - datetime.utcnow()).days
                return {
                    "status": "active",
                    "plan": subscription.plan.value,
                    "expires_at": subscription.expires_at,
                    "days_left": days_left,
                    "auto_renew": subscription.auto_renew,
                    "features": subscription.features
                }
            
            # Проверяем триал
            if user.trial_started_at:
                trial_end = user.trial_started_at + timedelta(days=7)
                if datetime.utcnow() < trial_end:
                    days_left = (trial_end - datetime.utcnow()).days
                    return {
                        "status": "trial",
                        "expires_at": trial_end,
                        "days_left": days_left
                    }
            
            return {"status": "expired"}
    
    async def cancel_subscription(self, user_id: int) -> bool:
        """Отменяет автопродление подписки"""
        
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return False
            
            result = await session.execute(
                select(Subscription).where(
                    and_(
                        Subscription.user_id == user.id,
                        Subscription.is_active == True,
                        Subscription.expires_at > datetime.utcnow()
                    )
                )
            )
            subscription = result.scalar_one_or_none()
            
            if subscription:
                subscription.auto_renew = False
                await session.commit()
                return True
            
            return False
    
    async def get_payment_history(self, user_id: int) -> List[Payment]:
        """Получает историю платежей пользователя"""
        
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return []
            
            result = await session.execute(
                select(Payment).where(
                    Payment.user_id == user.id
                ).order_by(Payment.created_at.desc()).limit(10)
            )
            
            return result.scalars().all()
    
    async def create_promo_code(
        self,
        code: str,
        promo_type: PromoType,
        value: float,
        max_uses: Optional[int] = None,
        valid_days: int = 30,
        applicable_plans: Optional[List[str]] = None,
        created_by_user_id: Optional[int] = None
    ) -> PromoCode:
        """Создает новый промокод"""
        
        async with get_session() as session:
            promo = PromoCode(
                code=code.upper(),
                promo_type=promo_type,
                value=Decimal(value),
                max_uses=max_uses,
                valid_until=datetime.utcnow() + timedelta(days=valid_days),
                applicable_plans=applicable_plans,
                created_by_user_id=created_by_user_id
            )
            session.add(promo)
            await session.commit()
            
            return promo
    
    async def generate_partner_promo_code(self, user_id: int) -> str:
        """Генерирует партнерский промокод для пользователя"""
        
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return None
            
            # Генерируем уникальный код
            base_code = f"PARTNER_{user.id}"
            unique_suffix = secrets.token_hex(2).upper()
            code = f"{base_code}_{unique_suffix}"
            
            # Создаем промокод с комиссией
            promo = await self.create_promo_code(
                code=code,
                promo_type=PromoType.DISCOUNT_PERCENT,
                value=20,  # 20% скидка
                max_uses=100,
                valid_days=90,
                created_by_user_id=user.id
            )
            
            # Устанавливаем комиссию партнеру
            promo.commission_percent = Decimal(10)  # 10% от платежа партнеру
            await session.commit()
            
            return code