"""
공연/전시 이벤트 데이터 수집기 v2.0
--------------------------------------------
수집 소스:
  1. 서울시 문화행사 API (data.seoul.go.kr) [API] - 페이징 수집
  2. 국립현대미술관 (mmca.go.kr) [내부 JSON API]
  3. 서울시립미술관 (sema.seoul.go.kr) [메인 페이지 파싱 + 상세 기간 조회]
  4. 예술의전당 (sac.or.kr) [메인 페이지 파싱]
  5. 네이버 데이터랩 API [검색 트렌드 인기도] - 수집 결과에 popularity 부여

[v2.0 변경 사항]
  - 공공데이터포털 공연전시 API: 서비스 폐기(NO_OPENAPI_SERVICE_ERROR) 확인 → 비활성화
  - 서울시 문화행사 API: rows=200 고정 → 1,000건 단위 페이징 (가용 약 19,500건)
  - MMCA: 목록이 JS 렌더링이라 HTML 파싱 불가 → 내부 JSON API 사용
  - SeMA: /kr/exhibition/exhToday 가 HTTP 500 → 메인 페이지 파싱으로 전환
  - 예술의전당: /show/showList 가 HTTP 404 → 메인 페이지 파싱으로 전환
  - 네이버 데이터랩: 정의만 되고 미호출이던 함수를 실제 파이프라인에 연결
  - realm 컬럼에 이미지 URL이 들어가던 매핑 오류 수정
  - crawled_at 컬럼 추가 (기존에는 수집 시각 추적 불가)

[API 키 발급]
- 서울시 문화행사: data.seoul.go.kr → seoul_api_key 사용
- 네이버 데이                               `터랩: developers.naver.com → 앱 등록 → naver_client_id, naver_client_secret
"""
import sys, io
import requests
import json
import os
import csv
import time
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

SEOUL_KEY   = CONFIG.get("api_keys", {}).get("seoul_api_key", "")
NAVER_ID    = CONFIG.get("api_keys", {}).get("naver_client_id", "")
NAVER_SEC   = CONFIG.get("api_keys", {}).get("naver_client_secret", "")

today = datetime.now()
NOW_STR   = today.strftime("%Y-%m-%d %H:%M:%S")
DATE_FROM = today.strftime("%Y%m%d")
DATE_TO   = (today + timedelta(days=60)).strftime("%Y%m%d")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


def http_get(url, *, params=None, headers=None, timeout=15, retries=2, label=""):
    """공통 GET 래퍼: 타임아웃 여유 + 재시도 + 실패 사유 로깅.

    기존 코드는 timeout 이 6~8초로 짧고 실패를 조용히 삼켜서, 일시적인
    지연과 영구 장애를 구분할 수 없었다. 여기서는 재시도 후에도 실패하면
    사유를 반드시 출력한다.
    """
    last_err = None
    for attempt in range(1, retries + 2):
        try:
            r = requests.get(url, params=params, headers=headers or HEADERS, timeout=timeout)
            if r.status_code == 200:
                return r
            last_err = f"HTTP {r.status_code}"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        if attempt <= retries:
            time.sleep(1.0 * attempt)
    print(f"  [{label} 실패] {last_err} ({url})")
    return None


# ─────────────────────────────────────────────────────
# 1. 공공데이터포털 공연전시정보 API — 서비스 폐기로 비활성화
# ─────────────────────────────────────────────────────
# 2026-08-23 실호출 확인 결과:
#   HTTP 400 / errMsg=NO_OPENAPI_SERVICE_ERROR
#   returnAuthMsg="해당 오픈API 서비스가 없거나 폐기됨" (returnReasonCode=12)
# 인증 실패가 아니라 서비스 자체가 사라진 것이므로 키를 재발급해도 복구되지
# 않는다. 대체 소스(KOPIS 공연예술통합전산망 등)를 도입하기 전까지는
# 호출하지 않는다. 호출을 남겨두면 매 실행마다 2회의 무의미한 요청과
# 오류 로그만 발생한다.
PUBLIC_API_ENABLED = False


