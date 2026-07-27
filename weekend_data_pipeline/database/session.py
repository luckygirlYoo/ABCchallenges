"""
데이터베이스 세션 관리
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

from config import settings
from database.models import Base


def get_engine():
    return create_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=3600,
    )

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """데이터베이스 테이블 생성"""
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db():
    """DB 세션 컨텍스트 매니저"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session():
    """FastAPI 등에서 사용할 세션 의존성"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
