"""
공통 유틸리티 함수
"""
import random
import time
import re
from typing import Dict, Any, Optional, List
from datetime import datetime

from fake_useragent import UserAgent


class RandomDelay:
    """랜덤 지연 유틸리티"""

    @staticmethod
    def sleep(min_sec: float = 1.5, max_sec: float = 4.0):
        """랜덤 시간 대기"""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    @staticmethod
    def get_delay(min_sec: float = 1.5, max_sec: float = 4.0) -> float:
        """랜덤 지연 시간 반환 (비동기용)"""
        return random.uniform(min_sec, max_sec)


class UserAgentRotator:
    """User-Agent 회전기"""

    def __init__(self):
        try:
            self.ua = UserAgent(fallback="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0")
        except Exception:
            self.ua = None

    def get(self) -> str:
        """랜덤 User-Agent 반환"""
        if self.ua:
            try:
                return self.ua.random
            except Exception:
                pass
        return random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        ])


def get_default_headers() -> Dict[str, str]:
    """기본 HTTP 헤더"""
    ua_rotator = UserAgentRotator()
    return {
        "User-Agent": ua_rotator.get(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
    }


def normalize_address(address: Optional[str]) -> Optional[str]:
    """주소 정규화"""
    if not address:
        return None
    address = address.strip()
    address = re.sub(r"\s+", " ", address)
    return address


def extract_region(address: Optional[str]) -> Optional[str]:
    """주소에서 지역(시/도) 추출"""
    if not address:
        return None
    patterns = [
        r"^(서울|부산|대구|인천|광주|대전|울산|세종)",
        r"^(경기|강원|충청북도|충청남도|전라북도|전라남도|경상북도|경상남도|제주)",
    ]
    for pattern in patterns:
        match = re.search(pattern, address)
        if match:
            return match.group(1)
    return None


def extract_district(address: Optional[str]) -> Optional[str]:
    """주소에서 구/군 추출"""
    if not address:
        return None
    match = re.search(r"(\S+구|\S+군|\S+시)", address)
    return match.group(1) if match else None


def assign_tags(
    name: str,
    category: Optional[str],
    description: Optional[str]
) -> Dict[str, Any]:
    """장소 데이터에 태그 및 타겟 속성 자동 부여"""
    text = f"{name or ''} {category or ''} {description or ''}"
    text_lower = text.lower()

    tags = []
    target_audience = []

    # 가족용 태그
    family_keywords = ["키즈", "아이", "유아", "어린이", "가족", "패밀리", "키즈카페", "놀이터", "동물원", "수족관", "아쿠아리움", "테마파크", "놀이공원"]
    if any(kw in text for kw in family_keywords):
        tags.append("가족용")
        target_audience.append("가족")

    # 커플용 태그
    couple_keywords = ["데이트", "커플", "로맨틱", "야경", "분위기", "와인", "캔들"]
    if any(kw in text for kw in couple_keywords):
        tags.append("커플용")
        target_audience.append("커플")

    # 싱글용 태그
    single_keywords = ["혼밥", "혼술", "혼자", "1인", "싱글", "독서", "카공"]
    if any(kw in text for kw in single_keywords):
        tags.append("싱글용")
        target_audience.append("싱글")

    # 유모차/육아 관련
    baby_keywords = ["유모차", "수유실", "기저귀", "아기", "영유아", "키즈존", "노키즈존"]
    if any(kw in text for kw in baby_keywords):
        if "노키즈존" in text:
            tags.append("노키즈존")
        else:
            tags.append("유모차가능")
            target_audience.append("육아가족")

    # 주차 관련
    parking_keywords = ["주차장", "주차가능", "무료주차", "발렛"]
    if any(kw in text for kw in parking_keywords):
        tags.append("주차가능")

    # 반려동물
    pet_keywords = ["반려동물", "애견", "펫", "dog", "cat"]
    if any(kw in text_lower for kw in pet_keywords):
        tags.append("반려동물동반")

    # 야외/실내
    outdoor_keywords = ["공원", "산책", "캠핑", "피크닉", "야외", "정원", "호수"]
    indoor_keywords = ["실내", "박물관", "미술관", "전시", "쇼핑몰", "백화점"]
    if any(kw in text for kw in outdoor_keywords):
        tags.append("야외")
    elif any(kw in text for kw in indoor_keywords):
        tags.append("실내")

    # 타겟 기본값
    if not target_audience:
        target_audience.append("전연령")

    return {
        "tags": list(set(tags)),
        "target_audience": list(set(target_audience)),
    }


def deduplicate_places(places: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """위도/경도 + 이름 기준 중복 제거"""
    seen = set()
    unique = []

    for place in places:
        lat = place.get("latitude")
        lng = place.get("longitude")
        name = place.get("name", "")

        # 위경도가 있으면 반올림해서 키 생성
        if lat is not None and lng is not None:
            key = (round(lat, 4), round(lng, 4), name.strip())
        else:
            key = (name.strip(),)

        if key not in seen:
            seen.add(key)
            unique.append(place)

    return unique