def fetch_culture_events_public_api(rows=100, area="서울"):
    """공공데이터포털 공연전시정보 API (현재 폐기된 서비스)."""
    if not PUBLIC_API_ENABLED:
        print("  [공연전시API] 서비스 폐기(NO_OPENAPI_SERVICE_ERROR) → 건너뜀. "
              "대체 소스 도입 필요")
        return []

    url = "https://apis.data.go.kr/B553457/nopenapi/rest/publicperformancedisplays/period"
    params = {
        "serviceKey": CONFIG.get("api_keys", {}).get("tour_api_key", ""),
        "from": DATE_FROM, "to": DATE_TO, "rows": rows, "_type": "json",
    }
    r = http_get(url, params=params, timeout=10, label="공연전시API")
    if r is None:
        return []
    try:
        items = r.json().get("msgBody", {}).get("perforList", [])
    except Exception as e:
        print(f"  [공연전시API 파싱 오류] {e}")
        return []
    print(f"  [공연전시API] {len(items)}건 수집 완료")
    return [{
        "title": it.get("title", ""), "place": it.get("place", ""),
        "start": it.get("startDate", "").replace(".", "-")[:10],
        "end":   it.get("endDate", "").replace(".", "-")[:10],
        "genre": it.get("genrenm", ""), "realm": it.get("realmName", ""),
        "url": it.get("url", ""), "thumbnail": it.get("thumbnail", ""),
        "source": "공공데이터포털",
    } for it in items]


# ─────────────────────────────────────────────────────
# 2. 서울시 문화행사 API (페이징 수집)
# ─────────────────────────────────────────────────────
SEOUL_PAGE_SIZE = 1000   # 서울열린데이터광장 1회 최대 조회 건수


def fetch_seoul_culture_events(max_rows=3000):
    """서울시 문화행사 정보 API.

    기존에는 rows=200 으로 1회만 호출해 전체 약 19,500건 중 1%만 가져왔다.
    여기서는 1,000건 단위로 페이징하며 max_rows 까지 수집한다.
    """
    if not SEOUL_KEY or SEOUL_KEY.startswith("YOUR_"):
        print("  [서울문화API] 키 없음 → 건너뜀")
        return []

    results = []
    start = 1
    total = None

    while len(results) < max_rows:
        end = start + SEOUL_PAGE_SIZE - 1
        url = f"http://openapi.seoul.go.kr:8088/{SEOUL_KEY}/json/culturalEventInfo/{start}/{end}/"
        r = http_get(url, timeout=20, label=f"서울문화API {start}~{end}")
        if r is None:
            break
        try:
            root = r.json().get("culturalEventInfo", {})
        except Exception as e:
            print(f"  [서울문화API 파싱 오류] {e}")
            break

        code = root.get("RESULT", {}).get("CODE")
        if code != "INFO-000":
            print(f"  [서울문화API] 응답 코드 {code} → 중단")
            break

        if total is None:
            total = root.get("list_total_count")
            print(f"  [서울문화API] 서버 보유 총 {total}건")

        rows = root.get("row", [])
        if not rows:
            break

        for item in rows:
            results.append({
                "title":  item.get("TITLE", ""),
                "place":  item.get("PLACE", ""),
                "start":  item.get("STRTDATE", "")[:10],
                "end":    item.get("END_DATE", "")[:10],
                "genre":  item.get("CODENAME", ""),
                # 기존 코드는 realm 에 MAIN_IMG(이미지 URL)를 넣는 매핑 오류가
                # 있었다. realm 은 분야/지역 정보이므로 GUNAME(자치구)을 넣는다.
                "realm":  item.get("GUNAME", ""),
                "url":    item.get("HMPG_ADDR", ""),
                "thumbnail": item.get("MAIN_IMG", ""),
                "source": "서울시 문화행사",
            })

        if len(rows) < SEOUL_PAGE_SIZE:
            break
        start = end + 1
        time.sleep(0.3)

    print(f"  [서울문화API] {len(results)}건 수집 완료")
    return results[:max_rows]


# ─────────────────────────────────────────────────────
# 3. 국립현대미술관 (MMCA) — 내부 JSON API
# ─────────────────────────────────────────────────────
# progressList.do 의 목록 영역(<div id="listDiv">)은 비어 있고 jQuery 의
# fn_getList() 가 아래 엔드포인트를 호출해 채운다. 따라서 requests+BS4 로
# HTML 을 긁으면 항상 0건이 된다.
MMCA_LIST_API = "https://www.mmca.go.kr/exhibitions/AjaxExhibitionList.do"
MMCA_REFERER  = "https://www.mmca.go.kr/exhibitions/progressList.do"


