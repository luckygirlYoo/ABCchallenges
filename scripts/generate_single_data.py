"""
total_single_data.csv / total_single_data.json 통합 생성 스크립트 v1.0
=============================================================================
generate_total_family_data.py 와 동일한 설계를 '싱글매니아' 세그먼트에 맞춰 재구성.

주요 기능:
  1. 3개 기존 수집 소스를 싱글 친화 기준으로 필터링·통합
     - 서울/경기 공공 문화행사   (culture_events_raw.csv) -> 전시·미술관 / 역사·문화 / 콘서트·공연
     - 인터파크 실시간 티켓      (live_interpark_tickets.csv)
     - 티켓링크 실시간 티켓      (live_ticketlink_tickets.csv)
  2. ai_tags 안의 'single:x.x' 점수를 파싱해서 SINGLE_SCORE_THRESHOLD 미만은 제외
  3. app.js THEMES.single 6종 카테고리로 재분류
     (전시·미술관 / 독립서점 / 콘서트·공연 / 조용한 힐링 / 역사·문화 / 자연·공원)
  4. 혼잡도(congestion_score), 인기도(popularity_score), 추천 사유(recommend_reason) 산출
  5. total_single_data.csv / total_single_data.json 저장

주의: 독립서점/조용한 힐링 카테고리는 현재 원천 데이터에 해당 소스가 없어 비어 있을 수 있음.
      -> 하단 "외부 API 추가 제안" 참고 (naver_place_collector 등 신규 수집기 필요)
"""
import sys, io, os, re, json, csv, random
from datetime import datetime
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")

PATH_CULTURE    = os.path.join(DATA_DIR, "culture_events_raw.csv")
PATH_INTERPARK  = os.path.join(DATA_DIR, "live_interpark_tickets.csv")
PATH_TICKETLINK = os.path.join(DATA_DIR, "live_ticketlink_tickets.csv")
PATH_NAVER_SINGLE = os.path.join(DATA_DIR, "naver_single_places.csv")  # naver_local_single_collector.py 결과
PATH_BOOKSTORE = os.path.join(DATA_DIR, "independent_bookstores.csv")  # independent_bookstore_collector.py 결과

OUT_CSV  = os.path.join(DATA_DIR, "total_single_data.csv")
OUT_JSON = os.path.join(DATA_DIR, "total_single_data.json")

NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# app.js THEMES.single 6종과 동일한 카테고리 체계
SINGLE_THEME_TAGS = {
    "전시·미술관": "exhibition:1.0;quiet:0.8;indoor:0.9",
    "독립서점":     "bookstore:1.0;quiet:1.0;indoor:1.0",
    "콘서트·공연":  "concert:1.0;immersive:0.9;indoor:0.7",
    "조용한 힐링":  "healing:1.0;quiet:1.0;solo:1.0",
    "역사·문화":    "culture:1.0;history:0.9;outdoor:0.5",
    "자연·공원":    "nature:1.0;outdoor:1.0;walk:0.9",
}

SINGLE_SCORE_THRESHOLD = 0.6  # 이 미만이면 싱글 추천에서 제외

TARGET_COLS = [
    "source_site", "category", "place_or_event_name", "period",
    "target_age", "region", "fee_info", "description", "booking_url",
    "ai_tags", "crawled_at", "theme_tags", "congestion_score",
    "popularity_score", "recommend_reason",
]


def safe_str(val, default=""):
    if pd.isna(val):
        return default
    return str(val).strip()


def parse_single_score(ai_tags_str):
    """'family:0.5;couple:0.9;single:0.8;...' 문자열에서 single 점수만 파싱"""
    if not ai_tags_str:
        return 0.0
    for part in str(ai_tags_str).split(";"):
        part = part.strip()
        if part.startswith("single:"):
            try:
                return float(part.split(":")[1])
            except (IndexError, ValueError):
                return 0.0
    return 0.0


def ensure_single_tag(ai_tags_str, score=0.8):
    """single: 태그가 없으면 강제로 부여 (family 파이프라인의 ensure_family_tag 대응)"""
    s = str(ai_tags_str or "")
    if "single:" not in s:
        return f"single:{score};{s}" if s else f"single:{score}"
    return s


