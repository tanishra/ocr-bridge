from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config import get_settings
from .models import Base


class DatabaseManager:
    def __init__(self):
        settings = get_settings()
        self.engine = create_engine(settings.DATABASE_URL)
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def create_tables(self):
        Base.metadata.create_all(self.engine)
    
    def get_session(self) -> Session:
        return self.SessionLocal()


db_manager = DatabaseManager()