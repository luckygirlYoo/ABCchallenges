import sys
import io
import csv
import os
import requests
from datetime import datetime, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

# 17개 시도별 위경도 좌표
REGIONS = {
    "서울": (37.5665, 126.9780),
    "인천": (37.4563, 126.7052),
    "대전": (36.3504, 127.3845),
    "대구": (35.8714, 128.6014),
    "광주": (35.1595, 126.8526),
    "부산": (35.1796, 129.0756),
    "울산": (35.5384, 129.3114),
    "세종": (36.4800, 127.2890),
    "수원": (37.2636, 127.0286),
    "춘천": (37.8813, 127.7298),
    "청주": (36.6424, 127.4890),
    "천안": (36.8151, 127.1139),
    "전주": (35.8242, 127.1480),
    "목포": (34.8118, 126.3922),
    "포항": (36.0190, 129.3435),
    "창원": (35.2279, 128.6811),
    "제주": (33.4996, 126.5312)
}

# WMO Weather interpretation codes (WMO 날씨 코드 해석)
WEATHER_CODES = {
    0: "맑음",
    1: "대체로 맑음",
    2: "구름조금",
    3: "흐림",
    45: "안개",
    48: "안개/서리",
    51: "가벼운 이슬비",
    53: "보통 이슬비",
    55: "강한 이슬비",
    61: "약한 비",
    63: "보통 비",
    65: "강한 비",
    71: "약한 눈",
    73: "보통 눈",
    75: "강한 눈",
    80: "소나기",
    95: "뇌우",
}

def get_weekly_weather():
    results = []
    print("🌍 [전국 주요 지역] 7일 주간 날씨 정보 가져오는 중...\n")
    
    for region, (lat, lon) in REGIONS.items():
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=weathercode,temperature_2m_max,temperature_2m_min&timezone=Asia%2FSeoul"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # 날씨 7일치 가져오기
            daily = data.get("daily", {})
            dates = daily.get("time", [])
            max_temps = daily.get("temperature_2m_max", [])
            min_temps = daily.get("temperature_2m_min", [])
            weather_codes = daily.get("weathercode", [])
            
            # 미세먼지 (현재 기준) 가져오기
            pm10_status = "보통"
            try:
                aq_url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=pm10&timezone=Asia%2FSeoul"
                aq_res = requests.get(aq_url, timeout=5)
                if aq_res.ok:
                    pm10_val = aq_res.json().get("current", {}).get("pm10", 0)
                    if pm10_val <= 30: pm10_status = "좋음"
                    elif pm10_val <= 80: pm10_status = "보통"
                    elif pm10_val <= 150: pm10_status = "나쁨"
                    else: pm10_status = "매우나쁨"
            except:
                pass
            
            for i in range(len(dates)):
                date = dates[i]
                max_t = max_temps[i]
                min_t = min_temps[i]
                w_code = weather_codes[i]
                status = WEATHER_CODES.get(w_code, "알수없음")
                
                results.append({
                    "region": region,
                    "date": date,
                    "min_temp": min_t,
                    "max_temp": max_t,
                    "status": status,
                    "dust": pm10_status if i == 0 else "-", # 오늘만 미세먼지 표시
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
            
            print(f"📍 {region} 주간 날씨(미세먼지 포함) 업데이트 완료")
            
        except Exception as e:
            print(f"❌ {region} 날씨 가져오기 실패: {e}")
            
    return results

def save_to_csv(data, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    headers = ["region", "date", "min_temp", "max_temp", "status", "dust", "updated_at"]
    
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)
    print(f"\n✅ 날씨 데이터 {len(data)}건 CSV 저장 완료: {filepath}")

if __name__ == "__main__":
    weather_data = get_weekly_weather()
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_path = os.path.join(base_dir, "data", "weather.csv")
    
    save_to_csv(weather_data, output_path)
