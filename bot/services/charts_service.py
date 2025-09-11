import io
import logging
from datetime import datetime, timedelta
from typing import List, Optional
import matplotlib
matplotlib.use('Agg')  # Для работы без GUI
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
import numpy as np

from database.models import CheckIn, User
from sqlalchemy import select, and_
from database.connection import get_session

logger = logging.getLogger(__name__)

class ChartsService:
    """Сервис для генерации графиков прогресса"""
    
    def __init__(self):
        # Настройка стиля графиков
        plt.style.use('seaborn-v0_8-darkgrid')
        self.colors = {
            'primary': '#2E7D32',
            'secondary': '#1976D2',
            'accent': '#FF6B6B',
            'success': '#4CAF50',
            'warning': '#FFA726',
            'background': '#F5F5F5'
        }
    
    async def generate_weight_chart(self, user_id: int, days: int = 30) -> Optional[bytes]:
        """
        Генерирует график изменения веса
        """
        try:
            async with get_session() as session:
                # Получаем данные о весе за период
                start_date = datetime.now() - timedelta(days=days)
                result = await session.execute(
                    select(CheckIn).where(
                        and_(
                            CheckIn.user_id == user_id,
                            CheckIn.date >= start_date,
                            CheckIn.weight.isnot(None)
                        )
                    ).order_by(CheckIn.date)
                )
                checkins = result.scalars().all()
                
                if len(checkins) < 2:
                    return None
                
                # Получаем целевой вес пользователя
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                
                # Подготовка данных
                dates = [c.date for c in checkins]
                weights = [c.weight for c in checkins]
                
                # Создание графика
                fig, ax = plt.subplots(figsize=(10, 6))
                
                # Основная линия веса
                ax.plot(dates, weights, 
                       color=self.colors['primary'], 
                       linewidth=2, 
                       marker='o', 
                       markersize=6,
                       label='Текущий вес')
                
                # Линия тренда
                z = np.polyfit(mdates.date2num(dates), weights, 1)
                p = np.poly1d(z)
                ax.plot(dates, p(mdates.date2num(dates)), 
                       color=self.colors['secondary'], 
                       linestyle='--', 
                       alpha=0.7,
                       label='Тренд')
                
                # Целевой вес
                if user and user.target_weight:
                    ax.axhline(y=user.target_weight, 
                              color=self.colors['accent'], 
                              linestyle=':', 
                              alpha=0.7,
                              label=f'Цель: {user.target_weight} кг')
                
                # Настройка осей
                ax.set_xlabel('Дата', fontsize=12)
                ax.set_ylabel('Вес (кг)', fontsize=12)
                ax.set_title('График изменения веса', fontsize=14, fontweight='bold')
                
                # Форматирование дат
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
                ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days//10)))
                plt.xticks(rotation=45)
                
                # Сетка и легенда
                ax.grid(True, alpha=0.3)
                ax.legend(loc='best')
                
                # Добавляем статистику
                weight_change = weights[-1] - weights[0]
                avg_weight = sum(weights) / len(weights)
                
                stats_text = (
                    f'Изменение: {weight_change:+.1f} кг\n'
                    f'Средний вес: {avg_weight:.1f} кг'
                )
                ax.text(0.02, 0.98, stats_text,
                       transform=ax.transAxes,
                       verticalalignment='top',
                       bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
                
                # Сохранение в байты
                plt.tight_layout()
                buffer = io.BytesIO()
                plt.savefig(buffer, format='png', dpi=100)
                buffer.seek(0)
                plt.close()
                
                return buffer.getvalue()
                
        except Exception as e:
            logger.error(f"Ошибка при генерации графика веса: {e}")
            return None
    
    async def generate_activity_chart(self, user_id: int, days: int = 7) -> Optional[bytes]:
        """
        Генерирует график активности (шаги и вода)
        """
        try:
            async with get_session() as session:
                start_date = datetime.now() - timedelta(days=days)
                result = await session.execute(
                    select(CheckIn).where(
                        and_(
                            CheckIn.user_id == user_id,
                            CheckIn.date >= start_date
                        )
                    ).order_by(CheckIn.date)
                )
                checkins = result.scalars().all()
                
                if not checkins:
                    return None
                
                # Подготовка данных
                dates = [c.date for c in checkins]
                steps = [c.steps if c.steps else 0 for c in checkins]
                water = [c.water_ml/1000 if c.water_ml else 0 for c in checkins]
                
                # Создание графика с двумя осями Y
                fig, ax1 = plt.subplots(figsize=(10, 6))
                
                # График шагов
                color1 = self.colors['primary']
                ax1.set_xlabel('Дата', fontsize=12)
                ax1.set_ylabel('Шаги', color=color1, fontsize=12)
                bars1 = ax1.bar([d - timedelta(hours=2) for d in dates], steps, 
                               width=0.35, color=color1, alpha=0.7, label='Шаги')
                ax1.tick_params(axis='y', labelcolor=color1)
                ax1.axhline(y=8000, color=color1, linestyle='--', alpha=0.5, label='Цель: 8000')
                
                # График воды на второй оси
                ax2 = ax1.twinx()
                color2 = self.colors['secondary']
                ax2.set_ylabel('Вода (л)', color=color2, fontsize=12)
                bars2 = ax2.bar([d + timedelta(hours=2) for d in dates], water, 
                               width=0.35, color=color2, alpha=0.7, label='Вода')
                ax2.tick_params(axis='y', labelcolor=color2)
                ax2.axhline(y=2.0, color=color2, linestyle='--', alpha=0.5, label='Цель: 2л')
                
                # Заголовок
                ax1.set_title('Активность за неделю', fontsize=14, fontweight='bold')
                
                # Форматирование дат
                ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
                plt.xticks(rotation=45)
                
                # Легенда
                lines1, labels1 = ax1.get_legend_handles_labels()
                lines2, labels2 = ax2.get_legend_handles_labels()
                ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
                
                # Статистика
                avg_steps = sum(steps) / len(steps) if steps else 0
                avg_water = sum(water) / len(water) if water else 0
                days_goal_reached = sum(1 for s in steps if s >= 8000)
                
                stats_text = (
                    f'Среднее:\n'
                    f'Шаги: {avg_steps:.0f}\n'
                    f'Вода: {avg_water:.1f}л\n'
                    f'Дней с 8000+: {days_goal_reached}'
                )
                ax1.text(0.02, 0.98, stats_text,
                        transform=ax1.transAxes,
                        verticalalignment='top',
                        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
                
                plt.tight_layout()
                buffer = io.BytesIO()
                plt.savefig(buffer, format='png', dpi=100)
                buffer.seek(0)
                plt.close()
                
                return buffer.getvalue()
                
        except Exception as e:
            logger.error(f"Ошибка при генерации графика активности: {e}")
            return None
    
    async def generate_sleep_chart(self, user_id: int, days: int = 14) -> Optional[bytes]:
        """
        Генерирует график сна и настроения
        """
        try:
            async with get_session() as session:
                start_date = datetime.now() - timedelta(days=days)
                result = await session.execute(
                    select(CheckIn).where(
                        and_(
                            CheckIn.user_id == user_id,
                            CheckIn.date >= start_date,
                            CheckIn.sleep_hours.isnot(None)
                        )
                    ).order_by(CheckIn.date)
                )
                checkins = result.scalars().all()
                
                if not checkins:
                    return None
                
                # Подготовка данных
                dates = [c.date for c in checkins]
                sleep_hours = [c.sleep_hours for c in checkins]
                
                # Маппинг настроения в числа
                mood_map = {'good': 3, 'normal': 2, 'bad': 1}
                moods = [mood_map.get(c.mood, 2) if c.mood else 2 for c in checkins]
                
                # Создание графика
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
                
                # График сна
                ax1.bar(dates, sleep_hours, color=self.colors['primary'], alpha=0.7)
                ax1.axhline(y=7, color='green', linestyle='--', alpha=0.5, label='Минимум: 7ч')
                ax1.axhline(y=9, color='orange', linestyle='--', alpha=0.5, label='Максимум: 9ч')
                ax1.set_ylabel('Часы сна', fontsize=12)
                ax1.set_title('Сон и самочувствие', fontsize=14, fontweight='bold')
                ax1.legend(loc='upper right')
                ax1.grid(True, alpha=0.3)
                
                # График настроения
                mood_colors = ['#FF6B6B', '#FFA726', '#4CAF50']
                mood_labels = ['Плохо', 'Нормально', 'Отлично']
                
                for i, (date, mood) in enumerate(zip(dates, moods)):
                    ax2.bar(date, mood, color=mood_colors[mood-1], alpha=0.7)
                
                ax2.set_ylabel('Настроение', fontsize=12)
                ax2.set_ylim(0.5, 3.5)
                ax2.set_yticks([1, 2, 3])
                ax2.set_yticklabels(mood_labels)
                ax2.grid(True, alpha=0.3)
                
                # Форматирование дат
                ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
                plt.xticks(rotation=45)
                ax2.set_xlabel('Дата', fontsize=12)
                
                # Статистика
                avg_sleep = sum(sleep_hours) / len(sleep_hours)
                good_days = sum(1 for m in moods if m == 3)
                
                stats_text = (
                    f'Средний сон: {avg_sleep:.1f}ч\n'
                    f'Дней с отличным настроением: {good_days}'
                )
                ax1.text(0.02, 0.98, stats_text,
                        transform=ax1.transAxes,
                        verticalalignment='top',
                        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
                
                plt.tight_layout()
                buffer = io.BytesIO()
                plt.savefig(buffer, format='png', dpi=100)
                buffer.seek(0)
                plt.close()
                
                return buffer.getvalue()
                
        except Exception as e:
            logger.error(f"Ошибка при генерации графика сна: {e}")
            return None
    
    async def generate_progress_summary(self, user_id: int) -> Optional[bytes]:
        """
        Генерирует общую сводку прогресса
        """
        try:
            # Создаем фигуру с подграфиками
            fig = plt.figure(figsize=(12, 10))
            
            # Получаем все необходимые данные
            weight_chart = await self._get_weight_data(user_id, 30)
            activity_data = await self._get_activity_data(user_id, 7)
            
            # График 1: Вес (верхняя половина)
            if weight_chart:
                ax1 = plt.subplot(2, 2, (1, 2))
                self._plot_weight_summary(ax1, weight_chart)
            
            # График 2: Шаги (нижний левый)
            if activity_data:
                ax2 = plt.subplot(2, 2, 3)
                self._plot_steps_summary(ax2, activity_data)
                
                # График 3: Вода (нижний правый)
                ax3 = plt.subplot(2, 2, 4)
                self._plot_water_summary(ax3, activity_data)
            
            plt.suptitle('Сводка прогресса', fontsize=16, fontweight='bold')
            plt.tight_layout()
            
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=100)
            buffer.seek(0)
            plt.close()
            
            return buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Ошибка при генерации сводки: {e}")
            return None
    
    async def _get_weight_data(self, user_id: int, days: int):
        """Получает данные о весе"""
        async with get_session() as session:
            start_date = datetime.now() - timedelta(days=days)
            result = await session.execute(
                select(CheckIn).where(
                    and_(
                        CheckIn.user_id == user_id,
                        CheckIn.date >= start_date,
                        CheckIn.weight.isnot(None)
                    )
                ).order_by(CheckIn.date)
            )
            return result.scalars().all()
    
    async def _get_activity_data(self, user_id: int, days: int):
        """Получает данные об активности"""
        async with get_session() as session:
            start_date = datetime.now() - timedelta(days=days)
            result = await session.execute(
                select(CheckIn).where(
                    and_(
                        CheckIn.user_id == user_id,
                        CheckIn.date >= start_date
                    )
                ).order_by(CheckIn.date)
            )
            return result.scalars().all()
    
    def _plot_weight_summary(self, ax, checkins):
        """Рисует график веса для сводки"""
        dates = [c.date for c in checkins]
        weights = [c.weight for c in checkins]
        
        ax.plot(dates, weights, color=self.colors['primary'], linewidth=2, marker='o')
        ax.set_title('Динамика веса (30 дней)', fontsize=12)
        ax.set_ylabel('Вес (кг)')
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
        
    def _plot_steps_summary(self, ax, checkins):
        """Рисует график шагов для сводки"""
        dates = [c.date for c in checkins[-7:]]
        steps = [c.steps if c.steps else 0 for c in checkins[-7:]]
        
        ax.bar(dates, steps, color=self.colors['primary'], alpha=0.7)
        ax.axhline(y=8000, color='red', linestyle='--', alpha=0.5)
        ax.set_title('Шаги (7 дней)', fontsize=12)
        ax.set_ylabel('Шаги')
        ax.tick_params(axis='x', rotation=45)
        
    def _plot_water_summary(self, ax, checkins):
        """Рисует график воды для сводки"""
        dates = [c.date for c in checkins[-7:]]
        water = [c.water_ml/1000 if c.water_ml else 0 for c in checkins[-7:]]
        
        ax.bar(dates, water, color=self.colors['secondary'], alpha=0.7)
        ax.axhline(y=2.0, color='red', linestyle='--', alpha=0.5)
        ax.set_title('Вода (7 дней)', fontsize=12)
        ax.set_ylabel('Литры')
        ax.tick_params(axis='x', rotation=45)