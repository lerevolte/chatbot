import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Optional
from aiogram import Bot
from sqlalchemy import select, and_
import re

from database.models import User, CheckIn
from database.connection import get_session
from bot.keyboards.checkin import get_checkin_reminder_keyboard

logger = logging.getLogger(__name__)

class SmartReminderService:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.running = False
        self.task = None

    async def start(self):
        if self.running:
            return
        self.running = True
        self.task = asyncio.create_task(self.reminder_loop())
        logger.info("Сервис умных напоминаний запущен")

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
        logger.info("Сервис умных напоминаний остановлен")

    def _get_timezone_offset(self, tz_string: str) -> timedelta:
        """Парсит строку часового пояса (напр. 'UTC+3') и возвращает смещение."""
        if tz_string == "UTC":
            return timedelta(hours=0)
        
        match = re.match(r"UTC([+-])(\d+)", tz_string)
        if match:
            sign = 1 if match.group(1) == '+' else -1
            hours = int(match.group(2))
            return timedelta(hours=sign * hours)
        
        return timedelta(hours=0) # Fallback to UTC

    async def reminder_loop(self):
        """Основной цикл, который проверяет, не пора ли отправить напоминания."""
        while self.running:
            try:
                now_utc = datetime.utcnow()
                
                async with get_session() as session:
                    result = await session.execute(
                        select(User).where(
                            User.is_active == True,
                            User.onboarding_completed == True
                        )
                    )
                    users = result.scalars().all()

                for user in users:
                    await self.check_and_send_reminders(user, now_utc, session)

                # Ждем до начала следующей минуты
                await asyncio.sleep(60 - now_utc.second)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в цикле напоминаний: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def check_and_send_reminders(self, user: User, now_utc: datetime, session: 'AsyncSession'):
        """Проверяет и отправляет напоминания для конкретного пользователя."""
        settings = user.reminder_settings or {}
        if settings.get("all_disabled", False):
            return

        offset = self._get_timezone_offset(user.timezone or "UTC")
        user_local_time = now_utc + offset

        today_start = datetime.combine(user_local_time.date(), time.min) - offset
        today_end = datetime.combine(user_local_time.date(), time.max) - offset

        # Утреннее напоминание
        morning_time_str = settings.get("morning_time", "08:00")
        try:
            morning_t = datetime.strptime(morning_time_str, "%H:%M").time()
            if morning_t.hour == user_local_time.hour and morning_t.minute == user_local_time.minute:
                # Проверяем, был ли уже утренний чек-ин
                checkin = await session.scalar(
                    select(CheckIn).where(
                        and_(CheckIn.user_id == user.id, CheckIn.date.between(today_start, today_end))
                    )
                )
                if not checkin or checkin.weight is None:
                    await self.send_reminder(user, 'morning')
        except Exception as e:
            logger.warning(f"Неверный формат утреннего времени для user {user.id}: {e}")

        # Вечернее напоминание
        evening_time_str = settings.get("evening_time", "20:00")
        try:
            evening_t = datetime.strptime(evening_time_str, "%H:%M").time()
            if evening_t.hour == user_local_time.hour and evening_t.minute == user_local_time.minute:
                # Проверяем, был ли уже вечерний чек-ин
                checkin = await session.scalar(
                    select(CheckIn).where(
                        and_(CheckIn.user_id == user.id, CheckIn.date.between(today_start, today_end))
                    )
                )
                if not checkin or checkin.steps is None:
                    await self.send_reminder(user, 'evening')
        except Exception as e:
            logger.warning(f"Неверный формат вечернего времени для user {user.id}: {e}")

        # Напоминание о воде
        if settings.get("water_reminders", True):
            # Простая логика: напоминаем в 10, 14, 18 часов
            water_reminder_hours = [10, 14, 18]
            if user_local_time.hour in water_reminder_hours and user_local_time.minute == 0:
                 checkin = await session.scalar(
                    select(CheckIn).where(
                        and_(CheckIn.user_id == user.id, CheckIn.date.between(today_start, today_end))
                    )
                )
                 current_water = checkin.water_ml if checkin and checkin.water_ml else 0
                 if current_water < 2000:
                     await self.send_reminder(user, 'water', current_water)


    async def send_reminder(self, user: User, reminder_type: str, water_level: int = 0):
        """Отправляет конкретный тип напоминания."""
        style = user.reminder_style or 'friendly'
        
        # Тексты напоминаний
        morning_texts = {
            'friendly': "🌅 Доброе утро! Не забудь сделать утренний чек-ин: взвеситься и оценить сон.",
            'motivational': "🔥 Новый день - новый шаг к цели! Время для утреннего чек-ина!",
            'strict': "📊 Требуется утренний чек-ин: вес, сон."
        }
        evening_texts = {
            'friendly': "🌙 Добрый вечер! Как прошел день? Запиши шаги и выпитую воду.",
            'motivational': "💪 Отличная работа сегодня! Зафиксируй свои результаты в вечернем чек-ине.",
            'strict': "📊 Требуется вечерний чек-ин: шаги, вода, заметки."
        }
        
        text = ""
        if reminder_type == 'morning':
            text = morning_texts.get(style, morning_texts['friendly'])
        elif reminder_type == 'evening':
            text = evening_texts.get(style, evening_texts['friendly'])
        elif reminder_type == 'water':
            text = f"💧 Напоминание о воде! Сегодня выпито: {water_level/1000:.1f}л. Не забывай пить достаточно!"

        try:
            keyboard = get_checkin_reminder_keyboard() if reminder_type != 'water' else None
            await self.bot.send_message(
                user.telegram_id,
                text,
                reply_markup=keyboard
            )
            logger.info(f"Отправлено '{reminder_type}' напоминание пользователю {user.telegram_id}")
        except Exception as e:
            logger.error(f"Не удалось отправить напоминание {user.telegram_id}: {e}")