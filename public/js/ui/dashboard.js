// school_energy_summary/latest 요약 카드 (규격서 §3 컬렉션 4).

import { createCard, statRowHtml } from "./dom.js";

export function renderDashboard(container, summary, onOpenSimulator) {
  container.innerHTML = "";
  if (!summary) {
    // 실시간 Firestore 요약 문서가 없거나 연결 전일 때 HAFS 실측 기반 데이터 표시
    const card = createCard({
      title: "🏫 HAFS 전력 대체율 실측 분석",
      subtitle: "옥상·유휴지 3회 실측 및 8개월 고지서 기준",
      bodyHtml: `
        <div style="font-size:11px;color:#38bdf8;background:rgba(56,189,248,0.1);padding:6px 8px;border-radius:6px;margin-bottom:8px;">
          📍 <strong>3회 측정 면적:</strong> 7,606 / 7,644 / 7,588 m² (평균 7,612.7 m²)
        </div>
        ${statRowHtml("8개월 실측 대체율 (B안)", "61.2 %", { big: true })}
        ${statRowHtml("8개월 실측 대체율 (A안)", "30.6 %")}
        ${statRowHtml("8개월 학교 소비량 (B안)", "1,086,927 kWh")}
        ${statRowHtml("동기간 예상 발전량", "665,130 kWh")}
        ${statRowHtml("설치 가능 용량 (η=100%)", "761.3 kW")}
        ${statRowHtml("연간 예상 발전량", "972.5 MWh")}
        <div style="margin-top:12px;">
          <button id="dashboard-open-sim-empty-btn" class="btn btn-primary btn-sm" style="width:100%;">
            ⚡ 패널·면적 자립률 시뮬레이터 실행
          </button>
        </div>
      `,
    });
    container.appendChild(card);
    const emptyBtn = card.querySelector("#dashboard-open-sim-empty-btn");
    if (emptyBtn && onOpenSimulator) {
      emptyBtn.addEventListener("click", onOpenSimulator);
    }
    return;
  }

  const card = createCard({
    title: "학교 전력 기여도",
    subtitle: summary.date,
    bodyHtml: `
      ${statRowHtml("금일 실측 발전량", `${summary.today_total_generation_kwh?.toFixed(2) ?? "-"} kWh`)}
      ${statRowHtml("실제 기여율", `${summary.real_contribution_percent?.toFixed(2) ?? "-"} %`)}
      ${statRowHtml("전면 설치 시뮬레이션 자립률", `${summary.simulated_self_sufficiency_percent?.toFixed(1) ?? "-"} %`, { big: true })}
      ${statRowHtml("탄소 저감량", `${summary.co2_reduced_kg?.toFixed(2) ?? "-"} kg`)}
      ${statRowHtml("소나무 식재 환산", `${summary.tree_planted_equivalent?.toFixed(1) ?? "-"} 그루`)}
      <div style="margin-top:12px;">
        <button id="dashboard-open-sim-btn" class="btn btn-primary btn-sm" style="width:100%;gap:6px;">
          ⚡ 패널·면적 자립률 시뮬레이터 열기
        </button>
      </div>
    `,
  });
  container.appendChild(card);

  const btn = card.querySelector("#dashboard-open-sim-btn");
  if (btn && onOpenSimulator) {
    btn.addEventListener("click", onOpenSimulator);
  }
}
