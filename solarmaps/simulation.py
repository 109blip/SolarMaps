"""학교 전력 자립률 시뮬레이션 엔진.

패널 개수, 설치 면적, 패널 사양 및 학교 전력 소비량을 바탕으로
태양광 발전량, 학교 전력 자립률(%), 탄소 감축량 및 전기요금 절감액을 계산한다.

CPython(테스트, Streamlit, CLI)과 Pyodide(웹 브라우저) 양쪽에서
표준 라이브러리만으로 동작하도록 설계되었다.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from solarmaps.constants import SYSTEM_LOSS_FRACTION

# HAFS(용인한국외대부고) 옥상 및 유휴지 실측 데이터 (2026-10 실측 3회)
# 1차: 7,606 m², 2차: 7,644 m², 3차: 7,588 m²
HAFS_MEASURED_AREAS_M2: list[float] = [7606.0, 7644.0, 7588.0]
HAFS_MEASURED_MEAN_AREA_M2: float = sum(HAFS_MEASURED_AREAS_M2) / len(HAFS_MEASURED_AREAS_M2)  # 7612.6666... m²
HAFS_MEASURED_STD_AREA_M2: float = 28.5890421898554  # 표본 표준편차 (평균 대비 0.38%)

# HAFS 8개월 전력 고지서 실측 데이터 (2025-12-17 ~ 2026-08-16, 243일)
# A안: 고지서 표 원본 합계 (기숙사동 포함 2,173,012 kWh)
# B안: 수전 중복 의심 기숙사동 행 제외 합계 (1,086,927 kWh)
HAFS_8MONTH_CONSUMPTION_KWH_A: float = 2173012.0
HAFS_8MONTH_CONSUMPTION_KWH_B: float = 1086927.0
HAFS_MONTHLY_CONSUMPTION_KWH_A: float = HAFS_8MONTH_CONSUMPTION_KWH_A / 8.0  # 271,626.5 kWh/월
HAFS_MONTHLY_CONSUMPTION_KWH_B: float = HAFS_8MONTH_CONSUMPTION_KWH_B / 8.0  # 135,865.875 kWh/월

# 한국 주요 지역 월별 평균 일일 최적각 경사면 일조시간 (Peak Sun Hours, h/day)
# NASA POWER 및 기상청 기후평년치(서울/경기 권역 경사각 30~33° 기준)
DEFAULT_MONTHLY_PSH: list[float] = [
    2.95,  # 1월: 맑으나 일조시간 짧음
    3.55,  # 2월
    4.25,  # 3월: 청명일수 증가
    4.45,  # 4월: 봄철 일사 피크
    4.35,  # 5월
    3.75,  # 6월: 장마 시작
    3.35,  # 7월: 장마/구름
    3.70,  # 8월: 폭염/대류성 운형
    3.85,  # 9월: 초가을 맑음
    3.90,  # 10월: 가을철 높은 일사
    3.20,  # 11월
    2.75,  # 12월: 동지 전후 최단
]

# 월별 일수 (평년 기준)
DAYS_PER_MONTH: list[int] = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

# 학교 전력 소비 계절 계수 (월간 평균 소비량 1.0 기준)
# 봄/가을 학기(기본 수업), 여름 냉방(방학 부분 보정), 겨울 난방(전기히트펌프 EHP)
DEFAULT_CONSUMPTION_FACTORS: list[float] = [
    1.08,  # 1월: 겨울방학 중 방과후/기숙사 난방 부하
    0.92,  # 2월: 개학 전 단축
    1.02,  # 3월: 1학기 개학, 조명/실습/수업
    0.97,  # 4월: 중간고사, 온화한 날씨
    0.96,  # 5월: 축제/행사, 냉난방 최소
    1.04,  # 6월: 하절기 냉방 가동 시작, 기말고사
    1.06,  # 7월: 본격 무더위 냉방 피크 + 여름방학 시작
    0.90,  # 8월: 여름방학 (기숙사/도서관 유지)
    0.98,  # 9월: 2학기 개학
    0.96,  # 10월: 가을철 안정기
    1.05,  # 11월: 수능, 초겨울 난방 시작
    1.06,  # 12월: 동절기 난방 최대, 기말고사
]

# 대표 일일 24시간 학교 부하 및 태양광 발전 정규화 곡선 (정규화 계수)
# 시간대별(0~23시) 학교 부하 비율 (일일 평균 kW 대비 배율)
HOURLY_LOAD_RATIO: list[float] = [
    0.28, 0.25, 0.24, 0.24, 0.26, 0.32,  # 00~05시: 심야 대기전력, 서버, 기숙사
    0.45, 0.75, 1.35, 1.65, 1.70, 1.55,  # 06~11시: 등교, 냉난방 가동, 1~4교시 수업
    1.30, 1.60, 1.65, 1.50, 1.25, 0.95,  # 12~17시: 점심, 5~7교시, 방과후수업
    0.75, 0.65, 0.55, 0.45, 0.38, 0.32,  # 18~23시: 야간자율학습, 잔류동아리, 퇴교
]

# 시간대별 태양광 발전 출력 비율 (피크 kW 대비 출력률)
HOURLY_SOLAR_RATIO: list[float] = [
    0.00, 0.00, 0.00, 0.00, 0.00, 0.00,  # 00~05시
    0.03, 0.15, 0.42, 0.72, 0.91, 0.98,  # 06~11시
    1.00, 0.95, 0.82, 0.58, 0.30, 0.08,  # 12~17시
    0.00, 0.00, 0.00, 0.00, 0.00, 0.00,  # 18~23시
]


@dataclass(frozen=True)
class MonthlySimulationPoint:
    month: int
    days: int
    daily_psh: float
    generation_kwh: float
    consumption_kwh: float
    self_sufficiency_percent: float
    self_consumed_kwh: float
    grid_import_kwh: float
    surplus_kwh: float
    bill_savings_krw: float


@dataclass(frozen=True)
class HourlyProfilePoint:
    hour: int
    school_load_kw: float
    solar_generation_kw: float
    net_load_kw: float


@dataclass(frozen=True)
class SimulationResult:
    # 설비 규격 및 설치 공간 지표
    system_capacity_kw: float
    total_panel_area_m2: float
    required_installation_area_m2: float
    area_utilization_percent: float
    recommended_max_panels: int
    is_area_exceeded: bool

    # 연간 핵심 에너지 지표
    annual_generation_kwh: float
    annual_consumption_kwh: float
    annual_self_sufficiency_percent: float
    annual_self_consumed_kwh: float
    annual_grid_import_kwh: float
    annual_surplus_kwh: float

    # 환경 및 경제성 지표
    annual_co2_reduced_kg: float
    annual_tree_planted_equivalent: float
    annual_bill_savings_krw: float

    # 시계열 세부 데이터
    monthly: list[MonthlySimulationPoint]
    hourly: list[HourlyProfilePoint]

    # 상태 등급 및 권고 메시지
    status_level: str  # "LOW", "MODERATE", "OPTIMAL", "FULL", "SURPLUS"
    status_badge_ko: str
    status_message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def calculate_school_self_sufficiency(
    *,
    installation_area_m2: float,
    panel_count: int,
    panel_rated_w: float = 400.0,
    panel_area_m2: float = 1.85,
    monthly_consumption_kwh: float = 12500.0,
    tilt_deg: float = 30.0,
    azimuth_deg: float = 180.0,
    system_loss_fraction: float = SYSTEM_LOSS_FRACTION,
    co2_kg_per_kwh: float = 0.4781,
    electricity_rate_krw_per_kwh: float = 130.0,
    monthly_psh_override: list[float] | None = None,
) -> SimulationResult:
    """패널 수와 설치 면적에 따른 학교 전력 자립률 및 경제성 시뮬레이션.

    Args:
        installation_area_m2: 건물 옥상/유휴지 유효 설치 면적 (m²)
        panel_count: 설치할 태양광 패널 수 (장)
        panel_rated_w: 패널 1장당 정격 출력 (W, 기본 400W)
        panel_area_m2: 패널 1장당 물리적 면적 (m², 기본 1.85m²)
        monthly_consumption_kwh: 학교 월평균 전력 소비량 (kWh, 기본 12,500 kWh)
        tilt_deg: 패널 경사각 (deg, 기본 30°)
        azimuth_deg: 패널 방위각 (deg, 기본 180° 남향)
        system_loss_fraction: 배선·인버터 등 시스템 손실률 (기본 14%)
        co2_kg_per_kwh: 한국 전력 배출계수 (kgCO2/kWh, 규격서 0.4781)
        electricity_rate_krw_per_kwh: 한전 교육용 고압 전력 단가 (원/kWh, 기본 130원)
        monthly_psh_override: 지점별 맞춤 월별 일조시간(h/day) 목록 (선택)
    """
    area = max(0.0, float(installation_area_m2))
    n_panels = max(0, int(panel_count))
    p_w = max(1.0, float(panel_rated_w))
    p_area = max(0.1, float(panel_area_m2))
    base_consumption = max(100.0, float(monthly_consumption_kwh))

    # 1. 설비 용량 및 면적 분석
    # 이격거리 및 보수 통로 배율: 30도 경사각 기준 앞뒤 패널 그림자 회피 간격 필요 (약 1.35배)
    spacing_multiplier = 1.0 + 0.35 * math.sin(math.radians(max(0.0, min(60.0, tilt_deg))))
    system_capacity_kw = (n_panels * p_w) / 1000.0
    total_panel_area_m2 = n_panels * p_area
    required_installation_area_m2 = total_panel_area_m2 * spacing_multiplier

    area_utilization_percent = (
        (required_installation_area_m2 / area * 100.0) if area > 0.0 else (100.0 if n_panels > 0 else 0.0)
    )
    recommended_max_panels = int(area / (p_area * spacing_multiplier)) if area > 0.0 else 0
    is_area_exceeded = required_installation_area_m2 > (area + 1e-4) and area > 0.0

    # 2. 방위각 및 경사각 보정 계수
    # 남향(180도) 대비 방위각 손실 근사 (SolarMaps optimizer/energy 모델과 정합)
    az_diff = abs(azimuth_deg - 180.0)
    azimuth_factor = max(0.70, 1.0 - 0.0015 * az_diff)
    # 최적 경사각(~32도) 대비 경사각 손실 계수
    tilt_diff = abs(tilt_deg - 32.0)
    tilt_factor = max(0.80, 1.0 - 0.002 * (tilt_diff**1.2))
    angle_efficiency_factor = azimuth_factor * tilt_factor

    # 3. 월별 발전량 및 전력 자립률 산출
    psh_list = monthly_psh_override if (monthly_psh_override and len(monthly_psh_override) == 12) else DEFAULT_MONTHLY_PSH

    monthly_points: list[MonthlySimulationPoint] = []
    tot_gen = 0.0
    tot_cons = 0.0
    tot_self_consumed = 0.0
    tot_surplus = 0.0
    tot_grid_import = 0.0
    tot_savings = 0.0

    efficiency_system = max(0.1, 1.0 - system_loss_fraction) * angle_efficiency_factor

    for m in range(12):
        month_idx = m + 1
        days = DAYS_PER_MONTH[m]
        daily_psh = psh_list[m]

        # 월별 발전량 (kWh) = 용량(kW) * 일일발전시간(h) * 효율 * 일수
        m_gen = system_capacity_kw * daily_psh * efficiency_system * days
        # 월별 학교 소비량 (kWh)
        m_cons = base_consumption * DEFAULT_CONSUMPTION_FACTORS[m]

        self_sufficiency = (m_gen / m_cons * 100.0) if m_cons > 0 else 0.0
        self_consumed = min(m_gen, m_cons)
        grid_import = max(0.0, m_cons - m_gen)
        surplus = max(0.0, m_gen - m_cons)
        savings = self_consumed * electricity_rate_krw_per_kwh

        tot_gen += m_gen
        tot_cons += m_cons
        tot_self_consumed += self_consumed
        tot_surplus += surplus
        tot_grid_import += grid_import
        tot_savings += savings

        monthly_points.append(
            MonthlySimulationPoint(
                month=month_idx,
                days=days,
                daily_psh=round(daily_psh, 2),
                generation_kwh=round(m_gen, 1),
                consumption_kwh=round(m_cons, 1),
                self_sufficiency_percent=round(self_sufficiency, 1),
                self_consumed_kwh=round(self_consumed, 1),
                grid_import_kwh=round(grid_import, 1),
                surplus_kwh=round(surplus, 1),
                bill_savings_krw=round(savings, 0),
            )
        )

    # 4. 연간 종합 성과 지표
    annual_self_sufficiency = (tot_gen / tot_cons * 100.0) if tot_cons > 0 else 0.0
    annual_co2_kg = tot_gen * co2_kg_per_kwh
    # 국립산림과학원 기준 30년생 소나무 1그루 연간 흡수량 6.6 kgCO2
    annual_trees = annual_co2_kg / 6.6

    # 5. 시간대별(24시) 대표 평일 부하 vs 발전 프로파일 (연평균 대표일)
    # 일평균 소비량 및 발전량 기준 kW 배분
    avg_daily_cons_kwh = tot_cons / 365.0
    avg_base_load_kw = avg_daily_cons_kwh / 24.0

    hourly_points: list[HourlyProfilePoint] = []
    for h in range(24):
        h_load = avg_base_load_kw * HOURLY_LOAD_RATIO[h]
        # 피크 일사량 시간대 태양광 출력 (kW)
        h_solar = system_capacity_kw * efficiency_system * HOURLY_SOLAR_RATIO[h]
        net_load = max(0.0, h_load - h_solar)
        hourly_points.append(
            HourlyProfilePoint(
                hour=h,
                school_load_kw=round(h_load, 1),
                solar_generation_kw=round(h_solar, 1),
                net_load_kw=round(net_load, 1),
            )
        )

    # 6. 자립률 상태 진단 및 메시지
    if annual_self_sufficiency < 10.0:
        status_level = "LOW"
        status_badge_ko = "기초 보조 수준 (10% 미만)"
        status_message = "학교 야간 대기전력 또는 특정 동의 기본 조명 전력을 보조하는 수준입니다."
    elif annual_self_sufficiency < 30.0:
        status_level = "MODERATE"
        status_badge_ko = "부분 자립 (10~30%)"
        status_message = "주간 수업 시간대 기본 전력의 상당 부분을 태양광으로 자체 충당할 수 있습니다."
    elif annual_self_sufficiency < 60.0:
        status_level = "OPTIMAL"
        status_badge_ko = "핵심 자립 (30~60%)"
        status_message = "학교 피크 부하의 절반 가까이를 상쇄하여 전기요금 절감 및 탄소 중립 효과가 매우 뛰어납니다."
    elif annual_self_sufficiency < 100.0:
        status_level = "FULL"
        status_badge_ko = "고도 자립 (60~100%)"
        status_message = "봄·가을 온화한 기간에는 학교 전체 전력을 100% 자립하며, 연간 대부분의 전력을 자가 조달합니다."
    else:
        status_level = "SURPLUS"
        status_badge_ko = "완전 자립 및 잉여 생산 (100% 이상)"
        status_message = "학교 전체 소비량을 초과 생산(RE100 달성). 잉여 전력은 한전 상계거래 또는 전력망 역송이 가능합니다."

    return SimulationResult(
        system_capacity_kw=round(system_capacity_kw, 2),
        total_panel_area_m2=round(total_panel_area_m2, 2),
        required_installation_area_m2=round(required_installation_area_m2, 2),
        area_utilization_percent=round(area_utilization_percent, 1),
        recommended_max_panels=recommended_max_panels,
        is_area_exceeded=is_area_exceeded,
        annual_generation_kwh=round(tot_gen, 1),
        annual_consumption_kwh=round(tot_cons, 1),
        annual_self_sufficiency_percent=round(annual_self_sufficiency, 1),
        annual_self_consumed_kwh=round(tot_self_consumed, 1),
        annual_grid_import_kwh=round(tot_grid_import, 1),
        annual_surplus_kwh=round(tot_surplus, 1),
        annual_co2_reduced_kg=round(annual_co2_kg, 1),
        annual_tree_planted_equivalent=round(annual_trees, 1),
        annual_bill_savings_krw=round(tot_savings, 0),
        monthly=monthly_points,
        hourly=hourly_points,
        status_level=status_level,
        status_badge_ko=status_badge_ko,
        status_message=status_message,
    )
