"""Pi 노드 케이스 조립 가이드 PDF (A4 인쇄용) 생성.

필요: pip install reportlab pillow
순서: Blender 에서 solarmaps_case.blend 연 뒤 case_guide/render_views.py 실행 → 이 스크립트 실행.
결과: modeling/solarmaps_case_assembly_guide.pdf
"""
import os
import sys

from reportlab.lib.colors import black
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

HERE = os.path.dirname(os.path.abspath(__file__))
MODELING = os.path.dirname(HERE)
sys.path.insert(0, MODELING)
from guide_pdf import (GREY, MARGIN, PH, PW, TW, blender_constants, bullets, cover,  # noqa: E402
                       draw_image, footer, header, note_box, paragraph, section, setup, table)

OUT = os.environ.get("GUIDE_OUT") or os.path.join(MODELING, "solarmaps_case_assembly_guide.pdf")
C = blender_constants(os.path.join(MODELING, "build_case.py"))
setup(os.path.join(HERE, "_img"), "SolarMaps Pi 노드 케이스 · 조립 가이드")

OUT_X = C["IN_X"] + 2 * C["WALL"]
OUT_Y = C["IN_Y"] + 2 * C["WALL"]
NOTCH_W = C["NOTCH_X"][1] - C["NOTCH_X"][0]
NOTCH_H = C["TONGUE_Z"] - C["NOTCH_Z"]

c = canvas.Canvas(OUT, pagesize=(PW, PH))
c.setTitle("SolarMaps Pi 노드 케이스 조립 가이드")
c.setAuthor("HAFS EURIF SolarMaps")
page = 1

# ---- 1. 표지 + 준비물 ----
cover(c, "Pi 노드 케이스 조립 가이드", [
    "HAFS EURIF · SolarMaps 측정 노드 (Raspberry Pi Zero W + FNB58 + 보조배터리)",
    f"케이스 {OUT_X:.0f} × {OUT_Y:.0f} × {C['H'] + C['LID_T']:.0f} mm · 출력 2판 · 뚜껑은 끼워 닫음 (나사 없음)",
])
draw_image(c, "c01_overview", MARGIN, PH - 146 * mm, w=TW, h=92 * mm, callouts=(
    ("lid", "뚜껑", 60, 10),
    ("body", "몸체", 55, -12),
    ("notch", "케이블 노치", -75, 18),
    ("cable", "태양광 케이블", 70, 22),
))
y = PH - 154 * mm
section(c, "준비물", MARGIN, y)
y -= 8
rows = [
    ["케이스 몸체 · 뚜껑", "각 1", "3D 출력 (solarmaps_case_body.stl / _lid.stl)"],
    ["Raspberry Pi Zero W", "1", "공식 케이스에 넣은 상태 (79 × 38 × 15 mm)"],
    ["FNB58 USB 테스터", "1", "태양광 → 배터리 충전 전력 측정"],
    ["Anker Zolo A110E 보조배터리", "1", "Pi 전원 (태양광으로 충전) · 20000 mAh"],
    ["① USB-A → USB-C 케이블", "1", "태양광 패널 → FNB58 입력"],
    ["② USB-C → USB-C 케이블", "1", "FNB58 출력 → 배터리"],
    ["③ Micro-USB OTG ↔ Micro-USB", "1", "FNB58 PC 포트 → Pi 'USB' (데이터)"],
    ["④ USB-A → Micro-USB 케이블", "1", "배터리 → Pi 'PWR IN' (전원)"],
]
y = table(c, MARGIN, y, [("품목", 62 * mm), ("수량", 14 * mm), ("용도", TW - 76 * mm)], rows, size=9)
y -= 8
paragraph(c, "※ 짧은 케이블(20~30 cm)일수록 케이스 안에 정리하기 쉽습니다. ③은 Pi 쪽이 OTG(호스트) 커넥터여야 "
             "FNB58 이 인식됩니다. 그림의 부품·포트는 개략 형상이며, 실제 연결은 기기에 인쇄된 표시(IN/OUT, USB/PWR)를 기준으로 합니다.",
          MARGIN, y, TW, size=9, color=GREY)
