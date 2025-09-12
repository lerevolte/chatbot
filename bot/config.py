from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Telegram
    BOT_TOKEN: str
    
    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "fitness_bot"
    DB_USER: str = "postgres"
    DB_PASSWORD: str
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    # Payments (для будущего)
    PAYMENT_PROVIDER_TOKEN: Optional[str] = None
    
    # ========== НОВОЕ: AI Integration ==========
    # OPENAI_API_KEY: Optional[str] = None
    # AI_MODEL: str = "gpt-3.5-turbo"  # или gpt-4

    # Gemini
    GEMINI_API_KEY: Optional[str] = None
    AI_MODEL: str = "gemini-1.5-flash"

    AI_TEMPERATURE: float = 0.7
    AI_MAX_TOKENS: int = 2000
    
    # ========== НОВОЕ: File Storage ==========
    UPLOAD_DIR: str = "/app/uploads"
    PDF_DIR: str = "/app/pdfs"
    
    # Payments
    TELEGRAM_PAYMENT_TOKEN: Optional[str] = None  # Токен от BotFather
    YOOKASSA_TOKEN: Optional[str] = None  # Для российских платежей
    YOOKASSA_SHOP_ID: Optional[str] = None
    CRYPTOBOT_TOKEN: Optional[str] = None  # Для крипто-платежей
    
    # Настройки подписки
    TRIAL_DAYS: int = 7
    SUBSCRIPTION_MONTHLY_PRICE: int = 299  # В рублях
    SUBSCRIPTION_QUARTERLY_PRICE: int = 699
    SUBSCRIPTION_YEARLY_PRICE: int = 1999
    DEBUG: bool = False
    
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"  # ========== ДОБАВЛЕНО: разрешаем дополнительные поля ==========
    
    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

settings = Settings()