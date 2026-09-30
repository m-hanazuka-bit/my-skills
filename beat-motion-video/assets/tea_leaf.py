# scene3d.subject.type = "custom" の例：「一芯二葉」（芽1つ＋葉2枚）と水滴。
# blender_scene.py から exec され、変数 hero に主役（親 Empty）を入れて返す。
# 使える変数: bpy, math, palette
import bmesh


def hex_lin(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4) for x in c) + (1.0,)


def leaf_mesh(name, length=2.0, width=0.8, curl=0.25, teeth=18):
    """葉脈に沿って少し反った、縁がギザギザの葉"""
    bm = bmesh.new()
    rows, cols = 40, 12
    grid = []
    for i in range(rows + 1):
        u = i / rows                                  # 0=付け根 1=先端
        half = width * math.sin(math.pi * u ** 0.8) * (1 - 0.15 * u)
        serr = 1 + 0.06 * abs(math.sin(u * teeth * math.pi))  # 鋸歯
        row = []
        for j in range(cols + 1):
            v = (j / cols) * 2 - 1                    # -1..1（左右）
            x = v * half * serr
            y = u * length
            z = curl * v * v * half + 0.25 * u * u    # 中央脈で折れ、先端が反る
            row.append(bm.verts.new((x, y, z - 0.08 * abs(v) ** 0.5 * half)))
        grid.append(row)
    for i in range(rows):
        for j in range(cols):
            bm.faces.new((grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    sol = ob.modifiers.new("thick", "SOLIDIFY")
    sol.thickness = 0.015
    sub = ob.modifiers.new("smooth", "SUBSURF")
    sub.levels = sub.render_levels = 1
    for p in me.polygons:
        p.use_smooth = True
    return ob


def leaf_material():
    m = bpy.data.materials.new("TeaLeaf")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = hex_lin(palette.get("primary", "#3f7d2c"))
    b.inputs["Roughness"].default_value = 0.3
    if "Subsurface Weight" in b.inputs:
        b.inputs["Subsurface Weight"].default_value = 0.15    # 逆光で透ける感じ
    if "Coat Weight" in b.inputs:
        b.inputs["Coat Weight"].default_value = 0.4           # 表面のツヤ
    em = "Emission Color" if "Emission Color" in b.inputs else "Emission"
    b.inputs[em].default_value = hex_lin(palette.get("accent", "#c9f27a"))
    b.inputs["Emission Strength"].default_value = 0.0
    return m


def water_material():
    m = bpy.data.materials.new("Water")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.0
    b.inputs["IOR"].default_value = 1.33
    if "Transmission Weight" in b.inputs:
        b.inputs["Transmission Weight"].default_value = 1.0
    return m


hero = bpy.data.objects.new("TeaSprig", None)
bpy.context.scene.collection.objects.link(hero)
mat = leaf_material()
# 芽（一芯）＋葉2枚（二葉）
parts = [
    ("Bud", 1.3, 0.16, 0.6, (0, 0, 0.0), 0),
    ("Leaf1", 2.0, 0.42, 0.35, (0.05, 0, -0.5), -50),
    ("Leaf2", 2.4, 0.5, 0.3, (-0.05, 0, -1.1), 55),
]
for name, L, W, curl, loc, tilt in parts:
    lf = leaf_mesh(name, L, W, curl)
    lf.data.materials.append(mat)
    lf.location = loc
    lf.rotation_euler = (math.radians(80), math.radians(tilt), 0)   # +Y(葉先)を上へ
    lf.parent = hero

# 水滴
wm = water_material()
for i, (x, y, z, r) in enumerate([(0.12, -0.25, 1.0, 0.06), (-0.6, -0.3, 0.4, 0.08), (0.8, -0.3, 0.2, 0.05)]):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=(x, y, z), segments=32, ring_count=16)
    d = bpy.context.object
    d.scale.z = 0.8
    bpy.ops.object.shade_smooth()
    d.data.materials.append(wm)
    d.parent = hero

use_hero_material = False                                   # 葉は自前マテリアルを使う
glow_nodes = [mat.node_tree.nodes["Principled BSDF"]]        # キックで葉をほのかに発光させる
