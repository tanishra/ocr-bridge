from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "OCRBridge"
    DEBUG: bool = False
    
    # Gemini
    GEMINI_API_KEY: str
    GEMINI_MODEL: str 
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str
    
    # Database
    DATABASE_URL: str 
    
    # Google Sheets
    GOOGLE_SHEETS_CREDENTIALS: str = "credentials.json"
    GOOGLE_SHEET_ID: str = ""

    # Payments (Razorpay)
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
