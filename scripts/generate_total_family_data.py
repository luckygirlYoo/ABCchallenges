"""
total_family_data.csv 1차 통합 및 스키마 정규화 스크립트 v5.0
=============================================================================
주요 기능:
  1. 5개 수집 소스 통합:
     - 공공 육아·키즈카페 (564건) -> '공공키즈카페'
     - 장소검색 (카카오 로컬 8대 테마: 키즈카페, 계곡, 수영장/물놀이터, 공원, 수목원, 농장, 박물관/과학관, 체험관) -> '사설키즈카페', '자연친화', '가족체험'
     - 서울·경기 공공 문화행사 (200건) -> '문화생활' / '가족체험'
     - 인터파크 티켓 (가족/어린이/아동 전용) -> '문화생활'
     - 티켓링크 티켓 (가족/어린이/아동 전용) -> '문화생활'
  2. 공공키즈카페 vs 사설키즈카페 정밀 분리 및 자연친화 5대 테마 획기적 확충
  3. 중복 제거 및 CSV / JSON 저장
"""
import sys, io, os, re, json, csv, random
from datetime import datetime
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "..", "data")

PATH_CHILDCARE = os.path.join(DATA_DIR, "public_childcare_data.csv")
PATH_CULTURE   = os.path.join(DATA_DIR, "culture_events_raw.csv")
PATH_INTERPARK = os.path.join(DATA_DIR, "live_interpark_tickets.csv")
PATH_TICKETLINK= os.path.join(DATA_DIR, "live_ticketlink_tickets.csv")
# 장소 수집 결과. v7.0 부터 카카오 로컬 기반 place_search_results.csv 를 쓴다.
# 새 수집기를 아직 돌리지 않은 환경에서는 구 파일(naver_search_results.csv)로
# 폴백한다. 폴백이 없으면 이 소스가 0건이 되어 통합 결과가 크게 줄어든다.
PATH_PLACES    = os.path.join(DATA_DIR, "place_search_results.csv")
PATH_NAVER_OLD = os.path.join(DATA_DIR, "naver_search_results.csv")

OUT_CSV  = os.path.join(DATA_DIR, "total_family_data.csv")
OUT_JSON = os.path.join(DATA_DIR, "total_family_data.json")

NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

TARGET_COLS = [
    "source_site", "category", "place_or_event_name", "period",
    "target_age", "region", "fee_info", "description", "booking_url",
    "ai_tags", "crawled_at", "theme_tags", "congestion_score", "popularity_score"
]

def safe_str(val, default=""):
    if pd.isna(val): return default
    return str(val).strip()

def categorize(raw, name="", source=""):
    t = (str(raw) + " " + str(name) + " " + str(source)).lower()
    
    # 1. 공공 키즈카페 & 육아센터
    if any(w in t for w in ['서울형키즈카페', '맘스하트', '아이러브맘', '육아종합지원센터', '공공키즈카페', '우리동네키즈', '어울림센터', '공공']):
        return '공공키즈카페'
        
    # 2. 사설 키즈카페
    if any(w in t for w in ['사설키즈카페', '키즈카페', '키즈룸', '캘리클럽', '챔피언', '바운스', '타요키즈', '뽀로로파크', '헬로방방', '점핑몬스터', '꿀잼키즈룸', '프레리키즈카페', '키즈델루나']):
        return '사설키즈카페'
        
    # 3. 자연친화 (계곡, 수영장, 모래놀이, 공원, 물놀이, 수목원, 피크닉, 유아숲, 해변, 휴양림, 백사장, 숲, 산책)
    if any(w in t for w in ['계곡', '수영장', '모래놀이', '공원', '물놀이', '수목원', '자연', '피크닉', '해변', '숲', '유아숲', '휴양림', '동물원', '생태공원', '바닥분수']):
        return '자연친화'
        
    # 4. 문화생활 (공연, 전시, 콘서트, 연극, 뮤지컬, 클래식, 오페라, 미술관)
    if any(w in t for w in ['공연', '전시', '콘서트', '연극', '뮤지컬', '클래식', '오페라', '티켓링크', '인터파크', '미술관']):
        return '문화생활'
        
    # 5. 가족체험 (미술, 드로잉, 농장, 목장, 박물관, 과학관, 체험관, 체험)
    return '가족체험'

