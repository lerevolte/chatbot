import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from bot.config import settings
from bot.handlers import start, profile, meal_plan, checkin, stats, integrations, payment, analytics, help
from bot.services.smart_reminder import SmartReminderService
from bot.services.fitness_tracker_integration import FitnessIntegrationService
from database.connection import init_db
from datetime import datetime, timedelta

# Настройка логирования
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальные сервисы
reminder_service = None
fitness_service = None

async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    global reminder_service, fitness_service
    
    logger.info("Запуск сервисов...")
    
    # Инициализация БД
    await init_db()
    
    # Запуск сервиса умных напоминаний
    reminder_service = SmartReminderService(bot)
    await reminder_service.start()
    logger.info("Сервис умных напоминаний запущен")
    
    # Инициализация сервиса интеграций
    fitness_service = FitnessIntegrationService()
    await fitness_service.load_user_integrations()
    logger.info("Сервис интеграций инициализирован")
    
    # Устанавливаем команды бота
    await set_bot_commands(bot)
    
    logger.info("Бот успешно запущен и готов к работе!")

async def on_shutdown(bot: Bot):
    """Действия при остановке бота"""
    global reminder_service
    
    logger.info("Остановка сервисов...")
    
    if reminder_service:
        await reminder_service.stop()
    
    logger.info("Все сервисы остановлены")

async def set_bot_commands(bot: Bot):
    """Установка команд бота в меню"""
    from aiogram.types import BotCommand
    
    commands = [
        BotCommand(command="start", description="🚀 Начать работу"),
        BotCommand(command="profile", description="👤 Мой профиль"),
        BotCommand(command="meal_plan", description="🍽 План питания"),
        BotCommand(command="checkin", description="✅ Чек-ин"),
        BotCommand(command="stats", description="📊 Статистика и графики"),
        BotCommand(command="analytics", description="📈 Аналитика и адаптация"),
        BotCommand(command="integrations", description="🔗 Интеграции"),
        BotCommand(command="reminder_settings", description="⏰ Настройки напоминаний"),
        BotCommand(command="settings", description="⚙️ Настройки"),
        BotCommand(command="help", description="❓ Помощь"),
    ]
    
    await bot.set_my_commands(commands)

async def auto_sync_task():
    """Фоновая задача для автоматической синхронизации данных"""
    global fitness_service
    
    while True:
        try:
            # Ждем до 6 утра следующего дня
            now = datetime.now()
            tomorrow = now.replace(hour=6, minute=0, second=0, microsecond=0) + timedelta(days=1)
            wait_seconds = (tomorrow - now).total_seconds()
            
            await asyncio.sleep(wait_seconds)
            
            # Синхронизируем данные для всех пользователей с интеграциями
            if fitness_service:
                logger.info("Начинаем автоматическую синхронизацию данных...")
                
                # Получаем всех пользователей с интеграциями
                for user_id, services in fitness_service.user_integrations.items():
                    try:
                        results = await fitness_service.sync_all(user_id)
                        logger.info(f"Синхронизация для пользователя {user_id}: {results}")
                    except Exception as e:
                        logger.error(f"Ошибка синхронизации для {user_id}: {e}")
                
                logger.info("Автоматическая синхронизация завершена")
            
            # Ждем 24 часа до следующей синхронизации
            await asyncio.sleep(86400)
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Ошибка в задаче автосинхронизации: {e}")
            await asyncio.sleep(3600)  # Ждем час при ошибке

async def main():
    # Инициализация БД
    await init_db()
    
    # Инициализация Redis для FSM
    redis = Redis.from_url(settings.redis_url)
    storage = RedisStorage(redis=redis)
    
    # Инициализация бота и диспетчера
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher(storage=storage)

    # Регистрация обработчиков startup и shutdown
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Регистрация хендлеров
    dp.include_router(start.router)
    dp.include_router(profile.router)
    dp.include_router(meal_plan.router)
    dp.include_router(checkin.router)
    dp.include_router(stats.router)  # Новый роутер для статистики
    dp.include_router(integrations.router)  # Новый роутер для интеграций
    dp.include_router(payment.router)
    dp.include_router(analytics.router)
    dp.include_router(help.router)

    # Создаем фоновые задачи
    auto_sync = asyncio.create_task(auto_sync_task())

    plateau_check = asyncio.create_task(plateau_check_task())
    
    # Запуск бота
    logger.info("Бот запущен")
    try:
        await dp.start_polling(bot)
    finally:
        auto_sync.cancel()
        await bot.session.close()
        await redis.aclose()

async def plateau_check_task():
    """Фоновая задача для автоматической проверки плато у всех пользователей"""
    from bot.services.plateau_adaptation import PlateauAdaptationService
    from bot.services.motivation_service import MotivationService
    
    plateau_service = PlateauAdaptationService()
    motivation_service = MotivationService()
    
    while True:
        try:
            # Проверяем раз в день в 10 утра
            now = datetime.now()
            tomorrow = now.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)
            wait_seconds = (tomorrow - now).total_seconds()
            
            await asyncio.sleep(wait_seconds)
            
            logger.info("Начинаем ежедневную проверку плато...")
            
            async with get_session() as session:
                # Получаем всех активных пользователей
                result = await session.execute(
                    select(User).where(
                        and_(
                            User.is_active == True,
                            User.onboarding_completed == True,
                            User.is_premium == True  # Только для премиум пользователей
                        )
                    )
                )
                users = result.scalars().all()
                
                for user in users:
                    try:
                        # Проверяем плато
                        plateau_data = await plateau_service._detect_plateau(user.id)
                        
                        if plateau_data['is_plateau'] and plateau_data['plateau_days'] == 7:
                            # Первая неделя плато - отправляем уведомление
                            motivation = await motivation_service.get_plateau_motivation(user.telegram_id)
                            
                            await bot.send_message(
                                user.telegram_id,
                                f"📊 **Автоматический анализ прогресса**\n\n"
                                f"Обнаружено плато веса (7 дней без изменений).\n\n"
                                f"{motivation}\n\n"
                                f"Используйте /analytics для детального анализа и адаптации плана.",
                                parse_mode="Markdown"
                            )
                            
                        elif plateau_data['plateau_days'] >= 14:
                            # Две недели плато - автоматическая адаптация
                            result = await plateau_service.check_and_adapt(user.telegram_id)
                            
                            if result['success'] and result.get('is_plateau'):
                                await bot.send_message(
                                    user.telegram_id,
                                    "🔄 **Автоматическая адаптация плана**\n\n"
                                    "Ваш план был автоматически скорректирован для прорыва плато.\n"
                                    "Изменения вступят в силу со следующего дня.\n\n"
                                    "Подробности: /analytics",
                                    parse_mode="Markdown"
                                )
                    
                    except Exception as e:
                        logger.error(f"Ошибка проверки плато для пользователя {user.id}: {e}")
            
            logger.info(f"Проверка плато завершена для {len(users)} пользователей")
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Ошибка в задаче проверки плато: {e}")
            await asyncio.sleep(3600)  # При ошибке ждем час

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise