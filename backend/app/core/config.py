from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Sotradies - Veille Appels d'Offres"
    ENV: str = "development"

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

    RELEVANCE_INSTANT_ALERT_THRESHOLD: int = 80
    RELEVANCE_RETAIN_THRESHOLD: int = 50


settings = Settings()