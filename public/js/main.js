import { analyzeAtPoint, getConstants, getPyodide } from "./py-bridge.js";
import { subscribe, subscribeDoc } from "./firestore.js";
import { focusOnStations, initMap, onMapClick, renderCampusPolygons, renderStationMarkers } from "./map.js";
import { renderDashboard } from "./ui/dashboard.js";
import { renderError, renderLoading, renderPlaceholder, renderResult } from "./ui/result-panel.js";
import { SolarSimulator } from "./ui/simulator.js";

// HAFS(용인한국외국어대학교부설고등학교) 기본 실측 노드(기계) 데이터
// Firebase 설정 전이거나 오프라인 상태에서도 설치된 기계의 위치가 즉시 지도에 표시되도록 보장한다.
export const DEFAULT_HAFS_STATIONS = [
  {
    station_id: "station_hafs_rooftop_01",
    name: "📍 HAFS 본관 옥상 실증 1호기",
    category: "ROOFTOP",
    building_id: "bldg_hafs_main",
    building_name: "본관 4층 옥상 (30° 경사)",
    floor: 4,
    location: {
      latitude: 37.3338,
      longitude: 127.2555,
      altitude_m: 165.0,
    },
    hardware: {
      panel_model: "Portable-Solar-30W (실증 거치형)",
      rated_power_w: 30.0,
      surface_area_m2: 0.18,
      tilt_angle_deg: 30,
      azimuth_deg: 180,
    },
    live_status: {
      state: "GENERATING",
      power_w: 22.4,
      voltage_v: 5.15,
      current_a: 4.35,
      today_energy_wh: 128.5,
      temp_c: 28.4,
      last_updated: new Date().toISOString(),
    },
    telemetry: {
      pi_cpu_temp_c: 42.1,
      wifi_rssi_dbm: -58,
    },
  },
  {
    station_id: "station_hafs_idle_02",
    name: "📍 HAFS 유휴지 거치대 2호기",
    category: "GROUND",
    building_id: "bldg_hafs_ground",
    building_name: "야외 유휴지 거치대 (0° 수평)",
    floor: 1,
    location: {
      latitude: 37.3345,
      longitude: 127.2562,
      altitude_m: 150.0,
    },
    hardware: {
      panel_model: "Portable-Solar-30W (수평 비교군)",
      rated_power_w: 30.0,
      surface_area_m2: 0.18,
      tilt_angle_deg: 0,
      azimuth_deg: 180,
    },
    live_status: {
      state: "GENERATING",
      power_w: 18.6,
      voltage_v: 5.08,
      current_a: 3.66,
      today_energy_wh: 104.2,
      temp_c: 29.8,
      last_updated: new Date().toISOString(),
    },
    telemetry: {
      pi_cpu_temp_c: 43.5,
      wifi_rssi_dbm: -64,
    },
  },
];

// HAFS 옥상 및 유휴지 3회 실측 기반 캠퍼스 폴리곤 (7,612.67 m²)
export const DEFAULT_HAFS_CAMPUS_POLYGON = [
  {
    type: "Feature",
    id: "poly_hafs_measured_full",
    properties: {
      building_name: "HAFS 옥상 및 유휴지 (3회 실측 합계)",
      total_roof_area_m2: 7612.67,
      usable_solar_area_m2: 7612.67,
      measured_trials_m2: [7606, 7644, 7588],
      measured_std_m2: 28.59,
      current_installed_stations: ["station_hafs_rooftop_01", "station_hafs_idle_02"],
      potential_capacity_kw: 761.27,
      monthly_consumption_kwh: 135866.0,
      monthly_consumption_kwh_a: 271626.5,
    },
    geometry: {
      type: "Polygon",
      coordinates: [
        [
          [127.2543, 37.3330],
          [127.2568, 37.3332],
          [127.2565, 37.3352],
          [127.2539, 37.3348],
          [127.2543, 37.3330],
        ],
      ],
    },
  },
];

