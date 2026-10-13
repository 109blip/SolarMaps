"""Pi 노드 케이스 조립 가이드용 그림 렌더 (Blender 5.x).

modeling/solarmaps_case.blend (또는 build_case.py 실행 후) 상태에서 실행한다.
결과: modeling/case_guide/_img/*.png (투명 배경, Workbench) + anchors.json (설명선 끝점의 화면 좌표).
부품·포트·케이블은 가이드용 개략 형상이다 (실제 포트 위치는 기기 인쇄 표시 기준).
"""
import json
import math
import os

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else \
    r"C:\Users\이민기\Desktop\개발\EURIF\SolarMaps\modeling\case_guide"
IMG_DIR = os.path.join(HERE, "_img")
CASE_PY = os.path.join(os.path.dirname(HERE), "build_case.py")

C = {"__file__": CASE_PY}
exec(open(CASE_PY, encoding="utf-8").read().split("FONT_PATHS")[0], C)
WALL, H, IN_X, IN_Y, LID_T = C["WALL"], C["H"], C["IN_X"], C["IN_Y"], C["LID_T"]
NOTCH_X, TONGUE_Z = C["NOTCH_X"], C["TONGUE_Z"]
NX = sum(NOTCH_X) / 2

T = Matrix.Translation
R = Matrix.Rotation
O = bpy.data.objects
SC = bpy.context.scene

# ---- 렌더 설정 ----
try:
    SC.render.engine = "BLENDER_WORKBENCH"
except TypeError:
    pass
SC.render.film_transparent = True
SC.render.image_settings.file_format = "PNG"
SC.render.image_settings.color_mode = "RGBA"
sh = SC.display.shading
sh.light = "STUDIO"
sh.color_type = "MATERIAL"
sh.show_object_outline = True
sh.object_outline_color = (0, 0, 0)
sh.show_cavity = True
sh.cavity_type = "BOTH"
SC.display.render_aa = "16"
SC.view_settings.view_transform = "Standard"

GUIDE = bpy.data.collections.get("Case_Guide") or bpy.data.collections.new("Case_Guide")
if GUIDE.name not in SC.collection.children:
    SC.collection.children.link(GUIDE)

cam_data = bpy.data.cameras.get("GuideCam") or bpy.data.cameras.new("GuideCam")
cam = O.get("GuideCam") or bpy.data.objects.new("GuideCam", cam_data)
if cam.name not in GUIDE.objects:
    GUIDE.objects.link(cam)
cam_data.clip_start, cam_data.clip_end = 1, 10000
SC.camera = cam


def mat(name, rgba):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = rgba
    return m


M_BATT = mat("Guide_Battery", (0.28, 0.28, 0.3, 1))
M_FNB = mat("Guide_FNB58", (0.2, 0.45, 0.8, 1))
M_PLUG = mat("Guide_Plug", (0.75, 0.75, 0.78, 1))
M_PI = mat("Guide_Pi", (0.25, 0.6, 0.35, 1))
M_PORT = mat("Guide_Port", (0.05, 0.05, 0.05, 1))
CABLE_COLORS = {1: (1.0, 0.55, 0.0, 1), 2: (0.85, 0.1, 0.1, 1), 3: (0.1, 0.7, 0.2, 1), 4: (0.55, 0.2, 0.8, 1),
                5: (0.45, 0.45, 0.45, 1)}                  # 5 = 배터리 내장 케이블 (사용 안 함, 회색)

ANCHORS = {}
CUR = []


def clear_guide():
    for ob in list(GUIDE.objects):
        if ob is cam:
            continue
        data = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if isinstance(data, bpy.types.Curve):
            bpy.data.curves.remove(data)
        elif isinstance(data, bpy.types.Mesh) and data.users == 0:
            bpy.data.meshes.remove(data)


def inst(src, m):
    ob = bpy.data.objects.new(src.name + "_g", src.data)
    GUIDE.objects.link(ob)
    ob.matrix_world = m
    return ob


def gbox(name, x0, x1, y0, y1, z0, z1, material):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = x1 if v.co.x > 0 else x0
        v.co.y = y1 if v.co.y > 0 else y0
        v.co.z = z1 if v.co.z > 0 else z0
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material)
    ob = bpy.data.objects.new(name, me)
    GUIDE.objects.link(ob)
    return ob


