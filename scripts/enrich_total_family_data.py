"""
total_family_data.csv 2차 실시간 보강 파이프라인 (Enrichment Engine) v3.0 - 초고속 재사용 & 캐시 추적
=============================================================================
주요 기능:
  1. 기존 naver_enrich_cache.json 자동 백업 (naver_enrich_cache_backup.json)
  2. 기존 캐시 및 기존 CSV/JSON 데이터에 이미 위도/경도 좌표 및 ai_tags가 존재하는 경우, 
     외부 API 호출 없이 즉시 재사용하여 처리 속도를 초고속화
  3. 캐시/기존 데이터에 없는 신규 항목만 카카오 로컬 API(좌표) 및 네이버 플레이스 검색(편의시설) 호출
  4. total_family_data.csv, total_family_data.json, total_family_data.xlsx 최종 저장
"""
import sys, io, os, re, json, csv, random, time, shutil
from datetime import datetime
from urllib.parse import quote
import requests
import pandas as pd

try:
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
except Exception:
    pass

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(BASE_DIR, "..", "data")
is_batch_mode = ("--batch-mode" in sys.argv) or os.environ.get("BATCH_MODE") == "1"
suffix      = "_batch" if is_batch_mode else ""
INPUT_CSV   = os.path.join(DATA_DIR, "total_family_data.csv")
OUTPUT_CSV  = os.path.join(DATA_DIR, f"total_family_data{suffix}.csv")
OUTPUT_JSON = os.path.join(DATA_DIR, f"total_family_data{suffix}.json")
OUTPUT_XLSX = os.path.join(DATA_DIR, f"total_family_data{suffix}.xlsx")
CACHE_FILE  = os.path.join(DATA_DIR, "naver_enrich_cache.json")
BACKUP_CACHE_FILE = os.path.join(DATA_DIR, "naver_enrich_cache_backup.json")

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

# ── 0. 캐시 백업 및 로드 ──────────────────────────────────
cache_data = {}
if os.path.exists(CACHE_FILE):
    try:
        shutil.copy2(CACHE_FILE, BACKUP_CACHE_FILE)
        print(f"📦 기존 캐시 백업 완료: {BACKUP_CACHE_FILE}")
    except Exception as _e:
        print(f"⚠️ 캐시 백업 중 경고: {_e}")

    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        print(f"💾 기존 캐시 {len(cache_data)}건 로드 완료")
    except Exception as _e:
        print(f"⚠️ 캐시 로드 중 오류: {_e}")
        cache_data = {}

def save_cache():
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except:
        pass

# 기존 JSON 데이터 사전 인덱싱 (기존 결과물 재사용)
existing_json_map = {}
if os.path.exists(OUTPUT_JSON):
    try:
        with open(OUTPUT_JSON, 'r', encoding='utf-8') as f:
            records = json.load(f)
            for rec in records:
                name = str(rec.get('place_or_event_name', '')).strip()
                region = str(rec.get('region', '')).strip()
                if name:
                    existing_json_map[name] = rec
                    clean_n = re.sub(r'[^\w\s]', '', name).strip()
                    if clean_n:
                        existing_json_map[clean_n] = rec
                    if region:
                        base_r = region.split('|')[0].strip()
                        existing_json_map[f"{base_r}_{name}"] = rec
        print(f"📦 기존 total_family_data.json ({len(records)}건) 빠른 매핑 완료")
    except Exception as e:
        print(f"⚠️ 기존 JSON 매핑 경고: {e}")

# 카카오 로컬 API 키 (지오코딩용)
_CFG_PATH = os.path.join(BASE_DIR, "config.json")
try:
    with open(_CFG_PATH, "r", encoding="utf-8") as _f:
        CONFIG_KAKAO_KEY = json.load(_f).get("api_keys", {}).get("kakao_api_key", "")
except Exception:
    CONFIG_KAKAO_KEY = ""