def categorize_single(genre_or_cat, name="", venue=""):
    """싱글 6대 테마로 분류 (helpers.py single_keywords + app.js THEME_FILTER 참고)"""
    t = f"{genre_or_cat} {name} {venue}".lower()

    if any(w in t for w in ["서점", "북카페", "북스토어", "책방"]):
        return "독립서점"
    if any(w in t for w in ["미술관", "전시", "갤러리", "박물관"]):
        return "전시·미술관"
    if any(w in t for w in ["콘서트", "공연", "페스티벌", "무용", "클래식", "오페라", "연극", "뮤지컬"]):
        return "콘서트·공연"
    if any(w in t for w in ["명상", "요가", "산책", "힐링", "카공", "스터디카페", "독서"]):
        return "조용한 힐링"
    if any(w in t for w in ["고궁", "사찰", "유적", "문화유산", "역사"]):
        return "역사·문화"
    if any(w in t for w in ["공원", "수목원", "정원", "산", "둘레길", "생태"]):
        return "자연·공원"
    return "전시·미술관"  # 기본값(콘텐츠 비중이 가장 큰 카테고리)


def theme_tags_single(cat):
    return SINGLE_THEME_TAGS.get(cat, "single:1.0")


# ── 소스별 변환 함수 ──────────────────────────────────────
def from_culture_events(df):
    """서울/경기 공공 문화행사: ai_tags가 없으므로 genre 키워드 기반으로 single_score 추정"""
    rows = []
    for _, r in df.iterrows():
        name = safe_str(r.get("title", ""))
        if not name:
            continue
        genre = safe_str(r.get("genre", ""))
        venue = safe_str(r.get("place", ""))

        # 콘서트/전시류는 싱글 친화도 높게, 나머지는 기본값
        est_score = 0.85 if any(k in genre for k in ["콘서트", "전시", "무용", "클래식"]) else 0.5
        if est_score < SINGLE_SCORE_THRESHOLD:
            continue

        cat = categorize_single(genre, name, venue)
        start = safe_str(r.get("start", ""))
        end = safe_str(r.get("end", ""))
        period = f"{start} ~ {end}" if start and end else "상시"

        rows.append({
            "source_site":         "서울시 문화행사",
            "category":            cat,
            "place_or_event_name": name,
            "period":              period,
            "target_age":          "성인 (개인 관람 적합)",
            "region":              venue,
            "fee_info":            "상세 페이지 참조",
            "description":         f"{venue}에서 열리는 {genre} 행사 [{name}]. 혼자 관람하기 좋은 몰입형 콘텐츠입니다.",
            "booking_url":         safe_str(r.get("url", "")),
            "ai_tags":             f"single:{est_score};couple:0.7;family:0.3;{genre};서울시문화행사",
            "crawled_at":          NOW,
            "theme_tags":          theme_tags_single(cat),
            "congestion_score":    random.randint(2, 4),
            "popularity_score":    random.randint(55, 85),
        })
    return rows


def from_tickets(df, source_label):
    """인터파크/티켓링크: 기존 ai_tags의 single 점수를 그대로 신뢰해서 필터링"""
    rows = []
    for _, r in df.iterrows():
        name = safe_str(r.get("title", ""))
        if not name:
            continue
        ai_tag = safe_str(r.get("ai_tags", ""))
        score = parse_single_score(ai_tag)
        if score < SINGLE_SCORE_THRESHOLD:
            continue

        cat_raw = safe_str(r.get("category", ""))
        venue = safe_str(r.get("venue", ""))
        cat = categorize_single(cat_raw, name, venue)

        start = safe_str(r.get("start_date", ""))
        end = safe_str(r.get("end_date", ""))
        period = f"{start} ~ {end}" if start and end else "상시"

        rows.append({
            "source_site":         source_label,
            "category":            cat,
            "place_or_event_name": name,
            "period":              period,
            "target_age":          "성인 (개인 관람 적합)",
            "region":              venue,
            "fee_info":            safe_str(r.get("price_info", "유료")),
            "description":         f"{source_label} 실시간 인기 콘텐츠 [{name}]. 혼자 즐기기 좋은 몰입감 있는 콘텐츠입니다.",
            "booking_url":         safe_str(r.get("booking_url", "")),
            "ai_tags":             ensure_single_tag(ai_tag, score),
            "crawled_at":          safe_str(r.get("crawled_at", NOW)),
            "theme_tags":          theme_tags_single(cat),
            "congestion_score":    random.randint(3, 5),
            "popularity_score":    min(100, int(score * 100)),
        })
    return rows


