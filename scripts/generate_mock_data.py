import os
import random
from datetime import datetime, timedelta
import db_manager

def generate_mock_data():
    print("가상 데이터 생성 중...")
    
    # 1. 20개의 현실적인 서울 핫플레이스 정의
    raw_places = [
        {
            "name": "여의도 한강공원",
            "category": "공원/야외",
            "address": "서울 영등포구 여의동로 330",
            "latitude": 37.5284,
            "longitude": 126.9331,
            "is_parking": True,
            "is_stroller": True,
            "has_nursing": True,
            "no_kids": False,
            "event_title": "한강 여름 야시장 & 달빛 버스킹",
            "event_desc": "주말 한강의 바람을 맞으며 푸드트럭 음식과 멋진 인디 음악 공연을 즐겨보세요! 유모차 접근성이 좋고 돗자리를 깔 수 있어 온 가족이 함께 즐기기 안성맞춤입니다.",
            "tags": "family:0.95;couple:0.80;single:0.60;주차편리;유모차;수유실;야외공원;피크닉",
            "tmap_rank": 1,
            "crowd": "CONGESTED"
        },
        {
            "name": "성수동 에스팩토리 팝업 존",
            "category": "팝업스토어",
            "address": "서울 성동구 연무장15길 11",
            "latitude": 37.5425,
            "longitude": 127.0601,
            "is_parking": False,
            "is_stroller": False,
            "has_nursing": False,
            "no_kids": False,
            "event_title": "2026 무신사 뷰티 & 브랜드 팝업쇼",
            "event_desc": "글로벌 패션&뷰티 브랜드들이 참여하는 초대형 팝업스토어! 한정판 굿즈 배포 및 셀럽 방문, 인생샷을 찍을 수 있는 포토존이 다채롭게 마련되어 있습니다.",
            "tags": "family:0.20;couple:0.95;single:0.85;인생샷;팝업스토어;핫플;주말데이트",
            "tmap_rank": 3,
            "crowd": "VERY_CONGESTED"
        },
        {
            "name": "국립현대미술관 서울관",
            "category": "미술관/전시",
            "address": "서울 종로구 삼청로 30",
            "latitude": 37.5786,
            "longitude": 126.9798,
            "is_parking": True,
            "is_stroller": True,
            "has_nursing": True,
            "no_kids": False,
            "event_title": "디지털 캔버스: 현대 미술의 경계전",
            "event_desc": "세계적인 미디어 아티스트들이 참여하여 관객의 모션에 실시간으로 반응하는 몰입형 미디어 아트 특별전. 혼자서 사색하며 깊이 있는 문화예술을 즐기기 좋습니다.",
            "tags": "family:0.40;couple:0.75;single:0.95;실내;미술관;사색;조용한;예약제",
            "tmap_rank": 12,
            "crowd": "MODERATE"
        },
        {
            "name": "서울 어린이대공원",
            "category": "공원/야외",
            "address": "서울 광진구 능동로 216",
            "latitude": 37.5480,
            "longitude": 127.0815,
            "is_parking": True,
            "is_stroller": True,
            "has_nursing": True,
            "no_kids": False,
            "event_title": "아기동물 교감 스쿨 & 물놀이 페스티벌",
            "event_desc": "어린이 동반 가족을 위한 맞춤형 체험 행사. 유모차 대여 시설이 잘 갖춰져 있으며 넓은 잔디광장과 무료 동물원 관람이 가능해 아기 동반 가족의 만족도가 매우 높습니다.",
            "tags": "family:1.00;couple:0.50;single:0.30;주차편리;유모차;수유실;체험;아이와함께",
            "tmap_rank": 5,
            "crowd": "CONGESTED"
        },
        {
            "name": "낙산공원 성곽길",
            "category": "공원/야외",
            "address": "서울 종로구 낙산길 41",
            "latitude": 37.5807,
            "longitude": 127.0076,
            "is_parking": False,
            "is_stroller": False,
            "has_nursing": False,
            "no_kids": False,
            "event_title": "혜화동 대학로 연계 야경 도보 산책",
            "event_desc": "서울 성곽을 따라 펼쳐지는 은은한 조명과 아름다운 야경을 바라보며 걸을 수 있는 성곽 데이트 코스. 주변의 예쁜 루프탑 카페와 연계하기 좋습니다.",
            "tags": "family:0.30;couple:0.98;single:0.70;야경;데이트코스;산책로;인생샷",
            "tmap_rank": 15,
            "crowd": "LOW"
        },
        {
            "name": "북촌 익선동 한옥 갤러리",
            "category": "미술관/전시",
            "address": "서울 종로구 수표로28길 17",
            "latitude": 37.5744,
            "longitude": 126.9897,
            "is_parking": False,
            "is_stroller": False,
            "has_nursing": False,
            "no_kids": True,
            "event_title": "전통 한옥 속 현대 공예 팝업 전",
            "event_desc": "100년 된 익선동 한옥에서 펼쳐지는 청년 작가들의 현대 도자기 및 섬유 예술품 전시. 협소한 한옥 구조로 인해 안전상의 이유로 노키즈존으로 운영됩니다.",
            "tags": "family:0.10;couple:0.85;single:0.90;노키즈존;한옥;갤러리;데이트;사색;소품샵",
            "tmap_rank": 8,
            "crowd": "VERY_CONGESTED"
        },
        {
            "name": "스타필드 코엑스몰 별마당도서관",
            "category": "복합문화공간",
            "address": "서울 강남구 영동대로 513",
            "latitude": 37.5126,
            "longitude": 127.0589,
            "is_parking": True,
            "is_stroller": True,
            "has_nursing": True,
            "no_kids": False,
            "event_title": "명사 초청 주말 문학 아카데미",
            "event_desc": "초대형 책장 인테리어로 전 세계 여행객들의 이목을 끄는 복합 인문학 공간. 쾌적한 실내 쇼핑몰과 연결되어 날씨에 상관없이 유모차를 타거나 아이들과 걷기 좋습니다.",
            "tags": "family:0.80;couple:0.85;single:0.85;실내;도서관;주차편리;유모차;복합쇼핑몰",
            "tmap_rank": 2,
            "crowd": "CONGESTED"
        },
        {
            "name": "경복궁 야간개장",
            "category": "문화유산/역사",
            "address": "서울 종로구 사직로 161",
            "latitude": 37.5796,
            "longitude": 126.9770,
            "is_parking": True,
            "is_stroller": True,
            "has_nursing": False,
            "no_kids": False,
            "event_title": "2026 경복궁 주말 달빛 기행",
            "event_desc": "어두운 밤 달빛 아래 고요하게 빛나는 근정전과 경회루를 거니는 최고 인기 야간 문화 행사. 한복 착용 시 무료입장이 가능하며 웅장한 인생샷을 남길 수 있습니다.",
            "tags": "family:0.70;couple:0.97;single:0.60;고궁;야간개장;인생샷;한복체험;사전예약",
            "tmap_rank": 4,
            "crowd": "VERY_CONGESTED"
        },
        {
            "name": "연남동 독립서점 '글자숲'",
            "category": "도서/문화",
            "address": "서울 마포구 성미산로 198",
            "latitude": 37.5621,
            "longitude": 126.9245,
            "is_parking": False,
            "is_stroller": False,
            "has_nursing": False,
            "no_kids": True,
            "event_title": "심야 책방 & 작가와의 북토크",
            "event_desc": "주말 저녁 소수의 인원만 예약을 받아 진행하는 독립작가 북토크 콘서트. 잔잔한 음악과 아늑한 공간에서 조용하게 한 주간의 스트레스를 해소하고 깊은 독서를 즐길 수 있습니다.",
            "tags": "family:0.05;couple:0.50;single:1.00;노키즈존;독립서점;조용한;북토크;사색;예약제",
            "tmap_rank": 25,
            "crowd": "LOW"
        },
        {
            "name": "반포한강공원 예빛섬",
            "category": "공원/야외",
            "address": "서울 서초구 신반포로11길 145-8",
            "latitude": 37.5113,
            "longitude": 126.9959,
            "is_parking": True,
            "is_stroller": True,
            "has_nursing": True,
            "no_kids": False,
            "event_title": "반포 달빛무지개분수 & 재즈나잇",
            "event_desc": "세계 최장 분수로 기네스북에 등재된 반포 한강의 달빛무지개분수 쇼를 배경으로 흐르는 감미로운 재즈 선율. 낭만적인 분위기로 커플들의 주말 필수 데이트 성지입니다.",
            "tags": "family:0.75;couple:0.99;single:0.65;야외;분수쇼;야경;주차편리;데이트코스",
            "tmap_rank": 6,
            "crowd": "CONGESTED"
        },
        {
            "name": "동대문디자인플라자 (DDP)",
            "category": "미술관/전시",
            "address": "서울 중구 을지로 281",
            "latitude": 37.5665,
            "longitude": 127.0092,
            "is_parking": True,
            "is_stroller": True,
            "has_nursing": True,
            "no_kids": False,
            "event_title": "헬로키티 50주년 특별 글로벌 네트워킹 전",
            "event_desc": "전 세계에서 사랑받는 캐릭터 헬로키티의 탄생 50주년 특별전. 추억을 회상할 수 있어 데이트 커플과 아기자기한 캐릭터를 좋아하는 싱글, 아이가 있는 가족 모두에게 즐거움을 줍니다.",
            "tags": "family:0.85;couple:0.88;single:0.80;실내전시;굿즈샵;유모차;주차편리;캐릭터",
            "tmap_rank": 7,
            "crowd": "CONGESTED"
        },
        {
            "name": "성수연무장길 카페거리",
            "category": "카페/식음",
            "address": "서울 성동구 연무장길 37-14",
            "latitude": 37.5432,
            "longitude": 127.0544,
            "is_parking": False,
            "is_stroller": False,
            "has_nursing": False,
            "no_kids": True,
            "event_title": "해외 유명 바리스타 초청 주말 에스프레소 위크",
            "event_desc": "커피 애호가들을 위한 스페셜티 에스프레소 시음 축제. 골목 전체가 개성 있는 편집숍과 베이커리로 가득 차 걷는 즐거움이 크지만, 매장이 협소하고 인파가 많습니다.",
            "tags": "family:0.15;couple:0.96;single:0.88;카페거리;베이커리;노키즈존;핫플;골목투어",
            "tmap_rank": 9,
            "crowd": "VERY_CONGESTED"
        },
        {
            "name": "선유도공원 온실관",
            "category": "공원/야외",
            "address": "서울 영등포구 선유로 343",
            "latitude": 37.5422,
            "longitude": 126.9017,
            "is_parking": False,
            "is_stroller": True,
            "has_nursing": False,
            "no_kids": False,
            "event_title": "폐정수장의 친환경 생태 가치 기획 전",
            "event_desc": "정수장 공장을 개조하여 만든 독창적인 친환경 생태공원. 비교적 한적하며, 빈티지한 콘크리트 구조물 사이로 피어난 이끼와 식물들이 신비로운 분위기를 내어 사색하기 아주 좋습니다.",
            "tags": "family:0.60;couple:0.82;single:0.92;친환경;사색;출사지;산책;한적한",
            "tmap_rank": 20,
            "crowd": "LOW"
        },
        {
            "name": "롯데월드 어드벤처",
            "category": "테마파크",
            "address": "서울 송파구 올림픽로 240",
            "latitude": 37.5111,
            "longitude": 127.0982,
            "is_parking": True,
            "is_stroller": True,
            "has_nursing": True,
            "no_kids": False,
            "event_title": "삼바 피에스타 페스티벌 2026",
            "event_desc": "더운 여름 실내에서 즐기는 화려한 삼바 카니발 퍼레이드와 어트랙션! 연중무휴 쾌적하게 수유실 및 유모차 대여를 이용할 수 있어 패밀리 고객층의 부동의 1위 명소입니다.",
            "tags": "family:0.98;couple:0.87;single:0.40;실내테마파크;퍼레이드;주차편리;유모차;수유실",
            "tmap_rank": 10,
            "crowd": "VERY_CONGESTED"
        },
        {
            "name": "송파 한성백제박물관",
            "category": "박물관/전시",
            "address": "서울 송파구 위례성대로 71",
            "latitude": 37.5173,
            "longitude": 127.1264,
            "is_parking": True,
            "is_stroller": True,
            "has_nursing": True,
            "no_kids": False,
            "event_title": "한성백제 고대 무덤 속 비밀 체험전",
            "event_desc": "올림픽공원 안에 위치한 조용하고 유익한 역사 박물관. 넓은 실내 공간과 철저한 장애인/유모차 경사로 설계, 그리고 무료 체험 학습지가 있어 학부모들에게 숨겨진 명소입니다.",
            "tags": "family:0.92;couple:0.60;single:0.75;박물관;어린이체험;실내;주차편리;유모차;한적한",
            "tmap_rank": 18,
            "crowd": "LOW"
        }
    ]
    
    # 2. 데이터베이스 초기화 보장
    db_manager.ensure_data_dir()
    
    today = datetime.now()
    
    for rp in raw_places:
        # Places 추가
        place_id = db_manager.add_or_update_place(
            name=rp["name"],
            category=rp["category"],
            address=rp["address"],
            latitude=rp["latitude"],
            longitude=rp["longitude"],
            is_parking=rp["is_parking"],
            is_stroller=rp["is_stroller"],
            has_nursing=rp["has_nursing"],
            no_kids=rp["no_kids"]
        )
        
        # Events 추가
        start_date = today.strftime("%Y-%m-%d")
        end_date = (today + timedelta(days=random.randint(14, 60))).strftime("%Y-%m-%d")
        source_url = f"https://example.com/events/{place_id}"
        
        db_manager.add_or_update_event(
            place_id=place_id,
            title=rp["event_title"],
            start_date=start_date,
            end_date=end_date,
            source_url=source_url,
            raw_description=rp["event_desc"],
            ai_tags=rp["tags"]
        )
        
        # Metrics 추가
        db_manager.update_real_time_metric(
            place_id=place_id,
            tmap_rank=rp["tmap_rank"],
            seoul_crowd_level=rp["crowd"]
        )
        
    print(f"가상 데이터 생성 완료: {len(raw_places)}개의 장소 및 이벤트 정보가 DB(CSV)에 저장되었습니다.")
    
    # 맛집 데이터 별도 추가
    generate_restaurant_mock_data()

