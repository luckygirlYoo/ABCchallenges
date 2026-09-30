"""
total_single_data.csv 2차 실시간 보강 파이프라인 (Enrichment Engine) v2.0 - 초고속 재사용 최적화
=============================================================================
주요 기능:
  1. 기존 total_single_data.json 및 캐시(naver_enrich_cache_single.json)에 이미 존재하는 
     행사나 장소는 기존 편의시설, ai_tags, 좌표, 설명, 추천이유를 그대로 재사용하고 API 호출을 skip!
  2. 존재하지 않는 신규 장소에 대해서만 Kakao API 및 검색을 수행하여 
     예약 필요 여부, 주차 가능 여부, 좌표, ai_tags 등을 검색
  3. total_single_data.csv, total_single_data.json, total_single_data.xlsx 엑셀 최종 저장
"""
import sys, io, os, re, json, csv, random, time, shutil
from datetime import datetime
from urllib.parse import quote
import requests
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(BASE_DIR, "..", "data")
INPUT_CSV   = os.path.join(DATA_DIR, "total_single_data.csv")
OUTPUT_CSV  = os.path.join(DATA_DIR, "total_single_data.csv")
OUTPUT_JSON = os.path.join(DATA_DIR, "total_single_data.json")
OUTPUT_XLSX = os.path.join(DATA_DIR, "total_single_data.xlsx")
CACHE_FILE  = os.path.join(DATA_DIR, "naver_enrich_cache_single.json")

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

# ── 카카오 로컬 API 키 ──────────────────────────────────
_CFG_PATH = os.path.join(BASE_DIR, "config.json")
try:
    with open(_CFG_PATH, "r", encoding="utf-8") as _f:
        CONFIG_KAKAO_KEY = json.load(_f).get("api_keys", {}).get("kakao_api_key", "")
except Exception:
    CONFIG_KAKAO_KEY = ""

KAKAO_KEY = CONFIG_KAKAO_KEY
KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"

# ── 캐시 및 기존 JSON 로드 ──────────────────────────────
cache_data = {}
if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
    except Exception:
        cache_data = {}

def save_cache():
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ── 기존 total_single_data.json 읽기 (가장 정확한 1순위 재사용 원천) ──
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
        print(f"📦 기존 total_single_data.json ({len(records)}건) 빠른 매핑 완료")
    except Exception as e:
        print(f"⚠️ 기존 JSON 로드 경고: {e}")

# ── 1. 장소명 클리닝 ────────────────────────────────────
def clean_name(name):
    if not name:
        return ""
    name = re.sub(r'새\s*창\s*열림|더보기|내돈내산|쿠팡.*|네이버페이.*|쿠폰.*|할인.*|솔직후기.*', '', str(name))
    name = re.sub(r'\(.*?\)|\[.*?\]', '', name)
    name = re.sub(r'[^\w\s\-\.\(\)]', '', name)
    return name.strip()

# ── 2. Kakao Local API 키워드 검색 (좌표 및 장소 파악) ─────
def geocode_kakao(name, region):
    if not KAKAO_KEY or KAKAO_KEY.startswith("YOUR_"):
        return None, None, {}

    clean_r = region.split('|')[0].strip() if region else ""
    query = f"{clean_r} {name}".strip() if clean_r else name

    try:
        r = requests.get(
            KAKAO_KEYWORD_URL,
            headers={"Authorization": f"KakaoAK {KAKAO_KEY}"},
            params={"query": query, "size": 1},
            timeout=5
        )
        if r.status_code == 200:
            docs = r.json().get("documents", [])
            if docs:
                d = docs[0]
                # 카카오: x=경도(lng), y=위도(lat)
                return d.get("y"), d.get("x"), d
    except Exception:
        pass
    return None, None, {}

