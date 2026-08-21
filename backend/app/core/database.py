from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings
from contextlib import contextmanager


engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        

@contextmanager
def session_scope():
    """Pour tout code hors requête HTTP (pipeline, notifier, scripts, tâches
    Celery), où Depends(get_db) n'est pas utilisable. Garantit un commit en
    cas de succès, un rollback en cas d'exception, et une fermeture
    systématique — remplace le pattern SessionLocal()/db.close() manuel qui
    fuit une connexion si une exception survient entre les deux."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
