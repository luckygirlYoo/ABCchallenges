"""
커플 통합 데이터 생성기 v1.0
=============================================================================
[커플 테마 파이프라인 2단계: 원천 통합]

⚠️ 이 스크립트는 어떤 경우에도 git add / commit / push 를 실행하지 않는다.
⚠️ 원천 CSV 를 읽기만 한다. 어떤 기존 파일도 수정·삭제하지 않는다.
   출력은 data/total_couple_data.csv 하나뿐이다.

무엇을 하는가
-----------------------------------------------------------------------------
6개 원천을 하나로 합쳐 커플 탭용 데이터셋을 만든다.

  [통일 스키마 3종 — 그대로 적재]
    popup_couple_events_raw.csv      팝가 팝업스토어
    visitkorea_couple_spots_raw.csv  대한민국 구석구석 커플/데이트 태그
    kopis_performances_raw.csv       KOPIS 공연

  [고유 스키마 3종 — 어댑터로 14컬럼 변환]
    live_ticketlink_tickets.csv      티켓링크 공연/전시
    live_interpark_tickets.csv       인터파크 공연/전시
    culture_events_raw.csv           서울시 문화행사

왜 total_family_data.csv 를 쓰지 않는가
-----------------------------------------------------------------------------
이름 키워드로 커플 항목을 건지면 오탐이 절반을 넘는다. 실측 결과 "카페"
키워드로 656건이 잡혔는데 대부분 '맘스하트카페', '아이러브맘카페' 같은
육아 카페였고, 656건 중 407건에 baby:1.0 태그가 붙어 있었다.
place_search_results.csv 는 396건 전량이 baby 태그였다.
→ 애초에 가족·영유아 쿼리로 수집된 데이터셋이라 커플용 재활용을 포기한다.
   (레거시 events.csv 의 single 점수 1위가 '경기도육아종합지원센터'였던
    것과 같은 종류의 사고를 만들지 않는다)

무엇을 하지 않는가
-----------------------------------------------------------------------------
1. couple_score 를 만들지 않는다.
   팝업 수집기의 couple_score 도 작성자 주석에 "1차 추정치이며 실측
   데이터로 재검토 필요"라고 적혀 있고, 레거시 events.csv 의 single 점수는
   76건 중 72건이 0.7 이상이라 정렬에 아무 역할을 못 했다.
   → 테마 소속 여부와 사실 기반 신호(마감임박·무료·거리)로만 순위를 낸다.

2. popularity 를 소스 간에 섞지 않는다.
   VisitKorea 조회수(중앙 8,006 / 최대 209,466)는 그 사이트 내부 지표이고,
   KOPIS 예매순위는 공연끼리만 비교된다. 한 축에 세우면 VisitKorea 가
   상위를 독식한다. → 소스별로 백분위를 따로 내고 popularity_src 에
   근거를 명시한다. 근거가 없으면 공란이다.

3. congestion_score 를 채우지 않는다.
   실측 소스는 서울시 실시간 121지점뿐이고, 프론트가 이미 좌표 매칭으로
   붙이고 있다(findNearestCongestion). 여기서 중복으로 만들지 않는다.
"""

import sys
import io
import os
import re
import csv
import json
import math
from datetime import datetime, date