def fetch_single_realtime_info(name, region):
    """
    1) 기존 total_single_data.json 또는 캐시에 존재하면 API 스킵 & 즉시 재사용.
    2) 없을 때만 Kakao API 및 검색 호출.
    """
    clean_r = region.split('|')[0].strip() if region else ""
    c_name = clean_name(name) or name

    # 1. 기존 json/캐시 키 후보들
    candidate_keys = [
        f"{region}_{name}",
        f"{clean_r}_{name}",
        f"{clean_r}_{c_name}",
        name,
        c_name
    ]

    for k in candidate_keys:
        if k in existing_json_map:
            rec = existing_json_map[k]
            _m = re.search(r'위도:([\d.]+), 경도:([\d.]+)', rec.get('region', ''))
            lat = _m.group(1) if _m else None
            lng = _m.group(2) if _m else None
            tags = str(rec.get('ai_tags', ''))
            return {
                "from_existing": True,
                "existing_record": rec,
                "lat": lat,
                "lng": lng,
                "wifi": ("wifi:1.0" in tags),
                "outlet": ("outlet:1.0" in tags),
                "is_24h": ("24h:1.0" in tags),
                "parking": ("parking:1.0" in tags),
                "reservation": ("reservation_required:1.0" in tags),
            }

        if k in cache_data and cache_data[k] is not None:
            c_info = cache_data[k]
            c_info["from_existing"] = False
            return c_info

    # 2. 캐시에 없으므로 KAKAO API 호출
    lat, lng, kakao_doc = geocode_kakao(name, region)

    # 기본 검색어 검증
    query = f"{clean_r} {name}".strip()
    search_url = f"https://search.naver.com/search.naver?where=nexearch&query={quote(query)}"

    has_wifi, has_outlet, is_24h, has_parking, needs_reservation = False, False, False, False, False

    # 카카오 카테고리나 네이버 검색 결과로 편의시설 추론
    cat_name = kakao_doc.get("category_name", "")
    if "주차" in cat_name or "발렛" in cat_name:
        has_parking = True

    try:
        r = requests.get(search_url, headers=HTTP_HEADERS, timeout=4)
        if r.status_code == 200:
            html = r.text
            has_wifi        = any(k in html for k in ["와이파이", "wifi", "WIFI", "무선인터넷"])
            has_outlet      = any(k in html for k in ["콘센트", "전원", "충전"])
            is_24h          = any(k in html for k in ["24시간", "밤샘", "심야운영"])
            has_parking     = has_parking or any(k in html for k in ["주차", "주차장", "발렛", "무료주차"])
            needs_reservation = any(k in html for k in ["예약필수", "예약 필수", "사전예약", "예약제", "네이버예약"])
    except Exception:
        pass

    result = {
        "from_existing": False,
        "lat": lat, "lng": lng,
        "wifi": has_wifi, "outlet": has_outlet, "is_24h": is_24h,
        "parking": has_parking, "reservation": needs_reservation,
    }

    cache_key = f"{clean_r}_{c_name}"
    cache_data[cache_key] = result
    return result

def sanitize_single_tags(tags_str):
    if not tags_str:
        return "single:1.0"
    toks = [t.strip() for t in str(tags_str).split(';') if t.strip()]
    cleaned = ["single:1.0"]
    for t in toks:
        if t.startswith("family:") or t.startswith("couple:") or t in ["family", "couple"]:
            continue
        if t not in cleaned:
            cleaned.append(t)
    return ";".join(cleaned)

# ── 3. 편의시설 태그 조합 ──────────────────────────────
def build_ai_tags(real_info, cat, orig_tags):
    tags = ["single:1.0"]

    if real_info.get("wifi"):   tags.append("wifi:1.0")
    if real_info.get("outlet"): tags.append("outlet:1.0")
    if real_info.get("is_24h"): tags.append("24h:1.0")
    if real_info.get("parking"): tags.append("parking:1.0")
    if real_info.get("reservation"): tags.append("reservation_required:1.0")

    if '독립서점' in cat or '북카페' in cat: tags.append("bookstore:1.0")
    if '힐링' in cat: tags.append("healing:1.0")
    if '역사' in cat or '문화' in cat: tags.append("culture:1.0")
    if '자연' in cat or '공원' in cat: tags.append("nature:1.0")
    if '콘서트' in cat or '공연' in cat: tags.append("performance:1.0")
    if '전시' in cat or '미술관' in cat: tags.append("exhibition:1.0")

    existing_list = [t.strip() for t in str(orig_tags).split(';') if t.strip() and not t.startswith("family") and not t.startswith("couple") and t not in tags]
    all_tags = tags + existing_list
    return ";".join(dict.fromkeys(all_tags))

# ── 4. 추천 이유 및 설명 생성 ────────────────────────────
def generate_recommend_reason(name, cat, ai_tags, real_info):
    if real_info.get("wifi") and real_info.get("outlet"):
        return "🔌 와이파이·콘센트 완비로 혼자 몰입하기 완벽한 공간"
    elif real_info.get("is_24h"):
        return "🌙 24시간 운영 — 시간 눈치 안 보고 혼자 여유롭게 머물기 좋은 곳"
    elif real_info.get("parking"):
        return "🅿️ 주차 지원으로 혼자 편하게 방문하기 좋은 곳"
    elif 'bookstore:1.0' in ai_tags:
        return "📚 혼자만의 시간을 보내기 좋은 조용한 독서 공간"
    elif 'healing:1.0' in ai_tags:
        return "🌿 혼자 사색하며 힐링하기 좋은 장소"
    elif 'performance:1.0' in ai_tags:
        return "🎵 몰입감 있는 공연으로 혼자 즐기기 좋은 라이브 콘텐츠"
    elif 'exhibition:1.0' in ai_tags:
        return "🖼️ 조용히 몰입할 수 있는 전시 콘텐츠로 나 홀로 관람 최적"
    elif 'culture:1.0' in ai_tags:
        return "🏯 깊이 있게 둘러보기 좋은 역사·문화 명소"
    elif 'nature:1.0' in ai_tags:
        return "🌳 혼자 걷기 좋은 자연 친화 공간"
    else:
        return "🙋 혼자 즐기기 좋은 싱글 추천 명소"

