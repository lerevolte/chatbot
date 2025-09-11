import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Optional
from aiogram import Bot
from sqlalchemy import select, and_

from database.models import User, CheckIn
from database.connection import get_session
from bot.keyboards.checkin import get_checkin_reminder_keyboard

logger = logging.getLogger(__name__)

class ReminderService:
    """Сервис для отправки напоминаний о чек-инах"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.running = False
        self.tasks = []
        
        # ========== НАСТРОЙКИ ВРЕМЕНИ НАПОМИНАНИЙ ==========
        self.morning_time = time(8, 0)  # 8:00 утра
        self.evening_time = time(20, 0)  # 20:00 вечера
        self.water_reminder_times = [
            time(10, 0),  # 10:00
            time(13, 0),  # 13:00
            time(16, 0),  # 16:00
            time(19, 0),  # 19:00
        ]
    
    async def start(self):
        """Запуск сервиса напоминаний"""
        if self.running:
            return
        
        self.running = True
        logger.info("Сервис напоминаний запущен")
        
        # Запускаем задачи
        self.tasks = [
            asyncio.create_task(self.morning_reminder_loop()),
            asyncio.create_task(self.evening_reminder_loop()),
            asyncio.create_task(self.water_reminder_loop()),
        ]
    
    async def stop(self):
        """Остановка сервиса"""
        self.running = False
        for task in self.tasks:
            task.cancel()
        logger.info("Сервис напоминаний остановлен")
    
    async def morning_reminder_loop(self):
        """Цикл утренних напоминаний"""
        while self.running:
            try:
                # Вычисляем время до следующего напоминания
                now = datetime.now()
                next_reminder = datetime.combine(now.date(), self.morning_time)
                
                if next_reminder <= now:
                    # Если время уже прошло, планируем на завтра
                    next_reminder += timedelta(days=1)
                
                # Ждем до времени напоминания
                wait_seconds = (next_reminder - now).total_seconds()
                await asyncio.sleep(wait_seconds)
                
                if not self.running:
                    break
                
                # Отправляем напоминания
                await self.send_morning_reminders()
                
                # Ждем минуту перед следующей проверкой
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в утренних напоминаниях: {e}")
                await asyncio.sleep(60)
    
    async def evening_reminder_loop(self):
        """Цикл вечерних напоминаний"""
        while self.running:
            try:
                now = datetime.now()
                next_reminder = datetime.combine(now.date(), self.evening_time)
                
                if next_reminder <= now:
                    next_reminder += timedelta(days=1)
                
                wait_seconds = (next_reminder - now).total_seconds()
                await asyncio.sleep(wait_seconds)
                
                if not self.running:
                    break
                
                await self.send_evening_reminders()
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в вечерних напоминаниях: {e}")
                await asyncio.sleep(60)
    
    async def water_reminder_loop(self):
        """Цикл напоминаний о воде"""
        while self.running:
            try:
                now = datetime.now()
                
                # Находим следующее время напоминания
                next_time = None
                for reminder_time in self.water_reminder_times:
                    next_reminder = datetime.combine(now.date(), reminder_time)
                    if next_reminder > now:
                        next_time = next_reminder
                        break
                
                if not next_time:
                    # Все напоминания на сегодня прошли, планируем на завтра
                    next_time = datetime.combine(
                        now.date() + timedelta(days=1),
                        self.water_reminder_times[0]
                    )
                
                wait_seconds = (next_time - now).total_seconds()
                await asyncio.sleep(wait_seconds)
                
                if not self.running:
                    break
                
                await self.send_water_reminders()
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в напоминаниях о воде: {e}")
                await asyncio.sleep(60)
    
    async def send_morning_reminders(self):
        """Отправка утренних напоминаний"""
        async with get_session() as session:
            # Получаем активных пользователей
            result = await session.execute(
                select(User).where(
                    and_(
                        User.is_active == True,
                        User.onboarding_completed == True
                    )
                )
            )
            users = result.scalars().all()
            
            keyboard = get_checkin_reminder_keyboard()
            
            for user in users:
                try:
                    # Проверяем, не сделан ли уже утренний чек-ин
                    today = datetime.now().date()
                    result = await session.execute(
                        select(CheckIn).where(
                            and_(
                                CheckIn.user_id == user.id,
                                CheckIn.date >= datetime.combine(today, datetime.min.time()),
                                CheckIn.date <= datetime.combine(today, datetime.max.time())
                            )
                        )
                    )
                    checkin = result.scalar_one_or_none()
                    
                    if not checkin or not checkin.weight:
                        # Если чек-ин не сделан или не записан вес
                        await self.bot.send_message(
                            user.telegram_id,
                            "🌅 Доброе утро!\n\n"
                            "Не забудь сделать утренний чек-ин:\n"
                            "• Взвесься натощак\n"
                            "• Отметь качество сна\n"
                            "• Оцени самочувствие\n\n"
                            "Это займет всего минуту!",
                            reply_markup=keyboard
                        )
                        logger.info(f"Отправлено утреннее напоминание пользователю {user.telegram_id}")
                
                except Exception as e:
                    logger.error(f"Ошибка при отправке напоминания пользователю {user.telegram_id}: {e}")
    
    async def send_evening_reminders(self):
        """Отправка вечерних напоминаний"""
        async with get_session() as session:
            result = await session.execute(
                select(User).where(
                    and_(
                        User.is_active == True,
                        User.onboarding_completed == True
                    )
                )
            )
            users = result.scalars().all()
            
            keyboard = get_checkin_reminder_keyboard()
            
            for user in users:
                try:
                    # Получаем сегодняшний чек-ин
                    today = datetime.now().date()
                    result = await session.execute(
                        select(CheckIn).where(
                            and_(
                                CheckIn.user_id == user.id,
                                CheckIn.date >= datetime.combine(today, datetime.min.time()),
                                CheckIn.date <= datetime.combine(today, datetime.max.time())
                            )
                        )
                    )
                    checkin = result.scalar_one_or_none()
                    
                    # Формируем персонализированное сообщение
                    message = "🌙 Добрый вечер!\n\n"
                    
                    if not checkin or not checkin.steps:
                        message += "📝 Не забудь записать:\n"
                        if not checkin or not checkin.steps:
                            message += "• Количество шагов за день\n"
                        if not checkin or not checkin.water_ml:
                            message += "• Сколько воды выпил(а)\n"
                        message += "• Заметки о дне\n"
                    else:
                        message += "Как прошел день? Запиши свои впечатления!"
                    
                    await self.bot.send_message(
                        user.telegram_id,
                        message,
                        reply_markup=keyboard
                    )
                    logger.info(f"Отправлено вечернее напоминание пользователю {user.telegram_id}")
                
                except Exception as e:
                    logger.error(f"Ошибка при отправке напоминания пользователю {user.telegram_id}: {e}")
    
    async def send_water_reminders(self):
        """Отправка напоминаний о воде"""
        async with get_session() as session:
            result = await session.execute(
                select(User).where(
                    and_(
                        User.is_active == True,
                        User.onboarding_completed == True
                    )
                )
            )
            users = result.scalars().all()
            
            for user in users:
                try:
                    # Получаем сегодняшний чек-ин
                    today = datetime.now().date()
                    result = await session.execute(
                        select(CheckIn).where(
                            and_(
                                CheckIn.user_id == user.id,
                                CheckIn.date >= datetime.combine(today, datetime.min.time()),
                                CheckIn.date <= datetime.combine(today, datetime.max.time())
                            )
                        )
                    )
                    checkin = result.scalar_one_or_none()
                    
                    current_water = checkin.water_ml if checkin and checkin.water_ml else 0
                    
                    # Отправляем напоминание только если выпито меньше цели
                    if current_water < 2000:
                        remaining = 2000 - current_water
                        await self.bot.send_message(
                            user.telegram_id,
                            f"💧 Напоминание о воде!\n\n"
                            f"Сегодня выпито: {current_water/1000:.1f}л\n"
                            f"До цели осталось: {remaining/1000:.1f}л\n\n"
                            f"Используй /checkin для быстрого добавления"
                        )
                        logger.info(f"Отправлено напоминание о воде пользователю {user.telegram_id}")
                
                except Exception as e:
                    logger.error(f"Ошибка при отправке напоминания пользователю {user.telegram_id}: {e}")