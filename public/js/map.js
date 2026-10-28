// Leaflet 지도 초기화, 클릭 핸들러, 발전소 마커/캠퍼스 폴리곤 레이어.

import { computeMarkerVisual, stationPopupHtml } from "./ui/station-popup.js";

export function initMap(elementId) {
  const map = L.map(elementId, { zoomControl: true }).setView([36.5, 127.8], 7); // 대한민국 중심 기본 뷰
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
  }).addTo(map);

  // 폰트/스타일시트 로딩 타이밍에 따라 Leaflet이 컨테이너 크기를 실제보다
  // 작게(때로는 0으로) 캐싱해 타일이 좁은 영역에만 렌더링되는 문제가 있다.
  // 레이아웃이 안정된 후(다음 프레임) 한 번, 이후 창 크기 변경 시마다
  // invalidateSize()로 강제 재계산한다.
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
  for (const station of stations) {
    const { latitude, longitude } = station.location || {};
    if (latitude == null || longitude == null) continue;
    seen.add(station.station_id);

    const visual = computeMarkerVisual(station, thresholds);
    let cm = stationMarkers.get(station.station_id);
    if (!cm) {
      cm = L.circleMarker([latitude, longitude], { radius: 8, weight: 2 }).addTo(map);
      stationMarkers.set(station.station_id, cm);
    } else {
      cm.setLatLng([latitude, longitude]);
    }
    cm.setStyle({ color: visual.color, fillColor: visual.color, fillOpacity: 0.7 });
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
}

export function renderCampusPolygons(map, features, onSelectBuilding) {
  return L.geoJSON(
    { type: "FeatureCollection", features },
    {
      style: { color: "var(--primary, #60a5fa)", weight: 1.5, fillOpacity: 0.08 },
      onEachFeature: (feature, layer) => {
        const p = feature.properties || {};
        const popupContent = document.createElement("div");
        popupContent.style.minWidth = "180px";
        popupContent.innerHTML = `
          <strong>${p.building_name ?? feature.id}</strong>
          <div style="font-size:12px;margin:6px 0 8px;line-height:1.4;">
            유효 설치면적: <strong>${p.usable_solar_area_m2 ?? "-"} m²</strong><br/>
            잠재 설비용량: <strong>${p.potential_capacity_kw ?? "-"} kW</strong><br/>
            월간 소비량: <strong>${p.monthly_consumption_kwh ? p.monthly_consumption_kwh.toLocaleString() + " kWh" : "-"}</strong>
          </div>
          <button class="btn btn-primary btn-sm bldg-sim-btn" style="width:100%;font-size:11px;padding:4px 8px;">
            ⚡ 이 건물로 자립률 시뮬레이션
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
