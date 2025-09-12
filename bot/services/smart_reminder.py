mport asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Optional, List, Dict
from zoneinfo import ZoneInfo
from aiogram import Bot
from sqlalchemy import select, and_, func

from database.models import User, CheckIn
from database.connection import get_session
from bot.keyboards.checkin import get_checkin_reminder_keyboard
from bot.config import settings

logger = logging.getLogger(__name__)

class SmartReminderService:
    """Сервис умных адаптивных напоминаний с учетом часового пояса и паттернов пользователя"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.running = False
        self.tasks = []
        
        # Хранилище паттернов пользователей
        self.user_patterns = {}
        
        # Базовые времена напоминаний (по умолчанию в UTC)
        self.default_reminders = {
            'morning': time(8, 0),
            'lunch': time(12, 30),
            'evening': time(20, 0),
            'water': [time(10, 0), time(14, 0), time(16, 0), time(18, 0)]
        }
    
    async def start(self):
        """Запуск сервиса умных напоминаний"""
        if self.running:
            return
        
        self.running = True
        logger.info("Сервис умных напоминаний запущен")
        
        # Загружаем паттерны пользователей
        await self.load_user_patterns()
        
        # Запускаем основной цикл
        self.tasks = [
            asyncio.create_task(self.smart_reminder_loop()),
            asyncio.create_task(self.pattern_analyzer_loop()),
        ]
    
    async def stop(self):
        """Остановка сервиса"""
        self.running = False
        for task in self.tasks:
            task.cancel()
        logger.info("Сервис умных напоминаний остановлен")
    
    async def load_user_patterns(self):
        """Загружает и анализирует паттерны активности пользователей"""
        async with get_session() as session:
            # Получаем всех активных пользователей
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
                # Анализируем паттерны чек-инов за последние 30 дней
                month_ago = datetime.now() - timedelta(days=30)
                result = await session.execute(
                    select(CheckIn).where(
                        and_(
                            CheckIn.user_id == user.id,
                            CheckIn.date >= month_ago
                        )
                    )
                )
                checkins = result.scalars().all()
                
                if len(checkins) >= 7:  # Минимум неделя данных
                    pattern = self.analyze_user_pattern(checkins, user)
                    self.user_patterns[user.telegram_id] = pattern
                    logger.info(f"Загружен паттерн для пользователя {user.telegram_id}")
    
    def analyze_user_pattern(self, checkins: List[CheckIn], user: User) -> Dict:
        """Анализирует паттерны активности пользователя"""
        pattern = {
            'timezone': self.detect_timezone(checkins),
            'morning_time': None,
            'evening_time': None,
            'most_active_time': None,
            'checkin_consistency': 0,
            'preferred_reminder_style': 'friendly',  # friendly, motivational, strict
            'water_consumption_pattern': [],
            'sleep_pattern': {'average': 0, 'bedtime': None, 'wake_time': None},
            'skip_days': [],  # Дни недели, когда пользователь обычно пропускает
            'reminder_effectiveness': {}
        }
        
        # Анализ времени утренних чек-инов
        morning_times = []
        evening_times = []
        
        for checkin in checkins:
            checkin_hour = checkin.date.hour
            
            # Определяем утренние чек-ины (обычно с весом)
            if checkin.weight and 4 <= checkin_hour <= 11:
                morning_times.append(checkin_hour)
            
            # Определяем вечерние чек-ины (обычно с шагами)
            if checkin.steps and 17 <= checkin_hour <= 23:
                evening_times.append(checkin_hour)
        
        # Среднее время утренних чек-инов
        if morning_times:
            avg_morning = sum(morning_times) / len(morning_times)
            pattern['morning_time'] = time(int(avg_morning), int((avg_morning % 1) * 60))
        
        # Среднее время вечерних чек-инов
        if evening_times:
            avg_evening = sum(evening_times) / len(evening_times)
            pattern['evening_time'] = time(int(avg_evening), int((avg_evening % 1) * 60))
        
        # Анализ consistency (регулярности)
        total_days = (checkins[-1].date - checkins[0].date).days + 1
        pattern['checkin_consistency'] = len(checkins) / total_days if total_days > 0 else 0
        
        # Анализ паттерна сна
        sleep_data = [c.sleep_hours for c in checkins if c.sleep_hours]
        if sleep_data:
            pattern['sleep_pattern']['average'] = sum(sleep_data) / len(sleep_data)
            
            # Предполагаемое время сна (на основе среднего сна и времени утреннего чек-ина)
            if pattern['morning_time']:
                wake_hour = pattern['morning_time'].hour
                bedtime_hour = (wake_hour - int(pattern['sleep_pattern']['average'])) % 24
                pattern['sleep_pattern']['bedtime'] = time(bedtime_hour, 0)
                pattern['sleep_pattern']['wake_time'] = pattern['morning_time']
        
        # Определяем стиль напоминаний на основе цели
        if user.goal == "lose_weight":
            pattern['preferred_reminder_style'] = 'motivational'
        elif user.goal == "gain_muscle":
            pattern['preferred_reminder_style'] = 'strict'
        else:
            pattern['preferred_reminder_style'] = 'friendly'
        
        # Анализ дней пропусков
        weekday_counts = {i: 0 for i in range(7)}
        for checkin in checkins:
            weekday_counts[checkin.date.weekday()] += 1
        
        avg_checkins = sum(weekday_counts.values()) / 7
        pattern['skip_days'] = [day for day, count in weekday_counts.items() 
                                if count < avg_checkins * 0.5]
        
        return pattern
    
    def detect_timezone(self, checkins: List[CheckIn]) -> str:
        """Пытается определить часовой пояс пользователя по паттернам активности"""
        # Анализируем время создания чек-инов
        creation_hours = [c.date.hour for c in checkins if c.weight]  # Утренние чек-ины
        
        if not creation_hours:
            return "UTC"  # По умолчанию
        
        # Предполагаем, что утренние взвешивания происходят между 6:00 и 10:00 местного времени
        avg_hour = sum(creation_hours) / len(creation_hours)
        
        # Оцениваем смещение от UTC
        if 6 <= avg_hour <= 10:
            # Вероятно, уже в правильном часовом поясе
            return "UTC"
        elif avg_hour < 6:
            # Чек-ины раньше, возможно пользователь восточнее
            offset = 6 - avg_hour
            return f"UTC+{int(offset)}"
        else:
            # Чек-ины позже, возможно пользователь западнее
            offset = avg_hour - 8
            return f"UTC-{int(offset)}"
    
    async def smart_reminder_loop(self):
        """Основной цикл умных напоминаний"""
        while self.running:
            try:
                now = datetime.now()
                
                # Проверяем каждого пользователя
                for telegram_id, pattern in self.user_patterns.items():
                    await self.check_and_send_reminders(telegram_id, pattern, now)
                
                # Ждем 5 минут перед следующей проверкой
                await asyncio.sleep(300)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в цикле умных напоминаний: {e}")
                await asyncio.sleep(60)
    
    async def check_and_send_reminders(self, telegram_id: int, pattern: Dict, now: datetime):
        """Проверяет и отправляет персонализированные напоминания"""
        # Проверяем, не день ли пропуска
        if now.weekday() in pattern.get('skip_days', []):
            return
        
        async with get_session() as session:
            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return
            
            # Получаем сегодняшний чек-ин
            today = now.date()
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
            
            # Определяем, какие напоминания нужно отправить
            current_time = now.time()
            
            # Утреннее напоминание
            if pattern.get('morning_time'):
                reminder_time = pattern['morning_time']
                time_diff = abs((current_time.hour * 60 + current_time.minute) - 
                              (reminder_time.hour * 60 + reminder_time.minute))
                
                if time_diff <= 5 and (not checkin or not checkin.weight):
                    await self.send_smart_morning_reminder(telegram_id, user, pattern)
            
            # Вечернее напоминание
            if pattern.get('evening_time'):
                reminder_time = pattern['evening_time']
                time_diff = abs((current_time.hour * 60 + current_time.minute) - 
                              (reminder_time.hour * 60 + reminder_time.minute))
                
                if time_diff <= 5 and (not checkin or not checkin.steps):
                    await self.send_smart_evening_reminder(telegram_id, user, pattern, checkin)
            
            # Адаптивные напоминания о воде
            if self.should_send_water_reminder(pattern, current_time, checkin):
                await self.send_smart_water_reminder(telegram_id, user, pattern, checkin)
    
    async def send_smart_morning_reminder(self, telegram_id: int, user: User, pattern: Dict):
        """Отправляет персонализированное утреннее напоминание"""
        style = pattern.get('preferred_reminder_style', 'friendly')
        
        messages = {
            'friendly': [
                "🌅 Доброе утро! Как спалось? Не забудь записать утренний вес и настроение 😊",
                "☀️ Привет! Новый день - новые возможности! Начнем с утреннего чек-ина?",
                "🌞 Утро! Время для быстрого чек-ина. Это займет всего минутку!"
            ],
            'motivational': [
                "💪 Вставай, чемпион! Время взвеситься и начать день с победы!",
                "🔥 Подъем! Каждый день - это шаг к твоей цели. Начнем с чек-ина!",
                "⚡ Утро! Ты на пути к лучшей версии себя. Зафиксируем прогресс?"
            ],
            'strict': [
                "📊 Время утреннего чек-ина. Вес, сон, настроение - записываем всё.",
                "⏰ Утренний чек-ин. Дисциплина - ключ к результату.",
                "📝 Доброе утро. Не забудь про обязательный утренний чек-ин."
            ]
        }
        
        # Выбираем сообщение
        import random
        message = random.choice(messages.get(style, messages['friendly']))
        
        # Добавляем персонализацию на основе данных
        if pattern.get('sleep_pattern', {}).get('average'):
            avg_sleep = pattern['sleep_pattern']['average']
            if avg_sleep < 7:
                message += "\n\n💤 Кстати, ты в последнее время мало спишь. Постарайся сегодня лечь пораньше!"
        
        keyboard = get_checkin_reminder_keyboard()
        
        try:
            await self.bot.send_message(
                telegram_id,
                message,
                reply_markup=keyboard
            )
            logger.info(f"Отправлено умное утреннее напоминание пользователю {telegram_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки напоминания: {e}")
    
    async def send_smart_evening_reminder(self, telegram_id: int, user: User, pattern: Dict, checkin: Optional[CheckIn]):
        """Отправляет персонализированное вечернее напоминание"""
        style = pattern.get('preferred_reminder_style', 'friendly')
        
        # Базовое сообщение
        base_messages = {
            'friendly': "🌙 Добрый вечер! Как прошел день?",
            'motivational': "🔥 Вечер - время подвести итоги! Ты молодец!",
            'strict': "📊 Вечерний чек-ин. Время записать активность."
        }
        
        message = base_messages.get(style, base_messages['friendly'])
        
        # Добавляем персонализированные элементы
        missing = []
        if not checkin or not checkin.steps:
            missing.append("шаги")
        if not checkin or not checkin.water_ml:
            missing.append("воду")
        
        if missing:
            message += f"\n\n📝 Не забудь записать: {', '.join(missing)}"
        
        # Добавляем мотивацию на основе consistency
        if pattern.get('checkin_consistency', 0) > 0.8:
            message += "\n\n🏆 У тебя отличная дисциплина! Продолжай в том же духе!"
        elif pattern.get('checkin_consistency', 0) < 0.5:
            message += "\n\n💡 Регулярные чек-ины помогут достичь цели быстрее!"
        
        keyboard = get_checkin_reminder_keyboard()
        
        try:
            await self.bot.send_message(
                telegram_id,
                message,
                reply_markup=keyboard
            )
            logger.info(f"Отправлено умное вечернее напоминание пользователю {telegram_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки напоминания: {e}")
    
    async def send_smart_water_reminder(self, telegram_id: int, user: User, pattern: Dict, checkin: Optional[CheckIn]):
        """Отправляет умное напоминание о воде"""
        current_water = checkin.water_ml if checkin and checkin.water_ml else 0
        target_water = 2000  # или calculate_water_intake(user.current_weight)
        
        if current_water >= target_water:
            return  # Цель достигнута
        
        remaining = target_water - current_water
        percent_done = (current_water / target_water) * 100
        
        # Персонализированное сообщение
        if percent_done < 30:
            message = f"💧 Пора пить воду! Сегодня выпито всего {current_water/1000:.1f}л из {target_water/1000:.1f}л"
            emoji = "🏜"
        elif percent_done < 60:
            message = f"💦 Не забывай про воду! Выпито {current_water/1000:.1f}л, осталось {remaining/1000:.1f}л"
            emoji = "💧"
        else:
            message = f"💦 Почти у цели! Осталось всего {remaining/1000:.1f}л воды"
            emoji = "🌊"
        
        # Добавляем совет
        tips = [
            "💡 Совет: Держи бутылку воды на видном месте",
            "💡 Лайфхак: Выпивай стакан воды перед каждым приемом пищи",
            "💡 Попробуй добавить лимон или мяту для вкуса",
            "💡 Установи напоминания на телефоне каждые 2 часа"
        ]
        
        import random
        message += f"\n\n{random.choice(tips)}"
        
        try:
            await self.bot.send_message(telegram_id, f"{emoji} {message}")
            logger.info(f"Отправлено напоминание о воде пользователю {telegram_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки напоминания о воде: {e}")
    
    def should_send_water_reminder(self, pattern: Dict, current_time: time, checkin: Optional[CheckIn]) -> bool:
        """Определяет, нужно ли отправить напоминание о воде"""
        # Не напоминаем ночью
        if current_time.hour < 7 or current_time.hour > 22:
            return False
        
        # Проверяем, сколько уже выпито
        current_water = checkin.water_ml if checkin and checkin.water_ml else 0
        if current_water >= 2000:
            return False
        
        # Адаптивная логика: чаще напоминаем, если мало пьет
        hour_of_day = current_time.hour
        expected_by_now = (hour_of_day - 7) / 15 * 2000  # Линейное распределение с 7:00 до 22:00
        
        if current_water < expected_by_now * 0.7:  # Отстает от графика
            # Напоминаем каждые 2 часа
            return current_time.minute < 5 and current_time.hour % 2 == 0
        else:
            # Напоминаем каждые 3 часа
            return current_time.minute < 5 and current_time.hour % 3 == 0
    
    async def pattern_analyzer_loop(self):
        """Периодически обновляет паттерны пользователей"""
        while self.running:
            try:
                # Обновляем паттерны раз в сутки
                await asyncio.sleep(86400)  # 24 часа
                
                if not self.running:
                    break
                
                logger.info("Обновление паттернов пользователей...")
                await self.load_user_patterns()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в анализаторе паттернов: {e}")
                await asyncio.sleep(3600)
    
    async def update_reminder_effectiveness(self, telegram_id: int, reminder_type: str, responded: bool):
        """Обновляет данные об эффективности напоминаний"""
        if telegram_id not in self.user_patterns:
            return
        
        pattern = self.user_patterns[telegram_id]
        if 'reminder_effectiveness' not in pattern:
            pattern['reminder_effectiveness'] = {}
        
        if reminder_type not in pattern['reminder_effectiveness']:
            pattern['reminder_effectiveness'][reminder_type] = {
                'sent': 0,
                'responded': 0,
                'response_rate': 0
            }
        
        stats = pattern['reminder_effectiveness'][reminder_type]
        stats['sent'] += 1
        if responded:
            stats['responded'] += 1
        stats['response_rate'] = stats['responded'] / stats['sent']
        
        # Адаптируем стратегию на основе эффективности
        if stats['response_rate'] < 0.3 and stats['sent'] > 10:
            # Низкая эффективность - меняем подход
            logger.info(f"Низкая эффективность напоминаний {reminder_type} для {telegram_id}")
            await self.adapt_reminder_strategy(telegram_id, reminder_type)
    
    async def adapt_reminder_strategy(self, telegram_id: int, reminder_type: str):
        """Адаптирует стратегию напоминаний на основе обратной связи"""
        pattern = self.user_patterns.get(telegram_id)
        if not pattern:
            return
        
        # Меняем стиль напоминаний
        styles = ['friendly', 'motivational', 'strict']
        current_style = pattern.get('preferred_reminder_style', 'friendly')
        current_index = styles.index(current_style)
        new_style = styles[(current_index + 1) % len(styles)]
        pattern['preferred_reminder_style'] = new_style
        
        logger.info(f"Изменен стиль напоминаний для {telegram_id}: {current_style} -> {new_style}")
    
    async def set_user_timezone(self, telegram_id: int, timezone: str):
        """Устанавливает часовой пояс пользователя"""
        if telegram_id not in self.user_patterns:
            self.user_patterns[telegram_id] = {}
        
        self.user_patterns[telegram_id]['timezone'] = timezone
        logger.info(f"Установлен часовой пояс {timezone} для пользователя {telegram_id}")
    
    async def set_custom_reminder_time(self, telegram_id: int, reminder_type: str, custom_time: time):
        """Устанавливает пользовательское время напоминания"""
        if telegram_id not in self.user_patterns:
            self.user_patterns[telegram_id] = {}
        
        if reminder_type == 'morning':
            self.user_patterns[telegram_id]['morning_time'] = custom_time
        elif reminder_type == 'evening':
            self.user_patterns[telegram_id]['evening_time'] = custom_time
        
        logger.info(f"Установлено время {reminder_type} напоминания {custom_time} для {telegram_id}")
    
    async def disable_reminders(self, telegram_id: int, reminder_type: Optional[str] = None):
        """Отключает напоминания для пользователя"""
        if telegram_id not in self.user_patterns:
            return
        
        if reminder_type:
            # Отключаем конкретный тип
            self.user_patterns[telegram_id][f'{reminder_type}_disabled'] = True
        else:
            # Отключаем все напоминания
            self.user_patterns[telegram_id]['all_disabled'] = True
        
        logger.info(f"Отключены напоминания {reminder_type or 'все'} для {telegram_id}")