def generate_restaurant_mock_data():
    """서울 주요 맛집 가상 데이터를 CSV에 추가합니다."""
    print("맛집 가상 데이터 생성 중...")
    today = datetime.now()
    
    restaurants = [
        {
            "name": "광화문 국밥 공화국",
            "category": "맛집/한식",
            "address": "서울 종로구 세종대로 149",
            "latitude": 37.5724, "longitude": 126.9769,
            "is_parking": True, "is_stroller": True, "has_nursing": False, "no_kids": False,
            "event_title": "점심 특선 설렁탕 세트",
            "event_desc": "매일 점심 11시~2시, 설렁탕+깍두기+공기밥 세트를 특가로 제공합니다. 50년 전통의 깊고 진한 사골 육수로 만든 국밥. 어린이 전용 소메뉴도 있어 온 가족이 함께 방문하기 좋습니다.",
            "tags": "family:0.85;couple:0.50;single:0.70;food;한식;국밥;전통;점심;주차편리",
            "tmap_rank": 11, "crowd": "CONGESTED", "rating": 4.6, "food_type": "한식"
        },
        {
            "name": "성수 쌀국수 마당",
            "category": "맛집/아시안",
            "address": "서울 성동구 서울숲2길 32",
            "latitude": 37.5447, "longitude": 127.0431,
            "is_parking": False, "is_stroller": False, "has_nursing": False, "no_kids": False,
            "event_title": "여름 한정 냉쌀국수 런칭",
            "event_desc": "시원하고 담백한 냉쌀국수를 여름 한정으로 선보입니다. 성수동 골목 안 숨은 맛집으로 웨이팅이 있을 수 있으니 오픈 직후 방문을 추천드립니다.",
            "tags": "family:0.40;couple:0.85;single:0.90;food;아시안;쌀국수;성수동;분위기맛집;데이트",
            "tmap_rank": 14, "crowd": "VERY_CONGESTED", "rating": 4.8, "food_type": "아시안"
        },
        {
            "name": "연남동 파스타 하우스",
            "category": "맛집/양식",
            "address": "서울 마포구 연남동 228-51",
            "latitude": 37.5638, "longitude": 126.9244,
            "is_parking": False, "is_stroller": False, "has_nursing": False, "no_kids": True,
            "event_title": "시그니처 트러플 파스타 & 와인 페어링",
            "event_desc": "셰프의 시그니처 트러플 크림 파스타와 이탈리아 자연 와인의 환상적인 조합. 연남동 감성 가득한 내부 인테리어에서 특별한 저녁 식사를 즐겨보세요. 사전 예약 필수입니다.",
            "tags": "family:0.15;couple:0.98;single:0.80;food;양식;파스타;이탈리안;분위기;노키즈존;예약필수",
            "tmap_rank": 13, "crowd": "VERY_CONGESTED", "rating": 4.9, "food_type": "양식"
        },
        {
            "name": "이태원 수제버거 랩",
            "category": "맛집/양식",
            "address": "서울 용산구 이태원로 177",
            "latitude": 37.5340, "longitude": 126.9940,
            "is_parking": False, "is_stroller": False, "has_nursing": False, "no_kids": False,
            "event_title": "주말 브런치 버거 세트",
            "event_desc": "주말 한정 브런치 타임(10:00~13:00)에 에그 버거 + 감자튀김 + 음료가 포함된 세트를 즐길 수 있습니다. 두툼한 수제 패티와 신선한 재료를 사용합니다.",
            "tags": "family:0.50;couple:0.90;single:0.85;food;양식;버거;브런치;이태원;데이트",
            "tmap_rank": 18, "crowd": "CONGESTED", "rating": 4.5, "food_type": "양식"
        },
        {
            "name": "잠실 참치회 전문점 '청바다'",
            "category": "맛집/일식",
            "address": "서울 송파구 잠실로 148",
            "latitude": 37.5140, "longitude": 127.1000,
            "is_parking": True, "is_stroller": True, "has_nursing": False, "no_kids": False,
            "event_title": "제주산 생참치 특선 코스",
            "event_desc": "제주 청정 바다에서 직송한 생참치를 다양한 부위별로 즐길 수 있는 코스 요리. 가족 모임과 회식 장소로 인기가 높으며, 참치 해체 쇼도 진행됩니다.",
            "tags": "family:0.80;couple:0.90;single:0.70;food;일식;참치회;고급;가족모임;주차편리",
            "tmap_rank": 22, "crowd": "MODERATE", "rating": 4.7, "food_type": "일식"
        },
        {
            "name": "강남 뒷골목 순대국 할머니집",
            "category": "맛집/한식",
            "address": "서울 강남구 논현동 215-10",
            "latitude": 37.5165, "longitude": 127.0283,
            "is_parking": False, "is_stroller": False, "has_nursing": False, "no_kids": False,
            "event_title": "30년 전통 순대국밥 특선",
            "event_desc": "강남 한복판에서 30년을 이어온 노포 순대국밥. 진한 육수와 신선한 순대, 수육이 어우러진 한 그릇. 혼밥러들의 성지이며, 이른 아침부터 밤늦게까지 언제나 문을 엽니다.",
            "tags": "family:0.60;couple:0.40;single:0.95;food;한식;순대국;노포;숨은맛집;혼밥",
            "tmap_rank": 30, "crowd": "MODERATE", "rating": 4.8, "food_type": "한식"
        },
        {
            "name": "북촌 한옥 한정식",
            "category": "맛집/한식",
            "address": "서울 종로구 계동길 86",
            "latitude": 37.5826, "longitude": 126.9845,
            "is_parking": False, "is_stroller": False, "has_nursing": False, "no_kids": False,
            "event_title": "여름 보양식 한정식 코스",
            "event_desc": "전통 한옥을 개조한 고즈넉한 공간에서 계절 재료를 활용한 한정식을 즐겨보세요. 여름 한정으로 삼계탕 코스가 추가되었으며, 코스 예약 시 전통차 서비스가 제공됩니다.",
            "tags": "family:0.70;couple:0.95;single:0.75;food;한식;한정식;한옥;전통;분위기맛집",
            "tmap_rank": 25, "crowd": "MODERATE", "rating": 4.6, "food_type": "한식"
        },
        {
            "name": "망원동 디저트 카페 '단팥'",
            "category": "맛집/카페·디저트",
            "address": "서울 마포구 망원동 415-4",
            "latitude": 37.5558, "longitude": 126.9048,
            "is_parking": False, "is_stroller": True, "has_nursing": False, "no_kids": False,
            "event_title": "여름 빙수 페스티벌",
            "event_desc": "국산 팥을 사용한 정통 팥빙수부터 말차 크림 빙수, 딸기 우유 빙수까지 다양한 빙수 메뉴를 선보입니다. SNS에서 화제가 된 비주얼로 인스타그램 성지가 된 카페입니다.",
            "tags": "family:0.75;couple:0.90;single:0.70;food;카페;디저트;빙수;인생샷;망원동",
            "tmap_rank": 16, "crowd": "VERY_CONGESTED", "rating": 4.7, "food_type": "카페·디저트"
        },
        {
            "name": "서울숲 브런치 카페 '그리너리'",
            "category": "맛집/카페·디저트",
            "address": "서울 성동구 뚝섬로 273",
            "latitude": 37.5449, "longitude": 127.0376,
            "is_parking": True, "is_stroller": True, "has_nursing": False, "no_kids": False,
            "event_title": "서울숲 뷰 브런치 & 애프터눈 티",
            "event_desc": "서울숲 바로 앞에 위치한 대형 통창 카페. 싱그러운 녹음을 바라보며 즐기는 에그 베네딕트와 시그니처 커피가 유명합니다. 유모차 입장 가능하며 야외 테라스도 있습니다.",
            "tags": "family:0.88;couple:0.92;single:0.75;food;카페;브런치;서울숲;테라스;유모차",
            "tmap_rank": 12, "crowd": "CONGESTED", "rating": 4.6, "food_type": "카페·디저트"
        },
        {
            "name": "을지로 노포 타코야끼 '야끼야끼'",
            "category": "맛집/일식",
            "address": "서울 중구 을지로3가 347-5",
            "latitude": 37.5675, "longitude": 126.9927,
            "is_parking": False, "is_stroller": False, "has_nursing": False, "no_kids": False,
            "event_title": "을지로 야시장 합류 포장마차 이벤트",
            "event_desc": "을지로 골목 야시장에서 만나는 바삭하고 촉촉한 수제 타코야끼. 문어 가득한 오리지널부터 치즈, 명란 등 다양한 토핑을 선택할 수 있습니다. 인스타 챌린지 진행 중.",
            "tags": "family:0.30;couple:0.80;single:0.95;food;일식;타코야끼;야시장;을지로;야경;혼밥",
            "tmap_rank": 19, "crowd": "CONGESTED", "rating": 4.5, "food_type": "일식"
        },
        {
            "name": "마포 패밀리 레스토랑 '올리버'",
            "category": "맛집/양식",
            "address": "서울 마포구 양화로 45",
            "latitude": 37.5488, "longitude": 126.9066,
            "is_parking": True, "is_stroller": True, "has_nursing": True, "no_kids": False,
            "event_title": "아이 생일 파티 패키지",
            "event_desc": "어린이 메뉴, 생일 케이크, 파티 물품이 포함된 특별 생일 파티 패키지를 운영합니다. 수유실과 기저귀 교환대, 어린이 좌식 의자가 갖춰져 있어 영유아 동반 가족에게 안성맞춤입니다.",
            "tags": "family:0.98;couple:0.60;single:0.30;food;양식;패밀리레스토랑;키즈;수유실;주차편리",
            "tmap_rank": 17, "crowd": "MODERATE", "rating": 4.4, "food_type": "양식"
        },
        {
            "name": "신사동 고기집 '마블리'",
            "category": "맛집/한식",
            "address": "서울 강남구 압구정로2길 40",
            "latitude": 37.5247, "longitude": 127.0207,
            "is_parking": True, "is_stroller": False, "has_nursing": False, "no_kids": False,
            "event_title": "주말 한우 모둠 구이 특선",
            "event_desc": "1++ 등급 한우 채끝, 등심, 안심을 모아 담은 주말 특선 구이 세트. 특수 부위는 매일 한정 수량 운영됩니다. 연기 없는 스마트 그릴로 쾌적한 환경에서 식사 가능합니다.",
            "tags": "family:0.65;couple:0.90;single:0.70;food;한식;한우;고기;신사동;분위기맛집;주차편리",
            "tmap_rank": 20, "crowd": "CONGESTED", "rating": 4.7, "food_type": "한식"
        },
    ]
    
    db_manager.ensure_data_dir()
    today = datetime.now()
    
    for r in restaurants:
        place_id = db_manager.add_or_update_place(
            name=r["name"],
            category=r["category"],
            address=r["address"],
            latitude=r["latitude"],
            longitude=r["longitude"],
            is_parking=r["is_parking"],
            is_stroller=r["is_stroller"],
            has_nursing=r["has_nursing"],
            no_kids=r["no_kids"]
        )
        start_date = today.strftime("%Y-%m-%d")
        end_date = (today + timedelta(days=random.randint(7, 30))).strftime("%Y-%m-%d")
        db_manager.add_or_update_event(
            place_id=place_id,
            title=r["event_title"],
            start_date=start_date,
            end_date=end_date,
            source_url=f"https://example.com/food/{place_id}",
            raw_description=r["event_desc"],
            ai_tags=r["tags"]
        )
        db_manager.update_real_time_metric(
            place_id=place_id,
            tmap_rank=r["tmap_rank"],
            seoul_crowd_level=r["crowd"]
        )
    
    print(f"맛집 가상 데이터 생성 완료: {len(restaurants)}개의 맛집 정보가 DB(CSV)에 저장되었습니다.")

if __name__ == "__main__":
    generate_mock_data()

