"""
KOPIS 공연예술통합전산망 오픈API 수집기 v1.0
=============================================================================
[커플/싱글 테마 파이프라인 1단계: 원천 데이터 수집 — 세 번째 소스]

⚠️ 이 스크립트는 어떤 경우에도 git add / commit / push 를 실행하지 않는다.
   파일 생성·수정까지만 하고 멈춘다. 커밋 여부는 사람이 직접 결정한다.

무엇을 하는가
-----------------------------------------------------------------------------
KOPIS(예술경영지원센터 공연예술통합전산망) 오픈API 4종을 조합해
data/kopis_performances_raw.csv 를 만든다. 스키마는 total_family_data.csv 와
동일한 14개 컬럼이다.

  1) 공연목록   /openApi/restful/pblprfr          → 기간 내 공연 ID 목록
  2) 공연상세   /openApi/restful/pblprfr/{mt20id} → 가격·연령·출연진·예매처
  3) 시설상세   /openApi/restful/prfplc/{mt10id}  → ★위경도·주소·편의시설
  4) 예매상황판 /openApi/restful/boxoffice        → 실제 예매 기반 순위

이 소스가 메우는 구멍 (분석.md 대비)
-----------------------------------------------------------------------------
- 좌표: 시설상세가 la/lo 를 직접 준다. 카카오 지오코딩 불필요.
        venue_geocode_cache.json 이 공연장 65% 만 맞추던 문제를 대체한다.
- fee_info: 공연상세의 pcseguidance(티켓가격). 현재 전체 1.1% 인 항목.
- popularity_score: 예매상황판은 실제 예매/취소 집계 기반 순위다.
        난수로 채웠다가 걷어낸 그 자리에 넣을 수 있는 첫 실측 근거.
- 편의시설: 시설상세가 주차/카페/식당/엘리베이터에 더해 suyu(수유실),
        nolibang(놀이방)까지 준다. 네이버 어휘에 없어 보류했던 항목이다.

무엇을 하지 않는가 (중요)
-----------------------------------------------------------------------------
1. 없는 값을 지어내지 않는다.
   - fee_info 는 pcseguidance 가 있을 때만 채우고 없으면 공란으로 둔다.
   - congestion_score 는 이 API 에 측정값이 없으므로 전 건 공란이다.
   - popularity_score 는 예매상황판에 오른 공연만 채운다. 나머지는 공란이다.
     (순위에 없다 = 인기가 없다 가 아니라 = 근거가 없다)
   - description 은 원본 줄거리(sty)를 쓰고, 없으면 장르·공연장 사실만 적는다.
     홍보 문구를 생성하지 않는다.
2. couple/single 점수를 매기지 않는다.
   장르·관람연령·아동공연여부 같은 '사실'만 ai_tags/theme_tags 에 남긴다.
   테마 배분은 2단계 통합기(generate_total_*.py)가 전체 소스를 보고 정한다.
   여기서 점수를 박으면 소스마다 다른 척도가 섞여 비교가 깨진다.
3. 장르코드(shcate)·지역코드(signgucode)로 서버 필터링을 하지 않는다.
   코드표(kopis_openapi_code_v3.7)를 확보하기 전에 코드를 추측하면 조용히
   빈 결과가 나온다. 전량 받아서 응답의 genrenm/area 로 로컬 필터링한다.
   코드표를 확보하면 SETTINGS 의 shcate/signgucode 를 채워 서버 필터로
   전환할 수 있다(호출수 절약).

API 키
-----------------------------------------------------------------------------
아래 둘 중 하나. 환경변수가 우선한다.
  (권장) 환경변수  KOPIS_API_KEY
  (기존 관행) scripts/config.json → {"api_keys": {"kopis_api_key": "..."}}

호출량 주의
-----------------------------------------------------------------------------
KOPIS 는 일일 호출 한도가 있다(신청 등급에 따라 다름). 공연 1건당 상세 1회가
들기 때문에 기간을 넓게 잡으면 금방 소진된다. 그래서
  - 기본 수집 범위를 '오늘 ~ +60일'(진행중·예정)로 잡았다. 종료된 공연은
    추천 서비스에 쓸모가 없다.
  - max_requests 예산을 두고 초과하면 그때까지 모은 것을 저장하고 멈춘다.
  - 캐시에 원본 응답(detail_raw)과 가공된 row 를 함께 저장하고 row_v 를
    붙였다. 매핑 로직만 바꾸면 재요청 없이 로컬에서 row 를 다시 만든다.
    (popup_collector.py 와 같은 패턴)

재실행 / 캐시
-----------------------------------------------------------------------------
  python kopis_performance_collector.py            # 증분 수집
  python kopis_performance_collector.py --full     # 캐시 무시하고 전량 재수집

매핑 로직(build_* 함수)을 고쳤으면 ROW_SCHEMA_VERSION 을 올릴 것.
그래야 캐시에서 row 가 자동 재생성된다.
"""

