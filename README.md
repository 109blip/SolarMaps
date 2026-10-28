# SolarMaps

HAFS 유리프(유레카 리서치 프로젝트) 산출물. 지도에서 위치를 클릭하면 위도·경도와
쾨펜 기후 구분을 이용해 그 지점의 최적 태양광 패널 설치 각도(경사각·방위각)를
계산하고, **패널 개수 및 설치 면적 조절 시 학교 전력 자립률(%) 시뮬레이션**을 제공하는 웹 앱이다.

- **지도**: OpenStreetMap + Leaflet
- **시뮬레이터 UI**: **Chart.js** 기반 실시간 대화형 자립률 분석 UI + **Streamlit** 대시보드
- **호스팅/DB**: Firebase Hosting + Firestore
- **계산 엔진**: 파이썬(표준 라이브러리만 사용), 브라우저에서 **Pyodide**로 실행
- **기후 데이터**: 쾨펜 기후 분류(Chen & Chen 2013) + NASA POWER 월별 기후평년
- **실측 연동**: FNB58 → Raspberry Pi Zero W → Firestore ([pi/](pi/), 스키마는 [docs/DATA_SPEC.md](docs/DATA_SPEC.md))

물리 모델 상세와 문헌 근거는 [docs/MODEL.md](docs/MODEL.md) 참고.
최초 설치·업데이트·Pi 노드 운영 절차는 [docs/OPERATIONS.md](docs/OPERATIONS.md)에 정리돼 있다.

## 핵심 기능

1. **최적 설치각 지도**: 전 세계 지도 클릭 시 쾨펜 기후 분류 및 NASA POWER 월별 일사량을 기반으로 최적 경사각 및 방위각 산출
2. **학교 전력 자립률 시뮬레이터 (Chart.js / Streamlit)**:
   - 건물 옥상/유휴지 유효 면적($m^2$) 및 패널 개수 실시간 슬라이더 조절
   - 패널 모델 사양(400W 표준, 450W 고효율, 350W 소형) 및 한전 교육용 전기요금 연동
   - 면적 맞춤형 최적 패널 수 자동 배치(Auto-Fit) 및 면적 초과 음영 경고
   - **연간/월별 학교 전력 자립률(%)**, 총 설비용량(kW), 연간 발전량(MWh) 실시간 산출
   - **온실가스 감축량($tCO_2$) 및 소나무 식재 환산 효과**, 연간 전기요금 절감액 계산
   - **Chart.js 시각화**: 월별 수급 밸런스(Bar+Line), 자립률 도넛 게이지(Doughnut), 24시간 부하-발전 곡선(Area)
   - 건물별 프리셋(본관 옥상 550m², 과학관 400m², 체육관 800m², 전교 전면 설치 2,200m²) 원클릭 전환
   - 월별 시뮬레이션 데이터 CSV 다운로드 기능

## 개발 환경 설정

```bash
python -m venv venv
venv/Scripts/pip install -r requirements.txt
```

## 빌드

쾨펜 이진 격자와 Pyodide용 zip을 생성한다 (`public/data/`, `public/py/`는 git에 커밋하지 않음):

```bash
venv/Scripts/python scripts/build.py
```

## 테스트

```bash
venv/Scripts/python -m pytest tests/ -v
```

## 로컬 실행

### 1) 웹 지도 & Chart.js 시뮬레이터 (기본)

```bash
venv/Scripts/python -m http.server 8080 --directory public
```

브라우저에서 http://localhost:8080 접속 → 상단 **[⚡ 전력 자립률 시뮬레이터]** 탭 또는 지도 클릭.

### 2) Streamlit 전력 자립률 대시보드

```bash
pip install streamlit
streamlit run streamlit_app.py
```

## Firebase 설정

프로젝트가 아직 없다면 [docs/SETUP.md](docs/SETUP.md)를 따라 생성한다.
모니터링 기능(발전소 마커·대시보드)은 Firebase 설정 전까지 자동으로 비활성화되며,
지도·최적각 계산 및 자립률 시뮬레이터 기능은 그대로 동작한다.

## 디렉터리 구조

```
solarmaps/     계산 엔진 (표준 라이브러리만 사용, CPython/Pyodide 겸용)
               - simulation.py: 패널 개수 및 설치 면적 기반 학교 전력 자립률 계산 모듈
scripts/       빌드·시드 스크립트
tests/         pytest (test_simulation.py 등)
koppen/        쾨펜 기후 원본 데이터 (Chen & Chen 2013)
public/        Firebase Hosting 루트
               - js/ui/simulator.js: Chart.js 기반 인터랙티브 시뮬레이터 UI
               - css/simulator.css: 시뮬레이터 전용 다크 테마 반응형 스타일
streamlit_app.py Streamlit 기반 학교 전력 자립률 시뮬레이터 앱
docs/          모델 문서, 데이터 규격서, Firebase 설정 가이드
pi/            Raspberry Pi 노드 (FNB58 실측 → Firestore), 설치법은 pi/README.md
```

## 배포

```bash
venv/Scripts/python scripts/build.py
firebase deploy
```

최초 배포·이후 업데이트 시 캐시 버스팅 등 세부 절차는 [docs/OPERATIONS.md](docs/OPERATIONS.md) 참고.