def from_bookstore(df):
    """independent_bookstore_collector.py 결과: 문화공공데이터광장 독립서점 API.
    이미 total_single_data 스키마와 동일하므로 컬럼만 맞춰서 그대로 사용."""
    rows = []
    for _, r in df.iterrows():
        name = safe_str(r.get("place_or_event_name", ""))
        if not name:
            continue
        ai_tag = safe_str(r.get("ai_tags", ""))
        rows.append({
            "source_site":         safe_str(r.get("source_site", "문화공공데이터광장")),
            "category":            "독립서점",
            "place_or_event_name": name,
            "period":              safe_str(r.get("period", "상시")),
            "target_age":          safe_str(r.get("target_age", "성인 (개인 방문 적합)")),
            "region":              safe_str(r.get("region", "")),
            "fee_info":            safe_str(r.get("fee_info", "")),
            "description":         safe_str(r.get("description", f"{name} 독립서점")),
            "booking_url":         safe_str(r.get("booking_url", "")),
            "ai_tags":             ensure_single_tag(ai_tag, parse_single_score(ai_tag) or 0.95),
            "crawled_at":          safe_str(r.get("crawled_at", NOW)),
            "theme_tags":          safe_str(r.get("theme_tags", "bookstore:1.0;quiet:1.0;indoor:1.0")),
            "congestion_score":    int(r.get("congestion_score", 2) or 2),
            "popularity_score":    int(r.get("popularity_score", 70) or 70),
        })
    return rows


def from_naver_single(df):
    """naver_local_single_collector.py 결과: 독립서점/조용한힐링/역사문화/자연공원 보강 소스.
    이미 스키마가 total_single_data와 거의 동일하므로 컬럼만 맞춰서 그대로 사용."""
    rows = []
    for _, r in df.iterrows():
        name = safe_str(r.get("place_or_event_name", ""))
        if not name:
            continue
        ai_tag = safe_str(r.get("ai_tags", ""))
        score = parse_single_score(ai_tag)
        if score < SINGLE_SCORE_THRESHOLD:
            continue
        rows.append({
            "source_site":         safe_str(r.get("source_site", "네이버 지역검색 API")),
            "category":            safe_str(r.get("category", "전시·미술관")),
            "place_or_event_name": name,
            "period":              safe_str(r.get("period", "상시")),
            "target_age":          safe_str(r.get("target_age", "성인 (개인 방문 적합)")),
            "region":              safe_str(r.get("region", "")),
            "fee_info":            safe_str(r.get("fee_info", "")),
            "description":         safe_str(r.get("description", f"{name} 싱글 추천 장소")),
            "booking_url":         safe_str(r.get("booking_url", "")),
            "ai_tags":             ensure_single_tag(ai_tag, score),
            "crawled_at":          safe_str(r.get("crawled_at", NOW)),
            "theme_tags":          safe_str(r.get("theme_tags", theme_tags_single(r.get("category", "")))),
            "congestion_score":    int(r.get("congestion_score", 2) or 2),
            "popularity_score":    int(r.get("popularity_score", 70) or 70),
        })
    return rows


def build_recommend_reason(row):
    cat = row["category"]
    reasons = {
        "전시·미술관": "🖼️ 조용히 몰입할 수 있는 전시 콘텐츠로 나 홀로 관람 최적",
        "독립서점":     "📚 혼자만의 시간을 보내기 좋은 조용한 독서 공간",
        "콘서트·공연":  "🎵 몰입감 있는 공연으로 혼자 즐기기 좋은 라이브 콘텐츠",
        "조용한 힐링":  "🌿 혼자 사색하며 힐링하기 좋은 장소",
        "역사·문화":    "🏯 깊이 있게 둘러보기 좋은 역사·문화 명소",
        "자연·공원":    "🌳 혼자 걷기 좋은 자연 친화 공간",
    }
    return reasons.get(cat, "🙋 혼자 즐기기 좋은 싱글 추천 명소")


