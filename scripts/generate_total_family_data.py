"""
total_family_data.csv 1차 통합 및 스키마 정규화 스크립트 v5.0
=============================================================================
주요 기능:
  1. 5개 수집 소스 통합:
     - 공공 육아·키즈카페 (564건) -> '공공키즈카페'
     - 네이버 장소검색 (9대 테마: 사설키즈카페, 계곡, 수영장, 모래놀이, 공원, 물놀이터, 미술, 농장체험, 박물관) -> '사설키즈카페', '자연친화', '가족체험'
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
PATH_NAVER     = os.path.join(DATA_DIR, "naver_search_results.csv")

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
            "congestion_score":    random.randint(1, 3),
            "popularity_score":    random.randint(75, 95),
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
            "source_site":         safe_str(r.get('source_site', url or '문화행사')),
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
            "congestion_score":    random.randint(2, 4),
            "popularity_score":    random.randint(60, 88),
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
        
        try:   pop = max(50, 100 - int(rank) * 2)
        except: pop = random.randint(65, 92)
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
            "congestion_score":    random.randint(3, 5),
            "popularity_score":    min(100, pop),
        })
    return rows

def from_naver_search(df):
    rows = []
    for _, r in df.iterrows():
        name    = safe_str(r.get('place_or_event_name', ''))
        if not name: continue
        cat_raw = safe_str(r.get('category', ''))
        cat     = categorize(cat_raw, name, '네이버 장소검색')

        rows.append({
            "source_site":         safe_str(r.get('source_site', '네이버 장소검색')),
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
            "congestion_score":    int(r.get('congestion_score', 2)),
            "popularity_score":    int(r.get('popularity_score', 85)),
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

    if os.path.exists(PATH_NAVER):
        df_nav = pd.read_csv(PATH_NAVER, encoding='utf-8-sig')
        r_nav = from_naver_search(df_nav)
        all_rows.extend(r_nav)
        print(f"✅ 네이버 정밀 장소: {len(r_nav)}건")

    df_all = pd.DataFrame(all_rows)
    b_len = len(df_all)
    df_all = df_all.drop_duplicates(subset=['place_or_event_name'])
    a_len = len(df_all)
    print(f"\n중복 제거: {b_len} → {a_len}건")

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