def crawl_mmca(max_pages=3):
    """국립현대미술관 전시 목록 (내부 JSON API)."""
    headers = dict(HEADERS)
    headers.update({"X-Requested-With": "XMLHttpRequest", "Referer": MMCA_REFERER})

    results = []
    for page in range(1, max_pages + 1):
        params = {
            "exhFlag": "1",          # 1 = 현재 진행 중인 전시
            "searchExhPlaCd": "",
            "searchExhCd": "",
            "sort": "1",
            "pageIndex": str(page),
        }
        r = http_get(MMCA_LIST_API, params=params, headers=headers, label=f"MMCA p{page}")
        if r is None:
            break
        try:
            data = r.json()
        except Exception as e:
            print(f"  [MMCA 파싱 오류] {e}")
            break

        items = data.get("exhibitionsList", []) or []
        if not items:
            break

        for it in items:
            title = (it.get("exhTitle") or "").strip()
            if not title:
                continue
            branch = (it.get("exhPlaNm") or "").strip()      # 예: 서울, 과천
            detail = (it.get("exhPlaDtl") or "").strip()     # 예: 교육동 2층
            place = "국립현대미술관" + (f" {branch}" if branch else "")
            if detail:
                place = f"{place} {detail}"
            exh_id = it.get("exhId", "")
            thumb = it.get("exhThumbImg") or ""
            if thumb.startswith("/"):
                thumb = "https://www.mmca.go.kr" + thumb

            results.append({
                "title": title,
                "place": place,
                "start": (it.get("exhStDt") or "")[:10],
                "end":   (it.get("exhEdDt") or "")[:10],
                "genre": it.get("exhCd") or "전시",
                "realm": it.get("exhTpCd") or "미술",
                "url": f"https://www.mmca.go.kr/exhibitions/exhibitionsDetail.do?exhId={exh_id}"
                       if exh_id else MMCA_REFERER,
                "thumbnail": thumb,
                "source": "MMCA",
                "period_raw": f"{it.get('exhStDt','')} ~ {it.get('exhEdDt','')}",
            })

        paging = data.get("paginationInfo") or {}
        if page >= (paging.get("totalPageCount") or page):
            break
        time.sleep(0.3)

    print(f"  [MMCA] {len(results)}건 수집")
    return results


# ─────────────────────────────────────────────────────
# 4. 서울시립미술관 (SeMA) — 메인 페이지 파싱
# ─────────────────────────────────────────────────────
# 기존 URL /kr/exhibition/exhToday 는 HTTP 500 을 반환한다.
# /kr/whatson/exhibition 계열 목록 경로도 모두 500 이라, 현재 안정적으로
# 접근 가능한 경로는 메인 페이지의 전시 슬라이더뿐이다.
# 제목은 링크 텍스트가 비어 있고 <img alt> 에 들어 있다.
SEMA_HOME   = "https://sema.seoul.go.kr/"
SEMA_DETAIL = "https://sema.seoul.go.kr/kr/whatson/exhibition/detail?exNo={}"

_SEMA_PERIOD_RE = re.compile(
    r'전시기간\s*(20\d{2}[.\-]\d{1,2}[.\-]\d{1,2})\s*~\s*(20\d{2}[.\-]\d{1,2}[.\-]\d{1,2})'
)


def _sema_fetch_period(ex_no):
    """SeMA 상세 페이지에서 '전시기간 YYYY.MM.DD~YYYY.MM.DD' 추출."""
    r = http_get(SEMA_DETAIL.format(ex_no), timeout=15, retries=1,
                 label=f"SeMA detail {ex_no}")
    if r is None:
        return "", ""
    text = re.sub(r'\s+', ' ', BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True))
    m = _SEMA_PERIOD_RE.search(text)
    if not m:
        return "", ""
    norm = lambda s: s.replace(".", "-")
    return norm(m.group(1)), norm(m.group(2))