if hasattr(sys.stdout, "detach"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding="utf-8", line_buffering=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
OUTPUT_CSV = os.path.join(DATA_DIR, "total_couple_data.csv")

# ── 설정 ─────────────────────────────────────────────────────────────────
SETTINGS = {
    # 수도권 중심. 전국으로 넓히려면 region_scope 를 "all" 로 바꾼다.
    # 데이터를 버리는 게 아니라 출력에서 거르는 것이므로 재수집이 필요 없다.
    "region_scope": "capital",          # "capital" | "all"
    "capital_regions": ["서울", "경기", "인천"],
    "drop_expired": True,               # 종료된 항목 제외
    "drop_kids": True,
    # 지역을 판정 못 한 항목을 살릴지. 버리면 서울 공연장이 통째로 날아간다.
    "keep_unknown_region": True,                  # 아동 대상 항목 제외 (커플 탭이므로)
    "dedupe_radius_km": 0.1,            # 좌표 100m 이내 + 이름 유사 → 중복
    "description_max_chars": 300,
}

CSV_FIELDS = [
    # 기존 14컬럼 — 프론트 헬퍼(parseLatLon/isFreeItem/findNearestCongestion)
    # 를 수정 없이 재사용하기 위해 순서까지 그대로 유지한다.
    "source_site", "category", "place_or_event_name", "period", "target_age",
    "region", "fee_info", "description", "booking_url", "ai_tags",
    "crawled_at", "theme_tags", "congestion_score", "popularity_score",
    # 커플 통합에서 추가한 5컬럼
    "theme_ids",        # 커플 탭 테마 (다중값, ';' 구분)
    "theme_detail",     # 재편 전 세분류 — 나중에 다시 쪼갤 때 쓴다
    "origin",           # 어느 원천에서 왔는지
    "end_date",         # 마감 정렬용 ISO 날짜 (없으면 공란)
    "popularity_src",   # popularity_score 의 근거
    "region_group",     # capital | local
]

# ── 시도 정규화 ──────────────────────────────────────────────────────────
# 수집기마다 표기가 달라 여기서 한 번에 통일한다. 수집기를 각각 고치지
# 않는 이유는, 행정구역이 또 개편되면 네 군데가 아니라 한 군데만 고치면
# 되기 때문이다.
# ⚠️ 2026-07-01 광주광역시와 전라남도가 '전남광주통합특별시'로 통합됐다.
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
    "광주광역사": "전남광주",   # 원본 오타 교정 (VisitKorea 1건)
}

SIDO_SHORT = set(SIDO_NORMALIZE.values()) | {
    "서울", "경기", "인천", "부산", "대구", "대전", "울산", "세종",
    "강원", "충북", "충남", "전북", "경북", "경남", "제주", "전남광주",
}

# ── 커플 탭 테마 ─────────────────────────────────────────────────────────
# web/app.js 의 THEMES.couple 과 id 가 일치해야 한다.
#   popup / concert / nightview / cafe / exhibition / summer
# v1.1: 6개 → 4개로 재편했다.
# 실측 결과 cafe 8건, summer 8건, nightview 36건으로 세 탭이 사실상 비었다.
# 근거 데이터가 없는 탭을 남겨두면 사용자는 '결과가 없다'가 아니라
# '고장났다'로 받아들인다(updateSortChipAvailability 와 같은 판단).
# → 야경/카페/여름을 'outdoor'(야경·나들이) 하나로 합쳤다.
# 원래 세분류는 theme_detail 컬럼에 그대로 남기므로, TourAPI 로 카페·자연
# 데이터가 채워지면 재수집 없이 다시 쪼갤 수 있다.
THEME_POPUP = "popup"            # 팝업스토어
THEME_CONCERT = "concert"        # 공연·콘서트
THEME_EXHIBITION = "exhibition"  # 전시·미술관
THEME_OUTDOOR = "outdoor"        # 야경·나들이

# 세분류 → 대표 테마
DETAIL_TO_THEME = {
    "popup": THEME_POPUP,
    "concert": THEME_CONCERT,
    "exhibition": THEME_EXHIBITION,
    "nightview": THEME_OUTDOOR,
    "cafe": THEME_OUTDOOR,
    "summer": THEME_OUTDOOR,
}

# 공연 장르 → 테마. 전시성 장르만 exhibition, 나머지는 concert.
EXHIBITION_WORDS = ("전시", "미술", "갤러리", "박물")

# 아동 대상 판정 — 커플 탭에서 제외한다(버리지 않고 사유를 남긴다)
KIDS_PATTERNS = re.compile(
    r"가족/어린이|어린이|아동|키즈|유아|초등|교육/체험", re.I
)

_today = date.today()


# ═══════════════════════════════════════════════════════════════════════
# 공통 유틸
# ═══════════════════════════════════════════════════════════════════════