footer(c, page)
c.showPage()
page += 1

# ---- 2. 출력 ----
header(c, "0", "출력 (Bambu Lab A1, 2판)", page)
y = PH - 30 * mm
draw_image(c, "c02_print", MARGIN, y - 72 * mm, w=TW, h=70 * mm, callouts=(
    ("body", "몸체 — 그대로", -30, -22),
    ("lid", "뚜껑 — 글자면이 바닥", 40, 20),
))
y -= 82 * mm
y = bullets(c, [
    f"① 몸체와 뚜껑은 각각 {OUT_X:.0f} × {OUT_Y:.0f} mm 라서 A1 베드(256 mm)에 둘을 같이 올릴 수 없습니다. 한 판씩 두 번 출력합니다.",
    "② solarmaps_case_body.stl 은 바닥면이 베드에 닿는 방향 그대로, solarmaps_case_lid.stl 은 이미 뒤집혀 저장되어 있어 "
    "글자(HAFS EURIF / SolarMaps)가 새겨진 윗면이 베드에 닿습니다. 방향을 바꾸지 마세요.",
    "③ 서포트는 필요 없습니다. 권장: PLA, 0.4 노즐, 레이어 0.2 mm, 벽 3줄, 내부 채움 15~20%.",
    f"④ 뚜껑 립과 몸체 안쪽 사이 여유는 한쪽 {C['FIT']} mm 입니다. 첫 레이어가 퍼지면(코끼리 발) 뚜껑이 빡빡하니, "
    "끼울 때 걸리면 립 아래 모서리를 살짝 다듬으세요.",
], MARGIN, y, TW)
y -= 6
note_box(c, MARGIN, y, TW, "안쪽 구조 미리 보기", [
    "몸체 바닥에 BATTERY · FNB · PI 가 음각되어 있어 부품 자리를 바로 알 수 있습니다.",
    "FNB58 자리의 네 모서리 가이드와 Pi 뒤쪽 스토퍼가 부품을 잡아 줍니다. 부품 사이의 빈 통로(좌·우 채널, 뒤쪽 케이블 베이)로 케이블을 지나게 합니다.",
    f"뒷벽의 노치(폭 {NOTCH_W:.0f} mm)로 태양광 케이블이 들어옵니다. 뚜껑의 텅이 위에서 눌러 통로 높이는 {NOTCH_H:.1f} mm 입니다 (케이블 굵기 5 mm 이하).",
])
c.showPage()
page += 1

