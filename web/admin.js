// 전역 데이터 저장소
let dbData = {
  places: [],
  events: [],
  metrics: []
};
let currentTable = 'places';

// CSV 파서 (app.js와 동일한 고신뢰성 파서 사용)
function parseCSV(text) {
  const lines = text.split('\n');
  if (lines.length === 0 || !lines[0].trim()) return [];
  
  const headers = parseCSVLine(lines[0]);
  const result = [];
  
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    
    const values = parseCSVLine(lines[i]);
    const row = {};
    headers.forEach((header, index) => {
      row[header.trim()] = values[index] ? values[index].trim() : '';
    });
    result.push(row);
  }
  return result;
}

function parseCSVLine(line) {
  const result = [];
  let insideQuote = false;
  let entry = '';
  
  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (char === '"') {
      insideQuote = !insideQuote;
    } else if (char === ',' && !insideQuote) {
      result.push(entry);
      entry = '';
    } else {
      entry += char;
    }
  }
  result.push(entry);
  return result;
}

// 1. 데이터 로드
async function loadAllCSV() {
  try {
    const [placesRes, eventsRes, metricsRes] = await Promise.all([
      fetch('../data/places.csv').then(r => r.text()),
      fetch('../data/events.csv').then(r => r.text()),
      fetch('../data/real_time_metrics.csv').then(r => r.text())
    ]);

    dbData.places = parseCSV(placesRes);
    dbData.events = parseCSV(eventsRes);
    dbData.metrics = parseCSV(metricsRes);

    updateStats();
    renderTable();
  } catch (error) {
    console.error('관리자 데이터 로드 실패:', error);
    document.getElementById('table-body').innerHTML = `
      <tr>
        <td colspan="100%" class="error-msg">
          <i class="fa-solid fa-circle-exclamation"></i> 데이터를 불러오는데 실패했습니다. 
          CORS 정책 문제 우회를 위해 로컬 서버가 구동 중인지 확인하세요.
        </td>
      </tr>
    `;
  }
}

// 2. 상단 통계 갱신
function updateStats() {
  document.getElementById('admin-places-count').textContent = dbData.places.length;
  document.getElementById('admin-events-count').textContent = dbData.events.length;
  document.getElementById('admin-metrics-count').textContent = dbData.metrics.length;
}

// 3. 테이블 렌더링 핵심 로직
function renderTable() {
  const query = document.getElementById('admin-search-input').value.toLowerCase().trim();
  const headersRow = document.getElementById('table-headers');
  const bodyContainer = document.getElementById('table-body');
  
  let rawList = dbData[currentTable];
  let filtered = [...rawList];

  // A. 검색 필터 적용
  if (query) {
    filtered = filtered.filter(row => {
      return Object.values(row).some(val => val.toLowerCase().includes(query));
    });
  }

  // B. 테이블 컬럼 정의 및 한글화 맵핑
  const colMappings = {
    places: {
      place_id: 'ID',
      name: '장소명',
      category: '분류',
      address: '주소',
      latitude: '위도',
      longitude: '경도',
      is_parking_available: '주차',
      is_stroller_accessible: '유모차',
      has_nursing_room: '수유실',
      no_kids_zone: '노키즈'
    },
    events: {
      event_id: 'ID',
      place_id: '장소 ID',
      title: '행사 타이틀',
      start_date: '시작일',
      end_date: '종료일',
      source_url: '소스 URL',
      raw_description: '설명',
      ai_tags: 'AI 태그'
    },
    metrics: {
      metric_id: '지표 ID',
      place_id: '장소 ID',
      tmap_rank: 'TMap 순위',
      seoul_crowd_level: '인파 혼잡도',
      updated_at: '업데이트 시간'
    }
  };

  const currentMap = colMappings[currentTable];
  const keys = Object.keys(currentMap);

  // 헤더 그리기
  headersRow.innerHTML = keys.map(k => `<th>${currentMap[k]}</th>`).join('');

  // 내용 그리기
  if (filtered.length === 0) {
    bodyContainer.innerHTML = `
      <tr>
        <td colspan="${keys.length}" style="text-align: center; color: var(--text-secondary); padding: 40px 10px;">
          <i class="fa-solid fa-magnifying-glass" style="font-size: 24px; display:block; margin-bottom: 10px; opacity:0.4;"></i>
          조건에 부합하는 데이터가 존재하지 않습니다.
        </td>
      </tr>
    `;
    return;
  }

  bodyContainer.innerHTML = filtered.map(row => {
    const tds = keys.map(key => {
      const val = row[key] || '';
      
      // 특별한 타입의 필드 렌더링 가공
      if (val === 'TRUE') {
        return `<td><span class="admin-badge badge-true">Y</span></td>`;
      } else if (val === 'FALSE') {
        return `<td><span class="admin-badge badge-false">N</span></td>`;
      }
      
      if (key === 'seoul_crowd_level') {
        const crowdLabels = {
          'LOW': '여유',
          'MODERATE': '보통',
          'CONGESTED': '혼잡',
          'VERY_CONGESTED': '매우 혼잡'
        };
        const text = crowdLabels[val] || val;
        return `<td><span class="admin-badge crowd-${val.toLowerCase()}">${text}</span></td>`;
      }
      
      // 글자수 제한이 필요한 컬럼 (설명, 주소, 태그 등)
      if (val.length > 20) {
        const textToShow = val.substring(0, 18) + '...';
        // 전체 읽기 버튼 심기
        return `<td>
          <span title="${val.replace(/"/g, '&quot;')}">${textToShow}</span>
          <button class="text-more-btn" onclick="showFullText('${key}', '${val.replace(/'/g, "\\'").replace(/"/g, '&quot;')}')"><i class="fa-solid fa-expand"></i></button>
        </td>`;
      }

      return `<td>${val}</td>`;
    }).join('');

    return `<tr>${tds}</tr>`;
  }).join('');
}

