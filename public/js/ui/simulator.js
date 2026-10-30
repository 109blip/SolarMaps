/**
 * SolarMaps — 학교 전력 자립률 계산 시뮬레이터 (Chart.js 기반 UI 모듈)
 *
 * 패널 개수 및 설치 면적 실시간 조절, Chart.js 복합/도넛/영역 차트 시각화,
 * KPI 계산 및 CSV 내보내기를 담당한다.
 */

// 월별 일수 및 기본 일조시간(PSH, h/day)
const DAYS_PER_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
const DEFAULT_PSH = [2.95, 3.55, 4.25, 4.45, 4.35, 3.75, 3.35, 3.70, 3.85, 3.90, 3.20, 2.75];
const CONSUMPTION_FACTORS = [1.08, 0.92, 1.02, 0.97, 0.96, 1.04, 1.06, 0.90, 0.98, 0.96, 1.05, 1.06];
const HOURLY_LOAD_RATIO = [
  0.28, 0.25, 0.24, 0.24, 0.26, 0.32,
  0.45, 0.75, 1.35, 1.65, 1.70, 1.55,
  1.30, 1.60, 1.65, 1.50, 1.25, 0.95,
  0.75, 0.65, 0.55, 0.45, 0.38, 0.32
];
const HOURLY_SOLAR_RATIO = [
  0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
  0.03, 0.15, 0.42, 0.72, 0.91, 0.98,
  1.0, 0.95, 0.82, 0.58, 0.30, 0.08,
  0.0, 0.0, 0.0, 0.0, 0.0, 0.0
];

const PRESETS = {
  hafs_total: {
    name: "HAFS 옥상·유휴지 전체 (3회 실측 평균)",
    area: 7612.7,
    panels: 2057,
    monthlyKwh: 135866,
    desc: "3회 실측(1차 7,606 / 2차 7,644 / 3차 7,588 m², 평균 7,612.7m²) · 고지서 B안(기숙사 수전 중복 제외 월 135,866 kWh) 자립률 ~60%",
    trials: [7606, 7644, 7588],
  },
  hafs_scenario_a: {
    name: "HAFS 전체 — 고지서 A안 (표 원본)",
    area: 7612.7,
    panels: 2057,
    monthlyKwh: 271627,
    desc: "3회 실측 평균 7,612.7m² · 고지서 A안(표 원본 8개월 2,173,012 kWh, 월 271,627 kWh) 자립률 ~30%",
    trials: [7606, 7644, 7588],
  },
  main_bldg: {
    name: "본관 옥상 유휴지",
    area: 550,
    panels: 200,
    monthlyKwh: 12500,
    desc: "본관 4층 옥상 (유효면적 550m², 80kW 잠재용량)",
  },
  science_bldg: {
    name: "과학관 옥상",
    area: 400,
    panels: 150,
    monthlyKwh: 9500,
    desc: "과학실험실 및 연구동 옥상 (유효면적 400m²)",
  },
  gym_roof: {
    name: "체육관 대형 지붕",
    area: 800,
    panels: 300,
    monthlyKwh: 14000,
    desc: "실내체육관 지붕 유휴공간 (유효면적 800m²)",
  },
  stand_test: {
    name: "소형 실증 실험 1호기",
    area: 20,
    panels: 8,
    monthlyKwh: 12500,
    desc: "야외 거치대 1·2호기 실험용 구성",
  },
  custom: {
    name: "사용자 직접 설정",
    area: 500,
    panels: 180,
    monthlyKwh: 12500,
    desc: "슬라이더와 입력창으로 자유롭게 조절",
  },
};

export class SolarSimulator {
  constructor(containerEl) {
    this.container = containerEl;
    this.state = {
      preset: "hafs_total",
      areaM2: 7612.7,
      panelCount: 2057,
      panelRatedW: 400,
      panelAreaM2: 1.85,
      monthlyConsumptionKwh: 135866,
      tiltDeg: 30,
      azimuthDeg: 180,
      elecRateKrw: 130,
      co2Factor: 0.4781,
    };

    this.chartInstances = {
      monthly: null,
      donut: null,
      hourly: null,
    };

    this.initHtml();
    this.bindEvents();
    this.update();
  }

