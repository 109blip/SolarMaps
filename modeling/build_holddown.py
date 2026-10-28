r"""SolarMaps 압박 부품 (출력 1판) 생성 스크립트.

Blender 5.x 에서 실행한다 (MCP 또는 Text Editor 에서 Run Script). 새 씬 "SolarMaps_Holddown" 에 만든다.
1 BU = 1 mm. 결과물: modeling/solarmaps_holddown_plate.stl (한 판), 부품별은 holddown_parts/.

1) 패널 누름 클립 x8 — 거치대 쐐기식 클립(build_stand.py)을 대신한다.
   실제 패널은 얇아서 윗면이 프레임 테두리(턱 위 RIM_H) 높이와 거의 같다. 클립 윗날이
   테두리 위에 얹혀 높이가 정해지고, 윗날 아래 누름판이 테두리 안쪽으로 PRESS 만큼 내려와
   천 패널을 눌러 준다. 누름판 바깥 면이 테두리 안쪽 벽에 걸려 클립이 빠지지 않는다.

        윗날 (테두리 위)
     +-------------------+
     |  |rim|  [누름판]  |      <- 누름판 밑면 = 테두리 윗면 - PRESS
     |  |   |=== 패널 ====
     |  |      턱(레일)   |
     |  +----------------+ |    <- 레일 뒷면을 감싸고 안쪽 모서리에 걸쇠
     +-----------------------+

2) 케이스 누름판 x1 — 뚜껑 립 바로 아래, 오른쪽 열(Pi·FNB58)과 위쪽 케이블 베이를 덮는
   ㄱ자 판. 뚜껑을 닫으면 밑면이 케이블을 PAD_Z0 높이까지 누르고, 위로 미는 힘은 테두리를
   통해 뚜껑 립 밑면 → 뚜껑 가장자리로 간다 (뚜껑 가운데가 휘지 않게 가운데는 띄움).
   배터리(윗면 29.7) 위는 공간이 없어 덮지 않는다.
3) 케이스 고정 클립 x4 — 뚜껑 윗면과 몸체 바닥을 함께 물어 뚜껑이 뜨지 않게 한다.
   옆(긴 면 X=-WALL, X=IN_X+WALL)에서 밀어 끼운다. 뒷벽 케이블 노치는 피한다.

케이스 치수는 build_case.py, 프레임 치수는 build_stand.py 와 같아야 한다.
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix

OUT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else \
    r"C:\Users\이민기\Desktop\개발\EURIF\SolarMaps\modeling"
PARTS_DIR = os.path.join(OUT_DIR, "holddown_parts")

# ---- 거치대 프레임 레일 (build_stand.py 와 같게) ----
RIM_W = 4.0                           # 바깥 테두리 벽 폭
LEDGE = 10.0
RAIL_W = RIM_W + LEDGE                # 14
RAIL_T = 18.0                         # 턱 윗면 높이
RIM_H = 6.0                           # 턱 위 테두리 높이
PANEL_CLR = 1.5                       # 테두리 ~ 패널 가장자리

# ---- 패널 누름 클립 ----
PC_L = 15.0                           # 레일 방향 길이
PC_T = 2.4                            # 살 두께
PC_CLR = 0.25
PRESS = 1.5                           # 누름판이 테두리 윗면보다 내려오는 깊이 (천 압축량)
PC_REACH = 14.5                       # 레일 바깥 가장자리에서 윗날 끝까지
PAD_U = (RIM_W + PC_CLR, 13.5)        # 누름판 범위 (레일 바깥 가장자리 기준)
PAD_CHAMFER = 1.5                     # 끼울 때 테두리를 타고 넘도록 앞쪽 아래 모따기
HOOK_H = 0.8                          # 레일 뒷면 안쪽 모서리 걸쇠
N_PANEL_CLIPS = 8

# ---- 케이스 (build_case.py 와 같게) ----
WALL, IN_X, IN_Y, H = 2.4, 161.0, 182.0, 34.0
LID_T, LIP_DEPTH, LIP_T, FIT = 2.4, 3.0, 1.6, 0.25
BATT_X1, BATT_Y1 = 76.0, 145.0        # 배터리 열 칸막이 오른쪽 면 / 배터리 위 스토퍼 끝
NOTCH_X = (83.5, 90.5)
LIP_BOT = H - LIP_DEPTH               # 31: 뚜껑 립 밑면
LIP_IN = FIT + LIP_T                  # 1.85: 내벽에서 립 안쪽 면까지

# ---- 케이스 누름판 ----
PAD_CLR = 0.5                         # 내벽·칸막이와의 틈
PAD_Z0 = 23.0                         # 밑면 높이 (Pi 케이스 윗면 17, FNB58 15 위로 케이블 6mm)
PAD_SKIN = 1.0                        # 밑판 두께
PAD_RIM_W = 2.4                       # 립 밑을 받치는 테두리 폭 (립은 내벽에서 0.25~1.85)
PAD_RIB_T = 1.6
PAD_RIB_TOP = H - 0.6                 # 안쪽 리브 윗면 (뚜껑 밑면과 0.6 띄움)
PAD_RIB_PITCH = 42.0
PAD_HOLE_INSET = 9.0                  # 칸 구멍 가장자리 ~ 리브

# ---- 케이스 고정 클립 ----
CC_L = 18.0
CC_T = 2.4
CC_REACH = 9.0                        # 뚜껑 윗면·바닥을 덮는 길이
CC_GRIP = H + LID_T - 0.3             # 위아래 날 사이 (0.3mm 조임)
CC_CHAMFER = 1.2
CC_Y = (40.0, IN_Y - 40.0)            # 긴 면마다 2개 (내벽 기준 Y)


# =====================================================================
# 씬 / 헬퍼 (build_stand.py 와 같은 방식)
# =====================================================================
def get_scene(name):
    sc = bpy.data.scenes.get(name) or bpy.data.scenes.new(name)
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 0.001
    sc.unit_settings.length_unit = "MILLIMETERS"
    win = bpy.context.window or bpy.context.window_manager.windows[0]
    win.scene = sc
    return sc


SCENE = get_scene("SolarMaps_Holddown")


def get_collection(name):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
    if coll.name not in SCENE.collection.children:
        SCENE.collection.children.link(coll)
    coll.hide_viewport = False
    SCENE.view_layers[0].layer_collection.children[coll.name].hide_viewport = False
    SCENE.view_layers[0].layer_collection.children[coll.name].exclude = False
    for ob in list(coll.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    return coll


COLL = get_collection("SolarMaps_Holddown")
PLATES = get_collection("SolarMaps_Holddown_Plate")


def make_obj(name, bm, coll=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    (coll or COLL).objects.link(ob)
    return ob


def box(name, x0, x1, y0, y1, z0, z1):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = x1 if v.co.x > 0 else x0
        v.co.y = y1 if v.co.y > 0 else y0
        v.co.z = z1 if v.co.z > 0 else z0
    return make_obj(name, bm)


def prism(name, pts, lo, hi):
    """(x, y) 다각형을 Z 방향 lo~hi 로 돌출."""
    bm = bmesh.new()
    lo_v = [bm.verts.new((p[0], p[1], lo)) for p in pts]
    hi_v = [bm.verts.new((p[0], p[1], hi)) for p in pts]
    bm.faces.new(list(reversed(lo_v)))
    bm.faces.new(hi_v)
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((lo_v[i], lo_v[j], hi_v[j], hi_v[i]))
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return make_obj(name, bm)


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


# =====================================================================
# 1) 패널 누름 클립 — 로컬: x = 레일 바깥 가장자리 기준 u, y = 레일 두께 방향 (Z=0 이 레일 뒷면),
#    z = 레일 길이 방향. 단면이 베드에 눕도록 그대로 출력 (휘는 방향이 적층과 나란함)
# =====================================================================
c, t = PC_CLR, PC_T
hx = RAIL_W + c
zt0 = RAIL_T + RIM_H + c              # 윗날 아랫면 = 테두리 윗면 + 틈
zp = RAIL_T + RIM_H - PRESS           # 누름판 밑면
pc_pts = [
    (-c - t, -c - t), (hx + 2.2, -c - t), (hx + 2.2, -c), (hx + 1.6, -c),
    (hx + 1.6 - HOOK_H - c, HOOK_H), (hx, HOOK_H), (hx, -c), (-c, -c),
    (-c, zt0), (PAD_U[0], zt0), (PAD_U[0], zp),
    (PAD_U[1] - PAD_CHAMFER, zp), (PAD_U[1], zp + PAD_CHAMFER), (PAD_U[1], zt0),
    (PC_REACH, zt0), (PC_REACH, zt0 + t - 0.8), (PC_REACH - 0.8, zt0 + t),
    (-c - t, zt0 + t),
]
panel_clip = prism("Holddown_PanelClip", pc_pts, 0.0, PC_L)

# =====================================================================
# 2) 케이스 누름판 — 케이스 좌표 그대로 (내벽 좌하단 모서리 원점), 출력은 뒤집지 않고 밑판이 베드
# =====================================================================
x0, x1 = BATT_X1 + PAD_CLR, IN_X - PAD_CLR
y0, y1 = PAD_CLR, IN_Y - PAD_CLR
xb = PAD_CLR                          # 위쪽 베이의 왼쪽 끝
ell = [(x0, y0), (x1, y0), (x1, y1), (xb, y1), (xb, BATT_Y1 + PAD_CLR), (x0, BATT_Y1 + PAD_CLR)]
pad = prism("Holddown_CasePad", ell, PAD_Z0, PAD_Z0 + PAD_SKIN)

# 테두리: 내벽을 따라가는 세 변(오른쪽·아래·위)은 립 밑에 닿는 높이, 안쪽 자유단 두 변은 리브 높이
rim_top = LIP_BOT - 0.2
inner = [(x0 + PAD_RIM_W, y0 + PAD_RIM_W), (x1 - PAD_RIM_W, y0 + PAD_RIM_W),
         (x1 - PAD_RIM_W, y1 - PAD_RIM_W), (xb + PAD_RIM_W, y1 - PAD_RIM_W),
         (xb + PAD_RIM_W, BATT_Y1 + PAD_CLR + PAD_RIM_W), (x0 + PAD_RIM_W, BATT_Y1 + PAD_CLR + PAD_RIM_W)]
rim = prism("rim", ell, PAD_Z0, rim_top)
boolean(rim, prism("rim_in", inner, PAD_Z0 - 1, rim_top + 1), "DIFFERENCE")
boolean(pad, rim, "UNION")

# 안쪽 리브 격자 — 립 안쪽(LIP_IN)부터는 뚜껑 밑면 가까이까지 올려 판을 단단하게
gx0, gx1, gy0, gy1 = LIP_IN + 0.5, IN_X - LIP_IN - 0.5, LIP_IN + 0.5, IN_Y - LIP_IN - 0.5
yb = BATT_Y1 + PAD_CLR                # 위쪽 베이 시작


def divide(a, b):
    """a~b 를 PAD_RIB_PITCH 에 가깝게 나눈 경계 (양 끝 포함)."""
    n = max(1, round((b - a) / PAD_RIB_PITCH))
    return [a + (b - a) * k / n for k in range(n + 1)]


cx = divide(x0 + PAD_RIM_W, x1 - PAD_RIM_W)              # 오른쪽 열
cy = divide(y0 + PAD_RIM_W, y1 - PAD_RIM_W)
bx = divide(xb + PAD_RIM_W, x0)                          # 위쪽 베이 (배터리 위)
ribs = [(x - PAD_RIB_T / 2, x + PAD_RIB_T / 2, max(y0, gy0), min(y1, gy1)) for x in cx[1:-1]]
ribs += [(x0, min(x1, gx1), y - PAD_RIB_T / 2, y + PAD_RIB_T / 2) for y in cy[1:-1]]
ribs += [(x - PAD_RIB_T / 2, x + PAD_RIB_T / 2, yb, min(y1, gy1)) for x in bx[1:-1]]
# 자유단 두 변 (배터리 쪽)
ribs.append((x0, x0 + PAD_RIM_W, y0 + PAD_RIM_W, yb + PAD_RIM_W))
ribs.append((max(xb, gx0), x0 + PAD_RIM_W, yb, yb + PAD_RIM_W))
for i, (a, b, cc, d) in enumerate(ribs):
    boolean(pad, box(f"rib{i}", a, b, cc, d, PAD_Z0, PAD_RIB_TOP), "UNION")
# 리브가 립과 겹치는 부분은 립 밑면 높이로 깎는다
ring = box("lipzone", -1, IN_X + 1, -1, IN_Y + 1, rim_top, H + 1)
boolean(ring, box("lipzone_in", gx0, gx1, gy0, gy1, rim_top - 1, H + 2), "DIFFERENCE")
boolean(pad, ring, "DIFFERENCE")

# 밑판 칸마다 구멍 (무게·출력 시간 절약, 가장자리 PAD_HOLE_INSET 은 남겨 케이블을 누름)
cells = [(cx[i], cx[i + 1], cy[j], cy[j + 1]) for i in range(len(cx) - 1) for j in range(len(cy) - 1)]
cells += [(bx[i], bx[i + 1], yb + PAD_RIM_W, y1 - PAD_RIM_W) for i in range(len(bx) - 1)]
for i, (a, b, cc, d) in enumerate(cells):
    k = PAD_HOLE_INSET
    if b - a > 2 * k + 5 and d - cc > 2 * k + 5:
        boolean(pad, box(f"hole{i}", a + k, b - k, cc + k, d - k, PAD_Z0 - 1, H + 1), "DIFFERENCE")
# 불리언이 모서리에 남긴 길이 0 모서리 정리
bm = bmesh.new()
bm.from_mesh(pad.data)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-3)
bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-3)
bm.to_mesh(pad.data)
bm.free()

# =====================================================================
# 3) 케이스 고정 클립 — 로컬: x = 바깥벽 면에서 안쪽(+), y = 높이 (몸체 바닥 0, 뚜껑 윗면 H+LID_T),
#    z = 클립 길이. 날 끝 안쪽 모따기로 옆에서 밀어 끼운다.
# =====================================================================
g = CC_GRIP
cc_pts = [
    (-CC_T, -CC_T), (CC_REACH, -CC_T), (CC_REACH, -CC_CHAMFER * 0.3),
    (CC_REACH - CC_CHAMFER, 0.0), (0.0, 0.0),
    (0.0, g), (CC_REACH - CC_CHAMFER, g), (CC_REACH, g + CC_CHAMFER * 0.3),
    (CC_REACH, g + CC_T), (-CC_T, g + CC_T),
]
case_clip = prism("Holddown_CaseClip", cc_pts, 0.0, CC_L)


# =====================================================================
# 재질
# =====================================================================
def viewport_mat(name, rgba):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = rgba
    return mat


PARTS = (panel_clip, pad, case_clip)
for ob, col in zip(PARTS, ((0.9, 0.75, 0.2, 1), (0.3, 0.75, 0.35, 1), (0.85, 0.2, 0.6, 1))):
    ob.data.materials.append(viewport_mat(ob.name, col))

# =====================================================================
# 출력판 1장 — 누름판의 빈 모서리(배터리 자리)에 클립을 모은다
# =====================================================================
T = Matrix.Translation
pw = -pc_pts[0][0]                    # 클립 단면 왼쪽 끝 (원점 이동량)
pc_w = hx + 2.2 + pw                  # 단면 폭 (걸쇠 끝까지)
pc_h = zt0 + t + c + t                # 단면 높이
LAYOUT = [(pad, T((0, 0, -PAD_Z0)))]
for i in range(N_PANEL_CLIPS):
    col, row = i % 3, i // 3
    LAYOUT.append((panel_clip, T((5 + pw + col * (pc_w + 3), 5 + c + t + row * (pc_h + 3), 0))))
for i in range(4):
    LAYOUT.append((case_clip, T((5 + CC_T + i * (CC_REACH + CC_T + 3), 5 + 3 * (pc_h + 3) + CC_T, 0))))


def build_plate(name, layout):
    bm = bmesh.new()
    for ob, m in layout:
        tmp = bmesh.new()
        tmp.from_mesh(ob.data)
        bmesh.ops.transform(tmp, matrix=m, verts=tmp.verts)
        me = bpy.data.meshes.new("tmp")
        tmp.to_mesh(me)
        tmp.free()
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    bmesh.ops.translate(bm, verts=bm.verts, vec=(-min(xs), -min(ys), -min(zs)))
    return make_obj(name, bm, PLATES)


plate = build_plate("Holddown_Plate", LAYOUT)
plate.data.materials.append(viewport_mat("Holddown_Plate", (0.6, 0.6, 0.65, 1)))


def export_stl(ob, path):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True,
                          apply_modifiers=True, global_scale=1.0, use_scene_unit=False)
    # 선택이 안 된 채 내보내면 삼각형 0개짜리 84바이트 STL 이 조용히 생긴다
    if os.path.getsize(path) <= 84:
        raise RuntimeError(f"빈 STL 이 내보내졌습니다: {path} ({ob.name} 이 선택되지 않음)")


os.makedirs(PARTS_DIR, exist_ok=True)
bpy.context.view_layer.update()
export_stl(plate, os.path.join(OUT_DIR, "solarmaps_holddown_plate.stl"))
for ob in PARTS:
    export_stl(ob, os.path.join(PARTS_DIR, ob.name.lower() + ".stl"))
PLATES.hide_viewport = True

# =====================================================================
# 씬 표시: 레일 단면 위 클립, 케이스 위치의 누름판과 고정 클립
# =====================================================================
REF = get_collection("SolarMaps_Holddown_Ref")
rail = box("REF_Rail", 0, RAIL_W, 0, RAIL_T, -10, PC_L + 10)
boolean(rail, box("rim", 0, RIM_W, RAIL_T - 0.01, RAIL_T + RIM_H, -11, PC_L + 11), "UNION")
panel = box("REF_Panel", RIM_W + PANEL_CLR, 40, RAIL_T, RAIL_T + RIM_H, -10, PC_L + 10)
for ob in (rail, panel):
    COLL.objects.unlink(ob)
    REF.objects.link(ob)
    ob.location.x = -250
pc_show = bpy.data.objects.new("Holddown_PanelClip_show", panel_clip.data)
COLL.objects.link(pc_show)
pc_show.location.x = -250
for sx, ys in ((-1, CC_Y), (1, CC_Y)):
    for y in ys:
        ob = bpy.data.objects.new("Holddown_CaseClip_show", case_clip.data)
        COLL.objects.link(ob)
        # 로컬 (x 안쪽, y 높이, z 길이) -> 케이스 좌표
        if sx < 0:
            ob.matrix_world = Matrix(((1, 0, 0, -WALL), (0, 0, -1, y + CC_L / 2), (0, 1, 0, 0),
                                      (0, 0, 0, 1)))
        else:
            ob.matrix_world = Matrix(((-1, 0, 0, IN_X + WALL), (0, 0, 1, y - CC_L / 2), (0, 1, 0, 0),
                                      (0, 0, 0, 1)))
panel_clip.hide_viewport = case_clip.hide_viewport = True
# 참고용 케이스 몸체 (출력 안 함)
body_stl = os.path.join(OUT_DIR, "solarmaps_case_body.stl")
if os.path.exists(body_stl):
    bpy.ops.wm.stl_import(filepath=body_stl)
    ref_body = bpy.context.selected_objects[0]
    ref_body.name = "REF_CaseBody"
    for cl in list(ref_body.users_collection):
        cl.objects.unlink(ref_body)
    REF.objects.link(ref_body)

print("PLATE", tuple(round(v, 1) for v in plate.dimensions))
print("PANEL_CLIP", round(pc_w, 1), round(pc_h, 1), "PRESS_Z", zp, "TOP", zt0)
