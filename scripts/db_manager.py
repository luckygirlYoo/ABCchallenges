import csv
import os
import json
from datetime import datetime

# 설정 로드
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, config["settings"]["data_dir"]))
PLACES_CSV = os.path.join(DATA_DIR, "places.csv")
EVENTS_CSV = os.path.join(DATA_DIR, "events.csv")
METRICS_CSV = os.path.join(DATA_DIR, "real_time_metrics.csv")

def ensure_data_dir():
    """데이터 디렉토리 및 파일이 존재하는지 확인하고 기본 헤더를 가진 파일을 생성합니다."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    headers = {
        PLACES_CSV: ["place_id", "name", "category", "address", "latitude", "longitude", "is_parking_available", "is_stroller_accessible", "has_nursing_room", "no_kids_zone"],
        EVENTS_CSV: ["event_id", "place_id", "title", "start_date", "end_date", "source_url", "raw_description", "ai_tags"],
        METRICS_CSV: ["metric_id", "place_id", "tmap_rank", "seoul_crowd_level", "updated_at"]
    }
    
    for filepath, cols in headers.items():
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(cols)

# 공통 읽기/쓰기 유틸리티
def _read_csv(filepath):
    ensure_data_dir()
    data = []
    with open(filepath, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(dict(row))
    return data

def _write_csv(filepath, data, headers):
    ensure_data_dir()
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)

# PLACES 관리
def load_places():
    return _read_csv(PLACES_CSV)

def save_places(places):
    headers = ["place_id", "name", "category", "address", "latitude", "longitude", "is_parking_available", "is_stroller_accessible", "has_nursing_room", "no_kids_zone"]
    _write_csv(PLACES_CSV, places, headers)

def add_or_update_place(name, category, address, latitude, longitude, is_parking=False, is_stroller=False, has_nursing=False, no_kids=False):
    """
    이름과 주소가 유사하거나 같은 장소가 이미 있으면 업데이트하고, 없으면 신규 추가합니다.
    """
    places = load_places()
    
    # 중복 체크 (이름 및 주소 일부 유사성 확인)
    existing_place = None
    for p in places:
        # 이름이 정확히 같거나, 위경도 좌표가 매우 인접한 경우 (소수점 4째자리까지 일치, 약 11m)
        coords_match = False
        if p["latitude"] and p["longitude"] and latitude and longitude:
            try:
                coords_match = abs(float(p["latitude"]) - float(latitude)) < 0.0001 and abs(float(p["longitude"]) - float(longitude)) < 0.0001
            except ValueError:
                pass
        
        if p["name"] == name or coords_match:
            existing_place = p
            break
            
    if existing_place:
        # 기존 정보 업데이트 (기존 ID 유지)
        existing_place["category"] = category
        existing_place["address"] = address or existing_place["address"]
        if latitude: existing_place["latitude"] = str(latitude)
        if longitude: existing_place["longitude"] = str(longitude)
        existing_place["is_parking_available"] = "TRUE" if is_parking else "FALSE"
        existing_place["is_stroller_accessible"] = "TRUE" if is_stroller else "FALSE"
        existing_place["has_nursing_room"] = "TRUE" if has_nursing else "FALSE"
        existing_place["no_kids_zone"] = "TRUE" if no_kids else "FALSE"
        save_places(places)
        return int(existing_place["place_id"])
    else:
        # 신규 ID 생성 (최대 ID + 1)
        new_id = 1
        if places:
            ids = [int(p["place_id"]) for p in places if p["place_id"].isdigit()]
            if ids:
                new_id = max(ids) + 1
        
        new_place = {
            "place_id": str(new_id),
            "name": name,
            "category": category,
            "address": address,
            "latitude": str(latitude) if latitude else "",
            "longitude": str(longitude) if longitude else "",
            "is_parking_available": "TRUE" if is_parking else "FALSE",
            "is_stroller_accessible": "TRUE" if is_stroller else "FALSE",
            "has_nursing_room": "TRUE" if has_nursing else "FALSE",
            "no_kids_zone": "TRUE" if no_kids else "FALSE"
        }
        places.append(new_place)
        save_places(places)
        return new_id

# EVENTS 관리
def load_events():
    return _read_csv(EVENTS_CSV)

def save_events(events):
    headers = ["event_id", "place_id", "title", "start_date", "end_date", "source_url", "raw_description", "ai_tags"]
    _write_csv(EVENTS_CSV, events, headers)

def add_or_update_event(place_id, title, start_date, end_date, source_url="", raw_description="", ai_tags=""):
    events = load_events()
    
    # 동일 장소의 동일 타이틀 이벤트가 있는지 확인
    existing_event = None
    for e in events:
        if int(e["place_id"]) == int(place_id) and e["title"] == title:
            existing_event = e
            break
            
    if existing_event:
        existing_event["start_date"] = start_date
        existing_event["end_date"] = end_date
        existing_event["source_url"] = source_url or existing_event["source_url"]
        existing_event["raw_description"] = raw_description or existing_event["raw_description"]
        existing_event["ai_tags"] = ai_tags or existing_event["ai_tags"]
        save_events(events)
        return int(existing_event["event_id"])
    else:
        new_id = 1
        if events:
            ids = [int(e["event_id"]) for e in events if e["event_id"].isdigit()]
            if ids:
                new_id = max(ids) + 1
                
        new_event = {
            "event_id": str(new_id),
            "place_id": str(place_id),
            "title": title,
            "start_date": start_date,
            "end_date": end_date,
            "source_url": source_url,
            "raw_description": raw_description,
            "ai_tags": ai_tags
        }
        events.append(new_event)
        save_events(events)
        return new_id

# METRICS 관리
def load_metrics():
    return _read_csv(METRICS_CSV)

def save_metrics(metrics):
    headers = ["metric_id", "place_id", "tmap_rank", "seoul_crowd_level", "updated_at"]
    _write_csv(METRICS_CSV, metrics, headers)

def update_real_time_metric(place_id, tmap_rank=None, seoul_crowd_level=None):
    metrics = load_metrics()
    
    existing_metric = None
    for m in metrics:
        if int(m["place_id"]) == int(place_id):
            existing_metric = m
            break
            
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if existing_metric:
        if tmap_rank is not None:
            existing_metric["tmap_rank"] = str(tmap_rank)
        if seoul_crowd_level is not None:
            existing_metric["seoul_crowd_level"] = seoul_crowd_level
        existing_metric["updated_at"] = now_str
        save_metrics(metrics)
        return int(existing_metric["metric_id"])
    else:
        new_id = 1
        if metrics:
            ids = [int(m["metric_id"]) for m in metrics if m["metric_id"].isdigit()]
            if ids:
                new_id = max(ids) + 1
                
        new_metric = {
            "metric_id": str(new_id),
            "place_id": str(place_id),
            "tmap_rank": str(tmap_rank) if tmap_rank is not None else "",
            "seoul_crowd_level": seoul_crowd_level or "LOW",
            "updated_at": now_str
        }
        metrics.append(new_metric)
        save_metrics(metrics)
        return new_id

if __name__ == "__main__":
    # 테스트용 생성 확인
    ensure_data_dir()
    print("CSV Database initialized successfully in data folder.")
