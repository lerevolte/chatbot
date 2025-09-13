import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import select, and_, func

from database.models import User, CheckIn, Goal
from database.connection import get_session

logger = logging.getLogger(__name__)

class MotivationService:
    """Сервис для генерации персонализированного мотивационного контента"""
    
    def __init__(self):
        self.quotes = {
            Goal.LOSE_WEIGHT: [
                "Каждый шаг приближает тебя к цели! 🚶‍♀️",
                "Ты сильнее, чем думаешь! 💪",
                "Результат = постоянство × время ⏰",
                "Твое тело - это проект, над которым ты работаешь 🏗",
                "Не сдавайся! Самое сложное уже позади 🎯",
                "Прогресс, а не совершенство! 📈",
                "Ты уже прошел {progress}% пути! 🛤",
                "Минус {lost_weight} кг - это твоя победа! 🏆",
                "Каждый день ты становишься лучшей версией себя ✨",
                "Помни, зачем ты начал этот путь 🎯"
            ],
            Goal.GAIN_MUSCLE: [
                "Мышцы растут, когда ты отдыхаешь! 😴",
                "Сила приходит изнутри! 💪",
                "Каждая тренировка - это инвестиция в себя 📈",
                "Ты строишь не просто тело, а характер! 🏗",
                "Прогресс измеряется не только весом! 📊",
                "Питание - это 70% успеха! 🍽",
                "Плюс {gained_weight} кг качественной массы! 💪",
                "Ты на {progress}% ближе к цели! 🎯",
                "Терпение и труд - твои лучшие друзья 🤝",
                "Сильное тело = сильный дух! 🧠"
            ],
            Goal.MAINTAIN: [
                "Баланс - это искусство! ⚖️",
                "Стабильность - признак мастерства! 🎯",
                "Ты отлично держишь форму! 👏",
                "Поддержание результата - это тоже победа! 🏆",
                "Здоровье - это марафон, не спринт 🏃‍♂️",
                "Ты создаешь здоровые привычки на всю жизнь! 🌟",
                "Consistency is key! 🔑",
                "Твой вес стабилен уже {stable_days} дней! 📊",
                "Продолжай в том же духе! 💪",
                "Ты - пример для подражания! ⭐"
            ]
        }
        
        self.achievements = {
            "first_checkin": {"emoji": "🎯", "text": "Первый чек-ин"},
            "week_streak": {"emoji": "🔥", "text": "Неделя без пропусков"},
            "month_streak": {"emoji": "⭐", "text": "Месяц дисциплины"},
            "weight_milestone_5": {"emoji": "🏅", "text": "Минус 5 кг"},
            "weight_milestone_10": {"emoji": "🏆", "text": "Минус 10 кг"},
            "steps_10k": {"emoji": "👟", "text": "10 000 шагов"},
            "water_goal": {"emoji": "💧", "text": "Норма воды 7 дней подряд"},
            "photo_streak": {"emoji": "📸", "text": "Фото еды каждый день"},
            "perfect_week": {"emoji": "💯", "text": "Идеальная неделя"},
            "plateau_breakthrough": {"emoji": "🚀", "text": "Прорыв плато"}
        }
        
        self.tips = {
            "morning": [
                "💡 Начни день со стакана воды с лимоном",
                "💡 Сделай 10 минут зарядки для бодрости",
                "💡 Взвешивайся в одно и то же время",
                "💡 Съешь белковый завтрак в течение часа после пробуждения",
                "💡 Запланируй приемы пищи на день"
            ],
            "afternoon": [
                "💡 Время для прогулки! Добавь 2000 шагов",
                "💡 Не забудь про перекус с белком",
                "💡 Выпей 2 стакана воды прямо сейчас",
                "💡 Сделай 5-минутную растяжку",
                "💡 Проверь, достаточно ли ты съел белка"
            ],
            "evening": [
                "💡 Последний прием пищи за 3 часа до сна",
                "💡 Подготовь одежду для завтрашней тренировки",
                "💡 Запиши 3 вещи, за которые благодарен сегодня",
                "💡 Выключи экраны за час до сна",
                "💡 Выпей травяной чай для расслабления"
            ]
        }
        
        self.challenges = {
            "beginner": [
                {"name": "Водный старт", "task": "Выпивать 2л воды 3 дня подряд", "reward": "🏅"},
                {"name": "Шаговый марафон", "task": "8000 шагов каждый день недели", "reward": "🏃‍♂️"},
                {"name": "Фото-дневник", "task": "Фотографировать все приемы пищи 3 дня", "reward": "📸"},
                {"name": "Ранняя пташка", "task": "Завтрак до 9:00 всю неделю", "reward": "🌅"},
                {"name": "Белковый понедельник", "task": "Достичь нормы белка в понедельник", "reward": "💪"}
            ],
            "intermediate": [
                {"name": "10K челлендж", "task": "10 000 шагов 5 дней подряд", "reward": "🎯"},
                {"name": "Без сахара", "task": "3 дня без добавленного сахара", "reward": "🍯"},
                {"name": "HIIT неделя", "task": "3 HIIT тренировки за неделю", "reward": "🔥"},
                {"name": "Meal prep Sunday", "task": "Приготовить еду на 3 дня вперед", "reward": "🍱"},
                {"name": "Спящая красавица", "task": "8 часов сна 5 ночей подряд", "reward": "😴"}
            ],
            "advanced": [
                {"name": "Железная дисциплина", "task": "Месяц без пропусков чек-инов", "reward": "👑"},
                {"name": "Марафонец", "task": "100 000 шагов за неделю", "reward": "🏃‍♀️"},
                {"name": "Чистое питание", "task": "Неделя без обработанной пищи", "reward": "🥗"},
                {"name": "Силовой месяц", "task": "12 силовых тренировок за месяц", "reward": "💪"},
                {"name": "Трансформация", "task": "Достичь промежуточной цели веса", "reward": "🦋"}
            ]
        }
    
    async def get_daily_motivation(self, user_id: int) -> Dict:
        """Генерирует персонализированную мотивацию на день"""
        async with get_session() as session:
            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return {"success": False}
            
            # Получаем статистику
            stats = await self._get_user_stats(user.id)
            
            # Выбираем цитату
            quotes_pool = self.quotes.get(user.goal, self.quotes[Goal.MAINTAIN])
            quote = random.choice(quotes_pool)
            
            # Подставляем персональные данные
            quote = quote.format(
                progress=stats.get('progress_percent', 0),
                lost_weight=abs(stats.get('weight_change', 0)),
                gained_weight=abs(stats.get('weight_change', 0)),
                stable_days=stats.get('stable_days', 0)
            )
            
            # Выбираем совет дня
            hour = datetime.now().hour
            if hour < 12:
                tip = random.choice(self.tips['morning'])
            elif hour < 18:
                tip = random.choice(self.tips['afternoon'])
            else:
                tip = random.choice(self.tips['evening'])
            
            # Проверяем достижения
            new_achievements = await self._check_achievements(user.id)
            
            # Получаем активный челлендж
            active_challenge = await self._get_active_challenge(user.id)
            
            return {
                "success": True,
                "quote": quote,
                "tip": tip,
                "achievements": new_achievements,
                "challenge": active_challenge,
                "streak": stats.get('streak_days', 0),
                "stats": stats
            }
    
    async def _get_user_stats(self, user_id: int) -> Dict:
        """Получает статистику пользователя"""
        async with get_session() as session:
            # Получаем все чек-ины
            result = await session.execute(
                select(CheckIn).where(
                    CheckIn.user_id == user_id
                ).order_by(CheckIn.date)
            )
            all_checkins = result.scalars().all()
            
            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            stats = {
                'total_checkins': len(all_checkins),
                'streak_days': 0,
                'weight_change': 0,
                'progress_percent': 0,
                'stable_days': 0,
                'avg_steps': 0,
                'avg_water': 0
            }
            
            if all_checkins:
                # Подсчет streak
                today = datetime.now().date()
                streak = 0
                for i in range(len(all_checkins) - 1, -1, -1):
                    checkin_date = all_checkins[i].date.date()
                    expected_date = today - timedelta(days=streak)
                    if checkin_date == expected_date:
                        streak += 1
                    else:
                        break
                stats['streak_days'] = streak
                
                # Изменение веса
                weights = [c.weight for c in all_checkins if c.weight]
                if len(weights) >= 2:
                    stats['weight_change'] = weights[-1] - weights[0]
                    
                    # Прогресс к цели
                    if user and user.target_weight:
                        total_to_change = abs(user.target_weight - weights[0])
                        changed = abs(weights[-1] - weights[0])
                        stats['progress_percent'] = int((changed / total_to_change * 100)) if total_to_change > 0 else 0
                
                # Средние показатели за последнюю неделю
                week_checkins = all_checkins[-7:] if len(all_checkins) >= 7 else all_checkins
                steps = [c.steps for c in week_checkins if c.steps]
                water = [c.water_ml for c in week_checkins if c.water_ml]
                
                if steps:
                    stats['avg_steps'] = int(sum(steps) / len(steps))
                if water:
                    stats['avg_water'] = int(sum(water) / len(water))
            
            return stats
    
    async def _check_achievements(self, user_id: int) -> List[Dict]:
        """Проверяет новые достижения"""
        new_achievements = []
        
        async with get_session() as session:
            # Получаем статистику
            stats = await self._get_user_stats(user_id)
            
            # Проверяем различные достижения
            if stats['total_checkins'] == 1:
                new_achievements.append(self.achievements['first_checkin'])
            
            if stats['streak_days'] == 7:
                new_achievements.append(self.achievements['week_streak'])
            
            if stats['streak_days'] == 30:
                new_achievements.append(self.achievements['month_streak'])
            
            if stats['weight_change'] <= -5:
                new_achievements.append(self.achievements['weight_milestone_5'])
            
            if stats['weight_change'] <= -10:
                new_achievements.append(self.achievements['weight_milestone_10'])
            
            if stats['avg_steps'] >= 10000:
                new_achievements.append(self.achievements['steps_10k'])
            
            if stats['avg_water'] >= 2000:
                new_achievements.append(self.achievements['water_goal'])
        
        return new_achievements
    
    async def _get_active_challenge(self, user_id: int) -> Optional[Dict]:
        """Получает активный челлендж для пользователя"""
        stats = await self._get_user_stats(user_id)
        
        # Определяем уровень пользователя
        if stats['total_checkins'] < 7:
            level = "beginner"
        elif stats['total_checkins'] < 30:
            level = "intermediate"
        else:
            level = "advanced"
        
        # Выбираем случайный челлендж
        challenges = self.challenges[level]
        challenge = random.choice(challenges)
        
        return challenge
    
    async def generate_weekly_report(self, user_id: int) -> str:
        """Генерирует еженедельный отчет"""
        async with get_session() as session:
            # Получаем данные за неделю
            week_ago = datetime.now() - timedelta(days=7)
            result = await session.execute(
                select(CheckIn).where(
                    and_(
                        CheckIn.user_id == user_id,
                        CheckIn.date >= week_ago
                    )
                ).order_by(CheckIn.date)
            )
            week_checkins = result.scalars().all()
            
            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not week_checkins:
                return "Недостаточно данных для отчета"
            
            # Анализируем неделю
            weights = [c.weight for c in week_checkins if c.weight]
            steps = [c.steps for c in week_checkins if c.steps]
            water = [c.water_ml for c in week_checkins if c.water_ml]
            sleep = [c.sleep_hours for c in week_checkins if c.sleep_hours]
            
            report = "📊 **ЕЖЕНЕДЕЛЬНЫЙ ОТЧЕТ**\n"
            report += f"_Период: {week_ago.strftime('%d.%m')} - {datetime.now().strftime('%d.%m')}_\n\n"
            
            # Вес
            if len(weights) >= 2:
                weight_change = weights[-1] - weights[0]
                emoji = "📉" if weight_change < 0 else "📈" if weight_change > 0 else "➡️"
                report += f"{emoji} **Вес:** {weight_change:+.1f} кг\n"
                report += f"   {weights[0]:.1f} → {weights[-1]:.1f} кг\n\n"
            
            # Активность
            if steps:
                avg_steps = sum(steps) / len(steps)
                total_steps = sum(steps)
                report += f"👟 **Шаги:** {total_steps:,} за неделю\n"
                report += f"   В среднем: {avg_steps:,.0f}/день\n"
                if avg_steps >= 10000:
                    report += "   ✅ Отличная активность!\n\n"
                elif avg_steps >= 8000:
                    report += "   ⚠️ Хорошо, но можно больше\n\n"
                else:
                    report += "   ❌ Нужно больше двигаться\n\n"
            
            # Вода
            if water:
                avg_water = sum(water) / len(water) / 1000
                report += f"💧 **Вода:** {avg_water:.1f}л в среднем\n"
                if avg_water >= 2:
                    report += "   ✅ Отличная гидратация!\n\n"
                else:
                    report += f"   ⚠️ Добавьте еще {2-avg_water:.1f}л\n\n"
            
            # Сон
            if sleep:
                avg_sleep = sum(sleep) / len(sleep)
                report += f"😴 **Сон:** {avg_sleep:.1f}ч в среднем\n"
                if 7 <= avg_sleep <= 9:
                    report += "   ✅ Отличное восстановление!\n\n"
                else:
                    report += "   ⚠️ Оптимально 7-9 часов\n\n"
            
            # Рейтинг недели
            score = 0
            if len(week_checkins) >= 6:
                score += 25  # Регулярность
            if weights and abs(weights[-1] - weights[0]) > 0.2:
                score += 25  # Прогресс веса
            if steps and sum(steps)/len(steps) >= 8000:
                score += 25  # Активность
            if water and sum(water)/len(water) >= 2000:
                score += 25  # Гидратация
            
            stars = "⭐" * (score // 20)
            report += f"**Оценка недели:** {stars} ({score}/100)\n\n"
            
            # Рекомендации на следующую неделю
            report += "📝 **Рекомендации:**\n"
            
            if user and user.goal == Goal.LOSE_WEIGHT:
                if weights and weight_change >= 0:
                    report += "• Проверьте калорийность рациона\n"
                    report += "• Увеличьте кардио нагрузки\n"
                elif weights and weight_change < -1.5:
                    report += "• Отличный темп! Продолжайте\n"
                else:
                    report += "• Хороший прогресс, держите темп\n"
            
            if not steps or sum(steps)/len(steps) < 8000:
                report += "• Добавьте больше ходьбы\n"
            
            if not water or sum(water)/len(water) < 2000:
                report += "• Увеличьте потребление воды\n"
            
            # Мотивация
            motivational_endings = [
                "\n💪 Отличная работа! Продолжай в том же духе!",
                "\n🔥 Ты на правильном пути! Не останавливайся!",
                "\n⭐ Каждый день - это шаг к твоей цели!",
                "\n🎯 Фокус на процессе, результат придет!",
                "\n🚀 Следующая неделя будет еще лучше!"
            ]
            
            report += random.choice(motivational_endings)
            
            return report
    
    async def get_plateau_motivation(self, user_id: int) -> str:
        """Специальная мотивация при плато"""
        messages = [
            "🌟 **Плато - это не стоп!**\n\n"
            "Твое тело адаптировалось - это признак прогресса!\n"
            "Время внести небольшие изменения:\n"
            "• Измени тренировки\n"
            "• Попробуй интервальное голодание\n"
            "• Добавь новые виды активности\n\n"
            "Помни: плато временно, твоя решимость - навсегда! 💪",
            
            "🎯 **Прорыв близко!**\n\n"
            "Знаешь, что общего у всех, кто достиг цели?\n"
            "Они не сдались на плато!\n\n"
            "Твое тело готовится к новому рывку.\n"
            "Доверься процессу и продолжай! 🚀",
            
            "💡 **Время для экспериментов!**\n\n"
            "Плато = возможность попробовать новое:\n"
            "• Новые рецепты\n"
            "• Новые тренировки\n"
            "• Новый режим дня\n\n"
            "Встряхни рутину и увидишь результат! ⚡",
            
            "🏔 **Ты на вершине плато!**\n\n"
            "Это значит, что следующий шаг - только вверх!\n"
            "Не вес определяет прогресс:\n"
            "• Как ты себя чувствуешь?\n"
            "• Как сидит одежда?\n"
            "• Сколько энергии?\n\n"
            "Продолжай, прорыв неизбежен! 💪"
        ]
        
        return random.choice(messages)
    
    async def celebrate_achievement(self, achievement_type: str) -> str:
        """Генерирует праздничное сообщение для достижения"""
        celebrations = {
            "weight_goal": "🎉 **ПОЗДРАВЛЯЕМ! ЦЕЛ ДОСТИГНУТА!** 🎉\n\n"
                          "Ты сделал(а) это! Твоя дисциплина и упорство принесли результат!\n"
                          "Это не конец, а начало нового этапа твоей жизни!\n\n"
                          "Что дальше?\n"
                          "• Поддержание результата\n"
                          "• Новые фитнес-цели\n"
                          "• Помощь другим\n\n"
                          "Ты - вдохновение! 🌟",
            
            "month_streak": "🔥 **30 ДНЕЙ ПОДРЯД!** 🔥\n\n"
                           "Целый месяц дисциплины!\n"
                           "Ты доказал(а), что можешь все!\n\n"
                           "Это уже не просто привычка - это образ жизни! 💪",
            
            "10kg_lost": "🏆 **МИНУС 10 КГ!** 🏆\n\n"
                        "Это не просто цифра - это твоя победа над собой!\n"
                        "10 кг = 10 000 решений в пользу здоровья!\n\n"
                        "Гордись собой! Ты заслужил(а)! 👑",
            
            "100_days": "💯 **100 ДНЕЙ В ПРОГРАММЕ!** 💯\n\n"
                       "Ты с нами уже 100 дней!\n"
                       "За это время ты изменил(а) не только тело, но и мышление!\n\n"
                       "Это только начало твоей истории успеха! 📖",
            
            "perfect_week": "⭐ **ИДЕАЛЬНАЯ НЕДЕЛЯ!** ⭐\n\n"
                           "7 дней = 7 побед!\n"
                           "• Все чек-ины ✅\n"
                           "• Все цели ✅\n"
                           "• Все по плану ✅\n\n"
                           "Так держать, чемпион! 🏅"
        }
        
        return celebrations.get(achievement_type, 
                                "🎊 Поздравляем с достижением! Продолжай в том же духе! 🎊")