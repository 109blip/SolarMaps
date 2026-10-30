// Leaflet 지도 초기화, 클릭 핸들러, 발전소 마커/캠퍼스 폴리곤 레이어.

import { computeMarkerVisual, stationPopupHtml } from "./ui/station-popup.js";

// HAFS(용인한국외국어대학교부설고등학교) 기본 중심 좌표 (위도 37.3338°N, 경도 127.2555°E)
export const HAFS_CAMPUS_CENTER = [37.3338, 127.2555];

export function initMap(elementId) {
  // HAFS 캠퍼스가 한눈에 보이도록 기본 줌 레벨 17로 포커스
  const map = L.map(elementId, { zoomControl: true }).setView(HAFS_CAMPUS_CENTER, 17);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
  }).addTo(map);

  // 지도 우측 상단/좌측 하단에 '설치 기계 위치로 이동' 단축 버튼 추가
  const focusControl = L.control({ position: "topleft" });
  focusControl.onAdd = function () {
    const div = L.DomUtil.create("div", "leaflet-bar map-focus-control");
    div.innerHTML = `
      <button id="btn-focus-hafs-station" class="map-focus-btn" title="설치된 태양광 측정 기계 위치로 이동">
        📍 HAFS 기계 위치
      </button>
    `;
    div.querySelector("#btn-focus-hafs-station").addEventListener("click", (e) => {
      e.stopPropagation();
      focusOnStations(map);
    });
    return div;
  };
  focusControl.addTo(map);

  // 폰트/스타일시트 로딩 타이밍에 따른 타일 렌더링 깨짐 방지
  requestAnimationFrame(() => map.invalidateSize());
  window.addEventListener("resize", () => map.invalidateSize());

  return map;
}

export function onMapClick(map, handler) {
  let marker = null;
  map.on("click", (e) => {
    const { lat, lng } = e.latlng;
    if (marker) map.removeLayer(marker);
    marker = L.marker([lat, lng]).addTo(map);
    handler(lat, lng);
  });
}

const stationMarkers = new Map(); // station_id -> L.CircleMarker

export function renderStationMarkers(map, stations, thresholds) {
  const seen = new Set();
  const validLatLngs = [];

  for (const station of stations) {
    const { latitude, longitude } = station.location || {};
    if (latitude == null || longitude == null) continue;
    seen.add(station.station_id);
    validLatLngs.push([latitude, longitude]);

    const visual = computeMarkerVisual(station, thresholds);
    let cm = stationMarkers.get(station.station_id);
    if (!cm) {
      cm = L.circleMarker([latitude, longitude], {
        radius: 10,
        weight: 3,
        fillOpacity: 0.85,
      }).addTo(map);

      // 항상 보이는 툴팁 라벨 연결
      cm.bindTooltip(station.name || "태양광 측정기", {
        permanent: true,
        direction: "top",
        offset: [0, -12],
        className: "station-map-label",
      });

      stationMarkers.set(station.station_id, cm);
    } else {
      cm.setLatLng([latitude, longitude]);
    }

    cm.setStyle({ color: visual.color, fillColor: visual.color, fillOpacity: 0.85 });
    cm.bindPopup(stationPopupHtml(station, visual));

    const el = cm.getElement ? cm.getElement() : null;
    if (el) el.classList.toggle("marker-pulse", visual.animation === "pulse");
  }

  for (const [id, cm] of stationMarkers) {
    if (!seen.has(id)) {
      map.removeLayer(cm);
      stationMarkers.delete(id);
    }
  }

  return validLatLngs;
}

export function focusOnStations(map) {
  if (stationMarkers.size === 0) {
    map.flyTo(HAFS_CAMPUS_CENTER, 17, { duration: 1.2 });
    return;
  }
  const group = L.featureGroup(Array.from(stationMarkers.values()));
  map.flyToBounds(group.getBounds().pad(0.3), { maxZoom: 18, duration: 1.2 });

  // 첫 번째 마커 팝업 열기
  const firstMarker = stationMarkers.values().next().value;
  if (firstMarker) {
    setTimeout(() => firstMarker.openPopup(), 1300);
  }
}

export function renderCampusPolygons(map, features, onSelectBuilding) {
  return L.geoJSON(
    { type: "FeatureCollection", features },
    {
      style: {
        color: "var(--primary, #38bdf8)",
        weight: 2,
        fillColor: "var(--primary, #38bdf8)",
        fillOpacity: 0.12,
        dashArray: "4, 4",
      },
      onEachFeature: (feature, layer) => {
        const p = feature.properties || {};
        const popupContent = document.createElement("div");
        popupContent.style.minWidth = "220px";
        popupContent.innerHTML = `
          <strong style="font-size:13px;color:#38bdf8;">🏫 ${p.building_name ?? feature.id}</strong>
          <div style="font-size:12px;margin:6px 0 8px;line-height:1.5;">
            실측 옥상·유휴지 면적: <strong>${p.usable_solar_area_m2 ? Number(p.usable_solar_area_m2).toLocaleString() + " m²" : "-"}</strong><br/>
            ${p.measured_trials_m2 ? `<span style="font-size:11px;color:var(--text-secondary);">3회 실측: ${p.measured_trials_m2.join(" / ")} m²</span><br/>` : ""}
            잠재 설비용량: <strong>${p.potential_capacity_kw ? Number(p.potential_capacity_kw).toLocaleString() + " kW" : "-"}</strong><br/>
            월 전력 소비량: <strong>${p.monthly_consumption_kwh ? Number(p.monthly_consumption_kwh).toLocaleString() + " kWh" : "-"}</strong>
          </div>
          <button class="btn btn-primary btn-sm bldg-sim-btn" style="width:100%;font-size:11px;padding:5px 8px;font-weight:600;">
            ⚡ 이 실측 면적으로 자립률 시뮬레이션
          </button>
        `;
        const btn = popupContent.querySelector(".bldg-sim-btn");
        if (btn && onSelectBuilding) {
          btn.addEventListener("click", () => onSelectBuilding(p));
        }
        layer.bindPopup(popupContent);
      },
    }
  ).addTo(map);
}