def crawl_sema(fetch_detail=True):
    """서울시립미술관 전시 목록."""
    r = http_get(SEMA_HOME, timeout=20, label="SeMA")
    if r is None:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    seen = {}
    for a in soup.find_all("a", href=True):
        m = re.search(r'exhibition/detail\?exNo=(\d+)', a["href"])
        if not m:
            continue
        ex_no = m.group(1)
        img = a.find("img")
        title = (img.get("alt") or "").strip() if img else ""
        if not title:
            title = a.get_text(" ", strip=True)
        title = re.sub(r'\s+', ' ', title).strip()
        if not title:
            continue
        # 같은 전시가 여러 슬라이드에 중복 노출될 수 있어 exNo 로 중복 제거
        if ex_no not in seen or len(title) > len(seen[ex_no]):
            seen[ex_no] = title

    results = []
    for ex_no, title in seen.items():
        start, end = ("", "")
        if fetch_detail:
            start, end = _sema_fetch_period(ex_no)
            time.sleep(0.3)
        results.append({
            "title": title,
            "place": "서울시립미술관",
            "start": start or today.strftime("%Y-%m-%d"),
            "end":   end or (today + timedelta(days=60)).strftime("%Y-%m-%d"),
            "genre": "전시",
            "realm": "미술",
            "url": SEMA_DETAIL.format(ex_no),
            "thumbnail": "",
            "source": "SeMA",
            "period_raw": f"{start} ~ {end}" if start and end else "",
        })

    print(f"  [SeMA] {len(results)}건 수집")
    return results


# ─────────────────────────────────────────────────────
# 5. 예술의전당 (SAC) — 메인 페이지 파싱
# ─────────────────────────────────────────────────────
# 기존 URL /site/main/show/showList 는 HTTP 404.
# 실제 목록 경로는 /site/main/show/show_list (스네이크 케이스) 이지만,
# 그 페이지의 목록도 /site/main/show/dataList 를 통해 비동기로 채워지는데
# 해당 엔드포인트는 건수/페이징만 반환하고 항목 배열을 주지 않는다.
# 따라서 서버에서 직접 렌더링되는 메인 페이지의 공연 카드를 파싱한다.
SAC_HOME = "https://www.sac.or.kr/"

_SAC_FULL_DATE_RE  = re.compile(r'(20\d{2})\.(\d{1,2})\.(\d{1,2})')   # 2026.09.16
_SAC_SHORT_DATE_RE = re.compile(r'(?<!\d)(\d{1,2})\.(\d{1,2})(?!\d)')  # 07.17(금)


def _sac_parse_dates(text):
    """공연 카드의 기간 문자열에서 (start, end) 추출.

    메인 페이지 카드는 연도 포함('2026.09.16')과 연도 생략('07.17(금)~09.27(일)')
    두 형식이 섞여 있다. 연도가 없으면 올해로 보되, 이미 지난 달이면 내년으로 본다.
    """
    full = _SAC_FULL_DATE_RE.findall(text)
    if full:
        ds = [f"{y}-{int(mo):02d}-{int(d):02d}" for y, mo, d in full]
        return ds[0], ds[-1]

    short = _SAC_SHORT_DATE_RE.findall(text)
    if short:
        ds = []
        for mo, d in short:
            mo, d = int(mo), int(d)
            if not (1 <= mo <= 12 and 1 <= d <= 31):
                continue
            year = today.year + 1 if mo < today.month - 6 else today.year
            ds.append(f"{year}-{mo:02d}-{d:02d}")
        if ds:
            return ds[0], ds[-1]
    return "", ""


