"""
공공데이터포털 API 수집기
- 키즈카페, 물놀이장, 지자체 행사 등
"""
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from database import get_db, Place, Event
from database.models import Base
from utils.helpers import (
    get_default_headers, RandomDelay, 
    normalize_address, extract_region, extract_district,
    assign_tags, deduplicate_places
)
from collectors.base import BaseCollector


class PublicDataCollector(BaseCollector):
    """공공데이터포털 수집기"""

    BASE_URL = "http://apis.data.go.kr"

    def __init__(self):
        super().__init__("public_data")
        self.api_key = settings.PUBLIC_DATA_API_KEY
        self.headers = get_default_headers()

    @retry(
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def _request(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """API 요청 with Retry"""
        try:
            response = requests.get(
                url,
                params=params,
                headers=self.headers,
                timeout=settings.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.warning(f"[PublicData] 타임아웃: {url}")
            raise
        except requests.exceptions.HTTPError as e:
            logger.warning(f"[PublicData] HTTP 오류 {e.response.status_code}: {url}")
            raise
        except Exception as e:
            logger.error(f"[PublicData] 요청 실패: {e}")
            raise

    def _fetch_kids_cafe(self, page: int = 1, per_page: int = 100) -> List[Dict[str, Any]]:
        """키즈카페 정보 조회 (예시: 서울시 키즈카페)"""
        # 실제 API 엔드포인트는 공공데이터포털에서 확인 후 수정 필요
        url = f"{self.BASE_URL}/B551014/openapi/service/SeoulKidsCafeService/getSeoulKidsCafe"

        params = {
            "serviceKey": self.api_key,
            "pageNo": page,
            "numOfRows": per_page,
            "resultType": "json",
        }

        try:
            data = self._request(url, params)
            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            if not isinstance(items, list):
                items = [items] if items else []
            return items
        except Exception as e:
            logger.error(f"[PublicData] 키즈카페 조회 실패: {e}")
            return []

    def _fetch_water_parks(self, page: int = 1, per_page: int = 100) -> List[Dict[str, Any]]:
        """물놀이장 정보 조회 (예시)"""
        url = f"{self.BASE_URL}/B551014/openapi/service/SeoulWaterParkService/getSeoulWaterPark"

        params = {
            "serviceKey": self.api_key,
            "pageNo": page,
            "numOfRows": per_page,
            "resultType": "json",
        }

        try:
            data = self._request(url, params)
            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            if not isinstance(items, list):
                items = [items] if items else []
            return items
        except Exception as e:
            logger.error(f"[PublicData] 물놀이장 조회 실패: {e}")
            return []

    def _fetch_local_events(self, page: int = 1, per_page: int = 100) -> List[Dict[str, Any]]:
        """지자체 행사 정보 조회"""
        url = f"{self.BASE_URL}/B551014/openapi/service/SeoulEventService/getSeoulEvent"

        params = {
            "serviceKey": self.api_key,
            "pageNo": page,
            "numOfRows": per_page,
            "resultType": "json",
        }

        try:
            data = self._request(url, params)
            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            if not isinstance(items, list):
                items = [items] if items else []
            return items
        except Exception as e:
            logger.error(f"[PublicData] 행사 조회 실패: {e}")
            return []

    def _normalize_kids_cafe(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """키즈카페 원본 데이터 정규화"""
        name = raw.get("FAC_NAME", raw.get("name", "이름없음"))
        address = normalize_address(raw.get("ADDR", raw.get("address")))

        tags_info = assign_tags(name, "키즈카페", raw.get("DESCRIPTION"))

        return {
            "source": "public_data_kids_cafe",
            "source_id": raw.get("FAC_CODE", raw.get("id")),
            "name": name,
            "category": "키즈카페",
            "sub_category": raw.get("FAC_TYPE"),
            "address": address,
            "road_address": normalize_address(raw.get("ROAD_ADDR")),
            "latitude": float(raw.get("LAT", 0)) if raw.get("LAT") else None,
            "longitude": float(raw.get("LNG", 0)) if raw.get("LNG") else None,
            "region": extract_region(address) or "서울",
            "district": extract_district(address),
            "phone": raw.get("TEL"),
            "website": raw.get("HOMEPAGE"),
            "opening_hours": raw.get("OPEN_TIME"),
            "description": raw.get("DESCRIPTION"),
            "tags": tags_info["tags"],
            "target_audience": tags_info["target_audience"],
            "has_parking": "주차" in str(raw.get("ETC", "")),
            "has_nursing_room": "수유실" in str(raw.get("ETC", "")),
            "has_stroller_access": True,
            "has_diaper_changing": "기저귀" in str(raw.get("ETC", "")),
            "has_kids_menu": True,
            "rating": None,
            "review_count": 0,
        }

    def _normalize_water_park(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """물놀이장 원본 데이터 정규화"""
        name = raw.get("FAC_NAME", raw.get("name", "이름없음"))
        address = normalize_address(raw.get("ADDR", raw.get("address")))

        tags_info = assign_tags(name, "물놀이장", raw.get("DESCRIPTION"))
        tags_info["tags"].extend(["여름", "야외", "물놀이"])

        return {
            "source": "public_data_water_park",
            "source_id": raw.get("FAC_CODE", raw.get("id")),
            "name": name,
            "category": "물놀이장",
            "sub_category": raw.get("FAC_TYPE"),
            "address": address,
            "road_address": normalize_address(raw.get("ROAD_ADDR")),
            "latitude": float(raw.get("LAT", 0)) if raw.get("LAT") else None,
            "longitude": float(raw.get("LNG", 0)) if raw.get("LNG") else None,
            "region": extract_region(address) or "서울",
            "district": extract_district(address),
            "phone": raw.get("TEL"),
            "website": raw.get("HOMEPAGE"),
            "opening_hours": raw.get("OPEN_TIME"),
            "description": raw.get("DESCRIPTION"),
            "tags": list(set(tags_info["tags"])),
            "target_audience": tags_info["target_audience"],
            "has_parking": True,
            "has_nursing_room": "수유실" in str(raw.get("ETC", "")),
            "has_stroller_access": True,
            "has_diaper_changing": True,
            "rating": None,
            "review_count": 0,
        }

    def _normalize_event(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """행사 원본 데이터 정규화"""
        name = raw.get("TITLE", raw.get("name", "이름없음"))
        address = normalize_address(raw.get("ADDR", raw.get("address")))

        tags_info = assign_tags(name, raw.get("CATEGORY"), raw.get("DESCRIPTION"))

        # 날짜 파싱
        start_date = None
        end_date = None
        try:
            if raw.get("START_DATE"):
                start_date = datetime.strptime(raw["START_DATE"], "%Y-%m-%d")
            if raw.get("END_DATE"):
                end_date = datetime.strptime(raw["END_DATE"], "%Y-%m-%d")
        except ValueError:
            pass

        return {
            "source": "public_data_event",
            "source_id": raw.get("EVENT_CODE", raw.get("id")),
            "title": name,
            "place_name": raw.get("PLACE"),
            "address": address,
            "latitude": float(raw.get("LAT", 0)) if raw.get("LAT") else None,
            "longitude": float(raw.get("LNG", 0)) if raw.get("LNG") else None,
            "start_date": start_date,
            "end_date": end_date,
            "category": raw.get("CATEGORY", "행사"),
            "sub_category": raw.get("SUB_CATEGORY"),
            "tags": tags_info["tags"],
            "target_audience": tags_info["target_audience"],
            "description": raw.get("DESCRIPTION"),
            "price": raw.get("PRICE"),
            "booking_url": raw.get("BOOKING_URL"),
            "images": [raw.get("IMAGE_URL")] if raw.get("IMAGE_URL") else [],
        }

    def collect(self) -> List[Dict[str, Any]]:
        """공공데이터 수집 (동기)"""
        all_places = []
        all_events = []

        # 키즈카페 수집
        logger.info("[PublicData] 키즈카페 수집 시작")
        for page in range(1, 6):  # 최대 5페이지
            RandomDelay.sleep(1.0, 2.5)
            items = self._fetch_kids_cafe(page=page)
            if not items:
                break
            all_places.extend([self._normalize_kids_cafe(item) for item in items])

        # 물놀이장 수집
        logger.info("[PublicData] 물놀이장 수집 시작")
        for page in range(1, 4):
            RandomDelay.sleep(1.0, 2.5)
            items = self._fetch_water_parks(page=page)
            if not items:
                break
            all_places.extend([self._normalize_water_park(item) for item in items])

        # 행사 수집
        logger.info("[PublicData] 지자체 행사 수집 시작")
        for page in range(1, 6):
            RandomDelay.sleep(1.0, 2.5)
            items = self._fetch_local_events(page=page)
            if not items:
                break
            all_events.extend([self._normalize_event(item) for item in items])

        # 중복 제거
        all_places = deduplicate_places(all_places)

        # 결과 통합
        results = []
        results.extend([{"type": "place", "data": p} for p in all_places])
        results.extend([{"type": "event", "data": e} for e in all_events])

        return results

    async def collect_async(self) -> List[Dict[str, Any]]:
        """비동기 수집"""
        return await asyncio.to_thread(self.collect)

    def save(self, items: List[Dict[str, Any]]) -> None:
        """데이터베이스 저장 (Upsert)"""
        with get_db() as db:
            for item in items:
                try:
                    if item["type"] == "place":
                        data = item["data"]

                        # 기존 데이터 확인
                        existing = db.query(Place).filter(
                            Place.source == data["source"],
                            Place.name == data["name"],
                        ).first()

                        if existing:
                            # 업데이트
                            for key, value in data.items():
                                if hasattr(existing, key):
                                    setattr(existing, key, value)
                            existing.updated_at = datetime.utcnow()
                            self.updated_count += 1
                        else:
                            # 신규 삽입
                            place = Place(**data)
                            db.add(place)
                            self.inserted_count += 1

                    elif item["type"] == "event":
                        data = item["data"]

                        existing = db.query(Event).filter(
                            Event.source == data["source"],
                            Event.source_id == data["source_id"],
                        ).first()

                        if existing:
                            for key, value in data.items():
                                if hasattr(existing, key):
                                    setattr(existing, key, value)
                            existing.updated_at = datetime.utcnow()
                            self.updated_count += 1
                        else:
                            event = Event(**data)
                            db.add(event)
                            self.inserted_count += 1

                except Exception as e:
                    logger.error(f"[PublicData] 저장 오류: {e}")
                    continue