def generate_llm_description(name, cat, region, target_age):
    reg_clean = region.split('|')[0].strip() if region else "수도권"
    return (
        f"[{name}]는 {reg_clean} 지역에 위치한 혼자를 위한 최적의 공간입니다. "
        f"와이파이·콘센트·주차 등 편의시설이 잘 갖춰져 있으며, "
        f"{cat}을(를) 좋아하는 {target_age}에게 적극 추천합니다."
    )

# ── 5. 메인 보강 파이프라인 ────────────────────────────────
def enrich_data():
    start_time = time.time()
    print("=" * 75)
    print("  total_single_data.csv 2차 보강 파이프라인 (기존 데이터 재사용 최적화) 구동")
    print("=" * 75)

    if not os.path.exists(INPUT_CSV):
        print(f"❌ 입력 파일 없음: {INPUT_CSV}")
        return

    df = pd.read_csv(INPUT_CSV, encoding='utf-8-sig')
    print(f"📥 기존 데이터 {len(df)}건 로드 완료")

    enriched_rows = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    skipped_count = 0
    api_count = 0

    count = 0
    for idx, row in df.iterrows():
        raw_name    = str(row.get('place_or_event_name', '')).strip()
        c_name      = clean_name(raw_name) or raw_name
        category    = str(row.get('category', '전시·미술관')).strip()
        orig_region = str(row.get('region', '')).strip()
        target_age  = str(row.get('target_age', '성인 (개인 방문 적합)')).strip()
        fee_info    = str(row.get('fee_info', '')).strip()
        orig_tags   = str(row.get('ai_tags', '')).strip()

        # 1) 기존 데이터/캐시 확인 (있으면 즉시 재사용 & API 스킵)
        real_info = fetch_single_realtime_info(c_name, orig_region)

        if real_info.get("from_existing") and real_info.get("existing_record"):
            # 기존 JSON 항목 그대로 보존/재사용!
            rec = real_info["existing_record"]
            enriched_rows.append({
                "source_site":         str(rec.get('source_site', row.get('source_site', '네이버 추천'))),
                "category":            str(rec.get('category', category)),
                "place_or_event_name": c_name,
                "period":              str(rec.get('period', row.get('period', '상시'))),
                "target_age":          target_age,
                "region":              str(rec.get('region', orig_region)),
                "fee_info":            str(rec.get('fee_info', fee_info)),
                "description":         str(rec.get('description', generate_llm_description(c_name, category, orig_region, target_age))),
                "booking_url":         str(rec.get('booking_url', row.get('booking_url', 'https://search.naver.com'))),
                "ai_tags":             sanitize_single_tags(str(rec.get('ai_tags', orig_tags))),
                "crawled_at":          now_str,
                "theme_tags":          str(rec.get('theme_tags', 'single:1.0')),
                "congestion_score":    rec.get('congestion_score', row.get('congestion_score', 2)),
                "popularity_score":    rec.get('popularity_score', row.get('popularity_score', 75)),
                "recommend_reason":    str(rec.get('recommend_reason', '🙋 혼자 즐기기 좋은 싱글 추천 명소'))
            })
            skipped_count += 1
        else:
            # 2) 신규 항목만 KAKAO API & 실검증 진행
            api_count += 1
            base_addr = orig_region.split('|')[0].strip() if orig_region else f"수도권 {c_name}"
            lat = real_info.get("lat")
            lng = real_info.get("lng")
            region_fmt = f"{base_addr} | 위도:{lat}, 경도:{lng}" if (lat and lng) else base_addr

            new_ai_tags = build_ai_tags(real_info, category, orig_tags)

            pop_score = row.get('popularity_score', 75)
            cong_score = row.get('congestion_score', 2)

            description = generate_llm_description(c_name, category, base_addr, target_age)
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
                "theme_tags":          str(row.get('theme_tags', 'single:1.0')),
                "congestion_score":    cong_score,
                "popularity_score":    pop_score,
                "recommend_reason":    recommend_reason
            })

        count += 1
        if count % 500 == 0 or count == len(df):
            print(f"  [보강 진행] {count}/{len(df)}건 완료 (기존 재사용: {skipped_count}건, API 신규: {api_count}건)")
            save_cache()

    save_cache()

    # DataFrame 생성 및 중복 제거
    res_df = pd.DataFrame(enriched_rows)
    b_len = len(res_df)
    res_df = res_df.drop_duplicates(subset=['place_or_event_name', 'region'])
    final_len = len(res_df)
    print(f"\n중복 제거: {b_len} → {final_len}건")

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
        print(f"⚠️ XLSX 엑셀 저장 경고: {e}")

    total_time = time.time() - start_time
    print(f"✨ 완료! 총 소요시간: {total_time:.1f}초 (기존 데이터 재사용: {skipped_count}/{count}건)")
    print("=" * 75)

if __name__ == "__main__":
    enrich_data()