def theme_tags(cat, name=""):
    tags = {
        '공공키즈카페': 'toddler:1.0;indoor:1.0;public:1.0',
        '사설키즈카페': 'toddler:1.0;indoor:0.9;play:1.0',
        '자연친화':    'nature:1.0;outdoor:1.0;picnic:0.8',
        '문화생활':    'culture:1.0;educational:0.9;indoor:0.8',
        '가족체험':    'experience:1.0;family_time:1.0;activity:0.9',
    }.get(cat, 'family:1.0')
    if '계곡' in name or '수영' in name or '물놀이' in name: tags += ';water:1.0'
    if '농장' in name or '동물' in name: tags += ';animal:1.0'
    if '미술' in name or '드로잉' in name: tags += ';drawing:1.0'
    return tags

def ensure_family_tag(ai_tags_str):
    if 'family:' not in str(ai_tags_str):
        return f"family:1.0;{ai_tags_str}" if ai_tags_str else "family:1.0"
    return ai_tags_str

FAMILY_KIDS_KEYWORDS = [
    "어린이", "아동", "키즈", "유아", "가족", "뽀로로", "티니핑", "하츄핑", "핑크퐁",
    "타요", "카봇", "브레드이발소", "캐치", "인형극", "동화", "아기", "아동극", "가족극",
    "아이", "맘스", "생태", "체험", "놀이터", "어린이회관", "어린이뮤지컬", "가족뮤지컬"
]

def is_family_kids_only(ai_tag, cat_raw, name):
    combined = f"{ai_tag} {cat_raw} {name}".lower()
    if any(k in combined for k in ["19세", "청소년 관람불가", "19금", "성인전용"]):
        return False
    if 'family:1.0' in combined or 'baby:1.0' in combined or 'toddler:1.0' in combined:
        return True
    if any(k in combined for k in FAMILY_KIDS_KEYWORDS):
        return True
    return False

# ── 소스별 변환 함수 ──────────────────────────────────────
def from_childcare(df):
    rows = []
    for _, r in df.iterrows():
        name = safe_str(r.get('place_or_event_name', ''))
        cat  = categorize('공공키즈카페', name, safe_str(r.get('source_site', '')))
        rows.append({
            "source_site":         safe_str(r.get('source_site', '공공 육아정보')),
            "category":            cat,
            "place_or_event_name": name,
            "period":              "상시",
            "target_age":          safe_str(r.get('target_age', '영유아 및 어린이')),
            "region":              safe_str(r.get('region', '')),
            "fee_info":            safe_str(r.get('fee_info', '무료/유료')),
            "description":         safe_str(r.get('description', f'{name} 어린이 공공 육아 공간')),
            "booking_url":         safe_str(r.get('booking_url', '')),
            "ai_tags":             ensure_family_tag(safe_str(r.get('ai_tags', ''))),
            "crawled_at":          safe_str(r.get('crawled_at', NOW)),
            "theme_tags":          theme_tags(cat, name),
            # 난수 생성 제거. 측정 소스가 없으면 원본 값을 그대로 넘기고,
            # 원본도 없으면 공란으로 둔다. (기존: randint(1,3) / randint(75,95))
            "congestion_score":    safe_str(r.get('congestion_score', '')),
            "popularity_score":    safe_str(r.get('popularity_score', '')),
        })
    return rows