def cable(n, pts):
    cu = bpy.data.curves.new(f"cable{n}", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 1.7
    cu.bevel_resolution = 4
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p, co in zip(sp.points, pts):
        p.co = (*co, 1.0)
    cu.materials.append(mat(f"Guide_Cable{n}", CABLE_COLORS[n]))
    ob = bpy.data.objects.new(f"cable{n}", cu)
    GUIDE.objects.link(ob)
    return ob


def set_cam(loc, target, lens=50.0, ortho=None):
    cam.location = loc
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    if ortho:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = ortho
    else:
        cam_data.type = "PERSP"
        cam_data.lens = lens
    bpy.context.view_layer.update()


def top_cam(cx, cy, scale):
    cam.location = (cx, cy, 400)
    cam.rotation_euler = (0, 0, 0)
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = scale
    bpy.context.view_layer.update()


def callout(key, loc):
    """설명선이 가리킬 점 — 화면 정규화 좌표 (0~1, 좌하단 원점) 로 기록."""
    CUR.append((key, Vector(loc)))       # 투영은 render() 에서 해상도(화면비)를 정한 뒤에


def show_only(objs):
    keep = set(objs) | {cam} | set(GUIDE.objects)
    for ob in SC.objects:
        ob.hide_render = ob not in keep


def render(name, res=(1600, 1200)):
    SC.render.resolution_x, SC.render.resolution_y = res
    SC.render.resolution_percentage = 100
    pts = []
    for key, co in CUR:
        u, v, _ = world_to_camera_view(SC, cam, co)
        pts.append((key, round(u, 4), round(v, 4)))
    ANCHORS[name] = {"res": list(res), "points": pts}
    CUR.clear()
    SC.render.filepath = os.path.join(IMG_DIR, name + ".png")
    bpy.ops.render.render(write_still=True)


# ---- 개략 부품 (build_case.py 의 BATT_* 치수와 같음) ----
BATT_W, BATT_L, BATT_T = C["BATT_W"], C["BATT_L"], C["BATT_T"]    # Anker Zolo A110E
BATT_X0, BATT_Y0, BATT_Z0 = 1.0, 1.0, 2.0                          # 바닥·벽에서 살짝 띄운 위치
PORT_Y_BATT = BATT_Y0 + BATT_L                                     # 포트는 +Y 짧은 면 (실물 사진 확인)
BATT_PORT_Z = BATT_Z0 + BATT_T / 2                                 # 포트 높이는 두께 가운데 (사진으로 대략 추정)
# 뒤에서 본 왼쪽→오른쪽: USB-A, USB-C, 내장 USB-C 케이블 (X 위치는 사진에서 대략 추정, ±3 mm)
BATT_A, BATT_C, BATT_CABLE = (50.0, PORT_Y_BATT), (30.0, PORT_Y_BATT), (13.0, PORT_Y_BATT)
FNB_X0, FNB_X1 = 98.0, 140.0
FNB_CIN, FNB_COUT = (FNB_X0, 92.0), (FNB_X0, 125.0)
FNB_PC = (FNB_X1, 100.0)
PI_Y = 39.0
PI_PWR, PI_USB = (97.5, PI_Y), (110.0, PI_Y)


def parts():
    gbox("batt", BATT_X0, BATT_X0 + BATT_W, BATT_Y0, PORT_Y_BATT, BATT_Z0, BATT_Z0 + BATT_T, M_BATT)
    gbox("fnb", FNB_X0, FNB_X1, 77, 147, 2, 15, M_FNB)
    gbox("plug", 113, 125, 64.5, 77, 5, 9.5, M_PLUG)
    gbox("pi", 79.5, 158.5, 1, PI_Y, 2, 17, M_PI)
    for x, y in (BATT_C, BATT_A, BATT_CABLE):
        gbox("port", x - 4.5, x + 4.5, y - 0.5, y + 1.0, BATT_PORT_Z - 2, BATT_PORT_Z + 2, M_PORT)
    for x, y in (FNB_CIN, FNB_COUT):
        gbox("port", x - 1.0, x + 0.5, y - 4.5, y + 4.5, 6, 10, M_PORT)
    gbox("port", FNB_PC[0] - 0.5, FNB_PC[0] + 1.0, FNB_PC[1] - 4, FNB_PC[1] + 4, 6, 9, M_PORT)
    for x, y in (PI_PWR, PI_USB):
        gbox("port", x - 4, x + 4, y - 0.5, y + 1.0, 7, 10, M_PORT)


# 권장 케이블 경로 (① 태양광→FNB58 입력, ② FNB58 출력→배터리, ③ FNB58 PC→Pi USB, ④ 배터리→Pi PWR)
CABLES = {
    1: [(NX, 215, 14), (NX, IN_Y + 2, 12), (NX, 168, 12), (NX, 140, 8), (NX, 95, 8), (FNB_CIN[0] - 1, FNB_CIN[1], 8)],
    2: [(FNB_COUT[0] - 1, FNB_COUT[1], 8), (93, FNB_COUT[1], 8), (93, 158, 10), (80, 160, 10), (30, 160, 12),
        (BATT_C[0], 156, 14), (BATT_C[0], BATT_C[1] + 1, BATT_PORT_Z)],
    3: [(FNB_PC[0] + 1, FNB_PC[1], 8), (151, FNB_PC[1], 8), (151, 55, 8), (118, 50, 8), (PI_USB[0], 46, 8),
        (PI_USB[0], PI_USB[1] + 1, 8)],
    4: [(BATT_A[0], BATT_A[1] + 1, BATT_PORT_Z), (BATT_A[0], 172, 9), (80, 172, 5), (80, 60, 5), (90, 52, 6),
        (PI_PWR[0], 46, 8), (PI_PWR[0], PI_PWR[1] + 1, 8)],
    # 내장 케이블 (C타입, 이 설계에서는 사용 안 함): 짧은 면에서 나와 케이블 베이 안쪽으로 눕힌다
    5: [(BATT_CABLE[0], BATT_CABLE[1] + 1, BATT_PORT_Z), (BATT_CABLE[0], 160, 4), (10, 176, 4)],
}


def cables():
    for n, pts in CABLES.items():
        cable(n, pts)


os.makedirs(IMG_DIR, exist_ok=True)
BODY, LID = O["Case_Body"], O["Case_Lid"]
# 두 메시 모두 조립 위치 좌표로 모델링돼 있어서 단위 행렬 = 조립 상태 (오브젝트 위치는 무시)

# 1. 전체 (분해)
clear_guide()
inst(BODY, Matrix())
inst(LID, T((-10, 150, 110)))
parts()
cables()
show_only([])
set_cam((300, -300, 330), (80, 90, 45), lens=38)
callout("lid", (IN_X * 0.75 - 10, 150 - WALL, H + LID_T + 110))
callout("body", (IN_X * 0.8, -WALL, 10))
callout("notch", (NX, IN_Y + WALL, H - 2))
callout("cable", (NX, 210, 14))
render("c01_overview")

# 2. 출력 방향
clear_guide()
inst(BODY, Matrix())
LID_PRINT = T((IN_X + 2 * WALL + 20, 0, 0)) @ T((0, IN_Y, H + LID_T)) @ R(math.pi, 4, "X")
inst(LID, LID_PRINT)
show_only([])
set_cam((175, -300, 330), (175, 91, 0), lens=40)
callout("body", (IN_X / 2, -WALL, H))
callout("lid", LID_PRINT @ Vector((IN_X / 2, 0, H - C["LIP_DEPTH"])))
render("c02_print", (1800, 1100))

# 3. 빈 몸체 위에서 (구역)
clear_guide()
inst(BODY, Matrix())
show_only([])
set_cam((80, -150, 300), (80, 88, 0), lens=45)
callout("batt", (37, 60, 2))
callout("fnb", (119, 112, 2))
callout("pi", (119, 20, 2))
callout("notch", (NX, IN_Y + WALL / 2, 12))
callout("bay", (125, 166, 2))
callout("lch", (NX, 100, 2))
callout("rch", (151, 100, 2))
render("c03_zones", (1400, 1500))

# 4. 부품 배치
clear_guide()
inst(BODY, Matrix())
parts()
show_only([])
top_cam(IN_X / 2, IN_Y / 2 + 8, 235)
callout("batt_ports", (37, PORT_Y_BATT, 12))
callout("plug", (119, 68, 10))
callout("fnb_left", (FNB_X0, 108, 12))
callout("fnb_pc", (FNB_PC[0], FNB_PC[1], 12))
callout("pi_ports", (104, PI_Y, 12))
callout("batt", (37, 70, 17))
callout("fnb", (119, 125, 15))
callout("pi", (140, 20, 17))
render("c04_parts", (1400, 1500))

# 5. 배선
clear_guide()
inst(BODY, Matrix())
parts()
cables()
show_only([])
top_cam(IN_X / 2, IN_Y / 2 + 16, 250)
callout("c1", (NX, 118, 8))
callout("c2", (60, 160, 10))
callout("c3", (151, 78, 8))
callout("c4", (80, 88, 5))
callout("panel", (NX, 208, 14))
callout("builtin", (BATT_CABLE[0], 160, 4))
render("c05_wiring", (1400, 1600))

# 6. 뚜껑 아래면
clear_guide()
FLIP = T((0, IN_Y, H + LID_T)) @ R(math.pi, 4, "X")   # 뒤집어 든 모습 (아래면이 위로)
inst(LID, FLIP)
show_only([])
set_cam((80, -170, 190), (80, 85, 0), lens=45)
callout("lip", FLIP @ Vector((30, C["FIT"], H - C["LIP_DEPTH"])))
callout("tongue", FLIP @ Vector((NX, IN_Y, TONGUE_Z)))
render("c06_lid_under", (1600, 1100))

# 7. 뚜껑 닫기 — 뒤에서, 텅이 노치 위로
clear_guide()
inst(BODY, Matrix())
inst(LID, T((0, 0, 40)))
parts()
cables()
show_only([])
set_cam((-20, 430, 75), (80, 150, 30), lens=35)
callout("tongue", (NX, IN_Y + WALL / 2, TONGUE_Z + 40))
callout("notch", (NX, IN_Y + WALL, C["NOTCH_Z"] + 1))
callout("cable", (NX, 205, 14))
render("c07_close", (1600, 1150))

clear_guide()
for ob in SC.objects:
    ob.hide_render = False
with open(os.path.join(IMG_DIR, "anchors.json"), "w", encoding="utf-8") as fh:
    json.dump(ANCHORS, fh, ensure_ascii=False, indent=1)
print("rendered", sorted(os.listdir(IMG_DIR)))
