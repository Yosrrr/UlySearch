from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Sotradies - Veille Appels d'Offres"
    ENV: str = "development"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    ALLOW_PROCESS_CONTROL: bool = False

    DATABASE_URL: str = "postgresql+psycopg://sotradies_user:sotradies_pass@localhost:5432/sotradies_watch"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    JWT_SECRET_KEY: str = "changez-moi-en-production-avec-une-vraie-cle-secrete"
    JWT_EXPIRE_MINUTES: int = 480  # 8h — une journée de travail

    CACHE_REDIS_URL: str = "redis://localhost:6379/2"
    
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SENDER_EMAIL: str = "veille-ao@sotradies.tn"

    TUNEPS_USERNAME: str = ""
    TUNEPS_PASSWORD: str = ""
    
    GEMINI_API_KEY: str = ""
    
    DIRECTION_EMAIL: str = ""

    RELEVANCE_INSTANT_ALERT_THRESHOLD: int = 80
    RELEVANCE_RETAIN_THRESHOLD: int = 50

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        """Render fournit une URL PostgreSQL générique; l'application utilise psycopg 3."""
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @model_validator(mode="after")
    def validate_production_secrets(self):
        if self.ENV.lower() == "production" and self.JWT_SECRET_KEY.startswith("changez-moi"):
            raise ValueError("JWT_SECRET_KEY doit être défini en production")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