def main():
    print("=== total_single_data 통합 생성 시작 v1.0 ===")
    all_rows = []

    if os.path.exists(PATH_CULTURE):
        df_cult = pd.read_csv(PATH_CULTURE, encoding="utf-8-sig")
        r_cult = from_culture_events(df_cult)
        all_rows.extend(r_cult)
        print(f"✅ 문화행사(싱글 필터 적용): {len(r_cult)}건")

    if os.path.exists(PATH_INTERPARK):
        df_inter = pd.read_csv(PATH_INTERPARK, encoding="utf-8-sig")
        r_inter = from_tickets(df_inter, "인터파크 티켓")
        all_rows.extend(r_inter)
        print(f"✅ 인터파크(싱글 필터 적용): {len(r_inter)}건")

    if os.path.exists(PATH_TICKETLINK):
        df_tl = pd.read_csv(PATH_TICKETLINK, encoding="utf-8-sig")
        r_tl = from_tickets(df_tl, "티켓링크")
        all_rows.extend(r_tl)
        print(f"✅ 티켓링크(싱글 필터 적용): {len(r_tl)}건")

    if os.path.exists(PATH_BOOKSTORE):
        df_book = pd.read_csv(PATH_BOOKSTORE, encoding="utf-8-sig")
        r_book = from_bookstore(df_book)
        all_rows.extend(r_book)
        print(f"✅ 독립서점(문화공공데이터광장): {len(r_book)}건")
    else:
        print("ℹ️  independent_bookstores.csv 없음 — 먼저 independent_bookstore_collector.py를 실행하세요.")

    if os.path.exists(PATH_NAVER_SINGLE):
        df_nav = pd.read_csv(PATH_NAVER_SINGLE, encoding="utf-8-sig")
        r_nav = from_naver_single(df_nav)
        all_rows.extend(r_nav)
        print(f"✅ 네이버 지역검색(독립서점/힐링/역사/자연): {len(r_nav)}건")
    else:
        print("ℹ️  naver_single_places.csv 없음 — 먼저 naver_local_single_collector.py를 실행하면"
              " 독립서점/조용한 힐링/역사·문화/자연·공원 카테고리가 채워집니다.")

    if not all_rows:
        print("⚠️ 병합할 데이터가 없습니다. data/ 폴더의 원본 CSV를 확인하세요.")
        return

    df_all = pd.DataFrame(all_rows)
    df_all["recommend_reason"] = df_all.apply(build_recommend_reason, axis=1)

    b_len = len(df_all)
    is_placeholder = df_all["place_or_event_name"].isin(["이름없음", "", None])
    df_named = df_all[~is_placeholder].drop_duplicates(subset=["place_or_event_name", "region"])
    # 장소명 필드가 정상 매핑되지 않아 전부 "이름없음"으로 찍힌 행들은 이름 기준 중복 제거를
    # 하면 서로 다른 장소가 통째로 뭉개진다 -> description(운영시간/전화 등 세부정보) 기준으로만 중복 제거
    df_unnamed = df_all[is_placeholder].drop_duplicates(subset=["description"])
    if len(df_unnamed):
        print(f"⚠️ 장소명 필드 매핑 실패로 추정되는 {len(df_unnamed)}건은 이름 대신 설명(description) 기준으로 "
              f"중복 제거했습니다. scripts/independent_bookstore_collector.py 실행 시 생성되는 "
              f"data/independent_bookstores_debug.json에서 실제 API 필드명을 확인 후 정규화 로직을 고쳐주세요.")
    df_all = pd.concat([df_named, df_unnamed], ignore_index=True)
    a_len = len(df_all)
    print(f"\n중복 제거: {b_len} → {a_len}건")

    # 카테고리별 분포 출력
    print("\n카테고리별 분포:")
    print(df_all["category"].value_counts().to_string())

    os.makedirs(DATA_DIR, exist_ok=True)
    df_all = df_all[TARGET_COLS]
    df_all.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n✅ CSV 저장: {OUT_CSV}")

    records = df_all.to_dict(orient="records")
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON 저장: {OUT_JSON}")

    print(f"\n=== 완료! 최종 {a_len}건 ===")


if __name__ == "__main__":
    main()
