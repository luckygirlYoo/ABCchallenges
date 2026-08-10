"""
SQLAlchemy ORM 모델 정의
"""
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, 
    DateTime, Text, JSON, UniqueConstraint, Index
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Place(Base):
    """장소 기본 정보"""
    __tablename__ = "places"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 기본 정보
    source = Column(String(50), nullable=False, index=True)  # 수집 출처
    source_id = Column(String(100), nullable=True)  # 출처별 고유 ID
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)  # 카페, 공원, 박물관 등
    sub_category = Column(String(100), nullable=True)

    # 주소/위치
    address = Column(String(500), nullable=True)
    road_address = Column(String(500), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    region = Column(String(50), nullable=True, index=True)  # 서울, 경기 등
    district = Column(String(50), nullable=True)  # 강남구, 마포구 등

    # 연락처/운영
    phone = Column(String(50), nullable=True)
    website = Column(String(500), nullable=True)
    opening_hours = Column(Text, nullable=True)

    # 태그/속성 (JSON)
    tags = Column(JSON, default=list)  # ["가족용", "주차가능", "유모차가능"]
    target_audience = Column(JSON, default=list)  # ["가족", "커플", "싱글"]

    # 부가 정보
    description = Column(Text, nullable=True)
    images = Column(JSON, default=list)
    rating = Column(Float, nullable=True)
    review_count = Column(Integer, default=0)

    # POI 상세
    has_parking = Column(Boolean, default=False)
    has_nursing_room = Column(Boolean, default=False)
    has_stroller_access = Column(Boolean, default=False)
    is_no_kids_zone = Column(Boolean, default=False)
    has_diaper_changing = Column(Boolean, default=False)
    has_kids_menu = Column(Boolean, default=False)

    # 실시간 데이터
    congestion_level = Column(String(20), nullable=True)  # 여유, 보통, 혼잡
    congestion_rate = Column(Float, nullable=True)  # 0.0 ~ 1.0

    # 메타
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # 중복 제거용 유니크 제약
    __table_args__ = (
        UniqueConstraint('latitude', 'longitude', 'name', name='uq_place_location_name'),
        Index('idx_place_region_category', 'region', 'category'),
    )


class Event(Base):
    """이벤트/행사 정보"""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)

    source = Column(String(50), nullable=False, index=True)
    source_id = Column(String(100), nullable=True)
    title = Column(String(500), nullable=False)

    # 장소 연결
    place_id = Column(Integer, nullable=True)
    place_name = Column(String(255), nullable=True)
    address = Column(String(500), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # 기간
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)

    # 분류
    category = Column(String(100), nullable=True)  # 팝업, 공연, 축제, 전시
    sub_category = Column(String(100), nullable=True)
    tags = Column(JSON, default=list)
    target_audience = Column(JSON, default=list)

    # 상세
    description = Column(Text, nullable=True)
    price = Column(String(100), nullable=True)
    booking_url = Column(String(500), nullable=True)
    images = Column(JSON, default=list)

    # 메타
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint('source', 'source_id', name='uq_event_source'),
    )


class Performance(Base):
    """공연 정보 (KOPIS, 예스24 등)"""
    __tablename__ = "performances"

    id = Column(Integer, primary_key=True, autoincrement=True)

    source = Column(String(50), nullable=False)
    performance_id = Column(String(100), nullable=False, unique=True)
    title = Column(String(500), nullable=False)

    # 장소
    venue = Column(String(255), nullable=True)
    venue_address = Column(String(500), nullable=True)

    # 기간
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)

    # 분류
    genre = Column(String(100), nullable=True)  # 뮤지컬, 연극, 콘서트 등
    state = Column(String(50), nullable=True)  # 공연예정, 공연중, 공연완료

    # 상세
    cast = Column(Text, nullable=True)
    crew = Column(Text, nullable=True)
    runtime = Column(String(50), nullable=True)
    age_limit = Column(String(50), nullable=True)
    price_info = Column(Text, nullable=True)
    poster_url = Column(String(500), nullable=True)
    detail_url = Column(String(500), nullable=True)

    # 메타
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RealTimeData(Base):
    """실시간 인파/혼잡도 데이터"""
    __tablename__ = "realtime_data"

    id = Column(Integer, primary_key=True, autoincrement=True)

    place_id = Column(Integer, nullable=True, index=True)
    place_name = Column(String(255), nullable=True)
    area_name = Column(String(255), nullable=True, index=True)  # 명동, 강남역 등

    # 혼잡도
    congestion_level = Column(String(20), nullable=True)
    congestion_rate = Column(Float, nullable=True)
    congestion_message = Column(Text, nullable=True)

    # 인구
    population = Column(Integer, nullable=True)
    population_male = Column(Integer, nullable=True)
    population_female = Column(Integer, nullable=True)

    # 날씨 (연동 시)
    weather = Column(String(100), nullable=True)
    temperature = Column(Float, nullable=True)

    # 수집 시간
    collected_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index('idx_realtime_area_time', 'area_name', 'collected_at'),
    )


class CollectionLog(Base):
    """수집 작업 로그"""
    __tablename__ = "collection_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    collector_name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)  # success, failed, partial
    items_collected = Column(Integer, default=0)
    items_inserted = Column(Integer, default=0)
    items_updated = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
