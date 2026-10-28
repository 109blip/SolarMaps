"""py-bridge.js가 호출하는 단일 진입점.

브라우저(Pyodide)는 이 모듈의 함수만 알면 된다 — 나머지 solarmaps 서브모듈
구성은 이 파일 뒤로 캡슐화된다. 반환값은 JSON 직렬화 가능한 순수 dict/list만
사용해 pyodide.to_js() 변환이 항상 안전하게 되도록 한다.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from solarmaps.climate import get_climate_params
from solarmaps.constants import (
    KOPPEN_GROUP_COLORS,
    KOPPEN_NAME_KO,
    MARKER_STATE_THRESHOLDS,
    koppen_group,
)
from solarmaps.koppen import KoppenGrid, load_grid
from solarmaps.models import MonthlyClimate
from solarmaps.optimizer import build_fallback_monthly_climate, optimize
from solarmaps.simulation import calculate_school_self_sufficiency

_grid: KoppenGrid | None = None


def _get_grid() -> KoppenGrid:
    global _grid
    if _grid is None:
        _grid = load_grid()
    return _grid


def get_constants() -> dict[str, Any]:
    """JS가 색상·임계값을 하드코딩하지 않도록 파이썬 쪽 상수를 그대로 노출."""
    return {
        "koppen_group_colors": KOPPEN_GROUP_COLORS,
        "koppen_name_ko": KOPPEN_NAME_KO,
        "marker_state_thresholds": MARKER_STATE_THRESHOLDS,
    }


def lookup_koppen(lat: float, lon: float) -> dict[str, Any]:
    grid = _get_grid()
    result = grid.lookup(lat, lon)
    return {
        "code": result.code,
        "name_ko": KOPPEN_NAME_KO.get(result.code, result.code),
        "group": koppen_group(result.code),
        "group_color": KOPPEN_GROUP_COLORS.get(koppen_group(result.code), "#888888"),
        "is_interpolated": result.is_interpolated,
        "distance_deg": result.distance_deg,
    }


def _monthly_climate_from_payload(payload: list[dict] | None) -> list[MonthlyClimate] | None:
    if not payload:
        return None
    return [
        MonthlyClimate(
            month=m["month"],
            ghi_kwh_m2_day=m["ghi_kwh_m2_day"],
            diffuse_kwh_m2_day=m.get("diffuse_kwh_m2_day", 0.0),
            clearsky_ghi_kwh_m2_day=m.get("clearsky_ghi_kwh_m2_day", m["ghi_kwh_m2_day"] / 0.75),
            t_ambient_c=m.get("t_ambient_c", 15.0),
            source=m.get("source", "nasa_power"),
        )
        for m in payload
    ]


def analyze(
    lat: float,
    lon: float,
    utc_offset_hours: float,
    *,
    monthly_climate_payload: list[dict] | None = None,
    precise_azimuth_mode: bool = False,
) -> dict[str, Any]:
    """지점 분석 진입점.

    monthly_climate_payload: JS(py-bridge.js)가 NASA POWER에서 미리 fetch해
    dict 리스트로 넘긴 월별 기후값. None이면 쾨펜 기반 climate_fallback을 쓴다
    (오프라인이거나 POWER 조회가 실패한 경우).
    """
    koppen = lookup_koppen(lat, lon)
    koppen_code = koppen["code"]

    monthly_climate = _monthly_climate_from_payload(monthly_climate_payload)
    if monthly_climate is None:
        monthly_climate = build_fallback_monthly_climate(lat, koppen_code)

    result = optimize(
        latitude_deg=lat,
        longitude_deg=lon,
        koppen_code=koppen_code,
        koppen_name_ko=koppen["name_ko"],
        monthly_climate=monthly_climate,
        utc_offset_hours=utc_offset_hours,
        precise_azimuth_mode=precise_azimuth_mode,
    )

    payload = asdict(result)
    payload["koppen"] = koppen
    payload["climate_params"] = asdict(get_climate_params(koppen_code))
    return payload


def simulate_self_sufficiency(
    *,
    installation_area_m2: float,
    panel_count: int,
    panel_rated_w: float = 400.0,
    panel_area_m2: float = 1.85,
    monthly_consumption_kwh: float = 12500.0,
    tilt_deg: float = 30.0,
    azimuth_deg: float = 180.0,
    monthly_psh_override: list[float] | None = None,
) -> dict[str, Any]:
    """학교 전력 자립률 시뮬레이션 진입점 (JSON/JS 직렬화 가능 dict 반환)."""
    res = calculate_school_self_sufficiency(
        installation_area_m2=installation_area_m2,
        panel_count=panel_count,
        panel_rated_w=panel_rated_w,
        panel_area_m2=panel_area_m2,
        monthly_consumption_kwh=monthly_consumption_kwh,
        tilt_deg=tilt_deg,
        azimuth_deg=azimuth_deg,
        monthly_psh_override=monthly_psh_override,
    )
    return res.to_dict()
