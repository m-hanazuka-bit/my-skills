"""Blender で 3D パートをビート同期レンダリングする（ベーステンプレート）。

  blender -b -P blender_scene.py -- --plan storyboard.json --timeline work/timeline.json --out work/3d

- storyboard.json の scene3d を読み、主役オブジェクト・カメラ・ライトを組む。
- timeline.json のキック/インパクト/ドロップ時刻にスケールパンチ・発光・カメラシェイクを打つ。
- 背景は透過 PNG で書き出す（ファイル名は動画全体のフレーム番号: 00123.png）。
  → HTML 側がそのフレームを <img> で重ねるので 2D と 1 枚の画として合成できる。
- 2D→3D のつなぎ目は「ドリーズーム」：開始時は超望遠(=ほぼ平面に見える)で 2D の形と重ね、
  拍に合わせて広角へ寄せて奥行きを出す。終わりは主役にカメラが突っ込んで画面を埋め、2D に渡す。

主役を作品ごとに作り込むときは build_subject() を書き換える（または custom で .py を渡す）。
Blender 4.x / 5.x 想定。Brender(bl_*) MCP が繋がっているなら bl_execute でも同じコードが使える。
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--timeline", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--preview", action="store_true", help="解像度50%・6フレームおきで確認用")
    ap.add_argument("--percent", type=int, default=100, help="解像度の%%（下書きは 50）")
    ap.add_argument("--engine", choices=["eevee", "cycles"], default="eevee",
                    help="GPU/OpenGL の無いサーバーでは cycles（CPU）を使う")
    return ap.parse_args(argv)


def hex_rgba(h, a=1.0):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (*lin, a)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def set_engine(scene, want):
    if want == "cycles":
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.use_denoising = True
        return "CYCLES"
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = eng
            return eng
        except TypeError:
            continue
    scene.render.engine = "CYCLES"
    return "CYCLES"


def material(cfg, pal):
    m = bpy.data.materials.new("Hero")
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = hex_rgba(cfg.get("color", pal.get("primary", "#3aa0ff")))
    b.inputs["Metallic"].default_value = cfg.get("metallic", 0.3)
    b.inputs["Roughness"].default_value = cfg.get("roughness", 0.25)
    if "Transmission Weight" in b.inputs and cfg.get("glass"):
        b.inputs["Transmission Weight"].default_value = 1.0
    em_key = "Emission Color" if "Emission Color" in b.inputs else "Emission"
    b.inputs[em_key].default_value = hex_rgba(cfg.get("emission", pal.get("accent", "#ffffff")))
    b.inputs["Emission Strength"].default_value = 0.0
    return m, b


def build_subject(sub, pal, base_dir="."):
    """(主役, 共通マテリアルを使うか, キックで光らせる BSDF のリスト) を返す。作品ごとにここを作り込む。"""
    rel = lambda p: p if os.path.isabs(p) else os.path.join(base_dir, p)
    t = sub.get("type", "primitive")
    if t == "text":
        bpy.ops.object.text_add()
        o = bpy.context.object
        o.data.body = sub.get("text", "TEXT")
        if sub.get("font"):
            o.data.font = bpy.data.fonts.load(rel(sub["font"]))  # 日本語は必ず和文フォントを指定
        o.data.align_x = "CENTER"
        o.data.align_y = "CENTER"
        o.data.extrude = sub.get("extrude", 0.12)
        o.data.bevel_depth = sub.get("bevel", 0.015)
        o.data.size = sub.get("size", 1.2)
        o.rotation_euler = (math.radians(90), 0, 0)
    elif t == "import":
        path = rel(sub["path"])
        ext = os.path.splitext(path)[1].lower()
        if ext in (".glb", ".gltf"):
            bpy.ops.import_scene.gltf(filepath=path)
        elif ext == ".fbx":
            bpy.ops.import_scene.fbx(filepath=path)
        elif ext == ".obj":
            bpy.ops.wm.obj_import(filepath=path)
        objs = [o for o in bpy.context.selected_objects if o.type == "MESH"]
        bpy.ops.object.empty_add()
        o = bpy.context.object
        for c in objs:
            c.parent = o
        # 最大寸法を 2m に正規化
        dims = max(max(c.dimensions) for c in objs) if objs else 1
        o.scale = [2.0 / dims] * 3
        return o, False, []
    elif t == "custom":
        # 任意の bpy スクリプトを実行し、変数 hero に主役を入れてもらう
        ns = {"bpy": bpy, "palette": pal, "math": math}
        exec(open(rel(sub["script"])).read(), ns)
        return ns["hero"], ns.get("use_hero_material", False), ns.get("glow_nodes", [])
    else:
        kind = sub.get("primitive", "torus")
        ops = {
            "torus": lambda: bpy.ops.mesh.primitive_torus_add(major_radius=1, minor_radius=0.35),
            "sphere": lambda: bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=64, ring_count=32),
            "cube": lambda: bpy.ops.mesh.primitive_cube_add(size=1.4),
            "ico": lambda: bpy.ops.mesh.primitive_ico_sphere_add(radius=1, subdivisions=1),
            "monkey": lambda: bpy.ops.mesh.primitive_monkey_add(size=1.6),
            "cylinder": lambda: bpy.ops.mesh.primitive_cylinder_add(radius=0.8, depth=1.6, vertices=64),
        }
        ops.get(kind, ops["torus"])()
        o = bpy.context.object
        if kind == "cube":
            bev = o.modifiers.new("bevel", "BEVEL")
            bev.width, bev.segments = 0.12, 4
        bpy.ops.object.shade_smooth()
    return o, True, []


def track(obj, target):
    c = obj.constraints.new("TRACK_TO")
    c.target = target
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"


def fit_to_frame(hero, size):
    """主役のバウンディングボックス中心を原点に移し、最大寸法を size(m) にそろえる。
    これでどんな主役でもカメラ設定（distance/lens）を共通で使える。"""
    bpy.context.view_layer.update()
    pts = []
    for o in [hero] + list(hero.children_recursive):
        if o.type in ("MESH", "FONT", "CURVE"):
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    if not pts:
        return
    mn = Vector([min(p[i] for p in pts) for i in range(3)])
    mx = Vector([max(p[i] for p in pts) for i in range(3)])
    k = size / max(mx - mn)
    hero.location = (hero.location - (mn + mx) / 2) * k
    hero.scale = hero.scale * k


def main():
    a = args()
    plan = json.load(open(a.plan))
    tl = json.load(open(a.timeline))
    cfg = plan.get("scene3d", {})
    pal = plan.get("palette", {})
    fps = tl.get("fps", 30)
    spb = tl["seconds_per_beat"]
    t0 = cfg.get("start_bar", 0) * 4 * spb
    t1 = cfg.get("end_bar", tl["bars"]) * 4 * spb
    f0, f1 = round(t0 * fps), round(t1 * fps) - 1
    F = lambda t: round(t * fps)  # 動画全体のフレーム番号

    reset()
    sc = bpy.context.scene
    eng = set_engine(sc, a.engine)
    w, h = tl.get("size", [1920, 1080])
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 50 if a.preview else a.percent
    sc.render.fps = fps
    sc.frame_start, sc.frame_end = f0, f1
    sc.frame_step = 6 if a.preview else 1
    sc.render.film_transparent = cfg.get("transparent", True)
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.use_motion_blur = True
    if eng.startswith("BLENDER_EEVEE"):
        sc.eevee.taa_render_samples = a.samples
    else:
        sc.cycles.samples = a.samples
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass

    world = bpy.data.worlds.new("W")
    sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = hex_rgba(pal.get("bg", "#0b0f1a"))
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.4

    # ---- 主役
    hero, use_mat, glow_nodes = build_subject(cfg.get("subject", {}), pal, os.path.dirname(os.path.abspath(a.plan)))
    if use_mat and hero.type in ("MESH", "FONT"):
        mat, bsdf = material(cfg.get("material", {}), pal)
        hero.data.materials.clear()
        hero.data.materials.append(mat)
        glow_nodes = [bsdf]
    fit_to_frame(hero, cfg.get("fit", 2.6))
    pivot = bpy.data.objects.new("Pivot", None)
    sc.collection.objects.link(pivot)
    hero.parent = pivot
    base_scale = pivot.scale.copy()

    # ---- ライト（キー＋リム＋フィル）。色はパレットから
    def light(name, kind, loc, energy, color):
        d = bpy.data.lights.new(name, kind)
        d.energy = energy
        d.color = hex_rgba(color)[:3]
        if kind == "AREA":
            d.size = 3
        o = bpy.data.objects.new(name, d)
        o.location = loc
        sc.collection.objects.link(o)
        track(o, pivot)
        return o

    light("Key", "AREA", (3, -4, 4), 900, pal.get("light", "#ffffff"))
    rim = light("Rim", "AREA", (-3, 3, 2.5), 1400, pal.get("accent", "#66ccff"))
    light("Fill", "AREA", (-4, -3, 0.5), 200, pal.get("primary", "#3aa0ff"))

    # ---- カメラ
    cam_d = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    rig = bpy.data.objects.new("CamRig", None)  # 回転でオービット
    sc.collection.objects.link(rig)
    cam.parent = rig
    track(cam, pivot)
    cam_cfg = cfg.get("camera", {})
    move = cam_cfg.get("move", "orbit")
    base_lens = cam_cfg.get("lens", 50)
    base_dist = cam_cfg.get("distance", 7.0)
    drop = tl.get("drop_time") or (t0 + t1) / 2

    def place(frame, lens, dist, height=0.6):
        cam_d.lens = lens
        cam.location = (0, -dist, height * dist / base_dist)
        cam_d.keyframe_insert("lens", frame=frame)
        cam.keyframe_insert("location", frame=frame)

    # 2D→3D：望遠(平面的)→標準へのドリーズーム。被写体サイズを保つため距離を lens に比例させる
    intro_tele = cam_cfg.get("handoff_in", True)
    reveal = min(t1, t0 + 4 * spb)  # 1小節で立体化
    if intro_tele:
        place(F(t0), base_lens * 4, base_dist * 4, 0.0)
    place(F(reveal), base_lens, base_dist)
    if move == "push_in":
        place(F(t1 - 2 * spb), base_lens, base_dist * 0.75)
    # 3D→2D：最後の2拍で主役に突っ込み画面を埋める
    if cam_cfg.get("handoff_out", True):
        place(F(t1 - 2 * spb), base_lens, base_dist * (0.75 if move == "push_in" else 1.0))
        place(F(t1), base_lens * 0.8, base_dist * 0.18)

    # オービット：ドロップ以降は回転速度を上げる
    spin_pre = math.radians(cam_cfg.get("deg_per_beat", 8))
    spin_post = spin_pre * cam_cfg.get("drop_speedup", 3)
    ang = 0.0
    beat_times = [t for t in tl["beats"] if t0 <= t <= t1] + [t1]
    prev = t0
    rig.rotation_euler = (0, 0, 0)
    rig.keyframe_insert("rotation_euler", frame=F(t0))
    for bt in beat_times:
        dt = (bt - prev) / spb
        ang += dt * (spin_post if bt > drop else spin_pre) * (1 if move != "static" else 0)
        rig.rotation_euler = (0, 0, ang)
        rig.keyframe_insert("rotation_euler", frame=F(bt))
        prev = bt

    # ---- ビート反応
    punch = cfg.get("punch", 0.08)
    for k in tl.get("kicks", []):
        if not (t0 <= k < t1):
            continue
        pivot.scale = base_scale * (1 + punch * (1.6 if k >= drop else 1))
        pivot.keyframe_insert("scale", frame=F(k))
        pivot.scale = base_scale
        pivot.keyframe_insert("scale", frame=F(k) + max(3, round(spb * fps * 0.5)))
        for b in glow_nodes:
            s = b.inputs["Emission Strength"]
            s.default_value = cfg.get("glow", 3.0)
            s.keyframe_insert("default_value", frame=F(k))
            s.default_value = 0.0
            s.keyframe_insert("default_value", frame=F(k) + round(spb * fps * 0.7))
    # 主役自体の回転（スネアでカクッと回す）
    rot = 0.0
    pivot.keyframe_insert("rotation_euler", frame=F(t0))
    for s_ in tl.get("snares", []):
        if t0 <= s_ < t1:
            pivot.keyframe_insert("rotation_euler", frame=F(s_))
            rot += math.radians(cfg.get("snare_turn", 30))
            pivot.rotation_euler = (0, 0, rot)
            pivot.keyframe_insert("rotation_euler", frame=F(s_) + 4)
    # インパクトでカメラシェイク＋リムライト点滅
    for imp in tl.get("impacts", []):
        if not (t0 <= imp < t1):
            continue
        for i, amp in enumerate((0.12, -0.09, 0.05, -0.02, 0.0)):
            cam.delta_location = (amp, 0, amp * 0.5)
            cam.keyframe_insert("delta_location", frame=F(imp) + i * 2)
        rim.data.energy = 4000
        rim.data.keyframe_insert("energy", frame=F(imp))
        rim.data.energy = 1400
        rim.data.keyframe_insert("energy", frame=F(imp) + 10)

    # スケール・シェイクは素早く戻す（BEZIER→EXPO 相当で弾ませる）
    for ob in (pivot, cam, rig):
        ad = ob.animation_data
        if not ad or not ad.action:
            continue
        for fc in getattr(ad.action, "fcurves", []):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR" if ob is rig else "BEZIER"
                kp.easing = "EASE_OUT"

    os.makedirs(a.out, exist_ok=True)
    sc.render.filepath = os.path.join(os.path.abspath(a.out), "#####")
    if cfg.get("save_blend"):
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.path.abspath(a.out), "scene.blend"))
    print(f"[beat-motion] render {eng} frames {f0}-{f1} -> {a.out}")
    bpy.ops.render.render(animation=True)


main()
