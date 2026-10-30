// 규격서(docs/DATA_SPEC.md) §4 마커 상태 매핑. 임계값 자체는 solarmaps.constants
// (Python)에서 가져오되, 미로딩 시 안전한 기본 폴백을 제공한다.

const FALLBACK_THRESHOLDS = {
  GENERATING_HIGH: { power_ratio_of_rated: 0.7, color: "#10B981", animation: "pulse" },
  GENERATING_LOW: { power_w_min: 0.5, color: "#F59E0B", animation: "none" },
  IDLE: { power_w_max: 0.5, color: "#6B7280", animation: "none" },
  OFFLINE: { stale_minutes: 5, color: "#EF4444", animation: "none" },
};

export function computeMarkerVisual(station, thresholds) {
  const th = thresholds || FALLBACK_THRESHOLDS;
  const live = station.live_status || {};
  const rated = station.hardware?.rated_power_w ?? 0;
  const power = live.power_w ?? 0;
  const lastUpdated = live.last_updated ? new Date(live.last_updated) : null;
  const staleMinutes = lastUpdated ? (Date.now() - lastUpdated.getTime()) / 60000 : Infinity;

  const offlineCfg = th.OFFLINE || FALLBACK_THRESHOLDS.OFFLINE;
  if (staleMinutes > offlineCfg.stale_minutes) {
    return offlineCfg;
  }
  const genHigh = th.GENERATING_HIGH || FALLBACK_THRESHOLDS.GENERATING_HIGH;
  if (rated > 0 && power >= rated * (genHigh.power_ratio_of_rated ?? 0.7)) {
    return genHigh;
  }
  const genLow = th.GENERATING_LOW || FALLBACK_THRESHOLDS.GENERATING_LOW;
  if (power > (genLow.power_w_min ?? 0.5)) {
    return genLow;
  }
  return th.IDLE || FALLBACK_THRESHOLDS.IDLE;
}

export function stationPopupHtml(station, visual) {
  const live = station.live_status || {};
  const hw = station.hardware || {};
  const loc = station.location || {};
  const latStr = loc.latitude != null ? Number(loc.latitude).toFixed(4) : "-";
  const lonStr = loc.longitude != null ? Number(loc.longitude).toFixed(4) : "-";

  return `
    <div style="min-width:220px">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:6px;">
        <strong style="font-size:14px;color:var(--text, #f8fafc);">${station.name || station.station_id}</strong>
        <span style="font-size:10px;padding:2px 6px;border-radius:4px;background:${visual.color}22;color:${visual.color};font-weight:700;">
          ${live.state || "ON"}
        </span>
      </div>
      <div style="margin-top:2px;color:var(--text-secondary, #94a3b8);font-size:11px;">
        📍 ${station.building_name || "HAFS 교내"} (${latStr}°N, ${lonStr}°E)
      </div>
      <div style="margin-top:8px;padding-top:6px;border-top:1px solid var(--border, #334155);display:grid;grid-template-columns:1fr 1fr;gap:4px 10px;font-size:12px;">
        <span>실시간 출력</span><strong style="color:#38bdf8;">${(live.power_w ?? 0).toFixed(1)} W</strong>
        <span>금일 발전량</span><strong>${(live.today_energy_wh ?? 0).toFixed(0)} Wh</strong>
        <span>설치 각도</span><strong>${hw.tilt_angle_deg ?? "-"}° / ${hw.azimuth_deg ?? "-"}°</strong>
        <span>전압 / 전류</span><strong>${(live.voltage_v ?? 0).toFixed(2)}V / ${(live.current_a ?? 0).toFixed(2)}A</strong>
        <span>패널 모델</span><span style="font-size:11px;color:var(--text-secondary);">${hw.panel_model || "30W 실증기"}</span>
        <span>패널 온도</span><strong>${live.temp_c != null ? live.temp_c.toFixed(1) + "°C" : "-"}</strong>
      </div>
    </div>
  `;
}
