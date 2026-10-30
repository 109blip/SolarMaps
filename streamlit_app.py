"""SolarMaps — 학교 전력 자립률 계산 시뮬레이터 (Streamlit 앱).

실행 방법:
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from solarmaps.simulation import calculate_school_self_sufficiency

# 페이지 기본 설정
st.set_page_config(
    page_title="SolarMaps — 학교 전력 자립률 시뮬레이터",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 커스텀 CSS (다크 테마 및 카드 스타일링)
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 18px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }
    .metric-label {
        font-size: 0.85rem;
        color: #94a3b8;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #38bdf8;
    }
    .metric-sub {
        font-size: 0.75rem;
        color: #64748b;
        margin-top: 4px;
    }
    .status-box {
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# 학교 건물 프리셋 데이터 (docs/DATA_SPEC.md 및 HAFS 유리프 실측 기준)
CAMPUS_PRESETS = {
    "HAFS 옥상 및 유휴지 전체 (3회 실측 평균) - B안(기숙사 중복 제외 61.2%)": {
        "area": 7612.67,
        "panels": 2057,
        "monthly_kwh": 135865.9,
        "desc": "HAFS 3회 실측(1차 7,606 / 2차 7,644 / 3차 7,588 m², 평균 7,612.67 m² ±0.38%) · 고지서 B안(기숙사 수전 중복 제외 월 135,866 kWh) 반영 시 자립률 약 60%",
        "trials": [7606, 7644, 7588],
    },
    "HAFS 옥상 및 유휴지 전체 (3회 실측 평균) - A안(고지서 원본 표 합계 30.6%)": {
        "area": 7612.67,
        "panels": 2057,
        "monthly_kwh": 271626.5,
        "desc": "HAFS 3회 실측(평균 7,612.67 m²) · 고지서 A안(표 원본 8개월 2,173,012 kWh, 월 271,627 kWh) 반영 시 자립률 약 30%",
        "trials": [7606, 7644, 7588],
    },
    "본관 옥상 유휴지 (기본 실증지)": {
        "area": 550.0,
        "panels": 200,
        "monthly_kwh": 12500.0,
        "desc": "본관 4층 옥상 (총 면적 850m² 중 실외기·통로 제외 유효면적 550m²)",
    },
    "과학관 옥상": {
        "area": 400.0,
        "panels": 150,
        "monthly_kwh": 9500.0,
        "desc": "과학실험실 및 연구동 옥상 (유효면적 400m²)",
    },
    "체육관 대형 지붕": {
        "area": 800.0,
        "panels": 300,
        "monthly_kwh": 14000.0,
        "desc": "실내체육관 지붕 유휴공간 (유효면적 800m²)",
    },
    "소형 실증 실험 1호기 (Stand)": {
        "area": 20.0,
        "panels": 8,
        "monthly_kwh": 12500.0,
        "desc": "야외 거치대 1·2호기 실험용 소형 구성",
    },
    "사용자 직접 설정 (Custom)": {
        "area": 500.0,
        "panels": 180,
        "monthly_kwh": 12000.0,
        "desc": "면적과 패널 수를 자유롭게 조정",
    },
}

# 사이드바 — 입력 파라미터 제어
st.sidebar.title("☀️ 시뮬레이션 설정")
st.sidebar.caption("패널 개수 및 설치 면적에 따른 학교 전력 자립률 계산")

# 1. 프리셋 선택
preset_name = st.sidebar.selectbox("건물 / 구역 프리셋", list(CAMPUS_PRESETS.keys()))
preset_data = CAMPUS_PRESETS[preset_name]
st.sidebar.info(preset_data["desc"])

# HAFS 3회 실측치 배지 표시
if "trials" in preset_data:
    t1, t2, t3 = preset_data["trials"]
    st.sidebar.success(
        f"📊 **HAFS 3회 실측 데이터**\n- 1차: `{t1:,} m²`\n- 2차: `{t2:,} m²`\n- 3차: `{t3:,} m²`\n- **평균: `7,612.67 m²` (±28.6 m², 0.38%)**"
    )

# 2. 설치 면적 및 패널 개수 슬라이더
st.sidebar.subheader("📐 설치 면적 및 패널 개수")
install_area = st.sidebar.number_input(
    "설치 가능 면적 (m²)",
    min_value=10.0,
    max_value=30000.0,
    value=float(preset_data["area"]),
    step=10.0,
    help="건물 옥상이나 유휴지에서 패널 설치가 가능한 유효 바닥 면적",
)

# 권장 패널 계산 (이격거리 1.35배 및 1.85m² 패널 기준)
rec_max = int(install_area / (1.85 * 1.35))

if st.sidebar.button("⚡ 면적 맞춤 최적 패널 수 자동 입력"):
    st.session_state["panel_count_input"] = rec_max

panel_count = st.sidebar.number_input(
    "설치할 패널 개수 (장)",
    min_value=1,
    max_value=10000,
    value=st.session_state.get("panel_count_input", int(preset_data["panels"])),
    step=5,
    help=f"선택한 면적({install_area:.0f}m²) 기준 권장 최대 설치량은 약 {rec_max}장입니다.",
)

# 3. 패널 사양
st.sidebar.subheader("⚙️ 패널 사양")
panel_type = st.sidebar.selectbox(
    "패널 모델 유형",
    ["400W 표준 루프탑 패널 (1.85 m²)", "450W 고효율 대형 패널 (2.00 m²)", "350W 소형 패널 (1.65 m²)", "직접 입력"],
)

if panel_type == "400W 표준 루프탑 패널 (1.85 m²)":
    rated_w, panel_area = 400.0, 1.85
elif panel_type == "450W 고효율 대형 패널 (2.00 m²)":
    rated_w, panel_area = 450.0, 2.00
elif panel_type == "350W 소형 패널 (1.65 m²)":
    rated_w, panel_area = 350.0, 1.65
else:
    col_p1, col_p2 = st.sidebar.columns(2)
    rated_w = col_p1.number_input("출력 (W)", 50.0, 800.0, 400.0, 10.0)
    panel_area = col_p2.number_input("면적 (m²)", 0.2, 3.0, 1.85, 0.05)

# 4. 학교 전력 소비량
st.sidebar.subheader("🏫 학교 소비 전력")
monthly_kwh = st.sidebar.number_input(
    "월평균 전기 소비량 (kWh)",
    min_value=500.0,
    max_value=500000.0,
    value=float(preset_data["monthly_kwh"]),
    step=500.0,
    help="학교의 한전 고지서 기준 월간 평균 전력 사용량 (HAFS 실측 A안 271,627 kWh / B안 135,866 kWh)",
)

# 5. 설치 환경 (각도 및 단가)
with st.sidebar.expander("고급 설정 (설치 각도 / 요금 / 탄소)"):
    tilt_deg = st.slider("설치 경사각 (°)", 0.0, 60.0, 30.0, 1.0, help="한국 최적각 약 30~33°")
    azimuth_deg = st.slider("설치 방위각 (°)", 90.0, 270.0, 180.0, 5.0, help="정남향=180°")
    elec_rate = st.number_input("교육용 전기요금 단가 (원/kWh)", 50.0, 300.0, 130.0, 5.0)

# 시뮬레이션 계산 실행 (solarmaps.simulation 엔진 호출)
res = calculate_school_self_sufficiency(
    installation_area_m2=install_area,
    panel_count=panel_count,
    panel_rated_w=rated_w,
    panel_area_m2=panel_area,
    monthly_consumption_kwh=monthly_kwh,
    tilt_deg=tilt_deg,
    azimuth_deg=azimuth_deg,
    electricity_rate_krw_per_kwh=elec_rate,
)

# ── 메인 화면 ──────────────────────────────────────────────────────────
st.title("☀️ SolarMaps 학교 전력 자립률 시뮬레이터")
st.markdown(
    """
    **패널 개수 및 설치 면적**을 실시간으로 조절하며 학교의 **전력 자립률(%)**,
    월별 수급 밸런스, 피크 시간 감축 효과 및 온실가스 감축 성과를 정밀하게 분석합니다.
    """
)

# 면적 초과 경고 또는 권장 상태 안내
if res.is_area_exceeded:
    st.error(
        f"⚠️ **설치 면적 초과 경고**: 패널 {panel_count}장 설치에는 약 {res.required_installation_area_m2:.1f} m²(패널 간 그림자 이격 및 보수 통로 포함)가 필요하나, 사용 가능 면적은 {install_area:.1f} m²입니다 (점유율 {res.area_utilization_percent:.1f}%). 패널 간 음영 발생으로 발전 효율이 저하될 수 있으니 패널 수를 {res.recommended_max_panels}장 이하로 조정하는 것을 권장합니다."
    )
else:
    st.success(
        f"✅ **설치 공간 적합**: 사용 가능 면적 {install_area:.1f} m² 중 약 {res.required_installation_area_m2:.1f} m²를 사용하여 공간 점유율 **{res.area_utilization_percent:.1f}%**로 안전하게 배치됩니다."
    )

# 핵심 KPI 지표 카드 (5열 레이아웃)
c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">⚡ 연간 학교 전력 자립률</div>
            <div class="metric-value" style="color:#10b981;">{res.annual_self_sufficiency_percent:.1f} %</div>
            <div class="metric-sub">{res.status_badge_ko}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c2:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">🏢 총 설비 용량</div>
            <div class="metric-value">{res.system_capacity_kw:.1f} <span style="font-size:1rem;">kW</span></div>
            <div class="metric-sub">패널 {panel_count}장 ({panel_count * panel_area:.1f} m²)</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c3:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">☀️ 연간 예상 발전량</div>
            <div class="metric-value">{(res.annual_generation_kwh / 1000):.1f} <span style="font-size:1rem;">MWh</span></div>
            <div class="metric-sub">일평균 {(res.annual_generation_kwh / 365):.1f} kWh</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c4:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">💰 연간 전기요금 절감</div>
            <div class="metric-value">{(res.annual_bill_savings_krw / 10000):.0f} <span style="font-size:1rem;">만 원</span></div>
            <div class="metric-sub">교육용 고압 {elec_rate:.0f}원/kWh 기준</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c5:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">🌲 연간 탄소 감축량</div>
            <div class="metric-value">{(res.annual_co2_reduced_kg / 1000):.1f} <span style="font-size:1rem;">톤 CO₂</span></div>
            <div class="metric-sub">소나무 {res.annual_tree_planted_equivalent:.0f}그루 식재 효과</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ── 차트 섹션 ──────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 월별 수급 밸런스 및 자립률", "📈 24시간 피크 감축 곡선", "📋 월별 상세 데이터표"])

# 데이터프레임 변환
monthly_df = pd.DataFrame([asdict(m) for m in [m for m in res.monthly]])
hourly_df = pd.DataFrame([asdict(h) for h in [h for h in res.hourly]])

with tab1:
    st.subheader("월별 학교 전력 소비량 vs 태양광 발전량 (kWh)")
    chart_data = monthly_df.rename(
        columns={
            "month": "월",
            "consumption_kwh": "학교 전력 소비량 (kWh)",
            "generation_kwh": "태양광 발전량 (kWh)",
            "self_sufficiency_percent": "전력 자립률 (%)",
        }
    )
    chart_data["월"] = chart_data["월"].apply(lambda x: f"{x}월")
    chart_data.set_index("월", inplace=True)

    st.bar_chart(chart_data[["학교 전력 소비량 (kWh)", "태양광 발전량 (kWh)"]])
    st.line_chart(chart_data["전력 자립률 (%)"])
    st.caption("※ 봄·가을철에는 청명한 날씨와 높은 일사량으로 자립률이 최대치에 도달합니다.")

with tab2:
    st.subheader("대표 평일 24시간 부하-발전 곡선 (피크 감축 효과)")
    h_chart = hourly_df.rename(
        columns={
            "hour": "시간 (시)",
            "school_load_kw": "학교 기본 전력 부하 (kW)",
            "solar_generation_kw": "태양광 실시간 발전 출력 (kW)",
            "net_load_kw": "태양광 상쇄 후 한전 수전 부하 (kW)",
        }
    )
    h_chart.set_index("시간 (시)", inplace=True)
    st.area_chart(h_chart[["학교 기본 전력 부하 (kW)", "태양광 실시간 발전 출력 (kW)", "태양광 상쇄 후 한전 수전 부하 (kW)"]])
    st.caption(
        "학교는 오전 9시~오후 4시 사이 주간 수업·냉난방 피크가 발생하며, 이는 태양광 발전 피크 시간대(10시~15시)와 정밀하게 일치하여 한전 피크 요금 저감에 기여합니다."
    )

with tab3:
    st.subheader("월별 시뮬레이션 세부 수치")
    display_df = monthly_df[
        [
            "month",
            "daily_psh",
            "generation_kwh",
            "consumption_kwh",
            "self_sufficiency_percent",
            "self_consumed_kwh",
            "grid_import_kwh",
            "surplus_kwh",
            "bill_savings_krw",
        ]
    ].rename(
        columns={
            "month": "월",
            "daily_psh": "일평균일조(h)",
            "generation_kwh": "발전량(kWh)",
            "consumption_kwh": "소비량(kWh)",
            "self_sufficiency_percent": "자립률(%)",
            "self_consumed_kwh": "자가소비(kWh)",
            "grid_import_kwh": "한전수전(kWh)",
            "surplus_kwh": "잉여생산(kWh)",
            "bill_savings_krw": "절감액(원)",
        }
    )
    st.dataframe(display_df, use_container_width=True)

    csv_data = display_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "📥 월별 시뮬레이션 결과 CSV 다운로드",
        data=csv_data,
        file_name=f"solarmaps_simulation_panels_{panel_count}_area_{int(install_area)}m2.csv",
        mime="text/csv",
    )

# 모델 및 문헌 설명
with st.expander("📖 시뮬레이터 물리 모델 및 계산 기준 (SolarMaps 규격서 연계)"):
    st.markdown(
        """
        - **일사량 모형**: NASA POWER 및 기상청 기후평년(Chen & Chen 2013) 기준 최적 경사각 일조시간(PSH) 적산
        - **시스템 손실 계수**: 배선·인버터·오염 손실 14% 일괄 반영 (PVWatts / PVGIS 표준)
        - **설치 공간 산식**: 패널 단위면적 × 그림자 회피 경사각 이격거리 계수(1.35)
        - **탄소 감축 계수**: 0.4781 kgCO₂/kWh (전력거래소 전력 배출계수, 규격서 `docs/DATA_SPEC.md` §3)
        - **소나무 환산 계수**: 국립산림과학원 30년생 중부지방 소나무 기준 1그루당 연간 6.6 kgCO₂ 흡수량
        """
    )