import sys
import io
import os
import re
import csv
import json
import time
import argparse
from datetime import datetime, timedelta, date
from xml.etree import ElementTree as ET

import requests

if hasattr(sys.stdout, "detach"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding="utf-8", line_buffering=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
OUTPUT_CSV = os.path.join(DATA_DIR, "kopis_performances_raw.csv")
CACHE_FILE = os.path.join(DATA_DIR, "kopis_collect_cache.json")
VENUE_CACHE_FILE = os.path.join(DATA_DIR, "kopis_venue_cache.json")

API_ROOT = "http://www.kopis.or.kr/openApi/restful"

# ── 스키마 버전 ──────────────────────────────────────────────────────────
#   ROW_SCHEMA_VERSION  : row 를 만드는 매핑 로직의 버전.
#                         build_* 를 고치면 반드시 올릴 것.
#   FETCH_SCHEMA_VERSION: 무엇을 어떻게 가져오는지의 버전.
#                         새 필드를 받기 시작하면 올릴 것(재요청 유발).
ROW_SCHEMA_VERSION = 1
FETCH_SCHEMA_VERSION = 1

CSV_FIELDS = [
    "source_site", "category", "place_or_event_name", "period", "target_age",
    "region", "fee_info", "description", "booking_url", "ai_tags",
    "crawled_at", "theme_tags", "congestion_score", "popularity_score",
]

# ── 설정 (config.json 의 kopis_collector_settings 섹션에서 덮어쓸 수 있음) ──
DEFAULT_SETTINGS = {
    "request_interval_sec": 0.3,   # 요청 사이 최소 대기
    "max_retry": 3,
    "backoff_base_sec": 2.0,
    "timeout_sec": 15,
    "rows_per_page": 100,          # 문서상 최대 100
    "days_ahead": 60,              # 오늘 +N일 까지의 공연을 수집
    "days_back": 0,                # 오늘 -N일. 진행중 공연을 놓치지 않으려면 0 이상
    "max_requests": 3000,          # 일일 한도 보호. 초과 시 저장 후 중단
    "boxoffice_days": 7,           # 예매상황판 최근 N일 집계
    "areas_allow": [],             # 예: ["서울","경기","인천"]. 비우면 전국
    "shcate": "",                  # 장르코드. 코드표 확보 후에만 채울 것
    "signgucode": "",              # 지역(시도)코드. 코드표 확보 후에만 채울 것
    "description_max_chars": 300,
    "user_agent": (
        "ABCchallenges-WeekendData-Bot/1.0 "
        "(+internal weekend-data pipeline; contact: set-your-email-here)"
    ),
}

_CFG_PATH = os.path.join(BASE_DIR, "config.json")
CONFIG = {}
if os.path.exists(_CFG_PATH):
    try:
        with open(_CFG_PATH, "r", encoding="utf-8") as f:
            CONFIG = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        # config.json 이 깨졌으면 조용히 넘어가지 않는다. 기본값으로 돌되 알린다.
        print(f"⚠️ config.json 을 읽지 못했습니다({e}). 기본 설정으로 진행합니다.")

SETTINGS = dict(DEFAULT_SETTINGS)
SETTINGS.update(CONFIG.get("kopis_collector_settings", {}) or {})

API_KEY = (
    os.environ.get("KOPIS_API_KEY")
    or CONFIG.get("api_keys", {}).get("kopis_api_key", "")
).strip()

HTTP_HEADERS = {"User-Agent": SETTINGS["user_agent"]}

# ── 장르 → 테마 그룹 ─────────────────────────────────────────────────────
# genrenm 은 응답에 한글로 그대로 온다. category 에는 원본 장르명을 넣어
# 정보 손실을 만들지 않고, 묶음은 theme_tags 로 따로 부착한다.
GENRE_GROUP = {
    "연극": "theater",
    "뮤지컬": "musical",
    "서양음악(클래식)": "classical",
    "클래식": "classical",
    "한국음악(국악)": "traditional",
    "국악": "traditional",
    "대중음악": "popmusic",
    "무용": "dance",
    "무용(서양/한국무용)": "dance",
    "대중무용": "dance",
    "서커스/마술": "circus",
    "복합": "mixed",
    "아동": "kids",
}

# ── 시도명 정규화 ────────────────────────────────────────────────────────
# 세 수집기(팝업/VisitKorea/KOPIS)의 표기를 맞춘다. 팝업 v1.2 규칙과 동일.
# ⚠️ 2026-07-01 광주광역시와 전라남도가 '전남광주통합특별시'로 통합됐다.
#    주소 표기는 '전남광주통합특별시 동구' 형태이므로 별도 항목으로 둔다.
SIDO_NORMALIZE = {
    "서울특별시": "서울", "서울시": "서울",
    "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
    "대전광역시": "대전", "울산광역시": "울산",
    "세종특별자치시": "세종", "세종시": "세종",
    "경기도": "경기",
    "강원특별자치도": "강원", "강원도": "강원",
    "충청북도": "충북", "충청남도": "충남",
    "전북특별자치도": "전북", "전라북도": "전북",
    "경상북도": "경북", "경상남도": "경남",
    "제주특별자치도": "제주", "제주도": "제주",
    "전남광주통합특별시": "전남광주",
    "광주광역시": "전남광주", "전라남도": "전남광주",
}

_request_count = 0
_budget_exhausted = False


# ═══════════════════════════════════════════════════════════════════════
# HTTP
# ═══════════════════════════════════════════════════════════════════════

def polite_get(path: str, params: dict):
    """
    KOPIS 는 XML 만 반환한다. 성공하면 파싱된 Element 를, 실패하면 None 을
    돌려준다. 예산을 초과하면 더 이상 요청하지 않는다.

    실패를 조용히 삼키지 않는다 — 어떤 요청이 왜 실패했는지 항상 출력한다.
    """
    global _request_count, _budget_exhausted

    if _budget_exhausted:
        return None
    if _request_count >= SETTINGS["max_requests"]:
        _budget_exhausted = True
        print(f"\n⚠️ 요청 예산 {SETTINGS['max_requests']}회를 모두 썼습니다. "
              f"여기까지 모은 것을 저장하고 멈춥니다.")
        return None

    url = f"{API_ROOT}/{path}"
    q = dict(params)
    q["service"] = API_KEY

    last_err = None
    for attempt in range(1, SETTINGS["max_retry"] + 1):
        try:
            _request_count += 1
            resp = requests.get(url, params=q, headers=HTTP_HEADERS,
                                timeout=SETTINGS["timeout_sec"])
            time.sleep(SETTINGS["request_interval_sec"])

            if resp.status_code != 200:
                last_err = f"HTTP {resp.status_code}"
                # 인증 실패는 재시도해도 소용없다. 즉시 알리고 중단한다.
                if resp.status_code in (401, 403):
                    print(f"   ❌ 인증 실패({resp.status_code}). 서비스키를 확인하세요.")
                    return None
            else:
                text = resp.text.strip()
                try:
                    root = ET.fromstring(text)
                except ET.ParseError as e:
                    last_err = f"XML 파싱 실패: {e} / 응답 앞부분={text[:160]!r}"
                else:
                    # KOPIS 는 오류도 200 + XML 로 주는 경우가 있다.
                    err = root.findtext("returnReasonCode") or root.findtext("errmsg")
                    if err:
                        print(f"   ❌ API 오류 응답: {err} (path={path})")
                        return None
                    return root
        except requests.RequestException as e:
            last_err = repr(e)

        if attempt < SETTINGS["max_retry"]:
            wait = SETTINGS["backoff_base_sec"] * attempt
            print(f"   ↻ 재시도 {attempt}/{SETTINGS['max_retry'] - 1} "
                  f"({last_err}) — {wait:.1f}초 대기")
            time.sleep(wait)

    print(f"   ❌ 요청 실패: {path} params={ {k: v for k, v in params.items()} } / {last_err}")
    return None


def el_text(node, tag, default=""):
    if node is None:
        return default
    v = node.findtext(tag)
    return (v or default).strip()


# ═══════════════════════════════════════════════════════════════════════
# 1) 공연목록
# ═══════════════════════════════════════════════════════════════════════

def iter_date_windows(start: date, end: date, max_days: int = 31):
    """문서상 stdate~eddate 는 최대 31일이라 창을 쪼갠다."""
    cur = start
    while cur <= end:
        stop = min(cur + timedelta(days=max_days - 1), end)
        yield cur, stop
        cur = stop + timedelta(days=1)


def fetch_performance_list(start: date, end: date):
    """
    기간 내 공연 목록을 전부 모은다.
    반환: { mt20id: {prfnm, prfpdfrom, prfpdto, fcltynm, poster, area,
                     genrenm, openrun, prfstate} }
    """
    found = {}
    rows_per_page = SETTINGS["rows_per_page"]

    for w_start, w_end in iter_date_windows(start, end):
        page = 1
        while True:
            params = {
                "stdate": w_start.strftime("%Y%m%d"),
                "eddate": w_end.strftime("%Y%m%d"),
                "cpage": page,
                "rows": rows_per_page,
            }
            if SETTINGS["shcate"]:
                params["shcate"] = SETTINGS["shcate"]
            if SETTINGS["signgucode"]:
                params["signgucode"] = SETTINGS["signgucode"]

            root = polite_get("pblprfr", params)
            if root is None:
                return found

            items = root.findall("db")
            for db in items:
                mt20id = el_text(db, "mt20id")
                if not mt20id:
                    continue
                found[mt20id] = {
                    "prfnm": el_text(db, "prfnm"),
                    "prfpdfrom": el_text(db, "prfpdfrom"),
                    "prfpdto": el_text(db, "prfpdto"),
                    "fcltynm": el_text(db, "fcltynm"),
                    "poster": el_text(db, "poster"),
                    "area": el_text(db, "area"),
                    "genrenm": el_text(db, "genrenm"),
                    "openrun": el_text(db, "openrun"),
                    "prfstate": el_text(db, "prfstate"),
                }

            print(f"  [목록] {w_start}~{w_end} p{page}: {len(items)}건 "
                  f"(누적 {len(found)})")

            if len(items) < rows_per_page:
                break
            page += 1

    return found


# ═══════════════════════════════════════════════════════════════════════
# 2) 공연 상세 / 3) 시설 상세
# ═══════════════════════════════════════════════════════════════════════

DETAIL_FIELDS = [
    "mt20id", "prfnm", "mt10id", "mt13id", "fcltynm", "prfpdfrom", "prfpdto",
    "prfcast", "prfcrew", "prfruntime", "prfage", "entrpsnm", "pcseguidance",
    "poster", "sty", "area", "genrenm", "openrun", "visit", "child",
    "daehakro", "festival", "updatedate", "prfstate", "dtguidance",
]


def fetch_performance_detail(mt20id: str):
    root = polite_get(f"pblprfr/{mt20id}", {})
    if root is None:
        return None
    db = root.find("db")
    if db is None:
        return None

    d = {k: el_text(db, k) for k in DETAIL_FIELDS}

    # 예매처 목록 — relates/relate 구조 또는 relatenm/relateurl 평면 구조
    booking = []
    relates = db.find("relates")
    if relates is not None:
        for rel in relates.findall("relate"):
            nm = el_text(rel, "relatenm")
            url = el_text(rel, "relateurl")
            if url:
                booking.append({"name": nm, "url": url})
        if not booking:
            names = [e.text for e in relates.findall("relatenm") if e.text]
            urls = [e.text for e in relates.findall("relateurl") if e.text]
            for i, url in enumerate(urls):
                booking.append({"name": names[i] if i < len(names) else "", "url": url})
    d["_booking"] = booking
    return d


VENUE_FIELDS = [
    "mt10id", "fcltynm", "mt13cnt", "fcltychartr", "opende", "seatscale",
    "telno", "relateurl", "adres", "la", "lo",
    "restaurant", "cafe", "store", "nolibang", "suyu",
    "parkbarrier", "restbarrier", "runwbarrier", "elevbarrier", "parkinglot",
]


def fetch_venue_detail(mt10id: str):
    """공연시설 상세 — 위경도와 편의시설이 여기서 나온다."""
    root = polite_get(f"prfplc/{mt10id}", {})
    if root is None:
        return None
    db = root.find("db")
    if db is None:
        return None
    return {k: el_text(db, k) for k in VENUE_FIELDS}


# ═══════════════════════════════════════════════════════════════════════
# 4) 예매상황판 — popularity 의 근거
# ═══════════════════════════════════════════════════════════════════════

def fetch_boxoffice(days: int):
    """
    최근 N일 예매상황판. 반환: { mt20id: rank }
    같은 공연이 여러 날 오르면 가장 좋은(작은) 순위를 남긴다.
    """
    end = date.today()
    start = end - timedelta(days=max(days - 1, 0))
    ranks = {}

    root = polite_get("boxoffice", {
        "stdate": start.strftime("%Y%m%d"),
        "eddate": end.strftime("%Y%m%d"),
    })
    if root is None:
        print("  [예매상황판] 조회 실패 — popularity_score 는 전 건 공란으로 둡니다.")
        return ranks

    for boxof in root.iter("boxof"):
        mt20id = el_text(boxof, "mt20id")
        rnum = el_text(boxof, "rnum")
        if not mt20id or not rnum.isdigit():
            continue
        r = int(rnum)
        if mt20id not in ranks or r < ranks[mt20id]:
            ranks[mt20id] = r

    print(f"  [예매상황판] {start}~{end}: {len(ranks)}건 순위 확보")
    return ranks


# ═══════════════════════════════════════════════════════════════════════
# 매핑 — 여기를 고치면 ROW_SCHEMA_VERSION 을 올릴 것
# ═══════════════════════════════════════════════════════════════════════

def to_iso_date(s: str) -> str:
    """'2021.08.21' → '2021-08-21'. 형식이 다르면 원본을 그대로 돌려준다."""
    s = (s or "").strip()
    m = re.match(r"^(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})$", s)
    if not m:
        return s
    y, mo, d = m.groups()
    return f"{y}-{int(mo):02d}-{int(d):02d}"


def normalize_sido(addr: str) -> str:
    """주소 앞머리의 시도명을 짧은 표기로 통일한다."""
    addr = (addr or "").strip()
    if not addr:
        return ""
    head = addr.split()[0]
    short = SIDO_NORMALIZE.get(head)
    if short:
        return (short + addr[len(head):]).strip()
    return addr


def strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"&[a-zA-Z]+;|&#\d+;", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def sanitize(v: str) -> str:
    """
    ai_tags/theme_tags 의 구분자(; :)가 값에 섞이면 파싱이 깨진다.
    다만 콜론을 그냥 지우면 공연시간 '20:00' 이 '20 00' 이 되어 못 읽는다.
    → 세미콜론은 쉼표로, 콜론은 전각 콜론(：)으로 바꿔 의미를 보존한다.
      전각 콜론은 구분자로 쓰이지 않으므로 파싱에 영향이 없다.
    """
    s = str(v or "")
    s = s.replace(";", ",").replace(":", "：")
    return re.sub(r"\s+", " ", s).strip()


def build_period(detail: dict) -> str:
    s = to_iso_date(detail.get("prfpdfrom", ""))
    e = to_iso_date(detail.get("prfpdto", ""))
    if s and e:
        return f"{s} ~ {e}"
    return s or e or ""


def build_region(detail: dict, venue: dict) -> str:
    """
    '서울 송파구 올림픽로 424 | 위도:37.52112, 경도:127.128363'
    좌표가 없으면 좌표 부분을 붙이지 않는다(가짜 좌표를 만들지 않는다).
    """
    if not venue:
        # 시설 조회에 실패했으면 목록의 area 라도 남긴다.
        return normalize_sido(detail.get("area", ""))

    addr = normalize_sido(venue.get("adres", "")) or normalize_sido(detail.get("area", ""))
    la, lo = venue.get("la", ""), venue.get("lo", "")
    try:
        la_f, lo_f = float(la), float(lo)
    except (TypeError, ValueError):
        return addr
    # 한반도 범위를 벗어난 좌표는 버린다(원본 오류 방어)
    if not (33.0 <= la_f <= 39.5 and 124.0 <= lo_f <= 132.0):
        return addr
    return f"{addr} | 위도:{la_f}, 경도:{lo_f}"


def build_description(detail: dict, venue: dict) -> str:
    """
    원본 줄거리(sty)를 쓴다. 없으면 사실만 조합한다.
    홍보 문구를 생성하지 않는다.
    """
    sty = strip_html(detail.get("sty", ""))
    if sty:
        limit = SETTINGS["description_max_chars"]
        return sty[:limit] + ("…" if len(sty) > limit else "")

    parts = []
    if detail.get("genrenm"):
        parts.append(detail["genrenm"])
    fclty = detail.get("fcltynm") or (venue or {}).get("fcltynm", "")
    if fclty:
        parts.append(fclty)
    if detail.get("prfruntime"):
        parts.append(f"러닝타임 {detail['prfruntime']}")
    return " · ".join(parts)


def build_fee_info(detail: dict) -> str:
    """티켓가격이 있을 때만 채운다. 없으면 공란."""
    return strip_html(detail.get("pcseguidance", ""))


def build_booking_url(detail: dict) -> str:
    """예매처가 있으면 첫 번째, 없으면 KOPIS 상세 페이지."""
    for b in detail.get("_booking", []):
        if b.get("url", "").startswith("http"):
            return b["url"]
    return f"http://www.kopis.or.kr/por/db/pblprfr/pblprfrView.do?mt20id={detail.get('mt20id','')}"


def build_target_age(detail: dict) -> str:
    """원본 관람연령(prfage)을 그대로 쓴다. 추정하지 않는다."""
    return detail.get("prfage", "")


def build_ai_tags(detail: dict, venue: dict, rank) -> str:
    tags = []
    for key, val in (
        ("genre", detail.get("genrenm")),
        ("venue", detail.get("fcltynm") or (venue or {}).get("fcltynm")),
        ("runtime", detail.get("prfruntime")),
        ("cast", detail.get("prfcast")),
        ("producer", detail.get("entrpsnm")),
        ("state", detail.get("prfstate")),
        ("showtime", strip_html(detail.get("dtguidance", ""))),
    ):
        if val:
            tags.append(f"{key}={sanitize(val)}")

    # Y/N 플래그 — 사실 그대로
    for key, val in (
        ("openrun", detail.get("openrun")),
        ("visit_show", detail.get("visit")),
        ("child_show", detail.get("child")),
        ("daehakro", detail.get("daehakro")),
        ("festival", detail.get("festival")),
    ):
        if val == "Y":
            tags.append(f"{key}:1.0")

    if venue:
        if venue.get("seatscale"):
            tags.append(f"seats={sanitize(venue['seatscale'])}")
        if venue.get("telno"):
            tags.append(f"tel={sanitize(venue['telno'])}")
        # 편의시설 — 네이버로는 못 얻던 항목이 여기 있다
        amenity = {
            "parkinglot": "parking", "cafe": "cafe", "restaurant": "restaurant",
            "store": "store", "nolibang": "playroom", "suyu": "nursing_room",
            "elevbarrier": "elevator", "parkbarrier": "barrier_free_parking",
            "restbarrier": "barrier_free_restroom", "runwbarrier": "ramp",
        }
        for src, out in amenity.items():
            if venue.get(src) == "Y":
                tags.append(f"{out}:1.0")

    if rank:
        tags.append(f"boxoffice_rank:{rank}")

    tags.append(f"verified_at={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return ";".join(tags)


def build_theme_tags(detail: dict, venue: dict) -> str:
    tags = []
    group = GENRE_GROUP.get((detail.get("genrenm") or "").strip())
    if group:
        tags.append(f"{group}:1.0")
    tags.append("performance:1.0")
    # 공연장은 실내다. 야외공연장 여부는 시설 상세의 무대시설로만 알 수 있어
    # 여기서는 단정하지 않고 공연시설이라는 사실만 남긴다.
    tags.append("indoor:1.0")
    if detail.get("festival") == "Y":
        tags.append("festival:1.0")
    if detail.get("child") == "Y":
        tags.append("kids:1.0")
    if detail.get("daehakro") == "Y":
        tags.append("daehakro:1.0")
    if venue and venue.get("fcltychartr"):
        tags.append(f"{sanitize(venue['fcltychartr'])}:1.0")
    return ";".join(tags)


def detail_to_row(detail: dict, venue: dict, rank, crawled_at: str) -> dict:
    return {
        "source_site": f"KOPIS 공연예술통합전산망 | {detail.get('genrenm', '')}".strip(" |"),
        "category": detail.get("genrenm", "") or "공연",
        "place_or_event_name": detail.get("prfnm", ""),
        "period": build_period(detail),
        "target_age": build_target_age(detail),
        "region": build_region(detail, venue),
        "fee_info": build_fee_info(detail),
        "description": build_description(detail, venue),
        "booking_url": build_booking_url(detail),
        "ai_tags": build_ai_tags(detail, venue, rank),
        "crawled_at": crawled_at,
        "theme_tags": build_theme_tags(detail, venue),
        "congestion_score": "",   # 이 API 에 측정값 없음 — 지어내지 않는다
        "popularity_score": "",   # 아래 apply_popularity() 에서 순위 있는 건만 채움
    }


def apply_popularity(rows, ranks):
    """
    예매상황판에 오른 공연만 popularity_score 를 채운다.
    값은 '순위의 백분위'다 — 1위가 100, 꼴찌가 가장 낮다.
    ⚠️ 이 점수는 KOPIS 예매상황판 안에서만 비교 가능하다. 다른 소스의
       popularity 와 같은 축에 세우려면 통합 단계에서 소스별로 다시
       정규화해야 한다.
    """
    if not ranks:
        return 0
    worst = max(ranks.values())
    filled = 0
    for row in rows:
        m = re.search(r"boxoffice_rank:(\d+)", row["ai_tags"])
        if not m:
            continue
        r = int(m.group(1))
        score = 100.0 if worst <= 1 else round(100.0 * (worst - r) / (worst - 1), 1)
        row["popularity_score"] = score
        filled += 1
    return filled


# ═══════════════════════════════════════════════════════════════════════
# 캐시
# ═══════════════════════════════════════════════════════════════════════

def load_json(path, label):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️ {label} 캐시를 읽지 못했습니다({e}). 캐시 없이 진행합니다.")
        return {}


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ═══════════════════════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════════════════════

def collect(full: bool = False):
    if not API_KEY:
        print("=" * 75)
        print("❌ KOPIS 서비스키가 없습니다.")
        print("   아래 둘 중 하나로 넣어주세요 (환경변수가 우선합니다):")
        print()
        print("   1) 환경변수 (권장)")
        print("      Windows PowerShell : $env:KOPIS_API_KEY=\"발급받은키\"")
        print("      macOS / Linux      : export KOPIS_API_KEY=\"발급받은키\"")
        print()
        print("   2) scripts/config.json")
        print('      { "api_keys": { "kopis_api_key": "발급받은키" } }')
        print("=" * 75)
        return

    os.makedirs(DATA_DIR, exist_ok=True)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    start = date.today() - timedelta(days=SETTINGS["days_back"])
    end = date.today() + timedelta(days=SETTINGS["days_ahead"])

    print("=" * 75)
    print(f"KOPIS 공연 수집 시작 — {start} ~ {end}"
          f"{' (전량 재수집)' if full else ''}")
    print(f"요청 예산: {SETTINGS['max_requests']}회")
    print("=" * 75)

    cache = {} if full else load_json(CACHE_FILE, "공연")
    venue_cache = load_json(VENUE_CACHE_FILE, "공연시설")

    # ── 1단계: 목록 ──────────────────────────────────────────────
    print("\n[1/4] 공연 목록 조회")
    listing = fetch_performance_list(start, end)
    if not listing:
        print("\n❌ 목록을 한 건도 받지 못했습니다. "
              "기존 CSV 를 덮어쓰지 않고 종료합니다.")
        return
    print(f"  → 총 {len(listing)}건")

    # ── 2단계: 상세 (캐시 우선) ──────────────────────────────────
    print("\n[2/4] 공연 상세 조회")
    details, reused, regenerated, failed = {}, 0, 0, []

    for i, mt20id in enumerate(listing, 1):
        cached = cache.get(mt20id)
        if (cached and isinstance(cached, dict)
                and cached.get("fetch_v") == FETCH_SCHEMA_VERSION
                and cached.get("detail")):
            details[mt20id] = cached["detail"]
            reused += 1
            continue

        d = fetch_performance_detail(mt20id)
        if d is None:
            failed.append(mt20id)
            if _budget_exhausted:
                break
            continue
        details[mt20id] = d
        cache[mt20id] = {"fetch_v": FETCH_SCHEMA_VERSION, "detail": d}

        if i % 50 == 0:
            print(f"  [진행] {i}/{len(listing)} (캐시 {reused}, 실패 {len(failed)})")
            save_json(CACHE_FILE, cache)

    save_json(CACHE_FILE, cache)
    print(f"  → 상세 확보 {len(details)}건 "
          f"(캐시 재사용 {reused}, 신규 {len(details) - reused}, 실패 {len(failed)})")

    # ── 3단계: 시설 상세 (좌표·편의시설) ─────────────────────────
    print("\n[3/4] 공연시설 상세 조회 (위경도·편의시설)")
    venue_ids = {d.get("mt10id") for d in details.values() if d.get("mt10id")}
    print(f"  → 고유 시설 {len(venue_ids)}곳")

    for j, mt10id in enumerate(sorted(venue_ids), 1):
        if mt10id in venue_cache and not full:
            continue
        v = fetch_venue_detail(mt10id)
        if v:
            venue_cache[mt10id] = v
        if _budget_exhausted:
            break
        if j % 50 == 0:
            print(f"  [진행] {j}/{len(venue_ids)}")
            save_json(VENUE_CACHE_FILE, venue_cache)

    save_json(VENUE_CACHE_FILE, venue_cache)
    with_coord = sum(1 for v in venue_cache.values() if v.get("la") and v.get("lo"))
    print(f"  → 시설 정보 {len(venue_cache)}곳 (좌표 보유 {with_coord}곳)")

    # ── 4단계: 예매상황판 ────────────────────────────────────────
    print("\n[4/4] 예매상황판 조회")
    ranks = fetch_boxoffice(SETTINGS["boxoffice_days"])

    # ── 행 생성 ──────────────────────────────────────────────────
    allow = set(SETTINGS.get("areas_allow") or [])
    rows, skipped_area = [], 0

    for mt20id, d in details.items():
        venue = venue_cache.get(d.get("mt10id", ""), {})
        row = detail_to_row(d, venue, ranks.get(mt20id), now_str)

        if allow:
            head = (row["region"] or "").split()[0] if row["region"] else ""
            if head not in allow:
                skipped_area += 1
                continue
        rows.append(row)

    filled_pop = apply_popularity(rows, ranks)

    if not rows:
        print("\n❌ 저장할 행이 없습니다. 기존 CSV 를 덮어쓰지 않고 종료합니다.")
        return

    tmp = OUTPUT_CSV + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, OUTPUT_CSV)

    # ── 요약 ─────────────────────────────────────────────────────
    coord = sum(1 for r in rows if "위도:" in r["region"])
    fee = sum(1 for r in rows if r["fee_info"].strip())
    nursing = sum(1 for r in rows if "nursing_room:1.0" in r["ai_tags"])

    print("\n" + "=" * 75)
    print(f"✅ 저장 완료: {OUTPUT_CSV}")
    print(f"   총 {len(rows)}건" + (f" (지역 필터로 제외 {skipped_area}건)" if skipped_area else ""))
    print(f"   좌표 확보         {coord}건 ({coord / len(rows) * 100:.1f}%)")
    print(f"   티켓가격(fee_info) {fee}건 ({fee / len(rows) * 100:.1f}%)")
    print(f"   예매순위 기반 인기  {filled_pop}건")
    print(f"   수유실 보유 공연장  {nursing}건")
    print(f"   사용한 요청 수     {_request_count}회")
    if failed:
        print(f"   ⚠️ 상세 조회 실패 {len(failed)}건 (최대 20개): {failed[:20]}")
    if _budget_exhausted:
        print("   ⚠️ 요청 예산 소진으로 중간에 멈췄습니다. 다시 실행하면 "
              "캐시 덕분에 이어서 받습니다.")
    print("=" * 75)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="KOPIS 공연 데이터 수집기")
    ap.add_argument("--full", action="store_true",
                    help="캐시를 무시하고 전량 재수집")
    args = ap.parse_args()
    collect(full=args.full)