def read_csv(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        print(f"  ⚠️ {name} 없음 — 이 소스를 건너뜁니다.")
        return []
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        return list(csv.DictReader(f))


def read_json(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        print(f"  ⚠️ {name} 없음")
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (json.JSONDecodeError, OSError) as e:
        print(f"  ⚠️ {name} 읽기 실패: {e}")
        return {}


def strip_html(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"&[a-zA-Z]+;|&#\d+;", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def sanitize(v):
    """구분자 충돌 방지. 콜론은 지우지 않고 전각으로 바꿔 시간 표기를 살린다."""
    s = str(v or "").replace(";", ",").replace(":", "：")
    return re.sub(r"\s+", " ", s).strip()


def normalize_sido(addr):
    addr = (addr or "").strip()
    if not addr:
        return ""
    head = addr.split()[0]
    short = SIDO_NORMALIZE.get(head)
    return (short + addr[len(head):]).strip() if short else addr


def to_iso(s):
    """'2026.09.11' / '20260911' / '2026-09-11' → '2026-09-11'"""
    s = str(s or "").strip()[:10]
    if not s:
        return ""
    m = re.match(r"^(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})$", s)
    if m:
        y, mo, d = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    m = re.match(r"^(\d{4})(\d{2})(\d{2})$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return s


def parse_latlon(region):
    m = re.search(r"위도:\s*([\d.]+)\s*,\s*경도:\s*([\d.]+)", region or "")
    if not m:
        return None
    la, lo = float(m.group(1)), float(m.group(2))
    # 한반도 범위를 벗어나면 좌표로 인정하지 않는다
    if not (33.0 <= la <= 39.5 and 124.0 <= lo <= 132.0):
        return None
    return la, lo


class SidoResolver:
    """
    행의 시도를 판정한다. 판정 순서가 중요하다.

      1) 주소 앞머리가 알려진 시도명이면 그것을 쓴다
      2) 좌표가 있으면 '좌표로' 판정한다  ★ v1.1 핵심 수정
      3) 둘 다 없으면 unknown — 버리지 않고 표시만 한다

    v1.0 의 버그: 좌표를 찾아놓고도 주소 문자열로만 지역을 판정했다.
    티켓링크의 venue 는 '올림픽공원 올림픽공원 우리금융아트홀'처럼 시설명이
    이어붙은 형태라, 주소를 못 받으면 region 앞머리가 '올림픽공원'이 되고
    서울 한복판인데도 비수도권으로 분류돼 버려졌다. 실제로 티켓링크가
    212건 → 26건으로 줄었다.

    좌표 판정은 별도 지오코딩 없이, 이미 시도명과 좌표를 **둘 다** 가진
    행들을 기준점으로 삼아 가장 가까운 점의 시도를 따른다. KOPIS·팝업·
    VisitKorea 가 합쳐 약 5,900개의 라벨된 좌표를 제공하므로 촘촘하다.
    """

    MAX_KM = 20.0   # 이보다 멀면 판정하지 않는다(unknown)

    # 3차 폴백: 좌표도 주소도 없을 때 이름에서 지명을 찾는다.
    # 실측에 실제로 나온 것만 넣었다. 추측으로 늘리지 않는다.
    NAME_HINTS = [
        ("서울", ["대학로", "창덕궁", "경복궁", "덕수궁", "더현대서울", "홍대",
                  "강남", "잠실", "여의도", "성수", "명동", "올림픽공원"]),
        ("경기", ["킨텍스", "안양", "수원", "성남", "고양", "부천", "용인",
                  "화성", "일산", "판교"]),
        ("인천", ["인스파이어", "송도", "영종"]),
        ("강원", ["강원대학교", "춘천", "강릉", "원주", "속초"]),
        ("경북", ["김천", "경주", "포항", "안동", "구미"]),
        ("부산", ["부산", "해운대", "센텀"]),
        ("대구", ["대구", "수성"]),
    ]

    def __init__(self):
        self.points = []   # (lat, lon, sido)

    def add_reference(self, rows):
        for r in rows:
            region = r.get("region", "")
            head = region.split()[0] if region else ""
            if head not in SIDO_SHORT:
                continue
            pt = parse_latlon(region)
            if pt:
                self.points.append((pt[0], pt[1], head))

    def finalize(self):
        # 위도 기준으로 정렬해 탐색 범위를 좁힌다(전수 비교는 느리다)
        self.points.sort(key=lambda p: p[0])
        self._lats = [p[0] for p in self.points]

    def by_coord(self, la, lo):
        import bisect
        if not self.points:
            return ""
        span = self.MAX_KM / 111.0
        i = bisect.bisect_left(self._lats, la - span)
        j = bisect.bisect_right(self._lats, la + span)
        best, best_d = "", None
        for k in range(i, j):
            plat, plon, sido = self.points[k]
            d = math.hypot((plat - la) * 111, (plon - lo) * 88)
            if best_d is None or d < best_d:
                best, best_d = sido, d
        return best if (best_d is not None and best_d <= self.MAX_KM) else ""

    def resolve(self, region):
        head = region.split()[0] if region else ""
        if head in SIDO_SHORT:
            return head, "address"
        pt = parse_latlon(region)
        if pt:
            sido = self.by_coord(pt[0], pt[1])
            if sido:
                return sido, "coord"
        for sido, words in self.NAME_HINTS:
            if any(w in region for w in words):
                return sido, "name_hint"
        return "", "unknown"


def build_region(addr, la=None, lo=None):
    addr = normalize_sido(addr)
    if la is None or lo is None:
        return addr
    if not (33.0 <= la <= 39.5 and 124.0 <= lo <= 132.0):
        return addr
    return f"{addr} | 위도:{la}, 경도:{lo}" if addr else f"위도:{la}, 경도:{lo}"


def is_free(fee):
    """
    ⚠️ 함정: r'0원' 으로 매칭하면 '30,000원' 에 부분일치해 전부 무료가 된다.
       실제로 검증 중에 2,618건이 무료로 잘못 집계됐다. 경계 조건이 필수다.
    """
    return bool(re.search(r"무료|(?<![\d,])0원", fee or ""))


def clean_period(start, end):
    s, e = to_iso(start), to_iso(end)
    if s and e:
        return f"{s} ~ {e}", e
    if s:
        return s, ""
    return "", ""


def is_alive(end_iso):
    """종료일이 없으면(상설) 살아있는 것으로 본다."""
    if not end_iso:
        return True
    try:
        return date.fromisoformat(end_iso) >= _today
    except ValueError:
        return True


# ═══════════════════════════════════════════════════════════════════════
# 공연장 좌표 조회 — 2단 폴백
# ═══════════════════════════════════════════════════════════════════════

class VenueGeocoder:
    """
    티켓·문화행사에는 좌표가 없다. 공연장 이름으로 찾는다.
      1차: venue_geocode_cache.json  (기존, 1,161곳)
      2차: kopis_venue_cache.json    (KOPIS 수집물, 816곳 좌표 100%)
    기존 캐시가 공연장의 65%만 맞추던 문제를 KOPIS 캐시로 보완한다.
    """

    def __init__(self):
        self.index = {}
        n1 = n2 = 0

        for key, val in read_json("venue_geocode_cache.json").items():
            if isinstance(val, list) and len(val) >= 2:
                try:
                    la, lo = float(val[0]), float(val[1])
                except (TypeError, ValueError):
                    continue
                for name in [key] + [v for v in val[2:] if isinstance(v, str)]:
                    self._put(name, la, lo, "")
                n1 += 1

        for val in read_json("kopis_venue_cache.json").values():
            if not isinstance(val, dict):
                continue
            try:
                la, lo = float(val.get("la")), float(val.get("lo"))
            except (TypeError, ValueError):
                continue
            self._put(val.get("fcltynm", ""), la, lo, val.get("adres", ""))
            n2 += 1

        print(f"  좌표 인덱스: 기존 {n1}곳 + KOPIS {n2}곳 → 키 {len(self.index)}개")

    @staticmethod
    def _norm(name):
        return re.sub(r"[\s()（）\[\]]", "", str(name or "")).lower()

    def _put(self, name, la, lo, addr):
        k = self._norm(name)
        if k and k not in self.index:
            self.index[k] = (la, lo, addr)

    def lookup(self, venue):
        """정확 일치 → 부분 일치 순으로 찾는다."""
        k = self._norm(venue)
        if not k:
            return None
        if k in self.index:
            return self.index[k]
        # 공연장명이 '올림픽공원 우리금융아트홀'처럼 이어붙은 경우가 많다
        for key, val in self.index.items():
            if len(key) >= 4 and (key in k or k in key):
                return val
        return None


# ═══════════════════════════════════════════════════════════════════════
# 어댑터 — 고유 스키마를 14컬럼으로
# ═══════════════════════════════════════════════════════════════════════

def genre_theme(text):
    """장르 문자열 → exhibition 또는 concert"""
    t = str(text or "")
    return THEME_EXHIBITION if any(w in t for w in EXHIBITION_WORDS) else THEME_CONCERT


def adapt_ticketlink(rows, geo, now):
    out = []
    for x in rows:
        cat = (x.get("category") or "").strip()
        if cat == "예매권":          # 상품권이라 장소가 아니다
            continue
        period, end = clean_period(x.get("start_date"), x.get("end_date"))
        venue = (x.get("venue") or "").strip()
        hit = geo.lookup(venue)
        la, lo, addr = hit if hit else (None, None, "")
        out.append({
            "source_site": f"티켓링크 | {cat}",
            "category": cat or "공연",
            "place_or_event_name": (x.get("title") or "").strip(),
            "period": period,
            "target_age": (x.get("target_age") or "").strip(),
            "region": build_region(addr or venue, la, lo),
            "fee_info": (x.get("price_info") or "").strip(),
            "description": f"{cat} · {venue}".strip(" ·"),
            "booking_url": (x.get("booking_url") or "").strip(),
            "ai_tags": f"venue={sanitize(venue)};product_id={sanitize(x.get('product_id'))}",
            "crawled_at": now,
            "theme_tags": f"{genre_theme(cat)}:1.0;performance:1.0;indoor:1.0",
            "congestion_score": "",
            "popularity_score": "",
            "_themes": {genre_theme(cat)},
            "_origin": "ticketlink",
            "_end": end,
            "_kids": bool(KIDS_PATTERNS.search(cat)),
            "_pop_raw": None,
        })
    return out


def adapt_interpark(rows, geo, now):
    out = []
    for x in rows:
        cat = (x.get("category") or "").strip()
        period, end = clean_period(x.get("start_date"), x.get("end_date"))
        venue = (x.get("venue") or "").strip()
        hit = geo.lookup(venue)
        la, lo, addr = hit if hit else (None, None, "")

        # booking_percent('8.8%')는 인터파크 내부 예매율이다.
        # 소스 내부에서만 비교 가능하므로 정규화 단계에서 따로 처리한다.
        pct = None
        m = re.match(r"([\d.]+)\s*%", str(x.get("booking_percent") or ""))
        if m:
            try:
                pct = float(m.group(1))
            except ValueError:
                pct = None

        fee = (x.get("price_info") or "").strip()
        if "참조" in fee:   # '상세 페이지 참조'는 가격 정보가 아니다
            fee = ""

        out.append({
            "source_site": f"인터파크 | {cat}",
            "category": cat or "공연",
            "place_or_event_name": (x.get("title") or "").strip(),
            "period": period,
            "target_age": "",
            "region": build_region(addr or venue, la, lo),
            "fee_info": fee,
            "description": f"{cat} · {venue}".strip(" ·"),
            "booking_url": (x.get("booking_url") or "").strip(),
            "ai_tags": f"venue={sanitize(venue)};goods_code={sanitize(x.get('goods_code'))}"
                       + (f";booking_percent={pct}" if pct is not None else ""),
            "crawled_at": now,
            "theme_tags": f"{genre_theme(cat)}:1.0;performance:1.0;indoor:1.0",
            "congestion_score": "",
            "popularity_score": "",
            "_themes": {genre_theme(cat)},
            "_origin": "interpark",
            "_end": end,
            "_kids": bool(KIDS_PATTERNS.search(cat)),
            "_pop_raw": pct,
        })
    return out


def adapt_culture(rows, geo, now):
    out = []
    for x in rows:
        genre = (x.get("genre") or "").strip()
        period, end = clean_period(x.get("start"), x.get("end"))
        place = (x.get("place") or "").strip()
        hit = geo.lookup(place)
        la, lo, addr = hit if hit else (None, None, "")
        gu = (x.get("realm") or "").strip()

        # 서울시 문화행사이므로 자치구만 있으면 '서울 {구}' 로 복원한다
        base_addr = addr or (f"서울 {gu}" if gu else "서울")

        pop = None
        try:
            pop = float(x.get("popularity")) if (x.get("popularity") or "").strip() else None
        except ValueError:
            pop = None

        out.append({
            "source_site": f"서울시 문화행사 | {genre}",
            "category": genre or "문화행사",
            "place_or_event_name": (x.get("title") or "").strip(),
            "period": period,
            "target_age": "",
            "region": build_region(base_addr, la, lo),
            "fee_info": "",            # 원본에 요금 필드가 없다 — 지어내지 않는다
            "description": f"{genre} · {place}".strip(" ·"),
            "booking_url": (x.get("url") or "").strip(),
            "ai_tags": f"venue={sanitize(place)};gu={sanitize(gu)}"
                       + (f";thumbnail={sanitize(x.get('thumbnail'))}" if x.get("thumbnail") else ""),
            "crawled_at": now,
            "theme_tags": f"{genre_theme(genre)}:1.0;culture:1.0",
            "congestion_score": "",
            "popularity_score": "",
            "_themes": {genre_theme(genre)},
            "_origin": "culture_seoul",
            "_end": end,
            "_kids": bool(KIDS_PATTERNS.search(genre)),
            "_pop_raw": pop,
        })
    return out


# ═══════════════════════════════════════════════════════════════════════
# 통일 스키마 3종 적재
# ═══════════════════════════════════════════════════════════════════════

def load_unified(rows, origin):
    """이미 14컬럼인 소스. 테마 판정과 메타만 덧붙인다."""
    out = []
    for x in rows:
        row = {k: (x.get(k) or "").strip() for k in CSV_FIELDS[:14]}

        end = ""
        if "~" in row["period"]:
            end = to_iso(row["period"].split("~")[1])
        elif row["period"] and row["period"] != "상시":
            end = to_iso(row["period"])

        themes, kids, pop_raw = set(), False, None
        tags = row["ai_tags"]
        ttags = row["theme_tags"]

        if origin == "popup":
            themes.add(THEME_POPUP)

        elif origin == "visitkorea":
            cat = row["category"]
            if cat == "야경뷰포인트" or "night_view:" in ttags:
                themes.add("nightview")
            if cat == "실내데이트":
                themes.add("cafe" if re.search(r"음식|카페|찻집|외국식", ttags)
                           else THEME_EXHIBITION)
            if cat == "야외데이트":
                themes.add("summer")
            if re.search(r"전시시설|문화시설|박물|미술", ttags):
                themes.add(THEME_EXHIBITION)
            m = re.search(r"con_read[:=]([\d.]+)", tags)
            if m:
                pop_raw = float(m.group(1))

        elif origin == "kopis":
            themes.add(genre_theme(row["category"]))
            kids = "child_show:1.0" in tags or "kids:1.0" in ttags
            m = re.search(r"boxoffice_rank[:=](\d+)", tags)
            if m:
                # 순위는 작을수록 좋다 → 부호를 뒤집어 '클수록 좋음'으로 통일
                pop_raw = -int(m.group(1))

        if not themes:
            themes.add(THEME_CONCERT)

        row["_themes"] = themes
        row["_origin"] = origin
        row["_end"] = end
        row["_kids"] = kids
        row["_pop_raw"] = pop_raw
        out.append(row)
    return out


# ═══════════════════════════════════════════════════════════════════════
# 중복 제거
# ═══════════════════════════════════════════════════════════════════════

def name_key(name):
    """'[강남] 아무개 전시 - 서울' → '아무개전시'"""
    s = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", str(name or ""))
    s = re.sub(r"[^0-9A-Za-z가-힣]", "", s)
    return s.lower()


def dedupe(rows):
    """
    좌표 100m 이내 + 이름 유사 → 같은 항목으로 본다.
    ⚠️ 좌표가 다르면 이름이 같아도 남긴다. 팝업은 같은 브랜드가 명동점·
       홍대점처럼 여러 지점에서 동시에 열리는 정상 케이스가 있다.
    """
    kept, removed = [], []
    radius = SETTINGS["dedupe_radius_km"]
    # 소스 신뢰도 순으로 정렬해, 겹치면 앞선 소스를 남긴다
    priority = {"kopis": 0, "visitkorea": 1, "popup": 2,
                "ticketlink": 3, "interpark": 4, "culture_seoul": 5}
    rows = sorted(rows, key=lambda r: priority.get(r["_origin"], 9))

    buckets = {}
    for r in rows:
        nk = name_key(r["place_or_event_name"])
        pt = parse_latlon(r["region"])
        dup_of = None

        for cand in buckets.get(nk[:8], []):
            if cand["_nk"] != nk:
                continue
            cpt = cand["_pt"]
            if pt and cpt:
                d = math.hypot((pt[0] - cpt[0]) * 111, (pt[1] - cpt[1]) * 88)
                if d <= radius:
                    dup_of = cand
                    break
            elif not pt and not cpt:
                dup_of = cand
                break

        if dup_of:
            removed.append((r, dup_of["_origin"]))
            continue

        r["_nk"], r["_pt"] = nk, pt
        buckets.setdefault(nk[:8], []).append(r)
        kept.append(r)

    return kept, removed


# ═══════════════════════════════════════════════════════════════════════
# 소스별 popularity 정규화
# ═══════════════════════════════════════════════════════════════════════

POP_SRC_LABEL = {
    "visitkorea": "visitkorea_read",
    "kopis": "kopis_boxoffice",
    "interpark": "interpark_booking_pct",
    "culture_seoul": "seoul_culture_popularity",
}


def normalize_popularity(rows):
    """
    소스 안에서만 백분위를 낸다. 소스 간 비교는 하지 않는다.
    근거가 없는 항목은 공란으로 남긴다 — '0점'이 아니라 '모름'이다.
    """
    by_origin = {}
    for r in rows:
        if r["_pop_raw"] is not None:
            by_origin.setdefault(r["_origin"], []).append(r)

    filled = {}
    for origin, group in by_origin.items():
        vals = sorted(x["_pop_raw"] for x in group)
        lo, hi = vals[0], vals[-1]
        for r in group:
            if hi == lo:
                score = 50.0
            else:
                score = round(100.0 * (r["_pop_raw"] - lo) / (hi - lo), 1)
            r["popularity_score"] = score
            r["popularity_src"] = POP_SRC_LABEL.get(origin, origin)
        filled[origin] = len(group)
    return filled


# ═══════════════════════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════════════════════

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("=" * 78)
    print(f"커플 통합 데이터 생성 — 기준일 {_today}")
    print(f"지역 범위: {SETTINGS['region_scope']}"
          f" ({', '.join(SETTINGS['capital_regions'])})"
          if SETTINGS["region_scope"] == "capital" else "지역 범위: 전국")
    print("=" * 78)

    print("\n[1/6] 좌표 인덱스 구성")
    geo = VenueGeocoder()

    print("\n[2/6] 원천 적재")
    rows = []
    rows += load_unified(read_csv("kopis_performances_raw.csv"), "kopis")
    rows += load_unified(read_csv("popup_couple_events_raw.csv"), "popup")
    rows += load_unified(read_csv("visitkorea_couple_spots_raw.csv"), "visitkorea")
    rows += adapt_ticketlink(read_csv("live_ticketlink_tickets.csv"), geo, now)
    rows += adapt_interpark(read_csv("live_interpark_tickets.csv"), geo, now)
    rows += adapt_culture(read_csv("culture_events_raw.csv"), geo, now)

    tally = {}
    for r in rows:
        tally[r["_origin"]] = tally.get(r["_origin"], 0) + 1
    for k, v in sorted(tally.items(), key=lambda x: -x[1]):
        print(f"    {k:16s}{v:6d}")
    print(f"    {'합계':16s}{len(rows):6d}")

    print("\n[3/6] 필터")
    stats = {}

    if SETTINGS["drop_expired"]:
        before = len(rows)
        rows = [r for r in rows if is_alive(r["_end"])]
        stats["종료 제외"] = before - len(rows)

    # 해외 공연은 국내 나들이 추천에 쓸 수 없다.
    before = len(rows)
    rows = [r for r in rows if not re.match(r"^\s*해외", r["region"])]
    stats["해외 공연 제외"] = before - len(rows)

    if SETTINGS["drop_kids"]:
        before = len(rows)
        rows = [r for r in rows if not r["_kids"]]
        stats["아동 대상 제외"] = before - len(rows)

    # 지역 정규화 → 좌표 기반 시도 판정 → 그룹 분류
    caps = set(SETTINGS["capital_regions"])
    for r in rows:
        r["region"] = normalize_sido(r["region"])

    resolver = SidoResolver()
    resolver.add_reference(rows)     # 시도명+좌표를 둘 다 가진 행이 기준점
    resolver.finalize()
    print(f"    좌표 기준점 {len(resolver.points)}개 확보")

    how = {}
    for r in rows:
        sido, method = resolver.resolve(r["region"])
        how[method] = how.get(method, 0) + 1
        r["_sido"] = sido
        r["region_group"] = ("capital" if sido in caps
                             else "local" if sido else "unknown")
    print(f"    시도 판정: 주소 {how.get('address',0)} / "
          f"좌표 {how.get('coord',0)} / 지명힌트 {how.get('name_hint',0)} / "
          f"미상 {how.get('unknown',0)}")

    if SETTINGS["region_scope"] == "capital":
        before = len(rows)
        keep = {"capital"} | ({"unknown"} if SETTINGS["keep_unknown_region"] else set())
        rows = [r for r in rows if r["region_group"] in keep]
        stats["비수도권 제외"] = before - len(rows)

    for k, v in stats.items():
        print(f"    {k:18s}{v:6d}건")
    print(f"    {'잔여':18s}{len(rows):6d}건")

    print("\n[4/6] 중복 제거")
    rows, removed = dedupe(rows)
    print(f"    제거 {len(removed)}건 → 잔여 {len(rows)}건")
    if removed:
        pairs = {}
        for r, keeper in removed:
            key = f"{r['_origin']} ← {keeper}"
            pairs[key] = pairs.get(key, 0) + 1
        for k, v in sorted(pairs.items(), key=lambda x: -x[1])[:6]:
            print(f"      {k:34s}{v}건")

    print("\n[5/6] popularity 소스별 정규화")
    filled = normalize_popularity(rows)
    for k, v in filled.items():
        print(f"    {POP_SRC_LABEL.get(k, k):28s}{v:5d}건")
    if not filled:
        print("    근거 있는 항목 없음 — 전 건 공란")

    print("\n[6/6] 저장")
    out = []
    for r in rows:
        rec = {k: r.get(k, "") for k in CSV_FIELDS}
        detail = sorted(r["_themes"])
        rec["theme_detail"] = ";".join(detail)
        rec["theme_ids"] = ";".join(sorted({DETAIL_TO_THEME.get(t, t) for t in detail}))
        rec["origin"] = r["_origin"]
        rec["end_date"] = r["_end"]
        rec.setdefault("popularity_src", "")
        rec["popularity_src"] = r.get("popularity_src", "")
        out.append(rec)

    if not out:
        print("\n❌ 저장할 행이 없습니다. 기존 파일을 덮어쓰지 않고 종료합니다.")
        return

    tmp = OUTPUT_CSV + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(out)
    os.replace(tmp, OUTPUT_CSV)

    # ── 요약 ────────────────────────────────────────────────────
    coord = sum(1 for r in out if parse_latlon(r["region"]))
    fee = sum(1 for r in out if r["fee_info"].strip())
    free = sum(1 for r in out if is_free(r["fee_info"]))
    pop = sum(1 for r in out if str(r["popularity_score"]).strip())

    theme_count, detail_count = {}, {}
    for r in out:
        for t in r["theme_ids"].split(";"):
            if t:
                theme_count[t] = theme_count.get(t, 0) + 1
        for t in r["theme_detail"].split(";"):
            if t:
                detail_count[t] = detail_count.get(t, 0) + 1

    print("\n" + "=" * 78)
    print(f"✅ 저장 완료: {OUTPUT_CSV}")
    print(f"   총 {len(out)}건")
    print(f"   좌표 확보     {coord:5d}건 ({coord / len(out) * 100:.1f}%)")
    print(f"   요금 정보     {fee:5d}건 ({fee / len(out) * 100:.1f}%)  그중 무료 {free}건")
    print(f"   인기 근거     {pop:5d}건 ({pop / len(out) * 100:.1f}%)")
    print("\n   테마별 분포")
    for t, c in sorted(theme_count.items(), key=lambda x: -x[1]):
        print(f"     {t:12s}{c:5d}건")
    print("     (세분류: " + ", ".join(f"{k} {v}" for k, v in
          sorted(detail_count.items(), key=lambda x: -x[1])) + ")")
    print("\n   출처별 분포")
    o = {}
    for r in out:
        o[r["origin"]] = o.get(r["origin"], 0) + 1
    for k, v in sorted(o.items(), key=lambda x: -x[1]):
        print(f"     {k:14s}{v:5d}건")
    rg = {}
    for r in out:
        rg[r["region_group"]] = rg.get(r["region_group"], 0) + 1
    print("\n   지역 그룹")
    for k, v in sorted(rg.items(), key=lambda x: -x[1]):
        print(f"     {k:14s}{v:5d}건")
    print("=" * 78)


if __name__ == "__main__":
    main()
