"""SolarMaps 노드 케이스 (몸체 + 뚜껑) 생성 스크립트.

Blender 5.x 에서 실행한다 (MCP 또는 Text Editor 에서 Run Script).
1 BU = 1 mm. 결과물: modeling/solarmaps_case_body.stl, solarmaps_case_lid.stl

내부 배치 (위에서 본 모습, 좌하단 내벽 모서리가 원점, +Y 가 뒤쪽):

    Y=182 +--------------------------------------------+  <- 뒷벽 (X≈87 에 태양광 케이블 노치)
          |           케이블 베이 (배터리 포트 쪽)        |
    Y=150 +---------------+----+---------+-----+--------+
          |               |    |  FNB58  |     |        |
          |   BATTERY     | 좌 | 44 x 72 | 우  |        |
          |   74 x 143    | 채 | (좌측면  | 채  |        |
          |  (포트 +Y)    | 널 |  = -X)  | 널  |        |
          |               |    | A플러그 |     |        |
          |               +----+---------+-----+        |
          |               |   Pi 포트 케이블 공간        |
          |               |   PI 80 x 40 (포트 +Y)      |
    Y=0   +---------------+-----------------------------+
          X=0            74/76                        161
"""
import math
import os

import bmesh
import bpy

OUT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else \
    r"C:\Users\이민기\Desktop\개발\EURIF\SolarMaps\modeling"

# ---- 공통 치수 (mm) ----
WALL = 2.4          # 외벽 두께
FLOOR = 2.0         # 바닥 두께
IN_X, IN_Y = 161.0, 182.0
H = 34.0            # 몸체 높이 (내부 깊이 32 — 배터리 두께 27.7 + 위 여유, 뚜껑 립 하단 31)
CORNER_R = 3.0      # 외곽 모서리 라운드
ENGRAVE = 0.8       # 음각 깊이

LID_T = 2.4         # 뚜껑 판 두께
LIP_DEPTH = 3.0     # 뚜껑 립이 몸체 안으로 들어가는 깊이
LIP_T = 1.6         # 립 두께
FIT = 0.25          # 립-내벽 한쪽 공차

# 부품 포켓 (여유 포함)
# 배터리 Anker Zolo A110E (20000 mAh): 140.7 x 71.7 x 27.7 mm, 392 g
#   (Anker SG 제품 페이지 + 판매처 스펙, 두께는 판매처 간 일치) -> 포켓 74 x 143 (여유 ≈2.3 mm), 포트는 +Y 끝
#   두께 27.7 이 누워 있으므로 몸체 높이 H 를 22 -> 34 로 올렸다. 포트(USB-A·USB-C·내장 C 케이블)는 짧은 면(+Y)에 있다 (실물 사진 확인).
BATT_W, BATT_L, BATT_T = 71.7, 140.7, 27.7          # 폭(X) · 길이(Y, 포트 쪽 +Y) · 두께(Z)
BATT = (0.0, 74.0, 0.0, 143.0)
# Pi Zero 공식 케이스: 79 x 38 x 15 -> 80 x 40. 포트(mini HDMI/USB/PWR)는 기판 65mm 긴 변 -> +Y
PI = (79.0, 159.0, 0.0, 40.0)
# FNB58: 82 x 42 x 13 은 USB-A 수 플러그 포함 길이. 매뉴얼 도면 비율로 본체 ≈70, 플러그 ≈12.5.
# 본체 포켓 72 x 44, 플러그는 -Y 쪽 (Y 63.5~76) 으로 돌출. 좌측면(-X): C입력·micro입력·C출력·PD스위치,
# 우측면(+X): PC micro-USB·조작 스위치·BACK
FNB = (97.0, 141.0, 76.0, 148.0)
NOTCH_X = (83.5, 90.5)               # 태양광 A-to-C 케이블 인입 노치 (좌채널 위)
NOTCH_Z = 8.0                        # 노치 바닥 높이 (바닥면 기준 6mm 위)
TONGUE_Z = 13.5                      # 뚜껑 텅 하단 (케이블 통로 5.5mm)

