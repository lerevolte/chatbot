import io
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import seaborn as sns
import numpy as np
from scipy import stats
from sqlalchemy import select, and_, func

from database.models import User, CheckIn, Goal
from database.connection import get_session

logger = logging.getLogger(__name__)

class AnalyticsService:
    """Сервис продвинутой аналитики и визуализации"""
    
    def __init__(self):
        # Настройка стиля графиков
        sns.set_style("whitegrid")
        self.colors = {
            'primary': '#2E7D32',
            'secondary': '#1976D2', 
            'accent': '#FF6B6B',
            'success': '#4CAF50',
            'warning': '#FFA726',
            'danger': '#EF5350',
            'info': '#42A5F5',
            'light': '#E0E0E0',
            'dark': '#424242'
        }
        
        # Параметры для определения плато
        self.plateau_days = 7  # Минимум дней без прогресса
        self.plateau_threshold = 0.5  # Максимальное изменение веса в кг
    
    async def generate_comprehensive_report(self, user_id: int) -> bytes:
        """Генерирует комплексный отчет с графиками"""
        fig = plt.figure(figsize=(16, 20))
        
        # Создаем сетку для графиков
        gs = fig.add_gridspec(5, 2, hspace=0.3, wspace=0.3)
        
        # 1. График веса с прогнозом
        ax1 = fig.add_subplot(gs[0, :])
        await self._plot_weight_with_prediction(ax1, user_id)
        
        # 2. Тепловая карта активности
        ax2 = fig.add_subplot(gs[1, :])
        await self._plot_activity_heatmap(ax2, user_id)
        
        # 3. График состава тела (БЖУ)
        ax3 = fig.add_subplot(gs[2, 0])
        await self._plot_macros_distribution(ax3, user_id)
        
        # 4. График качества сна
        ax4 = fig.add_subplot(gs[2, 1])
        await self._plot_sleep_quality(ax4, user_id)
        
        # 5. График прогресса к цели
        ax5 = fig.add_subplot(gs[3, :])
        await self._plot_goal_progress(ax5, user_id)
        
        # 6. Статистика и рекомендации
        ax6 = fig.add_subplot(gs[4, :])
        await self._add_stats_and_recommendations(ax6, user_id)
        
        # Заголовок
        fig.suptitle('Комплексный отчет о прогрессе', fontsize=20, fontweight='bold')
        
        # Сохраняем в буфер
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        plt.close()
        
        return buffer.getvalue()
    
    async def _plot_weight_with_prediction(self, ax, user_id: int):
        """График веса с трендом и прогнозом"""
        async with get_session() as session:
            # Получаем данные о весе
            result = await session.execute(
                select(CheckIn).where(
                    and_(
                        CheckIn.user_id == user_id,
                        CheckIn.weight.isnot(None)
                    )
                ).order_by(CheckIn.date)
            )
            checkins = result.scalars().all()
            
            if len(checkins) < 2:
                ax.text(0.5, 0.5, 'Недостаточно данных', ha='center', va='center')
                ax.set_title('График веса')
                return
            
            # Получаем целевой вес
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            dates = [c.date for c in checkins]
            weights = [c.weight for c in checkins]
            
            # Основная линия
            ax.plot(dates, weights, 'o-', color=self.colors['primary'], 
                   linewidth=2, markersize=6, label='Фактический вес')
            
            # Тренд
            x_numeric = mdates.date2num(dates)
            z = np.polyfit(x_numeric, weights, 1)
            p = np.poly1d(z)
            trend_line = p(x_numeric)
            ax.plot(dates, trend_line, '--', color=self.colors['secondary'], 
                   alpha=0.7, linewidth=2, label='Тренд')
            
            # Прогноз на 30 дней
            future_days = 30
            last_date = dates[-1]
            future_dates = [last_date + timedelta(days=i) for i in range(1, future_days + 1)]
            future_x = mdates.date2num(future_dates)
            future_weights = p(future_x)
            
            ax.plot(future_dates, future_weights, ':', color=self.colors['info'], 
                   linewidth=2, alpha=0.7, label='Прогноз')
            
            # Зона неопределенности прогноза
            std_dev = np.std(weights - trend_line[:len(weights)])
            upper_bound = future_weights + std_dev
            lower_bound = future_weights - std_dev
            ax.fill_between(future_dates, lower_bound, upper_bound, 
                           color=self.colors['info'], alpha=0.1)
            
            # Целевой вес
            if user and user.target_weight:
                ax.axhline(y=user.target_weight, color=self.colors['accent'], 
                          linestyle='-.', linewidth=2, alpha=0.7, 
                          label=f'Цель: {user.target_weight} кг')
                
                # Прогноз достижения цели
                if z[0] != 0:  # Если есть изменение веса
                    days_to_goal = (user.target_weight - weights[-1]) / (z[0] * -1)
                    if 0 < days_to_goal < 365:
                        goal_date = last_date + timedelta(days=int(days_to_goal))
                        ax.axvline(x=goal_date, color=self.colors['success'], 
                                 linestyle=':', alpha=0.5)
                        ax.text(goal_date, user.target_weight, 
                               f'  Цель\n  {goal_date.strftime("%d.%m")}',
                               fontsize=9, color=self.colors['success'])
            
            # Определение плато
            plateau_periods = self._detect_plateau(dates, weights)
            for start, end in plateau_periods:
                ax.axvspan(start, end, color=self.colors['warning'], alpha=0.2)
            
            # Настройка осей
            ax.set_xlabel('Дата', fontsize=12)
            ax.set_ylabel('Вес (кг)', fontsize=12)
            ax.set_title('Динамика веса с прогнозом на 30 дней', fontsize=14, fontweight='bold')
            ax.legend(loc='best')
            ax.grid(True, alpha=0.3)
            
            # Форматирование дат
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates) // 10)))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
            
            # Добавляем статистику
            weight_change = weights[-1] - weights[0]
            rate_per_week = (weight_change / len(dates)) * 7 if len(dates) > 0 else 0
            
            stats_text = f'Изменение: {weight_change:+.1f} кг\n'
            stats_text += f'Темп: {rate_per_week:+.2f} кг/нед'
            
            ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
                   verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    async def _plot_activity_heatmap(self, ax, user_id: int):
        """Тепловая карта активности за последние 30 дней"""
        async with get_session() as session:
            month_ago = datetime.now() - timedelta(days=30)
            result = await session.execute(
                select(CheckIn).where(
                    and_(
                        CheckIn.user_id == user_id,
                        CheckIn.date >= month_ago
                    )
                ).order_by(CheckIn.date)
            )
            checkins = result.scalars().all()
            
            # Создаем матрицу активности 5x6 (30 дней)
            activity_matrix = np.zeros((5, 6))
            
            for i, checkin in enumerate(checkins[:30]):
                row = i // 6
                col = i % 6
                
                # Рассчитываем уровень активности (0-10)
                activity_score = 0
                if checkin.steps:
                    activity_score += min(5, checkin.steps / 2000)  # До 5 баллов за шаги
                if checkin.water_ml:
                    activity_score += min(3, checkin.water_ml / 700)  # До 3 баллов за воду
                if checkin.weight:
                    activity_score += 1  # 1 балл за взвешивание
                if checkin.mood == 'good':
                    activity_score += 1  # 1 балл за хорошее настроение
                
                activity_matrix[row, col] = min(10, activity_score)
            
            # Создаем тепловую карту
            im = ax.imshow(activity_matrix, cmap='RdYlGn', aspect='auto', vmin=0, vmax=10)
            
            # Добавляем значения в ячейки
            for i in range(5):
                for j in range(6):
                    if i * 6 + j < len(checkins):
                        date = checkins[i * 6 + j].date
                        text = ax.text(j, i, f'{date.day}',
                                     ha="center", va="center", color="black", fontsize=8)
            
            # Настройка осей
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_title('Карта активности за 30 дней', fontsize=14, fontweight='bold')
            
            # Цветовая шкала
            cbar = plt.colorbar(im, ax=ax, orientation='horizontal', pad=0.1)
            cbar.set_label('Уровень активности', fontsize=10)
    
    async def _plot_macros_distribution(self, ax, user_id: int):
        """График распределения БЖУ"""
        async with get_session() as session:
            # Получаем последние данные о питании
            week_ago = datetime.now() - timedelta(days=7)
            result = await session.execute(
                select(CheckIn).where(
                    and_(
                        CheckIn.user_id == user_id,
                        CheckIn.date >= week_ago,
                        CheckIn.breakfast_analysis.isnot(None)
                    )
                )
            )
            checkins = result.scalars().all()
            
            total_protein = 0
            total_fats = 0
            total_carbs = 0
            count = 0
            
            for checkin in checkins:
                for meal_analysis in [checkin.breakfast_analysis, checkin.lunch_analysis, 
                                     checkin.dinner_analysis, checkin.snack_analysis]:
                    if meal_analysis:
                        total_protein += meal_analysis.get('protein', 0)
                        total_fats += meal_analysis.get('fats', 0)
                        total_carbs += meal_analysis.get('carbs', 0)
                        count += 1
            
            if count > 0:
                avg_protein = total_protein / count
                avg_fats = total_fats / count
                avg_carbs = total_carbs / count
                
                # Получаем целевые значения
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                
                # Данные для графика
                categories = ['Белки', 'Жиры', 'Углеводы']
                actual = [avg_protein, avg_fats, avg_carbs]
                target = [user.daily_protein, user.daily_fats, user.daily_carbs] if user else actual
                
                x = np.arange(len(categories))
                width = 0.35
                
                # Столбцы
                bars1 = ax.bar(x - width/2, actual, width, label='Фактически', 
                              color=self.colors['primary'])
                bars2 = ax.bar(x + width/2, target, width, label='Цель', 
                              color=self.colors['secondary'], alpha=0.7)
                
                # Подписи
                ax.set_xlabel('Макронутриенты', fontsize=12)
                ax.set_ylabel('Граммы', fontsize=12)
                ax.set_title('Распределение БЖУ', fontsize=14, fontweight='bold')
                ax.set_xticks(x)
                ax.set_xticklabels(categories)
                ax.legend()
                
                # Добавляем значения на столбцы
                for bars in [bars1, bars2]:
                    for bar in bars:
                        height = bar.get_height()
                        ax.text(bar.get_x() + bar.get_width()/2., height,
                               f'{height:.0f}',
                               ha='center', va='bottom', fontsize=9)
            else:
                ax.text(0.5, 0.5, 'Нет данных о питании', ha='center', va='center')
                ax.set_title('Распределение БЖУ')
    
    async def _plot_sleep_quality(self, ax, user_id: int):
        """График качества сна"""
        async with get_session() as session:
            # Получаем данные о сне за 14 дней
            two_weeks_ago = datetime.now() - timedelta(days=14)
            result = await session.execute(
                select(CheckIn).where(
                    and_(
                        CheckIn.user_id == user_id,
                        CheckIn.date >= two_weeks_ago,
                        CheckIn.sleep_hours.isnot(None)
                    )
                ).order_by(CheckIn.date)
            )
            checkins = result.scalars().all()
            
            if checkins:
                dates = [c.date for c in checkins]
                sleep_hours = [c.sleep_hours for c in checkins]
                
                # График сна
                ax.bar(dates, sleep_hours, color=self.colors['primary'], alpha=0.7)
                
                # Оптимальная зона сна
                ax.axhspan(7, 9, color=self.colors['success'], alpha=0.2, 
                          label='Оптимальная зона')
                ax.axhline(y=8, color=self.colors['success'], linestyle='--', 
                          alpha=0.5, linewidth=1)
                
                # Настройка осей
                ax.set_xlabel('Дата', fontsize=12)
                ax.set_ylabel('Часы сна', fontsize=12)
                ax.set_title('Качество сна', fontsize=14, fontweight='bold')
                ax.legend()
                ax.grid(True, alpha=0.3, axis='y')
                
                # Форматирование дат
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
                plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
                
                # Статистика
                avg_sleep = np.mean(sleep_hours)
                quality = 'Отличное' if 7 <= avg_sleep <= 9 else 'Требует внимания'
                
                stats_text = f'Среднее: {avg_sleep:.1f}ч\nКачество: {quality}'
                ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
                       verticalalignment='top',
                       bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            else:
                ax.text(0.5, 0.5, 'Нет данных о сне', ha='center', va='center')
                ax.set_title('Качество сна')
    
    async def _plot_goal_progress(self, ax, user_id: int):
        """График прогресса к цели"""
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            # Получаем все записи веса
            result = await session.execute(
                select(CheckIn).where(
                    and_(
                        CheckIn.user_id == user_id,
                        CheckIn.weight.isnot(None)
                    )
                ).order_by(CheckIn.date)
            )
            checkins = result.scalars().all()
            
            if user and len(checkins) >= 2:
                start_weight = checkins[0].weight
                current_weight = checkins[-1].weight
                target_weight = user.target_weight
                
                # Рассчитываем прогресс
                total_to_change = abs(target_weight - start_weight)
                changed = abs(current_weight - start_weight)
                progress_percent = (changed / total_to_change * 100) if total_to_change > 0 else 0
                
                # Визуализация прогресса
                fig_progress = plt.figure(figsize=(10, 2))
                ax_progress = fig_progress.add_subplot(111)
                
                # Прогресс бар
                ax.barh([0], [progress_percent], height=0.5, 
                       color=self.colors['success'], alpha=0.7)
                ax.barh([0], [100 - progress_percent], left=[progress_percent], 
                       height=0.5, color=self.colors['light'], alpha=0.5)
                
                # Метки
                ax.text(progress_percent / 2, 0, f'{progress_percent:.1f}%',
                       ha='center', va='center', fontsize=14, fontweight='bold', 
                       color='white')
                
                # Контрольные точки
                milestones = [25, 50, 75]
                for milestone in milestones:
                    ax.axvline(x=milestone, color=self.colors['dark'], 
                             linestyle=':', alpha=0.3)
                    if progress_percent >= milestone:
                        ax.plot(milestone, 0, 'o', color=self.colors['success'], 
                               markersize=10)
                
                # Настройка осей
                ax.set_xlim(0, 100)
                ax.set_ylim(-0.5, 0.5)
                ax.set_xlabel('Прогресс (%)', fontsize=12)
                ax.set_title(f'Прогресс к цели: {start_weight:.1f} → {target_weight:.1f} кг', 
                           fontsize=14, fontweight='bold')
                ax.set_yticks([])
                
                # Информация
                days_passed = (checkins[-1].date - checkins[0].date).days
                rate = changed / days_passed * 7 if days_passed > 0 else 0
                
                info_text = f'Пройдено: {changed:.1f} кг из {total_to_change:.1f} кг\n'
                info_text += f'Темп: {rate:.2f} кг/неделю'
                
                ax.text(0.98, 0.5, info_text, transform=ax.transAxes,
                       ha='right', va='center',
                       bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            else:
                ax.text(0.5, 0.5, 'Недостаточно данных', ha='center', va='center')
                ax.set_title('Прогресс к цели')
    
    async def _add_stats_and_recommendations(self, ax, user_id: int):
        """Добавляет статистику и рекомендации"""
        ax.axis('off')
        
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            # Анализируем данные
            analysis = await self.analyze_user_progress(user_id)
            
            # Формируем текст
            text = "📊 АНАЛИЗ И РЕКОМЕНДАЦИИ\n\n"
            
            # Статус
            if analysis['is_plateau']:
                text += "⚠️ ВНИМАНИЕ: Обнаружено плато веса!\n"
                text += f"   Вес не меняется уже {analysis['plateau_days']} дней\n\n"
            
            # Рекомендации по калориям
            if analysis.get('calorie_adjustment'):
                adj = analysis['calorie_adjustment']
                if adj > 0:
                    text += f"📈 Рекомендация: Увеличить калории на {adj} ккал\n"
                else:
                    text += f"📉 Рекомендация: Уменьшить калории на {abs(adj)} ккал\n"
            
            # Рекомендации по активности
            if analysis.get('activity_recommendation'):
                text += f"🏃 Активность: {analysis['activity_recommendation']}\n"
            
            # Рекомендации по сну
            if analysis.get('sleep_recommendation'):
                text += f"💤 Сон: {analysis['sleep_recommendation']}\n"
            
            # Мотивация
            text += f"\n💪 {analysis.get('motivation', 'Продолжайте в том же духе!')}"
            
            # Выводим текст
            ax.text(0.05, 0.95, text, transform=ax.transAxes,
                   fontsize=11, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor=self.colors['light'], 
                           alpha=0.3, pad=1))
    
    def _detect_plateau(self, dates: List[datetime], weights: List[float]) -> List[Tuple[datetime, datetime]]:
        """Определяет периоды плато"""
        plateaus = []
        
        if len(weights) < self.plateau_days:
            return plateaus
        
        for i in range(len(weights) - self.plateau_days + 1):
            segment = weights[i:i + self.plateau_days]
            if max(segment) - min(segment) <= self.plateau_threshold:
                start_date = dates[i]
                end_date = dates[i + self.plateau_days - 1]
                
                # Объединяем перекрывающиеся периоды
                if plateaus and plateaus[-1][1] >= start_date:
                    plateaus[-1] = (plateaus[-1][0], end_date)
                else:
                    plateaus.append((start_date, end_date))
        
        return plateaus
    
    async def analyze_user_progress(self, user_id: int) -> Dict:
        """Анализирует прогресс пользователя и дает рекомендации"""
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            # Получаем последние чек-ины
            two_weeks_ago = datetime.now() - timedelta(days=14)
            result = await session.execute(
                select(CheckIn).where(
                    and_(
                        CheckIn.user_id == user_id,
                        CheckIn.date >= two_weeks_ago
                    )
                ).order_by(CheckIn.date)
            )
            recent_checkins = result.scalars().all()
            
            analysis = {
                'is_plateau': False,
                'plateau_days': 0,
                'calorie_adjustment': 0,
                'activity_recommendation': '',
                'sleep_recommendation': '',
                'motivation': ''
            }
            
            # Проверка плато
            weights = [c.weight for c in recent_checkins if c.weight]
            if len(weights) >= self.plateau_days:
                recent_weights = weights[-self.plateau_days:]
                if max(recent_weights) - min(recent_weights) <= self.plateau_threshold:
                    analysis['is_plateau'] = True
                    analysis['plateau_days'] = self.plateau_days
                    
                    # Корректировка калорий при плато
                    if user.goal == Goal.LOSE_WEIGHT:
                        analysis['calorie_adjustment'] = -100  # Уменьшить на 100 ккал
                        analysis['motivation'] = 'Плато - это нормально! Внесем небольшие изменения.'
                    elif user.goal == Goal.GAIN_MUSCLE:
                        analysis['calorie_adjustment'] = 150  # Увеличить на 150 ккал
                        analysis['motivation'] = 'Время увеличить нагрузку для прорыва!'
            
            # Анализ активности
            steps = [c.steps for c in recent_checkins if c.steps]
            if steps:
                avg_steps = np.mean(steps)
                if avg_steps < 5000:
                    analysis['activity_recommendation'] = 'Увеличьте активность до 8000 шагов в день'
                elif avg_steps < 8000:
                    analysis['activity_recommendation'] = f'Добавьте еще {8000 - int(avg_steps)} шагов в день'
                else:
                    analysis['activity_recommendation'] = 'Отличная активность! Так держать!'
            
            # Анализ сна
            sleep_hours = [c.sleep_hours for c in recent_checkins if c.sleep_hours]
            if sleep_hours:
                avg_sleep = np.mean(sleep_hours)
                if avg_sleep < 7:
                    analysis['sleep_recommendation'] = 'Старайтесь спать минимум 7-8 часов'
                elif avg_sleep > 9:
                    analysis['sleep_recommendation'] = 'Попробуйте придерживаться 7-9 часов сна'
                else:
                    analysis['sleep_recommendation'] = 'Отличное качество сна!'
            
            # Мотивационное сообщение
            if not analysis['is_plateau']:
                if len(weights) >= 2 and weights[-1] < weights[0]:
                    analysis['motivation'] = 'Отличный прогресс! Вы на правильном пути!'
                else:
                    analysis['motivation'] = 'Каждый день - это шаг к вашей цели!'
            
            return analysis