  initHtml() {
    this.container.innerHTML = `
      <div class="sim-header">
        <div class="sim-header-title">
          <h2>⚡ 학교 전력 자립률 계산 시뮬레이터</h2>
          <p>태양광 패널 개수 및 설치 면적 조절에 따른 학교 전력 자립률(%), 발전량, 경제성 및 피크 삭감 효과를 실시간으로 분석합니다.</p>
        </div>
        <div style="display:flex;gap:8px;">
          <button id="sim-export-csv-btn" class="btn btn-outline btn-sm">📥 CSV 데이터 내보내기</button>
          <button id="sim-close-btn" class="btn btn-primary btn-sm">🗺️ 지도로 돌아가기</button>
        </div>
      </div>

      <!-- 건물 / 구역 프리셋 선택바 -->
      <div class="sim-presets-bar">
        ${Object.entries(PRESETS)
          .map(
            ([key, p]) => `
          <button class="sim-preset-btn ${key === this.state.preset ? "active" : ""}" data-preset="${key}">
            ${p.name} (${p.area}m²)
          </button>
        `
          )
          .join("")}
      </div>

      <!-- 메인 2열 그리드 -->
      <div class="sim-grid-layout">
        <!-- 좌측: 입력 컨트롤 카드 -->
        <div class="sim-controls-card">
          <!-- 1. 설치 가능 면적 -->
          <div class="control-group">
            <div class="control-header">
              <label for="input-area-slider">📐 설치 가능 면적</label>
              <span class="control-hint">옥상/유휴지 유효면적</span>
            </div>
            <div class="control-input-row">
              <input type="range" id="input-area-slider" class="control-slider" min="10" max="15000" step="10" value="${this.state.areaM2}" />
              <input type="number" id="input-area-num" class="control-number-input" min="10" max="30000" step="10" value="${this.state.areaM2}" />
              <span class="control-unit">m²</span>
            </div>
            <div style="font-size:11px;color:#38bdf8;margin-top:4px;background:rgba(56,189,248,0.1);padding:4px 8px;border-radius:4px;">
              📊 HAFS 3회 실측치: <strong>1차 7,606</strong> / <strong>2차 7,644</strong> / <strong>3차 7,588 m²</strong> (평균 7,612.7 m², ±0.38%)
            </div>
          </div>

          <!-- 2. 패널 개수 -->
          <div class="control-group">
            <div class="control-header">
              <label for="input-panels-slider">☀️ 태양광 패널 개수</label>
              <span class="control-hint">설치 수량</span>
            </div>
            <div class="control-input-row">
              <input type="range" id="input-panels-slider" class="control-slider" min="1" max="5000" step="1" value="${this.state.panelCount}" />
              <input type="number" id="input-panels-num" class="control-number-input" min="1" max="10000" step="1" value="${this.state.panelCount}" />
              <span class="control-unit">장</span>
            </div>
          </div>

          <!-- 면적 맞춤 자동 배치 버튼 -->
          <button id="btn-auto-fit-panels" class="auto-fit-btn">
            ⚡ 면적 맞춤 권장 패널 수 자동 배치 (<span id="auto-fit-count-text">2057</span>장)
          </button>

          <!-- 면적 점유율 게이지 -->
          <div class="area-gauge-container">
            <div class="area-gauge-header">
              <span style="color:var(--text-secondary);">설치 면적 점유율</span>
              <strong id="area-gauge-percent-text">78.5%</strong>
            </div>
            <div class="area-gauge-bar-bg">
              <div id="area-gauge-bar-fill" class="area-gauge-bar-fill" style="width: 78.5%;"></div>
            </div>
            <div id="area-gauge-desc" style="font-size:11px;color:var(--text-muted);margin-top:2px;">
              패널 면적 370 m² + 경사각 그림자 회피 간격 반영
            </div>
          </div>

          <!-- 3. 패널 모델 선택 -->
          <div class="control-group">
            <div class="control-header">
              <label for="select-panel-spec">⚙️ 패널 사양 모델</label>
            </div>
            <select id="select-panel-spec" class="control-number-input" style="width:100%;text-align:left;padding:8px 10px;">
              <option value="400_1.85" selected>400W 표준 루프탑 패널 (1.85 m²)</option>
              <option value="450_2.00">450W 고효율 대형 패널 (2.00 m²)</option>
              <option value="350_1.65">350W 소형 경량 패널 (1.65 m²)</option>
              <option value="30_0.18">30W 휴대용 실증기 패널 (0.18 m²)</option>
            </select>
          </div>

          <!-- 4. 학교 월평균 전력 소비량 -->
          <div class="control-group">
            <div class="control-header">
              <label for="input-consumption-slider">🏫 학교 월 전력 소비량</label>
              <span class="control-hint">한전 고지서 기준</span>
            </div>
            <div class="control-input-row">
              <input type="range" id="input-consumption-slider" class="control-slider" min="1000" max="400000" step="1000" value="${this.state.monthlyConsumptionKwh}" />
              <input type="number" id="input-consumption-num" class="control-number-input" min="500" max="600000" step="1000" value="${this.state.monthlyConsumptionKwh}" />
              <span class="control-unit">kWh</span>
            </div>
            <div style="display:flex;gap:6px;margin-top:6px;">
              <button type="button" id="btn-quick-scen-b" class="btn btn-outline btn-sm" style="flex:1;font-size:10px;padding:3px 6px;">
                B안: 135,866 kWh (기숙사 제외)
              </button>
              <button type="button" id="btn-quick-scen-a" class="btn btn-outline btn-sm" style="flex:1;font-size:10px;padding:3px 6px;">
                A안: 271,627 kWh (표 원본)
              </button>
            </div>
          </div>

          <!-- 5. 설치 각도 정보 -->
          <div class="control-group" style="padding-top:6px;border-top:1px solid var(--border);">
            <div class="control-header">
              <label>📐 설치 각도 설정</label>
              <span style="font-size:11px;color:var(--primary);">SolarMaps 계산값 연동</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--text-secondary);margin-top:4px;">
              <span>경사각: <strong id="sim-tilt-text" style="color:var(--text);">30.0°</strong></span>
              <span>방위각: <strong id="sim-azimuth-text" style="color:var(--text);">180° (남향)</strong></span>
            </div>
          </div>
        </div>

        <!-- 우측: KPI 및 Chart.js 차트 대시보드 -->
        <div class="sim-dashboard-col">
          <!-- 면적 초과 경고 알림 (조건부 노출) -->
          <div id="sim-area-alert" class="alert alert-warning" style="display:none;margin-bottom:14px;">
            ⚠️ <strong>설치 면적 초과 경고:</strong> 패널 배치를 위한 필요 면적이 유효 면적을 초과했습니다. 패널 간 앞뒤 음영 간섭으로 발전량이 저하될 수 있습니다.
          </div>

          <!-- KPI 카드 4열 -->
          <div class="sim-kpi-grid">
            <div class="sim-kpi-card highlight">
              <div class="sim-kpi-label">⚡ 학교 전력 자립률</div>
              <div id="kpi-self-sufficiency" class="sim-kpi-val success">0.0 %</div>
              <div id="kpi-status-badge" class="sim-kpi-sub">계산 중…</div>
            </div>

            <div class="sim-kpi-card">
              <div class="sim-kpi-label">🏢 총 설비 용량</div>
              <div id="kpi-capacity" class="sim-kpi-val primary">0.0 kW</div>
              <div id="kpi-capacity-sub" class="sim-kpi-sub">패널 0장 (0 m²)</div>
            </div>

            <div class="sim-kpi-card">
              <div class="sim-kpi-label">☀️ 연간 예상 발전량</div>
              <div id="kpi-generation" class="sim-kpi-val">0.0 MWh</div>
              <div id="kpi-generation-daily" class="sim-kpi-sub">일평균 0.0 kWh</div>
            </div>

            <div class="sim-kpi-card">
              <div class="sim-kpi-label">💰 연간 전기요금 절감</div>
              <div id="kpi-bill-savings" class="sim-kpi-val">0 만 원</div>
              <div class="sim-kpi-sub">교육용 고압 130원/kWh 기준</div>
            </div>

            <div class="sim-kpi-card">
              <div class="sim-kpi-label">🌲 연간 탄소 감축량</div>
              <div id="kpi-co2-reduced" class="sim-kpi-val">0.0 톤 CO₂</div>
              <div id="kpi-trees-sub" class="sim-kpi-sub">소나무 0 그루 식재 효과</div>
            </div>
          </div>

          <!-- 차트 그리드: 1. 월별 수급 밸런스 / 2. 자립률 도넛 게이지 -->
          <div class="sim-charts-grid">
            <div class="sim-chart-card">
              <div class="sim-chart-header">
                <h3>📊 월별 학교 소비량 vs 태양광 발전량 및 자립률</h3>
                <span style="font-size:11px;color:var(--text-secondary);">막대: kWh / 꺾은선: 자립률(%)</span>
              </div>
              <div class="chart-canvas-box">
                <canvas id="chart-monthly-balance"></canvas>
              </div>
            </div>

            <div class="sim-chart-card">
              <div class="sim-chart-header">
                <h3>⚡ 전력 수급 밸런스</h3>
              </div>
              <div class="chart-canvas-box" style="display:flex;align-items:center;justify-content:center;">
                <canvas id="chart-donut-gauge"></canvas>
                <div class="donut-center-text">
                  <div id="donut-center-pct" class="donut-center-pct">0%</div>
                  <div class="donut-center-sub">연간 자립률</div>
                </div>
              </div>
            </div>
          </div>

          <!-- 하단: 24시간 피크 감축 곡선 차트 -->
          <div class="sim-chart-card" style="margin-bottom:20px;">
            <div class="sim-chart-header">
              <h3>📈 대표 평일 24시간 부하-발전 곡선 (주간 피크 삭감 효과)</h3>
              <span style="font-size:11px;color:var(--text-secondary);">학교 등교·수업 피크(09~16시)와 태양광 발전 피크 일치도</span>
            </div>
            <div class="chart-canvas-box" style="min-height:220px;">
              <canvas id="chart-hourly-profile"></canvas>
            </div>
          </div>

          <!-- 월별 상세 시뮬레이션 테이블 -->
          <div class="sim-table-card">
            <div class="sim-chart-header">
              <h3>📋 월별 시뮬레이션 세부 수치표</h3>
              <button id="toggle-table-btn" class="btn btn-outline btn-sm">세부 수치 접기/펼치기</button>
            </div>
            <div id="sim-table-container" class="sim-table-wrap">
              <table class="sim-data-table">
                <thead>
                  <tr>
                    <th>월</th>
                    <th>일평균 일조(h)</th>
                    <th>태양광 발전(kWh)</th>
                    <th>학교 소비(kWh)</th>
                    <th>자립률(%)</th>
                    <th>자가소비(kWh)</th>
                    <th>한전수전(kWh)</th>
                    <th>절감액(원)</th>
                  </tr>
                </thead>
                <tbody id="sim-data-table-body">
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  bindEvents() {
    // 1. 프리셋 버튼 클릭
    this.container.querySelectorAll(".sim-preset-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const key = btn.dataset.preset;
        this.selectPreset(key);
      });
    });

    // 2. 면적 슬라이더 및 숫자 입력 동기화
    const areaSlider = this.container.querySelector("#input-area-slider");
    const areaNum = this.container.querySelector("#input-area-num");
    areaSlider.addEventListener("input", (e) => {
      this.state.areaM2 = parseFloat(e.target.value) || 0;
      areaNum.value = this.state.areaM2;
      this.update();
    });
    areaNum.addEventListener("input", (e) => {
      this.state.areaM2 = parseFloat(e.target.value) || 0;
      areaSlider.value = this.state.areaM2;
      this.update();
    });

    // 3. 패널 수 슬라이더 및 숫자 입력 동기화
    const panelsSlider = this.container.querySelector("#input-panels-slider");
    const panelsNum = this.container.querySelector("#input-panels-num");
    panelsSlider.addEventListener("input", (e) => {
      this.state.panelCount = parseInt(e.target.value, 10) || 0;
      panelsNum.value = this.state.panelCount;
      this.update();
    });
    panelsNum.addEventListener("input", (e) => {
      this.state.panelCount = parseInt(e.target.value, 10) || 0;
      panelsSlider.value = this.state.panelCount;
      this.update();
    });

    // 4. 자동 맞춤 버튼
    this.container.querySelector("#btn-auto-fit-panels").addEventListener("click", () => {
      const rec = this.calculateRecommendedPanels();
      this.state.panelCount = rec;
      panelsSlider.value = rec;
      panelsNum.value = rec;
      this.update();
    });

    // 5. 패널 스펙 셀렉트
    this.container.querySelector("#select-panel-spec").addEventListener("change", (e) => {
      const [w, a] = e.target.value.split("_").map(Number);
      this.state.panelRatedW = w;
      this.state.panelAreaM2 = a;
      this.update();
    });

    // 6. 학교 전력 소비량 슬라이더 및 숫자 입력
    const consSlider = this.container.querySelector("#input-consumption-slider");
    const consNum = this.container.querySelector("#input-consumption-num");
    consSlider.addEventListener("input", (e) => {
      this.state.monthlyConsumptionKwh = parseFloat(e.target.value) || 0;
      consNum.value = this.state.monthlyConsumptionKwh;
      this.update();
    });
    consNum.addEventListener("input", (e) => {
      this.state.monthlyConsumptionKwh = parseFloat(e.target.value) || 0;
      consSlider.value = this.state.monthlyConsumptionKwh;
      this.update();
    });

    const btnScenB = this.container.querySelector("#btn-quick-scen-b");
    if (btnScenB) {
      btnScenB.addEventListener("click", () => {
        this.state.monthlyConsumptionKwh = 135866;
        consSlider.value = 135866;
        consNum.value = 135866;
        this.update();
      });
    }
    const btnScenA = this.container.querySelector("#btn-quick-scen-a");
    if (btnScenA) {
      btnScenA.addEventListener("click", () => {
        this.state.monthlyConsumptionKwh = 271627;
        consSlider.value = 271627;
        consNum.value = 271627;
        this.update();
      });
    }

    // 7. 테이블 토글
    const tableWrap = this.container.querySelector("#sim-table-container");
    this.container.querySelector("#toggle-table-btn").addEventListener("click", () => {
      tableWrap.hidden = !tableWrap.hidden;
    });

    // 8. CSV 내보내기
    this.container.querySelector("#sim-export-csv-btn").addEventListener("click", () => {
      this.exportCsv();
    });

    // 9. 지도로 복귀 버튼
    this.container.querySelector("#sim-close-btn").addEventListener("click", () => {
      if (this.onClose) this.onClose();
    });
  }

  selectPreset(key) {
    const p = PRESETS[key];
    if (!p) return;
    this.state.preset = key;
    this.state.areaM2 = p.area;
    this.state.panelCount = p.panels;
    this.state.monthlyConsumptionKwh = p.monthlyKwh;

    // UI 입력창 반영
    this.container.querySelector("#input-area-slider").value = p.area;
    this.container.querySelector("#input-area-num").value = p.area;
    this.container.querySelector("#input-panels-slider").value = p.panels;
    this.container.querySelector("#input-panels-num").value = p.panels;
    this.container.querySelector("#input-consumption-slider").value = p.monthlyKwh;
    this.container.querySelector("#input-consumption-num").value = p.monthlyKwh;

    this.container.querySelectorAll(".sim-preset-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.preset === key);
    });

    this.update();
  }

  calculateRecommendedPanels() {
    const spacing = 1.0 + 0.35 * Math.sin((Math.max(0, Math.min(60, this.state.tiltDeg)) * Math.PI) / 180);
    return Math.max(1, Math.floor(this.state.areaM2 / (this.state.panelAreaM2 * spacing)));
  }

  computeSimulation() {
    const { areaM2, panelCount, panelRatedW, panelAreaM2, monthlyConsumptionKwh, tiltDeg, azimuthDeg, elecRateKrw, co2Factor } = this.state;

    const spacing = 1.0 + 0.35 * Math.sin((Math.max(0, Math.min(60, tiltDeg)) * Math.PI) / 180);
    const capacityKw = (panelCount * panelRatedW) / 1000.0;
    const totalPanelAreaM2 = panelCount * panelAreaM2;
    const requiredAreaM2 = totalPanelAreaM2 * spacing;
    const areaUtilizationPct = areaM2 > 0 ? (requiredAreaM2 / areaM2) * 100 : 0;
    const isAreaExceeded = requiredAreaM2 > areaM2 + 0.1;

    // 각도 보정 계수
    const azDiff = Math.abs(azimuthDeg - 180);
    const azFactor = Math.max(0.7, 1.0 - 0.0015 * azDiff);
    const tiltDiff = Math.abs(tiltDeg - 32);
    const tiltFactor = Math.max(0.8, 1.0 - 0.002 * Math.pow(tiltDiff, 1.2));
    const angleEfficiency = azFactor * tiltFactor;
    const systemEfficiency = 0.86 * angleEfficiency; // 14% 시스템 손실 반영

    const monthly = [];
    let totGen = 0;
    let totCons = 0;
    let totSelf = 0;
    let totGrid = 0;
    let totSurplus = 0;
    let totSavings = 0;

    for (let m = 0; m < 12; m++) {
      const days = DAYS_PER_MONTH[m];
      const psh = DEFAULT_PSH[m];
      const mGen = capacityKw * psh * systemEfficiency * days;
      const mCons = monthlyConsumptionKwh * CONSUMPTION_FACTORS[m];
      const selfSuff = mCons > 0 ? (mGen / mCons) * 100 : 0;
      const selfConsumed = Math.min(mGen, mCons);
      const gridImport = Math.max(0, mCons - mGen);
      const surplus = Math.max(0, mGen - mCons);
      const savings = selfConsumed * elecRateKrw;

      totGen += mGen;
      totCons += mCons;
      totSelf += selfConsumed;
      totGrid += gridImport;
      totSurplus += surplus;
      totSavings += savings;

      monthly.push({
        month: m + 1,
        days,
        psh,
        gen: mGen,
        cons: mCons,
        selfSuff,
        selfConsumed,
        gridImport,
        surplus,
        savings,
      });
    }

    const annualSelfSuffPct = totCons > 0 ? (totGen / totCons) * 100 : 0;
    const co2ReducedKg = totGen * co2Factor;
    const trees = co2ReducedKg / 6.6;

    // 24시간 부하 곡선
    const avgDailyCons = totCons / 365;
    const baseKw = avgDailyCons / 24;
    const hourly = [];
    for (let h = 0; h < 24; h++) {
      const loadKw = baseKw * HOURLY_LOAD_RATIO[h];
      const solarKw = capacityKw * systemEfficiency * HOURLY_SOLAR_RATIO[h];
      const netKw = Math.max(0, loadKw - solarKw);
      hourly.push({ hour: h, loadKw, solarKw, netKw });
    }

    let statusText = "기초 보조 수준";
    if (annualSelfSuffPct >= 100) statusText = "완전 자립 & 잉여 (RE100)";
    else if (annualSelfSuffPct >= 60) statusText = "고도 자립 (60~100%)";
    else if (annualSelfSuffPct >= 30) statusText = "핵심 자립 (30~60%)";
    else if (annualSelfSuffPct >= 10) statusText = "부분 자립 (10~30%)";

    return {
      capacityKw,
      totalPanelAreaM2,
      requiredAreaM2,
      areaUtilizationPct,
      isAreaExceeded,
      annualSelfSuffPct,
      totGen,
      totCons,
      totSelf,
      totGrid,
      totSurplus,
      totSavings,
      co2ReducedKg,
      trees,
      monthly,
      hourly,
      statusText,
    };
  }

  update() {
    const data = this.computeSimulation();

    // 1. 게이지 및 면적 알림 갱신
    const recPanels = this.calculateRecommendedPanels();
    this.container.querySelector("#auto-fit-count-text").textContent = recPanels;
    this.container.querySelector("#area-gauge-percent-text").textContent = `${data.areaUtilizationPct.toFixed(1)}%`;

    const gaugeBar = this.container.querySelector("#area-gauge-bar-fill");
    gaugeBar.style.width = `${Math.min(100, data.areaUtilizationPct)}%`;
    gaugeBar.className = `area-gauge-bar-fill ${data.areaUtilizationPct > 100 ? "danger" : data.areaUtilizationPct > 85 ? "warning" : ""}`;

    this.container.querySelector("#area-gauge-desc").textContent = `패널 면적 ${data.totalPanelAreaM2.toFixed(1)} m² + 경사각 그림자 회피 간격 반영 (필요: ${data.requiredAreaM2.toFixed(1)} m²)`;

    const areaAlert = this.container.querySelector("#sim-area-alert");
    areaAlert.style.display = data.isAreaExceeded ? "block" : "none";

    // 2. KPI 카드 수치 갱신
    this.container.querySelector("#kpi-self-sufficiency").textContent = `${data.annualSelfSuffPct.toFixed(1)} %`;
    this.container.querySelector("#kpi-status-badge").textContent = data.statusText;
    this.container.querySelector("#donut-center-pct").textContent = `${data.annualSelfSuffPct.toFixed(1)}%`;

    this.container.querySelector("#kpi-capacity").innerHTML = `${data.capacityKw.toFixed(1)} <span style="font-size:14px;">kW</span>`;
    this.container.querySelector("#kpi-capacity-sub").textContent = `패널 ${this.state.panelCount}장 (${data.totalPanelAreaM2.toFixed(1)} m²)`;

    this.container.querySelector("#kpi-generation").innerHTML = `${(data.totGen / 1000).toFixed(1)} <span style="font-size:14px;">MWh</span>`;
    this.container.querySelector("#kpi-generation-daily").textContent = `일평균 ${(data.totGen / 365).toFixed(1)} kWh`;

    this.container.querySelector("#kpi-bill-savings").innerHTML = `${Math.round(data.totSavings / 10000).toLocaleString()} <span style="font-size:14px;">만 원</span>`;

    this.container.querySelector("#kpi-co2-reduced").innerHTML = `${(data.co2ReducedKg / 1000).toFixed(1)} <span style="font-size:14px;">톤 CO₂</span>`;
    this.container.querySelector("#kpi-trees-sub").textContent = `소나무 ${Math.round(data.trees).toLocaleString()} 그루 식재 효과`;

    this.container.querySelector("#sim-tilt-text").textContent = `${this.state.tiltDeg.toFixed(1)}°`;
    this.container.querySelector("#sim-azimuth-text").textContent = `${this.state.azimuthDeg.toFixed(0)}° (남향)`;

    // 3. 테이블 내용 갱신
    const tbody = this.container.querySelector("#sim-data-table-body");
    tbody.innerHTML = data.monthly
      .map(
        (m) => `
      <tr>
        <td><strong>${m.month}월</strong></td>
        <td>${m.psh.toFixed(2)}</td>
        <td style="color:var(--primary);font-weight:600;">${m.gen.toFixed(0).toLocaleString()}</td>
        <td>${m.cons.toFixed(0).toLocaleString()}</td>
        <td style="color:var(--success);font-weight:700;">${m.selfSuff.toFixed(1)}%</td>
        <td>${m.selfConsumed.toFixed(0).toLocaleString()}</td>
        <td>${m.gridImport.toFixed(0).toLocaleString()}</td>
        <td>${Math.round(m.savings).toLocaleString()}</td>
      </tr>
    `
      )
      .join("");

    // 4. Chart.js 차트 렌더링 / 갱신
    this.renderCharts(data);
  }

  renderCharts(data) {
    if (!window.Chart) return;

    // 1. 월별 수급 밸런스 복합 차트 (Bar + Line)
    const ctxMonthly = this.container.querySelector("#chart-monthly-balance");
    if (ctxMonthly) {
      const labels = data.monthly.map((m) => `${m.month}월`);
      const consData = data.monthly.map((m) => Math.round(m.cons));
      const genData = data.monthly.map((m) => Math.round(m.gen));
      const suffData = data.monthly.map((m) => parseFloat(m.selfSuff.toFixed(1)));

      if (this.chartInstances.monthly) {
        this.chartInstances.monthly.data.datasets[0].data = consData;
        this.chartInstances.monthly.data.datasets[1].data = genData;
        this.chartInstances.monthly.data.datasets[2].data = suffData;
        this.chartInstances.monthly.update("none");
      } else {
        this.chartInstances.monthly = new window.Chart(ctxMonthly, {
          type: "bar",
          data: {
            labels,
            datasets: [
              {
                label: "학교 소비량 (kWh)",
                data: consData,
                backgroundColor: "rgba(148, 163, 184, 0.45)",
                borderColor: "#94a3b8",
                borderWidth: 1,
                borderRadius: 4,
                yAxisID: "y",
              },
              {
                label: "태양광 발전량 (kWh)",
                data: genData,
                backgroundColor: "rgba(96, 165, 250, 0.8)",
                borderColor: "#38bdf8",
                borderWidth: 1,
                borderRadius: 4,
                yAxisID: "y",
              },
              {
                label: "전력 자립률 (%)",
                data: suffData,
                type: "line",
                borderColor: "#10b981",
                backgroundColor: "#10b981",
                borderWidth: 2.5,
                pointRadius: 3,
                tension: 0.25,
                yAxisID: "y1",
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: {
                labels: { color: "#94a3b8", font: { size: 11 } },
              },
              tooltip: {
                mode: "index",
                intersect: false,
              },
            },
            scales: {
              x: {
                grid: { color: "rgba(255,255,255,0.06)" },
                ticks: { color: "#94a3b8" },
              },
              y: {
                position: "left",
                grid: { color: "rgba(255,255,255,0.06)" },
                ticks: { color: "#94a3b8" },
                title: { display: true, text: "전력량 (kWh)", color: "#94a3b8", font: { size: 11 } },
              },
              y1: {
                position: "right",
                grid: { drawOnChartArea: false },
                ticks: { color: "#10b981" },
                min: 0,
                title: { display: true, text: "자립률 (%)", color: "#10b981", font: { size: 11 } },
              },
            },
          },
        });
      }
    }

    // 2. 전력 수급 밸런스 도넛 게이지 차트
    const ctxDonut = this.container.querySelector("#chart-donut-gauge");
    if (ctxDonut) {
      const selfVal = Math.round(data.totSelf);
      const gridVal = Math.round(data.totGrid);

      if (this.chartInstances.donut) {
        this.chartInstances.donut.data.datasets[0].data = [selfVal, gridVal];
        this.chartInstances.donut.update("none");
      } else {
        this.chartInstances.donut = new window.Chart(ctxDonut, {
          type: "doughnut",
          data: {
            labels: ["태양광 자가소비", "한전망 수전량"],
            datasets: [
              {
                data: [selfVal, gridVal],
                backgroundColor: ["#10b981", "#334155"],
                borderWidth: 0,
                cutout: "75%",
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: {
                position: "bottom",
                labels: { color: "#94a3b8", font: { size: 11 } },
              },
              tooltip: {
                callbacks: {
                  label: (ctx) => `${ctx.label}: ${ctx.parsed.toLocaleString()} kWh`,
                },
              },
            },
          },
        });
      }
    }

    // 3. 24시간 부하 vs 발전 영역 차트
    const ctxHourly = this.container.querySelector("#chart-hourly-profile");
    if (ctxHourly) {
      const labels = data.hourly.map((h) => `${h.hour}시`);
      const loadData = data.hourly.map((h) => h.loadKw);
      const solarData = data.hourly.map((h) => h.solarKw);
      const netData = data.hourly.map((h) => h.netKw);

      if (this.chartInstances.hourly) {
        this.chartInstances.hourly.data.datasets[0].data = loadData;
        this.chartInstances.hourly.data.datasets[1].data = solarData;
        this.chartInstances.hourly.data.datasets[2].data = netData;
        this.chartInstances.hourly.update("none");
      } else {
        this.chartInstances.hourly = new window.Chart(ctxHourly, {
          type: "line",
          data: {
            labels,
            datasets: [
              {
                label: "학교 기본 전력 부하 (kW)",
                data: loadData,
                borderColor: "#f59e0b",
                backgroundColor: "rgba(245, 158, 11, 0.12)",
                fill: true,
                borderWidth: 2,
                pointRadius: 1,
                tension: 0.3,
              },
              {
                label: "태양광 발전 출력 (kW)",
                data: solarData,
                borderColor: "#38bdf8",
                backgroundColor: "rgba(56, 189, 248, 0.25)",
                fill: true,
                borderWidth: 2,
                pointRadius: 1,
                tension: 0.3,
              },
              {
                label: "상쇄 후 한전 수전 부하 (kW)",
                data: netData,
                borderColor: "#94a3b8",
                borderDash: [4, 4],
                fill: false,
                borderWidth: 1.5,
                pointRadius: 0,
                tension: 0.3,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: {
                labels: { color: "#94a3b8", font: { size: 11 } },
              },
              tooltip: {
                mode: "index",
                intersect: false,
              },
            },
            scales: {
              x: {
                grid: { color: "rgba(255,255,255,0.06)" },
                ticks: { color: "#94a3b8" },
              },
              y: {
                grid: { color: "rgba(255,255,255,0.06)" },
                ticks: { color: "#94a3b8" },
                title: { display: true, text: "전력 (kW)", color: "#94a3b8", font: { size: 11 } },
                min: 0,
              },
            },
          },
        });
      }
    }
  }

  setCustomLocationAngles(tiltDeg, azimuthDeg) {
    if (tiltDeg != null) this.state.tiltDeg = tiltDeg;
    if (azimuthDeg != null) this.state.azimuthDeg = azimuthDeg;
    this.update();
  }

  exportCsv() {
    const data = this.computeSimulation();
    const headers = ["월,일평균일조(h),태양광발전(kWh),학교소비(kWh),자립률(%),자가소비(kWh),한전수전(kWh),절감액(원)"];
    const rows = data.monthly.map(
      (m) =>
        `${m.month}월,${m.psh.toFixed(2)},${m.gen.toFixed(1)},${m.cons.toFixed(1)},${m.selfSuff.toFixed(1)}%,${m.selfConsumed.toFixed(1)},${m.gridImport.toFixed(1)},${Math.round(m.savings)}`
    );

    const csvContent = "\uFEFF" + [headers, ...rows].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `SolarMaps_자립률시뮬레이션_${this.state.panelCount}장_${this.state.areaM2}m2.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
}