KAKAO_KEY = CONFIG_KAKAO_KEY
KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
_kakao_disabled = False

# ── 1. 장소명 클리닝 ────────────────────────────────────
def clean_name(name):
    if not name: return ""
    name = re.sub(r'새\s*창\s*열림|더보기|내돈내산|쿠팡.*|네이버페이.*|쿠폰.*|할인.*|솔직후기.*|주말\s*방문.*', '', str(name))
    name = re.sub(r'\(.*?\)|\[.*?\]', '', name)
    name = re.sub(r'키즈카페검색|아기랑가볼만한곳|아이랑가볼만한곳', '', name)
    name = re.sub(r'[^\w\s\-\.\(\)]', '', name)
    return name.strip()

def dedupe_repeated_suffix(name):
    if not name:
        return name
    prev = None
    while prev != name:
        prev = name
        n = len(name)
        for k in range(n // 2, 1, -1):
            if name[-k:] == name[-2 * k:-k]:
                name = name[:-k]
                break
        else:
            for k in range(n // 2, 3, -1):
                tail = name[-k:]
                if tail in name[:-k]:
                    name = name[:-k]
                    break
    return name.strip()

def normalize_place_name(name):
    if not name:
        return ""
    n = str(name).strip()
    n = re.sub(r'^\d[\d,]*만?\s*명?\s*(이상\s*)?(찾은|방문한|다녀온)\s*', '', n)
    n = re.sub(r'\s*(국내|해외|추천|모음|총정리|베스트|TOP\s*\d+)\s*$', '', n)
    n = dedupe_repeated_suffix(n)
    return n.strip()

_ADMIN_RE = re.compile(
    r'^((?:서울|경기|인천|부산|대구|광주|대전|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주)\S*)'
    r'\s+(\S*(?:구|시|군))'
)

def build_search_query(name, region):
    name = normalize_place_name(name)
    base = (region or "").split('|')[0].strip()

    prefix = ""
    am = _ADMIN_RE.match(base)
    if am:
        prefix = f"{am.group(1)} {am.group(2)}"

    if not name:
        return base

    if prefix and len(name) <= 4:
        return f"{prefix} {name}".strip()
    return name

def geocode_kakao(name, region):
    global _kakao_disabled

    if _kakao_disabled or not KAKAO_KEY or KAKAO_KEY.startswith("YOUR_"):
        return None, None

    query = build_search_query(name, region)
    if not query:
        return None, None

    try:
        r = requests.get(
            KAKAO_KEYWORD_URL,
            headers={"Authorization": f"KakaoAK {KAKAO_KEY}"},
            params={"query": query, "size": 1},
            timeout=4,
        )
        if r.status_code in (401, 403):
            _kakao_disabled = True
            return None, None
        if r.status_code != 200:
            return None, None

        docs = r.json().get("documents", [])
        if not docs:
            return None, None
        d = docs[0]
        return d.get("y"), d.get("x")
    except Exception:
        return None, None

_CONV_RE = re.compile(r'"conveniences"\s*:\s*\[([^\]]*)\]')

def parse_conveniences(html):
    m = _CONV_RE.search(html)
    if not m:
        return None
    items = re.findall(r'"([^"]+)"', m.group(1))
    return [it.replace(chr(92) + 'u002F', '/') for it in items]

# ── 2. 초고속 캐시 & 기존 데이터 조회 ──────────────────────
def fetch_naver_realtime_info(name, region, existing_row=None):
    """
    1) naver_enrich_cache.json 또는 기존 데이터(existing_row/json)에 존재하는 경우
       외부 API (카카오/네이버) 호출을 즉시 스킵하고 데이터 사용.
    2) 미존재 신규 항목만 선택적으로 카카오 지오코딩 및 네이버 검색 실행.
    """
    c_name = clean_name(name) or name
    base_addr = (region or "").split('|')[0].strip()

    # 이미 위도/경도가 들어있는 입력 행인 경우
    _m = re.search(r'위도:([\d.]+), 경도:([\d.]+)', region or '')
    row_lat = _m.group(1) if _m else None
    row_lng = _m.group(2) if _m else None

    # 다중 캐시 키 조회
    candidate_keys = [
        f"{region}_{name}",
        f"{region}_{c_name}",
        f"{base_addr}_{name}",
        f"{base_addr}_{c_name}",
        f"{name}",
        f"{c_name}"
    ]

    for k in candidate_keys:
        if k in cache_data and cache_data[k] is not None:
            c = cache_data[k]
            if not c.get("lat") and row_lat:
                c["lat"], c["lng"] = row_lat, row_lng
            return c

        if k in existing_json_map:
            rec = existing_json_map[k]
            _m2 = re.search(r'위도:([\d.]+), 경도:([\d.]+)', rec.get('region', ''))
            e_lat = _m2.group(1) if _m2 else row_lat
            e_lng = _m2.group(2) if _m2 else row_lng
            tags = str(rec.get('ai_tags', ''))
            return {
                "lat": e_lat,
                "lng": e_lng,
                "amenities_known": True,
                "conveniences": [],
                "parking":       ("parking:1.0" in tags),
                "kids_facility": ("kids_facility:1.0" in tags),
                "restroom":      ("restroom:1.0" in tags),
                "wifi":          ("wifi:1.0" in tags),
            }

    # 입력 행 자체에 이미 좌표가 존재할 때 API 스킵
    if row_lat and row_lng:
        tags = str(existing_row.get('ai_tags', '') if existing_row is not None else '')
        res = {
            "lat": row_lat,
            "lng": row_lng,
            "amenities_known": False,
            "conveniences": [],
            "parking":       ("parking:1.0" in tags),
            "kids_facility": ("kids_facility:1.0" in tags),
            "restroom":      ("restroom:1.0" in tags),
            "wifi":          False,
        }
        cache_data[f"{base_addr}_{c_name}"] = res
        return res

    # 신규 항목만 KAKAO & NAVER API 호출
    lat, lng = geocode_kakao(name, region)
    conv = None
    query = build_search_query(name, region)
    search_url = f"https://search.naver.com/search.naver?where=nexearch&query={quote(query)}"

    try:
        r = requests.get(search_url, headers=HTTP_HEADERS, timeout=4)
        if r.status_code == 200:
            conv = parse_conveniences(r.text)
    except Exception:
        pass

    joined = " ".join(conv) if conv else ""
    result = {
        "lat": lat,
        "lng": lng,
        "amenities_known": conv is not None,
        "conveniences": conv or [],
        "parking":       ("주차" in joined),
        "kids_facility": ("유아시설" in joined or "놀이방" in joined),
        "restroom":      ("화장실" in joined),
        "wifi":          ("인터넷" in joined or "와이파이" in joined),
    }

    primary_key = f"{base_addr}_{c_name}"
    cache_data[primary_key] = result
    return result

# ── 3. 편의시설 태그 조합 ──────────────────────────────
def build_ai_tags(real_info, cat, orig_tags):
    tags = ["family:1.0"]

    if real_info.get("parking"):
        tags.append("parking:1.0")
    if real_info.get("kids_facility"):
        tags.append("kids_facility:1.0")
    if real_info.get("restroom"):
        tags.append("restroom:1.0")

    if '키즈카페' in cat or '놀이터' in cat: tags.append("play:1.0")
    if '물놀이' in cat or '자연' in cat: tags.append("water:1.0")
    if '체험' in cat: tags.append("experience:1.0")
    if '문화' in cat or '티켓' in cat: tags.append("culture:1.0")

    existing_list = [t.strip() for t in str(orig_tags).split(';') if t.strip() and ':' not in t and t not in tags]
    all_tags = tags + existing_list
    return ";".join(dict.fromkeys(all_tags))

# ── 4. 추천 이유 및 설명 생성 ────────────────────────────
def generate_recommend_reason(name, cat, ai_tags, real_info):
    conv = real_info.get("conveniences") or []
    if real_info.get("parking") and real_info.get("kids_facility"):
        return "🅿️ 주차 가능 · 🧸 유아시설 보유 (네이버 플레이스 등록 정보)"
    elif real_info.get("parking"):
        return "🅿️ 주차 가능 (네이버 플레이스 등록 정보)"
    elif real_info.get("kids_facility"):
        return "🧸 유아시설 보유 (네이버 플레이스 등록 정보)"
    elif 'water:1.0' in ai_tags:
        return "🌊 시원한 물놀이와 야외 활동을 한 번에 즐길 수 있는 여름 인기 장소"
    elif 'play:1.0' in ai_tags or '키즈' in cat:
        return "🧸 영유아 안심 실내 놀이기구와 부모 쉼터가 잘 갖춰진 키즈 파라다이스"
    elif 'culture:1.0' in ai_tags or '문화' in cat:
        return "🎨 아이들 눈높이에 맞춘 체험형 관람 코스로 교육과 재미를 동시 만족"
    else:
        return "👨‍👧 아빠와 아이가 주말에 부담 없이 특별한 추억을 만들 수 있는 베스트 추천지"

_LEGACY_DESC_MARKERS = (
    "실시간 네이버 검색 기반으로",
    "주말 아이 동반 최적 명소입니다",
    "연령대 아이와 아빠가 함께 방문하기에 적극 추천",
)

def _is_legacy_template(text):
    return any(mk in text for mk in _LEGACY_DESC_MARKERS)

def generate_llm_description(name, cat, region, target_age, original="", real_info=None):
    original = (original or "").strip()
    if original and not _is_legacy_template(original) and original.lower() not in ("nan", "none"):
        return original[:400]

    reg_clean = region.split('|')[0].strip() if region else "수도권"
    parts = [f"[{name}]는 {reg_clean} 지역의 {cat} 장소입니다."]

    conv = (real_info or {}).get("conveniences") or []
    if conv:
        parts.append("네이버 플레이스 등록 편의시설: " + ", ".join(conv[:5]) + ".")

    if target_age and target_age.lower() not in ("nan", "none"):
        parts.append(f"대상 연령: {target_age}.")
    return " ".join(parts)

# ── 5. 메인 보강 파이프라인 ────────────────────────────────
def enrich_data():
    start_time = time.time()
    initial_cache_len = len(cache_data)
    print("=" * 75)
    print(f"  total_family_data.csv 2차 보강 파이프라인 구동 (현재 캐시: {initial_cache_len}건)")
    print("=" * 75)

    if not os.path.exists(INPUT_CSV):
        print(f"❌ 입력 파일 없음: {INPUT_CSV}")
        return

    df = pd.read_csv(INPUT_CSV, encoding='utf-8-sig')
    print(f"📥 기존 데이터 {len(df)}건 로드 완료")

    enriched_rows = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cache_hits = 0
    api_calls = 0

    count = 0
    for idx, row in df.iterrows():
        raw_name   = str(row.get('place_or_event_name', '')).strip()
        c_name     = clean_name(raw_name) or raw_name
        category   = str(row.get('category', '가족체험')).strip()
        orig_region= str(row.get('region', '')).strip()
        target_age = str(row.get('target_age', '영유아 및 어린이')).strip()
        fee_info   = str(row.get('fee_info', '무료/유료')).strip()
        orig_tags  = str(row.get('ai_tags', '')).strip()

        # 1) 캐시 / 기존 데이터 우선 적용
        prev_len = len(cache_data)
        real_info = fetch_naver_realtime_info(c_name, orig_region, existing_row=row)

        if len(cache_data) == prev_len:
            cache_hits += 1
        else:
            api_calls += 1

        # 2) 좌표 연동 region 포맷
        base_addr = orig_region.split('|')[0].strip() if orig_region else f"수도권 {c_name}"
        lat = real_info.get("lat")
        lng = real_info.get("lng")

        if lat and lng:
            region_fmt = f"{base_addr} | 위도:{lat}, 경도:{lng}"
        else:
            _m = re.search(r'위도:([\d.]+), 경도:([\d.]+)', orig_region)
            if _m:
                region_fmt = f"{base_addr} | 위도:{_m.group(1)}, 경도:{_m.group(2)}"
            else:
                region_fmt = base_addr

        # 3) ai_tags
        new_ai_tags = build_ai_tags(real_info, category, orig_tags)

        # 4) 인기도 & 혼잡도
        def _passthrough(key, valid=None):
            raw = str(row.get(key, '')).strip()
            if raw in ('', 'nan', 'None'):
                return ""
            try:
                v = int(float(raw))
            except (TypeError, ValueError):
                return ""
            if valid is not None and v not in valid:
                return ""
            return v

        pop_score  = _passthrough('popularity_score')
        cong_score = _passthrough('congestion_score', valid=[1, 2, 3, 4, 5])

        # 5) 설명 및 추천 이유
        original_desc = str(row.get('description', '')).strip()
        description = generate_llm_description(
            c_name, category, base_addr, target_age,
            original=original_desc, real_info=real_info)
        recommend_reason = generate_recommend_reason(c_name, category, new_ai_tags, real_info)

        enriched_rows.append({
            "source_site":         str(row.get('source_site', '네이버 추천')),
            "category":            category,
            "place_or_event_name": c_name,
            "period":              str(row.get('period', '상시')),
            "target_age":          target_age,
            "region":              region_fmt,
            "fee_info":            fee_info,
            "description":         description,
            "booking_url":         str(row.get('booking_url', 'https://search.naver.com')),
            "ai_tags":             new_ai_tags,
            "crawled_at":          now_str,
            "theme_tags":          str(row.get('theme_tags', 'family:1.0')),
            "congestion_score":    cong_score,
            "popularity_score":    pop_score,
            "recommend_reason":    recommend_reason
        })

        count += 1
        if count % 2000 == 0 or count == len(df):
            elapsed = time.time() - start_time
            print(f"  [보강 진행] {count}/{len(df)}건 완료 (캐시/기존 재사용: {cache_hits}건, API 신규: {api_calls}건, 현재 캐시 건수: {len(cache_data)}건, 소요시간: {elapsed:.1f}초)")
            save_cache()

    save_cache()

    # DataFrame 생성 및 중복 제거
    res_df = pd.DataFrame(enriched_rows)
    res_df = res_df.drop_duplicates(subset=['place_or_event_name'])
    final_len = len(res_df)

    # 1) CSV 저장
    res_df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
    print(f"✅ 보강된 CSV 저장 완료: {OUTPUT_CSV} ({final_len}건)")

    # 2) JSON 저장
    json_records = res_df.to_dict(orient='records')
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(json_records, f, ensure_ascii=False, indent=2)
    print(f"✅ 보강된 JSON 저장 완료: {OUTPUT_JSON} ({final_len}건)")

    # 3) XLSX (엑셀) 저장
    try:
        res_df.to_excel(OUTPUT_XLSX, index=False, engine='openpyxl')
        print(f"✅ 보강된 XLSX 엑셀 저장 완료: {OUTPUT_XLSX} ({final_len}건)")
    except Exception as e:
        print(f"⚠️ XLSX 저장 경고: {e}")

    total_time = time.time() - start_time
    print(f"✨ 총 소요시간: {total_time:.1f}초 | 최종 캐시 건수: {len(cache_data)}건 (새로 추가된 캐시: {len(cache_data) - initial_cache_len}건)")
    print("=" * 75)

if __name__ == "__main__":
    enrich_data()
