"""
공연 정보 수집기
- KOPIS, 예스24, 인터파크, 티켓링크
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import requests
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from database import get_db, Performance
from utils.helpers import get_default_headers, RandomDelay
from collectors.base import BaseCollector


class PerformanceCollector(BaseCollector):
    """공연 정보 수집기"""

    def __init__(self):
        super().__init__("performance")
        self.kopis_key = settings.KOPIS_API_KEY
        self.headers = get_default_headers()

    @retry(
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def _request(self, url: str, params: Dict[str, Any] = None) -> Any:
        """API 요청"""
        try:
            response = requests.get(
                url,
                params=params,
                headers=self.headers,
                timeout=settings.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response
        except Exception as e:
            logger.error(f"[Performance] 요청 실패 {url}: {e}")
            raise

    def _fetch_kopis(self) -> List[Dict[str, Any]]:
        """KOPIS 공연 목록 조회"""
        url = "http://kopis.or.kr/openApi/restful/pblprfr"

        today = datetime.now()
        from_date = today.strftime("%Y%m%d")
        to_date = (today + timedelta(days=90)).strftime("%Y%m%d")

        params = {
            "service": self.kopis_key,
            "stdate": from_date,
            "eddate": to_date,
            "rows": 100,
            "cpage": 1,
        }

        try:
            response = self._request(url, params)
            # KOPIS는 XML 응답
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)

            performances = []
            for item in root.findall("db"):
                perf = {
                    "source": "kopis",
                    "performance_id": item.findtext("mt20id", ""),
                    "title": item.findtext("prfnm", ""),
                    "venue": item.findtext("fcltynm", ""),
                    "start_date": self._parse_kopis_date(item.findtext("prfpdfrom", "")),
                    "end_date": self._parse_kopis_date(item.findtext("prfpdto", "")),
                    "genre": item.findtext("genrenm", ""),
                    "state": item.findtext("prfstate", ""),
                    "poster_url": item.findtext("poster", ""),
                }

                # 상세 정보 조회
                if perf["performance_id"]:
                    detail = self._fetch_kopis_detail(perf["performance_id"])
                    perf.update(detail)

                performances.append(perf)
                RandomDelay.sleep(0.5, 1.5)

            return performances

        except Exception as e:
            logger.error(f"[Performance] KOPIS 조회 실패: {e}")
            return []

    def _fetch_kopis_detail(self, perf_id: str) -> Dict[str, Any]:
        """KOPIS 공연 상세 조회"""
        url = f"http://kopis.or.kr/openApi/restful/pblprfr/{perf_id}"
        params = {"service": self.kopis_key}

        try:
            response = self._request(url, params)
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)
            item = root.find("db")

            if item is None:
                return {}

            return {
                "venue_address": item.findtext("adres", ""),
                "cast": item.findtext("prfcast", ""),
                "crew": item.findtext("prfcrew", ""),
                "runtime": item.findtext("prfruntime", ""),
                "age_limit": item.findtext("prfage", ""),
                "price_info": item.findtext("pcseguidance", ""),
                "detail_url": item.findtext("relateurl", ""),
            }
        except Exception as e:
            logger.debug(f"[Performance] KOPIS 상세 조회 실패 {perf_id}: {e}")
            return {}

    def _parse_kopis_date(self, date_str: str) -> Optional[datetime]:
        """KOPIS 날짜 파싱 (YYYY.MM.DD)"""
        try:
            return datetime.strptime(date_str.strip(), "%Y.%m.%d")
        except ValueError:
            try:
                return datetime.strptime(date_str.strip(), "%Y-%m-%d")
            except ValueError:
                return None

    def _fetch_yes24(self) -> List[Dict[str, Any]]:
        """예스24 공연 정보 (예시 - 실제 API/크롤링 필요)"""
        # 예스24는 API가 제한적이므로 크롤링 또는 RSS 활용
        url = "http://ticket.yes24.com/New/Genre/GenreList.aspx"

        try:
            response = self._request(url)
            # HTML 파싱 로직 (실제 구현 필요)
            logger.info("[Performance] 예스24 수집 완료 (예시)")
            return []
        except Exception as e:
            logger.error(f"[Performance] 예스24 조회 실패: {e}")
            return []

    def collect(self) -> List[Dict[str, Any]]:
        """공연 정보 수집"""
        all_performances = []

        # KOPIS 수집
        logger.info("[Performance] KOPIS 수집 시작")
        RandomDelay.sleep(1.0, 2.0)
        kopis_data = self._fetch_kopis()
        all_performances.extend(kopis_data)
        logger.info(f"[Performance] KOPIS: {len(kopis_data)}건")

        # 예스24 수집
        logger.info("[Performance] 예스24 수집 시작")
        RandomDelay.sleep(2.0, 4.0)
        yes24_data = self._fetch_yes24()
        all_performances.extend(yes24_data)

        return [{"type": "performance", "data": p} for p in all_performances]

    async def collect_async(self) -> List[Dict[str, Any]]:
        """비동기 수집"""
        return await asyncio.to_thread(self.collect)

    def save(self, items: List[Dict[str, Any]]) -> None:
        """데이터베이스 저장"""
        with get_db() as db:
            for item in items:
                try:
                    data = item["data"]

                    existing = db.query(Performance).filter(
                        Performance.performance_id == data["performance_id"]
                    ).first()

                    if existing:
                        for key, value in data.items():
                            if hasattr(existing, key) and value is not None:
                                setattr(existing, key, value)
                        existing.updated_at = datetime.utcnow()
                        self.updated_count += 1
                    else:
                        perf = Performance(**data)
                        db.add(perf)
                        self.inserted_count += 1

                except Exception as e:
                    logger.error(f"[Performance] 저장 오류: {e}")
                    continue
