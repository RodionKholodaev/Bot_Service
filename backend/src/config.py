from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", 
        env_file_encoding="utf-8"
        )

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"


settings = Settings() # type: ignore (все работает, но pylance об этом почему-то не знает)