# ---- 3. 1단계: 부품 배치 ----
header(c, "1", "부품 넣기", page)
y = PH - 28 * mm
w2 = (TW - 6 * mm) / 2
draw_image(c, "c03_zones", MARGIN, y - 100 * mm, w=w2, h=98 * mm, callouts=(
    ("notch", "케이블 노치", -45, 14),
    ("bay", "케이블 베이", 40, 16),
    ("lch", "좌 채널", -40, 10),
    ("rch", "우 채널", 30, -14),
    ("fnb", "FNB58 자리", 20, 26),
    ("batt", "배터리 자리", -30, -28),
    ("pi", "Pi 자리", 25, -22),
))
draw_image(c, "c04_parts", MARGIN + w2 + 6 * mm, y - 100 * mm, w=w2, h=98 * mm, callouts=(
    ("batt_ports", "배터리 포트", 20, 20),
    ("fnb_left", "C 입력·출력 면", -35, -22),
    ("fnb_pc", "PC 포트 면", 20, 24),
    ("plug", "USB-A 플러그 (안 씀)", 30, -22),
    ("pi_ports", "Pi 포트", -30, 16),
))
c.setFont("KRB", 10)
c.setFillColor(black)
c.drawCentredString(MARGIN + w2 / 2, y - 106 * mm, "빈 몸체 — 구역")
c.drawCentredString(MARGIN + w2 * 1.5 + 6 * mm, y - 106 * mm, "부품을 넣은 모습 (위에서)")
y -= 114 * mm
bullets(c, [
    "① 배터리: 왼쪽 긴 칸(BATTERY)에 눕혀 넣습니다. 포트가 있는 짧은 면이 뒤쪽(케이블 베이 쪽)을 향하게 합니다. "
    "뒤에서 보면 왼쪽부터 USB-A, USB-C, 내장 케이블(C) 순서입니다.",
    "② FNB58: 가운데 위 칸(FNB)의 네 모서리 가이드 안에 화면이 위로 오게 넣습니다. USB-A 플러그가 앞쪽(Pi 쪽)을 향하고, "
    "Type-C 입력·출력과 PD 스위치가 있는 면이 왼쪽(배터리 쪽), PC 용 Micro-USB 가 있는 면이 오른쪽입니다. USB-A 플러그는 쓰지 않습니다.",
    "③ Pi: 오른쪽 아래 칸(PI)에 넣고, 포트(mini HDMI · USB · PWR IN)가 뒤쪽(FNB58 쪽)을 향하게 합니다. "
    "Pi 뒤쪽 스토퍼가 끊겨 있는 가운데 구간이 포트 자리입니다.",
    f"④ 배선 전에 세 부품이 바닥에 평평하게 앉았는지 확인합니다. 부품 윗면이 벽 높이({C['H']:.0f} mm)보다 높으면 안 됩니다.",
], MARGIN, y, TW, size=9.5)
c.showPage()
page += 1

# ---- 4. 2단계: 배선 ----
header(c, "2", "배선", page)
y = PH - 28 * mm
draw_image(c, "c05_wiring", MARGIN, y - 120 * mm, w=TW * 0.56, h=118 * mm, callouts=(
    ("c1", "①", 22, 10),
    ("c2", "②", 0, 20),
    ("c3", "③", 20, 0),
    ("c4", "④", -20, 0),
    ("panel", "태양광 패널에서", 50, 0),
    ("builtin", "내장 케이블 (미사용)", 40, -30),
))
x2 = MARGIN + TW * 0.59
w_r = TW * 0.41
yy = y - 4
section(c, "전력·데이터 흐름", x2, yy, size=11)
yy -= 10
yy = bullets(c, [
    "① 태양광 → FNB58 Type-C 입력 (USB-A→C)",
    "② FNB58 Type-C 출력 → 배터리 C 포트 (C→C)",
    "③ FNB58 PC Micro-USB → Pi 'USB' (OTG 케이블)",
    "④ 배터리 USB-A → Pi 'PWR IN' (A→Micro)",
], x2, yy, w_r, size=9.5, gap=2)
yy -= 4
yy = paragraph(c, "FNB58 은 태양광이 배터리를 충전하는 전력을 재고, Pi 는 ③으로 측정값을 읽습니다. Pi 는 배터리(④)로 동작합니다.",
               x2, yy, w_r, size=9, color=GREY)
