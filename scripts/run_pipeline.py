import os
import json
import db_manager
import api_collector
import crawler
import generate_mock_data
from datetime import datetime, timedelta

def main():
    print("==================================================")
    print("  AI 기반 주말 맞춤형 여가 추천 서비스 수집 파이프라인")
    print("==================================================")
    
    # 1. 디렉토리 및 CSV 초기화
    db_manager.ensure_data_dir()
    
    # 2. 설정 로드
    with open(db_manager.CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
        
    api_keys = config["api_keys"]
    
    # API 키 검증 (사용할 수 있는 유효한 키가 하나라도 있는지 확인)
    has_api_keys = any(
        val and not val.startswith("YOUR_") 
        for val in api_keys.values()
    )
    
    if not has_api_keys:
        print("\n[알림] 설정 파일(config.json)에 유효한 API 키가 등록되지 않았습니다.")
        print("-> 데모용 고품질 가상 데이터를 먼저 생성하여 데이터베이스를 채웁니다.")
        generate_mock_data.generate_mock_data()
        print("\n[알림] API 키를 등록하려면 `scripts/config.json` 파일을 편집해 주세요.")
        print("==================================================")
        return

    print("\n[시작] API 및 크롤러 기반 데이터 수집 파이프라인을 실행합니다...")
    
    # TourAPI로부터 축제 리스트 가져오기
    print("\n1. TourAPI 4.0 축제 데이터 수집 중...")
    festivals = api_collector.fetch_tour_festivals()
    print(f"-> 수집 완료: {len(festivals)}개 행사")
    
    # 수집한 각 행사 처리
    for fest in festivals:
        name = fest["name"]
        address = fest["address"]
        lat = fest["latitude"]
        lon = fest["longitude"]
        
        # 1. Kakao나 Naver API로 상세 주소 및 좌표 보완 (위경도 없는 경우)
        if not lat or not lon:
            kakao_details = api_collector.fetch_kakao_place_details(name)
            if kakao_details:
                address = kakao_details["address"]
                lat = kakao_details["latitude"]
                lon = kakao_details["longitude"]
            else:
                naver_details = api_collector.fetch_naver_place_details(name)
                if naver_details:
                    address = naver_details["address"]
        
        # 2. 네이버 평점/블로그 리뷰 크롤링 및 AI 태깅 점수 도출
        print(f"   - '{name}' 리뷰 스크래핑 및 감성 분석 중...")
        reviews = crawler.crawl_naver_reviews(name)
        scores, matched_tags = crawler.analyze_review_tags(reviews)
        
        # ai_tags 구성 (family_score, couple_score, single_score 포함)
        tag_str = f"family:{scores['family']:.2f};couple:{scores['couple']:.2f};single:{scores['single']:.2f}"
        if matched_tags:
            tag_str += ";" + ";".join(matched_tags)
            
        # 3. 상세 속성 여부 (태그 기반 유추 또는 랜덤 기본값 부여)
        is_parking = "주차편리" in matched_tags or "주차" in "".join(reviews)
        is_stroller = "유모차" in matched_tags or "유모차" in "".join(reviews)
        has_nursing = "수유실" in matched_tags or "수유실" in "".join(reviews)
        no_kids = "노키즈" in matched_tags or "노키즈존" in matched_tags
        
        # 4. DB 적재 (places)
        place_id = db_manager.add_or_update_place(
            name=name,
            category="축제/행사",
            address=address,
            latitude=lat,
            longitude=lon,
            is_parking=is_parking,
            is_stroller=is_stroller,
            has_nursing=has_nursing,
            no_kids=no_kids
        )
        
        # 5. DB 적재 (events)
        db_manager.add_or_update_event(
            place_id=place_id,
            title=name,
            start_date=fest["start_date"],
            end_date=fest["end_date"],
            source_url=fest["source_url"],
            raw_description=f"지역 대표 축제 '{name}' 정보입니다.",
            ai_tags=tag_str
        )
        
        # 6. 실시간 혼잡도 수집 (서울 지역 명소에 해당하는 경우)
        # 매칭되는 구 이름 등이 있을 경우 서울 열린데이터 API 연동
        crowd_lvl = "LOW"
        for area in config["settings"]["seoul_areas"]:
            if area in address or area in name:
                crowd_lvl = api_collector.fetch_seoul_congestion(area)
                break
                
        db_manager.update_real_time_metric(
            place_id=place_id,
            tmap_rank=None, # TMap 랭킹은 민간 API 응답 또는 기본값으로 유지
            seoul_crowd_level=crowd_lvl
        )
        
    print("\n[완료] 파이프라인 수집 완료 후 DB 적재가 정상적으로 완료되었습니다.")
    print("==================================================")

if __name__ == "__main__":
    main()