def from_culture_events(df):
    rows = []
    for _, r in df.iterrows():
        name = safe_str(r.get('title', r.get('place_or_event_name', '')))
        if not name: continue
        cat  = categorize(safe_str(r.get('category', r.get('genre', ''))), name, safe_str(r.get('source_site', '')))
        start = safe_str(r.get('start', r.get('start_date', '')))
        end   = safe_str(r.get('end',   r.get('end_date',   '')))
        period = f"{start} ~ {end}" if start and end else "상시"
        
        venue  = safe_str(r.get('place', r.get('venue', r.get('region', ''))))
        desc   = safe_str(r.get('description', r.get('raw_description', f'{name} 문화 행사')))
        url    = safe_str(r.get('url', r.get('booking_url', '')))
        ai_tag = ensure_family_tag(safe_str(r.get('ai_tags', '')))
        
        rows.append({
            # culture_events_raw.csv 의 출처 컬럼명은 'source' 다.
            # 'source_site' 로만 찾으면 폴백이 걸려 긴 URL이 출처로 표시된다.
            "source_site":         safe_str(r.get('source_site', '')) or safe_str(r.get('source', '')) or '문화행사',
            "category":            cat,
            "place_or_event_name": name,
            "period":              period,
            "target_age":          "전체 (가족/어린이 동반)",
            "region":              venue,
            "fee_info":            safe_str(r.get('fee_info', safe_str(r.get('price', '')))),
            "description":         desc[:200],
            "booking_url":         url,
            "ai_tags":             ai_tag,
            "crawled_at":          safe_str(r.get('crawled_at', NOW)),
            "theme_tags":          theme_tags(cat, name),
            # 난수 생성 제거. (기존: randint(2,4) / randint(60,88))
            # culture_events_raw.csv 의 popularity 는 네이버 데이터랩 실측값이다.
            "congestion_score":    "",
            "popularity_score":    safe_str(r.get('popularity', '')),
        })
    return rows

def from_tickets(df, source_label):
    rows = []
    for _, r in df.iterrows():
        cat_raw = safe_str(r.get('category', ''))
        ai_tag  = safe_str(r.get('ai_tags', ''))
        name    = safe_str(r.get('title', ''))
        if not name: continue
        
        # 가족/어린이/아동 공연만 추출
        if not is_family_kids_only(ai_tag, cat_raw, name):
            continue
            
        cat   = categorize(cat_raw, name, source_label)
        start = safe_str(r.get('start_date', ''))
        end   = safe_str(r.get('end_date', ''))
        period= f"{start} ~ {end}" if start and end else "상시"
        rank  = safe_str(r.get('rank', ''))
        target_age = safe_str(r.get('target_age', ''), "전체 (가족/어린이 동반)")
        
        # rank 기반 계산은 인터파크가 제공하는 실제 순위이므로 유지한다.
        # 다만 rank 를 못 읽었을 때 난수로 메우던 폴백은 제거한다.
        try:   pop = max(50, 100 - int(rank) * 2)
        except: pop = None
        rows.append({
            "source_site":         source_label,
            "category":            cat,
            "place_or_event_name": name,
            "period":              period,
            "target_age":          target_age,
            "region":              safe_str(r.get('venue', '')),
            "fee_info":            safe_str(r.get('price_info', '유료')),
            "description":         safe_str(r.get('description', f'{source_label} 어린이/가족 공연')),
            "booking_url":         safe_str(r.get('booking_url', '')),
            "ai_tags":             ensure_family_tag(ai_tag),
            "crawled_at":          safe_str(r.get('crawled_at', NOW)),
            "theme_tags":          theme_tags(cat, name),
            "congestion_score":    "",
            "popularity_score":    min(100, pop) if pop is not None else "",
        })
    return rows

