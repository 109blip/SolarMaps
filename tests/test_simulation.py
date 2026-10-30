"""학교 전력 자립률 시뮬레이션 계산 로직 테스트."""

from solarmaps.api import simulate_self_sufficiency
from solarmaps.simulation import calculate_school_self_sufficiency


def test_zero_panels_returns_zero_generation_and_self_sufficiency() -> None:
    res = calculate_school_self_sufficiency(
        installation_area_m2=500.0,
        panel_count=0,
        monthly_consumption_kwh=10000.0,
    )
    assert res.system_capacity_kw == 0.0
    assert res.annual_generation_kwh == 0.0
    assert res.annual_self_sufficiency_percent == 0.0
    assert res.annual_grid_import_kwh > 0.0
    assert res.annual_surplus_kwh == 0.0
    assert not res.is_area_exceeded


def test_typical_school_rooftop_simulation() -> None:
    # 550 m2 유효 면적, 200장 400W 패널 (80 kW)
    res = calculate_school_self_sufficiency(
        installation_area_m2=550.0,
        panel_count=200,
        panel_rated_w=400.0,
        panel_area_m2=1.85,
        monthly_consumption_kwh=12500.0,
        tilt_deg=30.0,
        azimuth_deg=180.0,
    )

    # 200장 * 400W = 80 kW
    assert res.system_capacity_kw == 80.0
    # 면적 200 * 1.85 * ~1.175 ~ 434 m2 <= 550 m2
    assert not res.is_area_exceeded
    assert res.area_utilization_percent < 100.0
    assert res.annual_generation_kwh > 50000.0
    # 연간 소비량 ~150,000 kWh 대비 80kW 발전시 자립률 약 50~70%
    assert 30.0 < res.annual_self_sufficiency_percent < 90.0
    assert res.annual_co2_reduced_kg > 0.0
    assert res.annual_tree_planted_equivalent > 0.0
    assert res.annual_bill_savings_krw > 0.0
    assert len(res.monthly) == 12
    assert len(res.hourly) == 24


def test_area_exceeded_flag_when_too_many_panels() -> None:
    # 100 m2 면적에 300장 설치 시도 -> 명백한 면적 초과
    res = calculate_school_self_sufficiency(
        installation_area_m2=100.0,
        panel_count=300,
        panel_area_m2=1.85,
    )
    assert res.is_area_exceeded
    assert res.area_utilization_percent > 100.0


def test_api_simulate_self_sufficiency_dict_serializable() -> None:
    data = simulate_self_sufficiency(
        installation_area_m2=400.0,
        panel_count=150,
        monthly_consumption_kwh=10000.0,
    )
    assert isinstance(data, dict)
    assert "annual_self_sufficiency_percent" in data
    assert "monthly" in data
    assert "hourly" in data
    assert len(data["monthly"]) == 12


def test_hafs_measured_area_and_self_sufficiency() -> None:
    from solarmaps.simulation import (
        HAFS_MEASURED_AREAS_M2,
        HAFS_MEASURED_MEAN_AREA_M2,
        HAFS_MEASURED_STD_AREA_M2,
        HAFS_MONTHLY_CONSUMPTION_KWH_A,
        HAFS_MONTHLY_CONSUMPTION_KWH_B,
    )

    # 3회 측정치 확인
    assert HAFS_MEASURED_AREAS_M2 == [7606.0, 7644.0, 7588.0]
    assert abs(HAFS_MEASURED_MEAN_AREA_M2 - 7612.67) < 0.01
    assert abs(HAFS_MEASURED_STD_AREA_M2 - 28.59) < 0.01

    # B안 (기숙사 제외: 135,865.9 kWh/월) 기준 시뮬레이션: 자립률 ~60%
    res_b = calculate_school_self_sufficiency(
        installation_area_m2=HAFS_MEASURED_MEAN_AREA_M2,
        panel_count=2057,
        monthly_consumption_kwh=HAFS_MONTHLY_CONSUMPTION_KWH_B,
    )
    assert res_b.annual_self_sufficiency_percent > 50.0

    # A안 (표 원본: 271,626.5 kWh/월) 기준 시뮬레이션: 자립률 ~30%
    res_a = calculate_school_self_sufficiency(
        installation_area_m2=HAFS_MEASURED_MEAN_AREA_M2,
        panel_count=2057,
        monthly_consumption_kwh=HAFS_MONTHLY_CONSUMPTION_KWH_A,
    )
    assert res_a.annual_self_sufficiency_percent > 25.0