// 4. 모달 디테일 텍스트 팝업 제어
function showFullText(key, text) {
  const modal = document.getElementById('details-modal');
  const title = document.getElementById('details-modal-title');
  const desc = document.getElementById('details-modal-desc');
  
  const titleMap = {
    raw_description: '상세 설명 정보',
    ai_tags: 'AI 매핑 정보 및 가중치 상세',
    address: '도로명 전체 주소',
    source_url: '이벤트 원본 소스 주소'
  };

  title.textContent = titleMap[key] || '세부 데이터 정보';
  desc.textContent = text;
  modal.style.display = 'flex';
}

// 5. 이벤트 핸들러 초기화
function initAdminEvents() {
  // 테이블 스위치 탭 리스너
  const buttons = document.querySelectorAll('.switcher-btn');
  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      buttons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      
      currentTable = btn.getAttribute('data-table');
      // 검색창 리셋
      document.getElementById('admin-search-input').value = '';
      renderTable();
    });
  });

  // 검색창 입력 이벤트 리스너
  const searchInput = document.getElementById('admin-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', renderTable);
  }

  // 모달 닫기
  const modal = document.getElementById('details-modal');
  const closeBtn = document.getElementById('details-modal-close-btn');
  if (modal && closeBtn) {
    closeBtn.addEventListener('click', () => {
      modal.style.display = 'none';
    });
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.style.display = 'none';
      }
    });
  }

  // 관리자 수집 실행 버튼 리스너
  const runCollectBtn = document.getElementById('admin-run-collect-btn');
  if (runCollectBtn) {
    runCollectBtn.addEventListener('click', async () => {
      runCollectBtn.disabled = true;
      runCollectBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 수집 중...';
      try {
        const res = await fetch('/api/refresh', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          alert(`✅ 수집 성공!\n\n${data.status_msg || '실시간 데이터 수집 및 DB 반영이 완료되었습니다.'}`);
          await loadAllCSV();
        } else {
          alert(`❌ 오류: ${data.message}`);
        }
      } catch (err) {
        console.error(err);
        alert('❌ 서버 수집 요청에 실패했습니다. (run_web.py 구동 상태를 확인하세요)');
      } finally {
        runCollectBtn.disabled = false;
        runCollectBtn.innerHTML = '<i class="fa-solid fa-arrows-rotate"></i> 수집 파이프라인 실행';
      }
    });
  }
}

// 초기화 호출
document.addEventListener('DOMContentLoaded', () => {
  initAdminEvents();
  loadAllCSV();
});