def from_place_search(df):
    rows = []
    for _, r in df.iterrows():
        name    = safe_str(r.get('place_or_event_name', ''))
        if not name: continue
        cat_raw = safe_str(r.get('category', ''))
        cat     = categorize(cat_raw, name, '장소검색')

        rows.append({
            "source_site":         safe_str(r.get('source_site', '장소검색')),
            "category":            cat,
            "place_or_event_name": name,
            "period":              "상시",
            "target_age":          safe_str(r.get('target_age', '영유아 및 어린이')),
            "region":              safe_str(r.get('region', '')),
            "fee_info":            safe_str(r.get('fee_info', '무료/유료')),
            "description":         safe_str(r.get('description', f'{name} 아기 동반 명소')),
            "booking_url":         safe_str(r.get('booking_url', '')),
            "ai_tags":             ensure_family_tag(safe_str(r.get('ai_tags', ''))),
            "crawled_at":          safe_str(r.get('crawled_at', NOW)),
            "theme_tags":          safe_str(r.get('theme_tags', theme_tags(cat, name))),
            # 기존에는 값이 없으면 2 / 85 를 기본값으로 채워 넣었다.
            "congestion_score":    safe_str(r.get('congestion_score', '')),
            "popularity_score":    safe_str(r.get('popularity_score', '')),
        })
    return rows

def main():
    print("=== total_family_data 통합 생성 시작 v5.0 ===")
    all_rows = []

    if os.path.exists(PATH_CHILDCARE):
        df_child = pd.read_csv(PATH_CHILDCARE, encoding='utf-8-sig')
        r_child = from_childcare(df_child)
        all_rows.extend(r_child)
        print(f"✅ 공공 육아·키즈카페: {len(r_child)}건")

    if os.path.exists(PATH_CULTURE):
        df_cult = pd.read_csv(PATH_CULTURE, encoding='utf-8-sig')
        r_cult = from_culture_events(df_cult)
        all_rows.extend(r_cult)
        print(f"✅ 문화행사: {len(r_cult)}건")

    if os.path.exists(PATH_INTERPARK):
        df_inter = pd.read_csv(PATH_INTERPARK, encoding='utf-8-sig')
        r_inter = from_tickets(df_inter, "인터파크 티켓")
        all_rows.extend(r_inter)
        print(f"✅ 인터파크: {len(r_inter)}건")

    if os.path.exists(PATH_TICKETLINK):
        df_tl = pd.read_csv(PATH_TICKETLINK, encoding='utf-8-sig')
        r_tl = from_tickets(df_tl, "티켓링크")
        all_rows.extend(r_tl)
        print(f"✅ 티켓링크: {len(r_tl)}건")

    place_path = PATH_PLACES if os.path.exists(PATH_PLACES) else PATH_NAVER_OLD
    if os.path.exists(place_path):
        print(f"   (장소 소스: {os.path.basename(place_path)})")
        df_nav = pd.read_csv(place_path, encoding='utf-8-sig')
        r_nav = from_place_search(df_nav)
        all_rows.extend(r_nav)
        print(f"✅ 정밀 장소: {len(r_nav)}건")

    df_all = pd.DataFrame(all_rows)
    b_len = len(df_all)
    df_all = df_all.drop_duplicates(subset=['place_or_event_name'])
    a_len = len(df_all)
    print(f"\n중복 제거: {b_len} → {a_len}건")

    if a_len == 0:
        # 입력 소스가 전부 비면 total_family_data.csv/json 이 통째로 사라진다.
        # 덮어쓰지 않고 종료 코드 1 로 실패를 알린다.
        print(f"[실패] 생성 결과 0건 → 기존 파일 보존 (덮어쓰기 안 함): {OUT_CSV}")
        sys.exit(1)

    os.makedirs(DATA_DIR, exist_ok=True)
    df_all.to_csv(OUT_CSV, index=False, encoding='utf-8-sig')
    print(f"✅ CSV 저장: {OUT_CSV}")

    records = df_all.to_dict(orient='records')
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON 저장: {OUT_JSON}")

    print(f"\n=== 완료! 최종 {a_len}건 ===")

if __name__ == "__main__":
    main()