def crawl_sac():
    """예술의전당 공연 목록.

    메인 페이지에는 마크업이 다른 3가지 공연 카드가 섞여 있다:
      (a) h3.bannerName + p("콘서트홀 2026.09.16(수) 19:30")
      (b) img[alt] + p > b(공연장) / strong(제목) / span("07.17(금)~09.27(일)")
      (c) span.w-date + h4(제목)
    셋 다 처리하지 않으면 절반 가까이 누락된다.
    """
    r = http_get(SAC_HOME, timeout=20, label="예술의전당")
    if r is None:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    seen = {}
    txt = lambda el: re.sub(r'\s+', ' ', el.get_text(" ", strip=True)) if el else ""

    for a in soup.find_all("a", href=True):
        m = re.search(r'show_view\?SN=(\d+)', a["href"])
        if not m:
            continue
        sn = m.group(1)
        if sn in seen:
            continue

        title, venue, info = "", "", ""

        # (a) 배너형 카드
        name_el = a.select_one("h3.bannerName") or a.select_one("h3")
        if name_el:
            title = txt(name_el)
            info = txt(a.find("p"))
            venue = _SAC_FULL_DATE_RE.split(info)[0].strip() if info else ""

        # (b) 포스터형 카드: p > b(공연장) + strong(제목) + span(기간)
        if not title:
            p_el = a.find("p")
            if p_el:
                strong_el = p_el.find("strong")
                if strong_el:
                    title = txt(strong_el)
                    venue = txt(p_el.find("b"))
                    info = txt(p_el.find("span"))

        # (c) 리스트형 카드: span.w-date + h4(제목)
        if not title:
            h4 = a.find("h4")
            if h4:
                title = txt(h4)
                info = txt(a.select_one("span.w-date"))

        # 최후 폴백: 포스터 이미지 alt
        if not title:
            img = a.find("img")
            if img:
                title = re.sub(r'\s*\(포스터\)\s*$', '', (img.get("alt") or "")).strip()

        title = re.sub(r'\s+', ' ', title).strip()
        if not title or len(title) < 3:
            continue

        start, end = _sac_parse_dates(info)
        seen[sn] = {
            "title": title,
            "place": venue or "예술의전당",
            "start": start or today.strftime("%Y-%m-%d"),
            "end":   end or start or (today + timedelta(days=30)).strftime("%Y-%m-%d"),
            "genre": "공연",
            "realm": "클래식/오페라",
            "url": f"https://www.sac.or.kr/site/main/show/show_view?SN={sn}",
            "thumbnail": "",
            "source": "예술의전당",
            "period_raw": info,
        }

    results = list(seen.values())
    print(f"  [예술의전당] {len(results)}건 수집")
    return results


# ─────────────────────────────────────────────────────
# 6. 네이버 데이터랩 — 장소별 검색 트렌드 (인기도)
# ─────────────────────────────────────────────────────
# 데이터랩은 요청 1건당 키워드 그룹 5개까지 허용한다.
TREND_GROUP_SIZE = 5

# ── 절대 비교를 위한 앵커(기준 키워드) ────────────────────────
# 데이터랩은 절대 검색량을 주지 않는다. 요청에 포함된 키워드 × 전체 주차 중
# 최대 지점을 100으로 놓고 나머지를 비율 환산하므로, 값의 기준(尺)이 요청마다
# 달라진다. 실측 예: 동일 키워드 '예술의전당'이
#   - 세종문화회관/국립극장/블루스퀘어/LG아트센터와 묶이면 80.4
#   - 날씨/유튜브/쿠팡/네이버와 묶이면            0.3
# 따라서 서로 다른 요청의 원값끼리는 비교할 수 없다.
#
# 해결: 모든 요청에 동일한 앵커 키워드를 1개씩 넣고 (키워드값 / 앵커값) 비율을
# 쓴다. 임의의 정규화 계수가 분자·분모에서 상쇄되므로 이 비율은 요청과 무관한
# 절대 비교값이 된다.
#
# 앵커는 '공연'을 쓴다. 실측 선정 근거(기간평균 기준):
#   공연=39.43 / 전시=15.42 / 나들이=4.12 / 주말=3.25 / 문화행사=0.04
# 너무 작으면(문화행사) 비율이 수천대로 튀어 정밀도가 나빠지고, 너무 크면
# 소형 키워드가 0으로 뭉개진다. '공연'은 소형 키워드도 0.0146을 반환해 적합.
TREND_ANCHOR = "공연"

# 앵커가 슬롯 1개를 차지하므로 요청당 실제 조회 키워드는 4개다.
TREND_KEYWORDS_PER_REQUEST = TREND_GROUP_SIZE - 1

# 조회할 키워드 상한. None = 전량 조회.
# 참고: 네이버 데이터랩의 정확한 일일 허용량은 공식 문서에서 확인하지 못했다.
# developers.naver.com > 내 애플리케이션에서 앱별 일일 허용량/사용량을 볼 수 있으며,
# API 응답 헤더에는 잔여 호출수 정보가 포함되지 않는다.
TREND_MAX_KEYWORDS = None

