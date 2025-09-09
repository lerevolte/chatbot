from database.models import Gender, Goal, ActivityLevel

def calculate_calories_and_macros(
    gender: Gender,
    age: int,
    height: float,
    weight: float,
    activity_level: ActivityLevel,
    goal: Goal
) -> tuple[int, float, float, float]:
    """
    Рассчитывает дневную норму калорий и макронутриентов
    Возвращает: (calories, protein, fats, carbs)
    """
    
    # Расчет базального метаболизма (BMR) по формуле Миффлина-Сан Жеора
    if gender == Gender.MALE:
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:  # FEMALE
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    
    # Коэффициенты активности
    activity_multipliers = {
        ActivityLevel.SEDENTARY: 1.2,
        ActivityLevel.LIGHT: 1.375,
        ActivityLevel.MODERATE: 1.55,
        ActivityLevel.ACTIVE: 1.725,
        ActivityLevel.VERY_ACTIVE: 1.9
    }
    
    # TDEE (Total Daily Energy Expenditure)
    tdee = bmr * activity_multipliers[activity_level]
    
    # Корректировка калорий в зависимости от цели
    if goal == Goal.LOSE_WEIGHT:
        # Дефицит 20-25%
        calories = int(tdee * 0.75)
        # Больше белка для сохранения мышц
        protein_ratio = 0.35  # 35% от калорий
        fats_ratio = 0.25     # 25% от калорий
        carbs_ratio = 0.40    # 40% от калорий
    elif goal == Goal.GAIN_MUSCLE:
        # Профицит 10-15%
        calories = int(tdee * 1.15)
        # Умеренно высокий белок
        protein_ratio = 0.30  # 30% от калорий
        fats_ratio = 0.25     # 25% от калорий
        carbs_ratio = 0.45    # 45% от калорий
    else:  # MAINTAIN
        calories = int(tdee)
        protein_ratio = 0.30  # 30% от калорий
        fats_ratio = 0.30     # 30% от калорий
        carbs_ratio = 0.40    # 40% от калорий
    
    # Расчет макронутриентов в граммах
    # 1г белка = 4 ккал, 1г жира = 9 ккал, 1г углеводов = 4 ккал
    protein = round((calories * protein_ratio) / 4, 1)
    fats = round((calories * fats_ratio) / 9, 1)
    carbs = round((calories * carbs_ratio) / 4, 1)
    
    # Минимальные значения для здоровья
    protein = max(protein, weight * 1.2)  # Минимум 1.2г на кг веса
    fats = max(fats, weight * 0.8)        # Минимум 0.8г на кг веса
    
    return calories, protein, fats, carbs

def calculate_water_intake(weight: float) -> int:
    """
    Рассчитывает рекомендуемое потребление воды в мл
    """
    return int(weight * 35)  # 35 мл на кг веса

def calculate_weekly_progress(
    current_weight: float,
    target_weight: float,
    goal: Goal
) -> float:
    """
    Рассчитывает рекомендуемый недельный прогресс в кг
    """
    if goal == Goal.LOSE_WEIGHT:
        # Безопасная потеря веса 0.5-1 кг в неделю
        return min(0.75, (current_weight - target_weight) / 12)  # За 12 недель
    elif goal == Goal.GAIN_MUSCLE:
        # Набор массы 0.25-0.5 кг в неделю
        return min(0.35, (target_weight - current_weight) / 12)
    else:
        return 0

def adjust_calories_for_plateau(
    current_calories: int,
    days_without_progress: int,
    goal: Goal
) -> int:
    """
    Корректирует калории при плато
    """
    if days_without_progress < 7:
        return current_calories
    
    if goal == Goal.LOSE_WEIGHT:
        # Уменьшаем на 5-10%
        return int(current_calories * 0.93)
    elif goal == Goal.GAIN_MUSCLE:
        # Увеличиваем на 5-10%
        return int(current_calories * 1.07)
    else:
        return current_calories