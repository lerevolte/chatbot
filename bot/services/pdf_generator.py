import os
import logging
from datetime import datetime
from typing import List, Dict
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from bot.config import settings
from database.models import User, MealPlan, Goal

logger = logging.getLogger(__name__)

class PDFGenerator:
    """Генератор PDF документов"""
    
    def __init__(self):
        # ========== НАСТРОЙКА PDF ==========
        self.pdf_dir = settings.PDF_DIR
        os.makedirs(self.pdf_dir, exist_ok=True)
        
        # Попытка зарегистрировать кириллические шрифты
        try:
            # В Docker контейнере нужно будет добавить шрифты
            # pdfmetrics.registerFont(TTFont('DejaVu', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
            pass
        except:
            logger.warning("Не удалось загрузить кириллические шрифты")
    
    async def generate_meal_plan_pdf(
        self, 
        user: User, 
        meal_plans: List[MealPlan]
    ) -> str:
        """
        Генерирует PDF с планом питания на неделю
        ========== ГЕНЕРАЦИЯ PDF ПЛАНА ПИТАНИЯ ==========
        """
        # Имя файла
        filename = f"meal_plan_{user.telegram_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(self.pdf_dir, filename)
        
        # Создаем документ
        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=20*mm,
            bottomMargin=20*mm
        )
        
        # Стили
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2E7D32'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))
        styles.add(ParagraphStyle(
            name='DayTitle',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1976D2'),
            spaceAfter=12,
            spaceBefore=20
        ))
        
        # Элементы документа
        elements = []
        
        # ========== ЗАГОЛОВОК ==========
        title = Paragraph("План питания на неделю", styles['CustomTitle'])
        elements.append(title)
        
        # Информация о пользователе
        user_info = f"""
        <b>Ваши параметры:</b><br/>
        Калории: {user.daily_calories} ккал/день<br/>
        Белки: {user.daily_protein}г | Жиры: {user.daily_fats}г | Углеводы: {user.daily_carbs}г<br/>
        Цель: {self._get_goal_text(user.goal)}
        """
        elements.append(Paragraph(user_info, styles['Normal']))
        elements.append(Spacer(1, 20))
        
        # ========== ПЛАН ПО ДНЯМ ==========
        days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        
        for plan in sorted(meal_plans, key=lambda x: x.day_number):
            # Заголовок дня
            day_title = Paragraph(days[plan.day_number - 1], styles['DayTitle'])
            elements.append(day_title)
            
            # Таблица с блюдами
            data = [
                ['Прием пищи', 'Блюдо', 'Калории', 'Б/Ж/У']
            ]
            
            # Завтрак
            if plan.breakfast:
                data.append([
                    'Завтрак',
                    plan.breakfast['name'],
                    f"{plan.breakfast['calories']} ккал",
                    f"{plan.breakfast['protein']}/{plan.breakfast['fats']}/{plan.breakfast['carbs']}г"
                ])
            
            # Обед
            if plan.lunch:
                data.append([
                    'Обед',
                    plan.lunch['name'],
                    f"{plan.lunch['calories']} ккал",
                    f"{plan.lunch['protein']}/{plan.lunch['fats']}/{plan.lunch['carbs']}г"
                ])
            
            # Ужин
            if plan.dinner:
                data.append([
                    'Ужин',
                    plan.dinner['name'],
                    f"{plan.dinner['calories']} ккал",
                    f"{plan.dinner['protein']}/{plan.dinner['fats']}/{plan.dinner['carbs']}г"
                ])
            
            # Перекус
            if plan.snack:
                data.append([
                    'Перекус',
                    plan.snack['name'],
                    f"{plan.snack['calories']} ккал",
                    "-"
                ])
            
            # Итого
            data.append([
                'ИТОГО',
                '',
                f"{plan.total_calories} ккал",
                f"{plan.total_protein}/{plan.total_fats}/{plan.total_carbs}г"
            ])
            
            # Создаем таблицу
            table = Table(data, colWidths=[60, 180, 60, 60])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E8F5E9')),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(table)
            elements.append(Spacer(1, 10))
        
        # ========== СПИСОК ПОКУПОК ==========
        elements.append(PageBreak())
        shopping_title = Paragraph("Список покупок на неделю", styles['CustomTitle'])
        elements.append(shopping_title)
        
        shopping_list = self._generate_shopping_list(meal_plans)
        for category, items in shopping_list.items():
            if items:
                cat_title = Paragraph(f"<b>{category}:</b>", styles['Normal'])
                elements.append(cat_title)
                
                for item in items:
                    item_text = Paragraph(f"• {item}", styles['Normal'])
                    elements.append(item_text)
                
                elements.append(Spacer(1, 10))
        
        # Генерируем PDF
        doc.build(elements)
        
        logger.info(f"PDF сгенерирован: {filepath}")
        return filepath
    
    async def generate_shopping_list_pdf(
        self, 
        user: User, 
        meal_plans: List[MealPlan]
    ) -> str:
        """
        Генерирует PDF только со списком покупок
        ========== PDF СПИСОК ПОКУПОК ==========
        """
        filename = f"shopping_{user.telegram_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(self.pdf_dir, filename)
        
        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=20*mm,
            bottomMargin=20*mm
        )
        
        styles = getSampleStyleSheet()
        elements = []
        
        # Заголовок
        title = Paragraph("Список покупок на неделю", styles['Title'])
        elements.append(title)
        elements.append(Spacer(1, 20))
        
        # Генерируем список
        shopping_list = self._generate_shopping_list(meal_plans)
        
        # Создаем чек-лист
        data = []
        for category, items in shopping_list.items():
            if items:
                # Заголовок категории
                data.append(['', f'<b>{category}</b>', ''])
                # Товары
                for item in items:
                    data.append(['☐', item, '_____'])
        
        if data:
            table = Table(data, colWidths=[20, 250, 80])
            table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (0, -1), 5),
            ]))
            elements.append(table)
        
        doc.build(elements)
        logger.info(f"PDF список покупок сгенерирован: {filepath}")
        return filepath
    
    def _generate_shopping_list(self, meal_plans: List[MealPlan]) -> Dict[str, List[str]]:
        """
        Генерирует список покупок из планов питания
        ========== ОБРАБОТКА ИНГРЕДИЕНТОВ ==========
        """
        shopping_dict = {}
        
        for plan in meal_plans:
            for meal in [plan.breakfast, plan.lunch, plan.dinner, plan.snack]:
                if meal and meal.get('ingredients'):
                    for ingredient in meal['ingredients']:
                        # Парсим ингредиент
                        parts = ingredient.split(' - ')
                        name = parts[0].strip()
                        amount = parts[1].strip() if len(parts) > 1 else ""
                        
                        if name not in shopping_dict:
                            shopping_dict[name] = []
                        if amount:
                            shopping_dict[name].append(amount)
        
        # Группируем по категориям
        categories = {
            "Мясо и птица": [],
            "Рыба и морепродукты": [],
            "Молочные продукты": [],
            "Овощи": [],
            "Фрукты": [],
            "Крупы и макароны": [],
            "Другое": []
        }
        
        # Ключевые слова для категорий
        keywords = {
            "Мясо и птица": ["курица", "говядина", "свинина", "индейка", "фарш"],
            "Рыба и морепродукты": ["рыба", "треска", "лосось", "креветки", "тунец"],
            "Молочные продукты": ["молоко", "творог", "сыр", "йогурт", "кефир", "сметана"],
            "Овощи": ["помидор", "огурец", "капуста", "морковь", "лук", "картофель", "перец", "кабачок"],
            "Фрукты": ["яблоко", "банан", "апельсин", "груша", "ягоды"],
            "Крупы и макароны": ["рис", "гречка", "овсянка", "макароны", "паста", "киноа"]
        }
        
        # Распределяем по категориям
        for item, amounts in shopping_dict.items():
            categorized = False
            for category, keys in keywords.items():
                if any(key in item.lower() for key in keys):
                    amount_str = ", ".join(set(amounts)) if amounts else ""
                    categories[category].append(f"{item} - {amount_str}" if amount_str else item)
                    categorized = True
                    break
            
            if not categorized:
                amount_str = ", ".join(set(amounts)) if amounts else ""
                categories["Другое"].append(f"{item} - {amount_str}" if amount_str else item)
        
        return categories
    
    def _get_goal_text(self, goal: Goal) -> str:
        """Получить текстовое описание цели"""
        return {
            Goal.LOSE_WEIGHT: "Снижение веса",
            Goal.GAIN_MUSCLE: "Набор мышечной массы",
            Goal.MAINTAIN: "Поддержание веса"
        }.get(goal, "Поддержание веса")