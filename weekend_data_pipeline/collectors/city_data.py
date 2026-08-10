"""
실시간 도시 데이터 수집기
- 서울시 실시간 도시데이터 API
- TMap 인기 목적지 API
"""
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from database import get_db, RealTimeData
from utils.helpers import get_default_headers, RandomDelay
from collectors.base import BaseCollector


class CityDataCollector(BaseCollector):
    """실시간 도시 데이터 수집기"""

    SEOUL_API_URL = "http://openapi.seoul.go.kr:8088"
    TMAP_API_URL = "https://apis.openapi.sk.com/tmap"

    def __init__(self):
        super().__init__("city_data")
        self.seoul_key = settings.SEOUL_CITY_DATA_KEY
        self.tmap_key = settings.TMAP_APP_KEY
        self.headers = get_default_headers()

    @retry(
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def _request(self, url: str, params: Dict[str, Any] = None, headers: Dict[str, str] = None) -> Dict[str, Any]:
        """API 요청"""
        try:
            response = requests.get(
                url,
                params=params,
                headers=headers or self.headers,
                timeout=settings.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"[CityData] 요청 실패 {url}: {e}")
            raise

    def _fetch_seoul_congestion(self) -> List[Dict[str, Any]]:
        """서울시 실시간 인구밀집도 조회"""
        url = f"{self.SEOUL_API_URL}/{self.seoul_key}/json/citydata_ppltn/1/100"

        # 주요 지역 리스트
        areas = [
            "POI001",  # 강남역
            "POI002",  # 명동
            "POI003",  # 홍대입구
            "POI004",  # 이태원
            "POI005",  # 잠실
            "POI006",  # 여의도
            "POI007",  # 코엑스
            "POI008",  # 북촌
            "POI009",  # 남산
            "POI010",  # 한강공원
        ]

        results = []
        for area in areas:
            try:
                RandomDelay.sleep(0.5, 1.5)
                data = self._request(f"{url}/{area}")

                area_data = data.get("SeoulRtd.citydata_ppltn", [])
                if not isinstance(area_data, list):
                    area_data = [area_data] if area_data else []

                for item in area_data:
                    area_name = item.get("AREA_NM", item.get("area_nm", area))
                    congestion = item.get("AREA_CONGEST_LVL", item.get("area_congest_lvl", "보통"))
                    congestion_rate = self._parse_congestion_rate(congestion)

                    results.append({
                        "place_name": area_name,
                        "area_name": area_name,
                        "congestion_level": congestion,
                        "congestion_rate": congestion_rate,
                        "congestion_message": item.get("AREA_CONGEST_MSG", item.get("area_congest_msg", "")),
                        "population": item.get("AREA_PPLTN_MIN", item.get("area_ppltn_min")),
                        "population_male": item.get("MALE_PPLTN_RATE", item.get("male_ppltn_rate")),
                        "population_female": item.get("FEMALE_PPLTN_RATE", item.get("female_ppltn_rate")),
                        "weather": item.get("WEATHER", item.get("weather", "")),
                        "temperature": item.get("TEMP", item.get("temp")),
                        "collected_at": datetime.utcnow(),
                    })
            except Exception as e:
                logger.error(f"[CityData] {area} 조회 실패: {e}")
                continue

        return results

    def _parse_congestion_rate(self, level: str) -> Optional[float]:
        """혼잡도 레벨을 수치로 변환"""
        mapping = {
            "여유": 0.2,
            "보통": 0.5,
            "약간 붐빔": 0.7,
            "붐빔": 0.9,
        }
        return mapping.get(level)

    def _fetch_tmap_popular(self) -> List[Dict[str, Any]]:
        """TMap 인기 목적지 조회"""
        url = f"{self.TMAP_API_URL}/pois/search/around"

        headers = {
            **self.headers,
            "appKey": self.tmap_key,
        }

        # 서울 중심 좌표
        center_lat, center_lng = 37.5665, 126.9780

        params = {
            "version": 1,
            "centerLat": center_lat,
            "centerLon": center_lng,
            "radius": 10,
            "count": 50,
            "categories": "관광,쇼핑,문화,음식",
        }

        try:
            data = self._request(url, params, headers)

            results = []
            for poi in data.get("searchPoiInfo", {}).get("pois", {}).get("poi", []):
                results.append({
                    "place_name": poi.get("name"),
                    "area_name": poi.get("name"),
                    "latitude": float(poi.get("frontLat", 0)),
                    "longitude": float(poi.get("frontLon", 0)),
                    "congestion_level": None,
                    "congestion_rate": None,
                    "collected_at": datetime.utcnow(),
                })

            return results
        except Exception as e:
            logger.error(f"[CityData] TMap 조회 실패: {e}")
            return []

    def collect(self) -> List[Dict[str, Any]]:
        """실시간 데이터 수집"""
        all_data = []

        # 서울시 혼잡도
        logger.info("[CityData] 서울시 혼잡도 수집")
        RandomDelay.sleep(1.0, 2.0)
        seoul_data = self._fetch_seoul_congestion()
        all_data.extend(seoul_data)
        logger.info(f"[CityData] 서울시: {len(seoul_data)}건")

        # TMap 인기 장소
        logger.info("[CityData] TMap 인기 장소 수집")
        RandomDelay.sleep(1.0, 2.0)
        tmap_data = self._fetch_tmap_popular()
        all_data.extend(tmap_data)
        logger.info(f"[CityData] TMap: {len(tmap_data)}건")

        return [{"type": "realtime", "data": d} for d in all_data]

    async def collect_async(self) -> List[Dict[str, Any]]:
        """비동기 수집"""
        return await asyncio.to_thread(self.collect)

    def save(self, items: List[Dict[str, Any]]) -> None:
        """실시간 데이터 저장"""
        with get_db() as db:
            for item in items:
                try:
                    data = item["data"]
                    realtime = RealTimeData(**data)
                    db.add(realtime)
                    self.inserted_count += 1
                except Exception as e:
                    logger.error(f"[CityData] 저장 오류: {e}")
                    continue