FONT_PATHS = [r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\segoeuib.ttf"]


def get_collection(name):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    for ob in list(coll.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    return coll


COLL = get_collection("SolarMaps_Case")


def box(name, x0, x1, y0, y1, z0, z1, bevel=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = x1 if v.co.x > 0 else x0
        v.co.y = y1 if v.co.y > 0 else y0
        v.co.z = z1 if v.co.z > 0 else z0
    if bevel > 0:
        vert_edges = [e for e in bm.edges
                      if abs(e.verts[0].co.x - e.verts[1].co.x) < 1e-6
                      and abs(e.verts[0].co.y - e.verts[1].co.y) < 1e-6]
        bmesh.ops.bevel(bm, geom=vert_edges, offset=bevel, segments=10,
                        profile=0.5, affect="EDGES")
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    COLL.objects.link(ob)
    return ob


def load_font():
    for p in FONT_PATHS:
        if os.path.exists(p):
            return bpy.data.fonts.load(p, check_existing=True)
    return None


FONT = load_font()


def text(name, body, size, cx, cy, z0, depth, rot_deg=0.0):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.space_line = 1.15
    cu.extrude = depth / 2.0
    if FONT:
        cu.font = FONT
    tmp = bpy.data.objects.new(name + "_crv", cu)
    COLL.objects.link(tmp)
    tmp.location = (cx, cy, z0 + depth / 2.0)
    tmp.rotation_euler = (0, 0, math.radians(rot_deg))
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    me.transform(tmp.matrix_world)
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.curves.remove(cu)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    COLL.objects.link(ob)
    return ob


def boolean(target, cutter, op):
    mod = target.modifiers.new("bool", "BOOLEAN")
    mod.operation = op
    mod.solver = "EXACT"
    mod.object = cutter
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(target.evaluated_get(dg))
    target.modifiers.clear()
    old = target.data
    target.data = me
    bpy.data.meshes.remove(old)
    cut_me = cutter.data
    bpy.data.objects.remove(cutter, do_unlink=True)
    bpy.data.meshes.remove(cut_me)


def fnb_corner_posts(x0, x1, y0, y1, h):
    """FNB58 본체 네 모서리 L자 가이드. 짧은 변(USB-A 단) 8mm, 긴 변(측면 포트) 3mm 만 덮는다.

    좌측면 출력단 쪽 모서리(-X, +Y)는 PD 스위치 창이 끝까지 이어져 긴 변 다리를 뺀다.
    짧은 변 다리 사이 26mm 틈으로 USB-A 플러그(폭 12)가 빠진다.
    """
    t, short_leg, long_leg = 1.6, 8.0, 3.0
    posts = []
    for sx, cx in ((-1, x0), (1, x1)):
        for sy, cy in ((-1, y0), (1, y1)):
            # 짧은 변 방향(X) 다리
            xa, xb = sorted((cx + sx * t, cx - sx * short_leg))
            ya, yb = sorted((cy, cy + sy * t))
            posts.append((xa, xb, ya, yb))
            if sx < 0 and sy > 0:
                continue
            # 긴 변 방향(Y) 다리
            xa, xb = sorted((cx, cx + sx * t))
            ya, yb = sorted((cy + sy * t, cy - sy * long_leg))
            posts.append((xa, xb, ya, yb))
    return [(a, b, c, d, 1.0, h) for a, b, c, d in posts]


# =====================================================================
# 몸체
# =====================================================================
body = box("Case_Body", -WALL, IN_X + WALL, -WALL, IN_Y + WALL, 0.0, H, bevel=CORNER_R)
boolean(body, box("cavity", 0.0, IN_X, 0.0, IN_Y, FLOOR, H + 5), "DIFFERENCE")

inner_parts = [
    # 배터리 | 우측 열 칸막이 (좌채널 벽)
    (BATT[1], BATT[1] + 2.0, -0.5, BATT[3], 1.0, 18.0),
    # 배터리 상단 스토퍼 (포트면 양 끝만 막음)
    (-0.5, 6.0, BATT[3], BATT[3] + 2.0, 1.0, 10.0),
    (BATT[1] - 6.0, BATT[1] + 2.0, BATT[3], BATT[3] + 2.0, 1.0, 10.0),
    # Pi 포트쪽 스토퍼 (포트 구간 X≈90~146 비움)
    (BATT[1] + 1.0, PI[0] + 6.0, PI[3], PI[3] + 2.0, 1.0, 9.0),
    (PI[1] - 6.0, IN_X + 0.5, PI[3], PI[3] + 2.0, 1.0, 9.0),
] + fnb_corner_posts(*FNB, 9.0)

for i, p in enumerate(inner_parts):
    boolean(body, box(f"part{i}", *p), "UNION")

# 태양광 케이블 인입 노치 (뒷벽, 위에서 케이블을 눕혀 넣는 방식)
boolean(body, box("notch", NOTCH_X[0], NOTCH_X[1], IN_Y - 1.0, IN_Y + WALL + 2.0,
                  NOTCH_Z, H + 5), "DIFFERENCE")

# 구역 라벨 음각 (바닥)
z0 = FLOOR - ENGRAVE
for label, size, cx, cy in (
    ("BATTERY", 11.0, (BATT[0] + BATT[1]) / 2, (BATT[2] + BATT[3]) / 2),
    ("FNB", 14.0, (FNB[0] + FNB[1]) / 2, (FNB[2] + FNB[3]) / 2),
    ("PI", 16.0, (PI[0] + PI[1]) / 2, (PI[2] + PI[3]) / 2),
):
    boolean(body, text("lbl_" + label, label, size, cx, cy, z0, ENGRAVE + 1.0), "DIFFERENCE")

# =====================================================================
# 뚜껑 (조립 위치 기준으로 모델링)
# =====================================================================
lid = box("Case_Lid", -WALL, IN_X + WALL, -WALL, IN_Y + WALL, H, H + LID_T, bevel=CORNER_R)

lip_o = (FIT, IN_X - FIT, FIT, IN_Y - FIT)
lip = box("lip", *lip_o, H - LIP_DEPTH, H + 0.2)
boolean(lip, box("lip_in", lip_o[0] + LIP_T, lip_o[1] - LIP_T, lip_o[2] + LIP_T, lip_o[3] - LIP_T,
                 H - LIP_DEPTH - 1, H + 1), "DIFFERENCE")
boolean(lid, lip, "UNION")
# 노치를 덮어 케이블을 눌러주는 텅
boolean(lid, box("tongue", NOTCH_X[0] + 0.3, NOTCH_X[1] - 0.3, IN_Y - 0.1, IN_Y + WALL,
                 TONGUE_Z, H + 0.2), "UNION")

boolean(lid, text("lid_text", "HAFS EURIF\nSolarMaps", 19.0, IN_X / 2, IN_Y / 2,
                  H + LID_T - ENGRAVE, ENGRAVE + 1.0), "DIFFERENCE")

# =====================================================================
# 보기용 재질 / 표시 위치
# =====================================================================
def viewport_mat(name, rgba):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = rgba
    return mat


body.data.materials.append(viewport_mat("CaseBody", (0.15, 0.35, 0.55, 1)))
lid.data.materials.append(viewport_mat("CaseLid", (0.9, 0.75, 0.2, 1)))

# =====================================================================
# 출력: 몸체는 그대로, 뚜껑은 글자면이 베드에 닿도록 뒤집어서 저장
# =====================================================================
def export_stl(ob, path):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True,
                          apply_modifiers=True, global_scale=1.0, use_scene_unit=False)


os.makedirs(OUT_DIR, exist_ok=True)
export_stl(body, os.path.join(OUT_DIR, "solarmaps_case_body.stl"))

lid.rotation_euler = (math.pi, 0, 0)
lid.location = (0, IN_Y, H + LID_T)
bpy.context.view_layer.update()
export_stl(lid, os.path.join(OUT_DIR, "solarmaps_case_lid.stl"))

# 씬에서는 몸체 옆에 뚜껑(윗면이 보이게)을 놓아 둔다
lid.rotation_euler = (0, 0, 0)
lid.location = (IN_X + 2 * WALL + 15.0, 0, -H)