async function boot() {
  const overlay = document.getElementById("boot-overlay");
  const resultPanel = document.getElementById("result-panel");
  const dashboardPanel = document.getElementById("dashboard-panel");
  const simulatorOverlay = document.getElementById("simulator-overlay");
  const tabMapBtn = document.getElementById("nav-tab-map");
  const tabSimBtn = document.getElementById("nav-tab-sim");

  // 시뮬레이터 인스턴스 생성
  const simulator = new SolarSimulator(simulatorOverlay);

  function showMap() {
    simulatorOverlay.hidden = true;
    tabMapBtn.classList.add("active");
    tabSimBtn.classList.remove("active");
    map.invalidateSize();
  }

  function showSimulator() {
    simulatorOverlay.hidden = false;
    tabMapBtn.classList.remove("active");
    tabSimBtn.classList.add("active");
    simulator.update();
  }

  tabMapBtn.addEventListener("click", showMap);
  tabSimBtn.addEventListener("click", showSimulator);
  simulator.onClose = showMap;

  // 대시보드 기본 초기화 (HAFS 실측 요약 데이터)
  renderDashboard(dashboardPanel, null, showSimulator);

  renderPlaceholder(resultPanel);
  resultPanel.hidden = true;

  // 1. 지도 초기화 (HAFS 캠퍼스 중심)
  const map = initMap("map");

  const onSelectPolygon = (properties) => {
    showSimulator();
    if (properties.usable_solar_area_m2) {
      simulator.state.areaM2 = properties.usable_solar_area_m2;
      const areaSlider = simulator.container.querySelector("#input-area-slider");
      const areaNum = simulator.container.querySelector("#input-area-num");
      if (areaSlider) areaSlider.value = properties.usable_solar_area_m2;
      if (areaNum) areaNum.value = properties.usable_solar_area_m2;

      const rec = simulator.calculateRecommendedPanels();
      simulator.state.panelCount = rec;
      const panelsSlider = simulator.container.querySelector("#input-panels-slider");
      const panelsNum = simulator.container.querySelector("#input-panels-num");
      if (panelsSlider) panelsSlider.value = rec;
      if (panelsNum) panelsNum.value = rec;
    }
    if (properties.monthly_consumption_kwh) {
      simulator.state.monthlyConsumptionKwh = properties.monthly_consumption_kwh;
      const consSlider = simulator.container.querySelector("#input-consumption-slider");
      const consNum = simulator.container.querySelector("#input-consumption-num");
      if (consSlider) consSlider.value = properties.monthly_consumption_kwh;
      if (consNum) consNum.value = properties.monthly_consumption_kwh;
    }
    simulator.update();
  };

  // 2. 기본 HAFS 기계 위치 마커 및 폴리곤을 즉시 렌더링 (Firebase 연결 전에도 기계 위치 100% 노출)
  renderStationMarkers(map, DEFAULT_HAFS_STATIONS);
  let campusPolygonLayer = renderCampusPolygons(map, DEFAULT_HAFS_CAMPUS_POLYGON, onSelectPolygon);

  // Pyodide 부팅과 상수 로딩 (비동기)
  let constants = null;
  getPyodide()
    .then(() => getConstants())
    .then((loadedConstants) => {
      constants = loadedConstants;
      // 상수가 로드된 후 마커 스타일 다시 갱신
      renderStationMarkers(map, DEFAULT_HAFS_STATIONS, constants?.marker_state_thresholds);
    })
    .catch((err) => {
      console.warn("Pyodide 로딩 경고 (기본 지도 및 기계 마커는 정상 동작):", err);
    });

  overlay.hidden = true;
  resultPanel.hidden = false;
  map.invalidateSize();

  // 지도 클릭 시 최적각 분석
  onMapClick(map, async (lat, lon) => {
    renderLoading(resultPanel);
    try {
      const utcOffsetHours = Math.round(lon / 15);
      const result = await analyzeAtPoint(lat, lon, utcOffsetHours);
      renderResult(resultPanel, result);

      if (result.tilt_deg != null) {
        simulator.setCustomLocationAngles(result.tilt_deg, result.azimuth_deg);
      }
    } catch (err) {
      console.error(err);
      renderError(resultPanel, err.message || String(err));
    }
  });

  // 3. Firestore 실시간 구독 (연결된 경우 라이브 데이터로 자동 갱신)
  subscribe("solar_stations", (docs) => {
    if (docs && docs.length > 0) {
      renderStationMarkers(map, docs.map((d) => d.data), constants?.marker_state_thresholds);
    }
  });

  subscribe("campus_polygons", (docs) => {
    if (docs && docs.length > 0) {
      if (campusPolygonLayer) map.removeLayer(campusPolygonLayer);
      campusPolygonLayer = renderCampusPolygons(
        map,
        docs.map((d) => ({ type: "Feature", id: d.id, properties: d.data.properties, geometry: d.data.geometry })),
        onSelectPolygon
      );
    }
  });

  subscribeDoc("school_energy_summary", "latest", (data) => {
    if (data) {
      renderDashboard(dashboardPanel, data, showSimulator);
    }
  });
}

boot().catch((err) => {
  console.error("부팅 실패:", err);
  const bootText = document.getElementById("boot-text");
  if (bootText) bootText.textContent = `부팅 실패: ${err.message || err}`;
});