# 폭주 방지 상한. 데이터셋이 커져도 이 요청수를 넘지 않는다.
# (현재 약 1,500 키워드 = 307요청 수준이므로 충분한 여유)
TREND_MAX_REQUESTS = 1200


def _period_mean(data_points):
    """조회 기간 전체의 평균 ratio.

    마지막 주차 한 점만 쓰면 그 주의 일시적 변동에 휘둘린다.
    기간 평균이 인기도 지표로 더 안정적이다.
    """
    vals = [p.get("ratio", 0) for p in data_points if p.get("ratio") is not None]
    return sum(vals) / len(vals) if vals else 0.0


def fetch_naver_trend(place_names: list, max_keywords=TREND_MAX_KEYWORDS) -> dict:
    """네이버 데이터랩 API → 키워드별 '앵커 대비 비율' 반환 (절대 비교 가능).

    반환값은 (키워드 기간평균 / 앵커 기간평균) 이다.
    데이터랩이 요청마다 다르게 잡는 정규화 계수가 분자·분모에서 상쇄되므로,
    서로 다른 요청에서 나온 값끼리도 그대로 비교할 수 있다.

    앵커가 슬롯 1개를 쓰므로 요청당 실제 조회 키워드는 4개다.
    max_keywords=None 이면 전량 조회한다.
    검색량이 충분하지 않은 키워드는 데이터랩이 결과를 주지 않으므로,
    요청한 키워드 수보다 반환 수가 적은 것이 정상이다.
    """
    if not NAVER_ID or NAVER_ID.startswith("YOUR_"):
        print("  [네이버트렌드] 키 없음 → 건너뜀")
        return {}

    names = [n for n in place_names if n and n != TREND_ANCHOR]
    requested_total = len(names)
    if max_keywords is not None:
        names = names[:max_keywords]

    # 폭주 방지 상한 적용 (잘라낸 경우 반드시 로그로 알린다)
    cap = TREND_MAX_REQUESTS * TREND_KEYWORDS_PER_REQUEST
    if len(names) > cap:
        print(f"  [네이버트렌드] 안전 상한 적용: {len(names)} → {cap}개 "
              f"(TREND_MAX_REQUESTS={TREND_MAX_REQUESTS})")
        names = names[:cap]

    if not names:
        return {}

    chunks = [names[i:i + TREND_KEYWORDS_PER_REQUEST]
              for i in range(0, len(names), TREND_KEYWORDS_PER_REQUEST)]
    skipped = requested_total - len(names)
    print(f"  [네이버트렌드] 키워드 {len(names)}개 / 요청 {len(chunks)}회 시작 "
          f"(앵커='{TREND_ANCHOR}', 요청당 {TREND_KEYWORDS_PER_REQUEST}개)"
          + (f" · 미조회 {skipped}개" if skipped else ""))

    url = "https://openapi.naver.com/v1/datalab/search"
    headers = {
        "X-Naver-Client-Id":     NAVER_ID,
        "X-Naver-Client-Secret": NAVER_SEC,
        "Content-Type":          "application/json",
    }
    start_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    end_date   = (today - timedelta(days=1)).strftime("%Y-%m-%d")

    results = {}
    no_data = set()          # 데이터랩이 측정값을 주지 않은 키워드
    fail_count = 0
    anchor_zero = 0

    for idx, chunk in enumerate(chunks, 1):
        group = [TREND_ANCHOR] + chunk
        body = {
            "startDate": start_date,
            "endDate":   end_date,
            "timeUnit":  "week",
            "keywordGroups": [{"groupName": n, "keywords": [n]} for n in group],
        }
        try:
            r = requests.post(url, headers=headers, json=body, timeout=10)
            if r.status_code == 429:
                # 쿼터 소진 또는 초당 호출 초과. 남은 요청을 계속 던지지 않고 중단한다.
                print(f"  [네이버트렌드] HTTP 429 (호출 한도 초과) → {idx}/{len(chunks)}회에서 중단")
                print(f"                 {r.text[:200]}")
                break
            if r.status_code != 200:
                fail_count += 1
                print(f"  [네이버트렌드] HTTP {r.status_code}: {r.text[:200]}")
                continue

            means = {}
            for result in r.json().get("results", []):
                means[result["title"]] = _period_mean(result.get("data", []))

            anchor_val = means.pop(TREND_ANCHOR, 0.0)
            if not anchor_val:
                # 앵커가 0이면 이 요청의 값들은 절대 비교 기준을 만들 수 없다.
                # 잘못된 값을 남기느니 통째로 버린다.
                anchor_zero += 1
                continue

            for name, val in means.items():
                # val == 0 은 "인기도가 0" 이 아니라 "데이터랩이 측정값을 주지
                # 않았다"는 뜻이다(검색량이 임계 미만). 0으로 저장하면 측정된
                # 최하위값과 미측정이 구분되지 않으므로 아예 담지 않는다.
                if val > 0:
                    results[name] = round(val / anchor_val, 6)
                else:
                    no_data.add(name)

        except Exception as e:
            fail_count += 1
            print(f"  [네이버트렌드 오류] {type(e).__name__}: {e}")

        if idx % 50 == 0 or idx == len(chunks):
            print(f"    진행 {idx}/{len(chunks)}회 · 비율 확보 {len(results)}개")
        time.sleep(0.3)

    if fail_count:
        print(f"  [네이버트렌드] 실패 요청 {fail_count}회")
    if anchor_zero:
        print(f"  [네이버트렌드] 앵커값 0으로 폐기한 요청 {anchor_zero}회")
    if no_data:
        print(f"  [네이버트렌드] 측정값 미제공(검색량 임계 미만) {len(no_data)}개 → 값 비움")
    print(f"  [네이버트렌드] {len(results)}개 키워드 앵커대비 비율 수집 완료")
    return results