yy -= 6
note_box(c, x2, yy, w_r, "연결 순서", [
    "③ → ② → ① 순서로 먼저 꽂고, ④(Pi 전원)를 마지막에 꽂습니다.",
    "Pi 전원(④)을 꽂는 순간 Pi 가 켜집니다. 뚜껑을 닫기 전에 동작을 확인하세요 (3단계).",
], size=9)
y -= 128 * mm
bullets(c, [
    "① 태양광 케이블은 뒷벽 노치로 들어와 왼쪽 채널(배터리와 FNB58 사이)을 따라 FNB58 왼쪽 면의 Type-C 입력에 꽂습니다.",
    "② FNB58 왼쪽 면 Type-C 출력에서 왼쪽 채널 → 뒤쪽 케이블 베이를 지나 배터리 C 포트로 연결합니다.",
    "③ FNB58 오른쪽 면 PC 포트에서 오른쪽 채널을 따라 내려가 Pi 의 가운데 Micro-USB('USB')에 꽂습니다.",
    "④ 배터리 USB-A 에서 케이블 베이 → 왼쪽 채널 → Pi 포트 앞 공간을 지나 Pi 가장자리 Micro-USB('PWR IN')에 꽂습니다.",
    "배터리 내장 케이블(C, 회색)은 이 배선에서 쓰지 않습니다. 케이블 베이 안쪽에 눕혀 두고, 나머지 케이블도 베이와 채널 안에 눕혀 정리합니다. "
    "벽 위로 올라온 케이블은 뚜껑 립에 눌립니다.",
], MARGIN, y, TW, size=9.5)
c.showPage()
page += 1

# ---- 5. 3단계: 확인 후 뚜껑 닫기 ----
header(c, "3", "동작 확인 · 뚜껑 닫기", page)
y = PH - 28 * mm
w2 = (TW - 6 * mm) / 2
draw_image(c, "c06_lid_under", MARGIN, y - 64 * mm, w=w2, h=62 * mm, callouts=(
    ("lip", "립 (몸체 안으로 들어감)", 20, 18),
    ("tongue", "텅 (케이블 누름)", 40, -14),
))
draw_image(c, "c07_close", MARGIN + w2 + 6 * mm, y - 64 * mm, w=w2, h=62 * mm, callouts=(
    ("tongue", "텅", 30, 12),
    ("notch", "노치", 40, -12),
    ("cable", "태양광 케이블", -10, -26),
))
c.setFont("KRB", 10)
c.setFillColor(black)
c.drawCentredString(MARGIN + w2 / 2, y - 70 * mm, "뚜껑 아래면 (뒤집은 모습)")
c.drawCentredString(MARGIN + w2 * 1.5 + 6 * mm, y - 70 * mm, "뒤에서 본 모습 — 텅이 노치 위로")
y -= 80 * mm
y = note_box(c, MARGIN, y, TW, "닫기 전에 확인", [
    "Pi 전원(④)을 꽂고 1~2분 기다린 뒤 Pi 에 접속해 lsusb 결과에 FNB58(2e3c:5558)이 보이는지 확인합니다.",
    "journalctl -u solarmaps-pi -f 로 측정값이 올라오는지 봅니다. 문제가 있으면 docs/OPERATIONS.md 의 문제 해결 표를 참고하세요.",
    "해가 있을 때 FNB58 화면에 입력 전압·전류가 표시되면 ①②가 제대로 연결된 것입니다.",
])
y -= 8
y = bullets(c, [
    "① 태양광 케이블을 뒷벽 노치 안에 눕혀 끼웁니다. 노치 바닥에 닿도록 내려 두세요.",
    "② 뚜껑 글자가 앞쪽에서 바로 읽히는 방향으로 듭니다. 이때 뚜껑 아래 텅이 뒤쪽 노치 위에 옵니다.",
    "③ 뚜껑 립을 몸체 안쪽 벽에 맞추고 네 모서리를 고르게 눌러 끼웁니다. 텅이 노치 속 케이블을 위에서 눌러 고정합니다.",
    "④ 열 때는 앞쪽 모서리를 손톱으로 살짝 들어 올립니다. 케이블을 당겨서 열지 마세요.",
], MARGIN, y, TW, size=9.5)
note_box(c, MARGIN, y - 8, TW, "설치 시 주의", [
    "케이스는 방수가 아닙니다. 비와 이슬이 닿지 않는 곳(창가 안쪽, 처마 아래 등)에 둡니다.",
    "보조배터리는 고온에 약합니다. 한여름 직사광선이 케이스에 바로 닿지 않게 하세요.",
])
c.showPage()
c.save()
print("saved", OUT)
