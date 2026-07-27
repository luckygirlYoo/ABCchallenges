"""
팝업스토어 크롤러
- 백화점(더현대, 신세계, 롯데) 및 팝업 전문 플랫폼 크롤링
"""
import asyncio
import random
from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from database import get_db, Event
from utils.helpers import (
    get_default_headers, RandomDelay, UserAgentRotator,
    normalize_address, extract_region, extract_district,
    assign_tags
)
from collectors.base import BaseCollector


class PopupStoreCrawler(BaseCollector):
    """팝업스토어 크롤러"""

    def __init__(self):
        super().__init__("popup_store")
        self.ua_rotator = UserAgentRotator()
        self.headers = get_default_headers()

    def _get_headers(self) -> Dict[str, str]:
        """랜덤 User-Agent 헤더"""
        headers = self.headers.copy()
        headers["User-Agent"] = self.ua_rotator.get()
        return headers

    @retry(
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def _fetch_html(self, url: str) -> str:
        """정적 HTML 요청"""
        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=settings.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"[Popup] HTML 요청 실패 {url}: {e}")
            raise

    def _parse_thehyundai(self, html: str) -> List[Dict[str, Any]]:
        """더현대 팝업스토어 파싱"""
        soup = BeautifulSoup(html, "lxml")
        events = []

        # 실제 DOM 구조에 맞게 수정 필요 (예시)
        for item in soup.select(".popup-store-item, .event-item, [class*='popup']"):
            try:
                name = item.select_one(".title, .name, h3, h4")
                name = name.get_text(strip=True) if name else None
                if not name:
                    continue

                period = item.select_one(".date, .period, .event-date")
                period_text = period.get_text(strip=True) if period else ""

                location = item.select_one(".location, .place, .store")
                location_text = location.get_text(strip=True) if location else "더현대 서울"

                image = item.select_one("img")
                image_url = image.get("src", "") if image else ""

                link = item.select_one("a")
                detail_url = link.get("href", "") if link else ""

                # 날짜 파싱
                start_date, end_date = self._parse_period(period_text)

                tags_info = assign_tags(name, "팝업스토어", None)
                tags_info["tags"].extend(["팝업", "쇼핑", "백화점"])

                events.append({
                    "source": "thehyundai_popup",
                    "source_id": None,
                    "title": name,
                    "place_name": location_text,
                    "address": "더현대 서울" if "더현대" in location_text else location_text,
                    "latitude": None,
                    "longitude": None,
                    "start_date": start_date,
                    "end_date": end_date,
                    "category": "팝업스토어",
                    "sub_category": "백화점 팝업",
                    "tags": list(set(tags_info["tags"])),
                    "target_audience": tags_info["target_audience"],
                    "description": None,
                    "price": None,
                    "booking_url": urljoin("https://www.ehyundai.com", detail_url) if detail_url else None,
                    "images": [image_url] if image_url else [],
                })
            except Exception as e:
                logger.debug(f"[Popup] 파싱 오류: {e}")
                continue

        return events

    def _parse_shinsegae(self, html: str) -> List[Dict[str, Any]]:
        """신세계 팝업스토어 파싱"""
        soup = BeautifulSoup(html, "lxml")
        events = []

        for item in soup.select(".event-item, .popup-item, [class*='event']"):
            try:
                name = item.select_one(".title, .name, h3")
                name = name.get_text(strip=True) if name else None
                if not name:
                    continue

                period = item.select_one(".date, .period")
                period_text = period.get_text(strip=True) if period else ""

                location = item.select_one(".location, .place")
                location_text = location.get_text(strip=True) if location else "신세계백화점"

                image = item.select_one("img")
                image_url = image.get("src", "") if image else ""

                start_date, end_date = self._parse_period(period_text)

                tags_info = assign_tags(name, "팝업스토어", None)
                tags_info["tags"].extend(["팝업", "쇼핑", "백화점"])

                events.append({
                    "source": "shinsegae_popup",
                    "title": name,
                    "place_name": location_text,
                    "address": location_text,
                    "start_date": start_date,
                    "end_date": end_date,
                    "category": "팝업스토어",
                    "sub_category": "백화점 팝업",
                    "tags": list(set(tags_info["tags"])),
                    "target_audience": tags_info["target_audience"],
                    "images": [image_url] if image_url else [],
                })
            except Exception as e:
                logger.debug(f"[Popup] 신세계 파싱 오류: {e}")
                continue

        return events

    def _parse_popup_platform(self, html: str) -> List[Dict[str, Any]]:
        """팝업 전문 플랫폼 파싱 (예: 팝업스토어 정보 사이트)"""
        soup = BeautifulSoup(html, "lxml")
        events = []

        # 일반적인 팝업 플랫폼 구조
        for item in soup.select(".popup-card, .store-item, article"):
            try:
                name = item.select_one("h2, h3, .store-name, .title")
                name = name.get_text(strip=True) if name else None
                if not name:
                    continue

                period = item.select_one(".period, .date, .event-date")
                period_text = period.get_text(strip=True) if period else ""

                location = item.select_one(".location, .address, .place")
                location_text = location.get_text(strip=True) if location else ""

                desc = item.select_one(".description, .desc, p")
                description = desc.get_text(strip=True) if desc else None

                image = item.select_one("img")
                image_url = image.get("src", "") if image else ""

                start_date, end_date = self._parse_period(period_text)

                tags_info = assign_tags(name, "팝업스토어", description)
                tags_info["tags"].extend(["팝업", "쇼핑"])

                events.append({
                    "source": "popup_platform",
                    "title": name,
                    "place_name": location_text,
                    "address": normalize_address(location_text),
                    "start_date": start_date,
                    "end_date": end_date,
                    "category": "팝업스토어",
                    "sub_category": None,
                    "tags": list(set(tags_info["tags"])),
                    "target_audience": tags_info["target_audience"],
                    "description": description,
                    "images": [image_url] if image_url else [],
                })
            except Exception as e:
                logger.debug(f"[Popup] 플랫폼 파싱 오류: {e}")
                continue

        return events

    def _parse_period(self, period_text: str) -> tuple:
        """기간 텍스트 파싱 (예: '2024.01.01 ~ 2024.01.31')"""
        start_date = None
        end_date = None

        if not period_text:
            return start_date, end_date

        import re
        # 다양한 날짜 패턴
        patterns = [
            r"(\d{4}[./-]\d{1,2}[./-]\d{1,2})\s*[~~-]\s*(\d{4}[./-]\d{1,2}[./-]\d{1,2})",
            r"(\d{4}[./-]\d{1,2}[./-]\d{1,2})\s*부터\s*(\d{4}[./-]\d{1,2}[./-]\d{1,2})까지",
            r"(\d{2}[./-]\d{1,2}[./-]\d{1,2})\s*[~~-]\s*(\d{2}[./-]\d{1,2}[./-]\d{1,2})",
        ]

        for pattern in patterns:
            match = re.search(pattern, period_text)
            if match:
                try:
                    start_str = match.group(1).replace(".", "-").replace("/", "-")
                    end_str = match.group(2).replace(".", "-").replace("/", "-")

                    # 연도가 2자리인 경우 처리
                    if len(start_str.split("-")[0]) == 2:
                        start_str = "20" + start_str
                    if len(end_str.split("-")[0]) == 2:
                        end_str = "20" + end_str

                    start_date = datetime.strptime(start_str, "%Y-%m-%d")
                    end_date = datetime.strptime(end_str, "%Y-%m-%d")
                    break
                except ValueError:
                    continue

        return start_date, end_date

    async def _crawl_with_playwright(self, url: str, selector: str) -> str:
        """Playwright를 사용한 동적 크롤링"""
        html = ""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=self.ua_rotator.get(),
                viewport={"width": 1920, "height": 1080},
                locale="ko-KR",
            )
            page = await context.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(random.uniform(2.0, 4.0))

                # 추가 콘텐츠 로딩 대기
                try:
                    await page.wait_for_selector(selector, timeout=10000)
                except Exception:
                    pass

                html = await page.content()
            except Exception as e:
                logger.error(f"[Popup] Playwright 크롤링 실패 {url}: {e}")
            finally:
                await browser.close()

        return html

    def collect(self) -> List[Dict[str, Any]]:
        """동기 수집"""
        all_events = []

        # 더현대 팝업
        logger.info("[Popup] 더현대 팝업스토어 수집")
        RandomDelay.sleep(2.0, 4.0)
        try:
            html = self._fetch_html("https://www.ehyundai.com/newPortal/EV/EV000001_V.do")
            events = self._parse_thehyundai(html)
            all_events.extend(events)
            logger.info(f"[Popup] 더현대: {len(events)}건")
        except Exception as e:
            logger.error(f"[Popup] 더현대 수집 실패: {e}")

        # 신세계 팝업
        logger.info("[Popup] 신세계 팝업스토어 수집")
        RandomDelay.sleep(2.0, 4.0)
        try:
            html = self._fetch_html("https://www.shinsegae.com/event/popupstore")
            events = self._parse_shinsegae(html)
            all_events.extend(events)
            logger.info(f"[Popup] 신세계: {len(events)}건")
        except Exception as e:
            logger.error(f"[Popup] 신세계 수집 실패: {e}")

        # 팝업 플랫폼
        logger.info("[Popup] 팝업 플랫폼 수집")
        RandomDelay.sleep(2.0, 4.0)
        try:
            html = self._fetch_html("https://www.popup-store.co.kr")  # 예시 URL
            events = self._parse_popup_platform(html)
            all_events.extend(events)
            logger.info(f"[Popup] 플랫폼: {len(events)}건")
        except Exception as e:
            logger.error(f"[Popup] 플랫폼 수집 실패: {e}")

        return [{"type": "event", "data": e} for e in all_events]

    async def collect_async(self) -> List[Dict[str, Any]]:
        """비동기 수집 (Playwright 활용)"""
        all_events = []

        urls = [
            ("https://www.ehyundai.com/newPortal/EV/EV000001_V.do", ".popup-store-item"),
            ("https://www.shinsegae.com/event/popupstore", ".event-item"),
            ("https://www.popup-store.co.kr", ".popup-card"),
        ]

        for url, selector in urls:
            await asyncio.sleep(random.uniform(2.0, 4.0))
            try:
                html = await self._crawl_with_playwright(url, selector)
                if "ehyundai" in url:
                    events = self._parse_thehyundai(html)
                elif "shinsegae" in url:
                    events = self._parse_shinsegae(html)
                else:
                    events = self._parse_popup_platform(html)

                all_events.extend(events)
                logger.info(f"[Popup] {url}: {len(events)}건")
            except Exception as e:
                logger.error(f"[Popup] 비동기 수집 실패 {url}: {e}")

        return [{"type": "event", "data": e} for e in all_events]

    def save(self, items: List[Dict[str, Any]]) -> None:
        """데이터베이스 저장"""
        with get_db() as db:
            for item in items:
                try:
                    data = item["data"]

                    existing = db.query(Event).filter(
                        Event.source == data["source"],
                        Event.title == data["title"],
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
                    logger.error(f"[Popup] 저장 오류: {e}")
                    continue