def _trend_keyword(event: dict) -> str:
    """트렌드 조회용 키워드. 장소명이 검색량 지표로 더 안정적이다."""
    place = (event.get("place") or "").strip()
    if place and len(place) <= 20:
        return place
    return (event.get("title") or "").strip()[:20]


def apply_naver_trend(events: list, max_keywords=TREND_MAX_KEYWORDS):
    """수집 이벤트에 검색 트렌드 지표를 부여.

    두 컬럼을 채운다:
      - trend_ratio : 앵커('공연') 대비 검색량 비율. 상한 없는 실수.
                      요청 그룹과 무관한 절대 비교값이며, 배수 해석이 가능하다.
                      예) 2.31 = 앵커의 2.31배, 0.0146 = 앵커의 1.5% 수준
      - popularity  : trend_ratio 를 0~100 으로 환산한 정수 (UI 표시용).
                      검색량 분포가 로그 스케일에 가까우므로 log10 후 min-max 환산한다.
                      선형 환산은 상위 소수 키워드가 전 구간을 잡아먹어 변별력이 사라진다.

    ⚠ popularity 는 이번 수집분 내부의 상대 순위이므로 수집 회차가 바뀌면
      기준이 달라진다. 회차 간 비교가 필요하면 trend_ratio 를 써야 한다.
    """
    keywords = []
    for ev in events:
        kw = _trend_keyword(ev)
        if kw and kw not in keywords:
            keywords.append(kw)

    trend = fetch_naver_trend(keywords, max_keywords=max_keywords)
    if not trend:
        for ev in events:
            ev.setdefault("trend_ratio", "")
            ev.setdefault("popularity", "")
        return events

    # log10 기반 0~100 환산 테이블 구성
    import math
    positive = [v for v in trend.values() if v > 0]
    score_of = {}
    if positive:
        logs = {k: math.log10(v) for k, v in trend.items() if v > 0}
        lo, hi = min(logs.values()), max(logs.values())
        span = hi - lo
        for k, lg in logs.items():
            score_of[k] = int(round(100 * (lg - lo) / span)) if span > 0 else 50

    for ev in events:
        kw = _trend_keyword(ev)
        ratio = trend.get(kw)
        if ratio is None:
            ev["trend_ratio"] = ""
            ev["popularity"] = ""
        else:
            ev["trend_ratio"] = ratio
            ev["popularity"] = score_of.get(kw, 0)

    hit = sum(1 for ev in events if ev.get("popularity") != "")
    print(f"  [네이버트렌드] {hit}/{len(events)}건에 지표 부여 "
          f"(앵커 '{TREND_ANCHOR}' 대비 비율 + 0~100 환산)")
    if positive:
        print(f"  [네이버트렌드] trend_ratio 범위: {min(positive):.6f} ~ {max(positive):.4f}")
    return events


