"""
프로젝트 전역 설정 파일
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """애플리케이션 설정"""

    # 데이터베이스
    DATABASE_URL = os.getenv(
        "DATABASE_URL", 
        "sqlite:///weekend_data.db"
    )

    # API 키
    PUBLIC_DATA_API_KEY = os.getenv("PUBLIC_DATA_API_KEY", "")
    KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "")
    NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
    NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")
    SEOUL_CITY_DATA_KEY = os.getenv("SEOUL_CITY_DATA_KEY", "")
    KOPIS_API_KEY = os.getenv("KOPIS_API_KEY", "")
    TMAP_APP_KEY = os.getenv("TMAP_APP_KEY", "")

    # 크롤링 설정
    CRAWL_DELAY_MIN = 1.5
    CRAWL_DELAY_MAX = 4.0
    REQUEST_TIMEOUT = 30
    MAX_RETRIES = 3

    # 수집 설정
    BATCH_SIZE = 100
    COLLECTION_REGIONS = ["서울", "경기", "인천"]

    # 로깅
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