# ─────────────────────────────────────────────────────
# 7. 수집 결과 → CSV 저장
# ─────────────────────────────────────────────────────
CULTURE_EVENTS_CSV = os.path.join(BASE_DIR, "..", "data", "culture_events_raw.csv")
CULTURE_HEADERS = ["title", "place", "start", "end", "genre", "realm", "url",
                   "thumbnail", "source", "period_raw", "trend_ratio", "popularity",
                   "crawled_at"]


def save_culture_events(events: list):
    """수집된 공연/전시 이벤트를 CSV로 저장.

    수집이 0건이면 기존 파일을 덮어쓰지 않는다. 예전 구현은 무조건 덮어써서
    수집 전량 실패 시 기존 데이터가 사라질 수 있었다.
    """
    if not events:
        print("  저장할 이벤트 데이터 없음 → 기존 CSV 보존 (덮어쓰기 안 함)")
        return False

    os.makedirs(os.path.dirname(CULTURE_EVENTS_CSV), exist_ok=True)
    with open(CULTURE_EVENTS_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CULTURE_HEADERS, extrasaction="ignore")
        w.writeheader()
        for ev in events:
            ev.setdefault("crawled_at", NOW_STR)
            w.writerow({k: ev.get(k, "") for k in CULTURE_HEADERS})
    print(f"  공연/전시 이벤트 {len(events)}건 저장 → {CULTURE_EVENTS_CSV}")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("  공연/전시 이벤트 수집기 v2.0 (서울·경기)")
    print("=" * 60)

    all_events = []
    stats = {}

    print("\n[1] 공공데이터포털 공연전시 API...")
    got = fetch_culture_events_public_api()
    stats["공공데이터포털"] = len(got)
    all_events += got

    print("\n[2] 서울시 문화행사 API (페이징)...")
    got = fetch_seoul_culture_events(max_rows=3000)
    stats["서울시 문화행사"] = len(got)
    all_events += got

    print("\n[3] 국립현대미술관(MMCA) 내부 API...")
    got = crawl_mmca()
    stats["MMCA"] = len(got)
    all_events += got

    print("\n[4] 서울시립미술관(SeMA)...")
    got = crawl_sema()
    stats["SeMA"] = len(got)
    all_events += got

    print("\n[5] 예술의전당(SAC)...")
    got = crawl_sac()
    stats["예술의전당"] = len(got)
    all_events += got

    # 중복 제거 (title 기준)
    seen = set()
    unique_events = []
    for ev in all_events:
        key = (ev.get("title", "") or "").strip()
        if key and key not in seen:
            seen.add(key)
            ev.setdefault("period_raw", "")
            ev["crawled_at"] = NOW_STR
            unique_events.append(ev)

    print(f"\n총 {len(unique_events)}건 (중복 제거 후, 원본 {len(all_events)}건)")

    print("\n[6] 네이버 데이터랩 인기도 부여 (전량)...")
    apply_naver_trend(unique_events)

    print("\n[7] CSV 저장...")
    saved = save_culture_events(unique_events)

    print("\n" + "=" * 60)
    print("  소스별 수집 결과")
    print("=" * 60)
    for name, cnt in stats.items():
        mark = "OK  " if cnt > 0 else "FAIL"
        print(f"  [{mark}] {name:<16} {cnt:>6}건")
    print("=" * 60)

    if not saved:
        # 수집 전량 실패를 호출자(run_web.py)가 인지할 수 있도록 종료 코드를
        # 1 로 반환한다. 기존에는 0건이어도 exit 0 이라 배치가 SUCCESS 로 표시됐다.
        print("[실패] 수집 결과가 없어 CSV를 갱신하지 않았습니다.")
        sys.exit(1)

    print("[완료] culture_events_raw.csv 저장 완료!")
