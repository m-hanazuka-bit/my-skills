#!/usr/bin/env python3
"""layout.json → Illustrator で開ける編集用 SVG ＋ AI保存.jsx ＋ 縁取り文字変更.jsx ＋ お読みください.txt

座標・サイズはすべて mm（仕上がり左上が原点、y は下向き）。SVG 内部は 1 単位 = 1pt で書き出すので、
Illustrator が SVG の px を pt として読んでも実寸がずれない。

usage:
  python3 build_pop.py build layout.json --out out/シャインマスカット_B5横
  python3 build_pop.py pack  out/シャインマスカット_B5横        # プレビュー PNG を入れてから zip にする
"""
import argparse
import base64
import io
import json
import math
import os
import re
import struct
import subprocess
import sys
import zipfile
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
K = 72 / 25.4  # mm → pt
ASCENT = 0.88  # 行の上端からベースラインまで（em 比）。和文太字書体のおおよその値

SIZES = {
    "B5横": (257, 182), "POP1": (257, 182),
    "A3縦": (297, 420),
    "300x864横": (864, 300), "長尺横": (864, 300),
    "300x864縦": (300, 864), "長尺縦": (300, 864),
}

FONTS = json.load(open(os.path.join(HERE, "fonts.json"), encoding="utf-8"))


# ---------------------------------------------------------------- 画像

def image_size(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            m = data[i + 1]
            if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    raise ValueError("PNG/JPEG のサイズが読めません")


def load_image(path, place_w_mm, max_dpi=350):
    """PNG/JPEG はそのまま、それ以外（webp 等）は PNG に変換。大きすぎる画像は max_dpi まで縮小。"""
    data = open(path, "rb").read()
    is_png, is_jpg = data[:8] == b"\x89PNG\r\n\x1a\n", data[:2] == b"\xff\xd8"
    try:
        from PIL import Image  # あれば変換・縮小に使う
        im = Image.open(io.BytesIO(data))
        limit = int(place_w_mm / 25.4 * max_dpi)
        if not (is_png or is_jpg) or im.width > limit * 1.3:
            if im.width > limit:
                im = im.resize((limit, round(im.height * limit / im.width)), Image.LANCZOS)
            buf = io.BytesIO()
            if im.mode in ("RGBA", "LA", "P") or not is_jpg:
                im.save(buf, "PNG", optimize=True)
                data, mime = buf.getvalue(), "image/png"
            else:
                im.convert("RGB").save(buf, "JPEG", quality=92)
                data, mime = buf.getvalue(), "image/jpeg"
            return data, mime, im.size
    except ImportError:
        if not (is_png or is_jpg):
            out = path + ".conv.png"
            subprocess.run(["node", os.path.join(HERE, "img_convert.mjs"), path, out], check=True)
            data = open(out, "rb").read()
            is_png = True
    mime = "image/png" if data[:4] == b"\x89PNG" else "image/jpeg"
    return data, mime, image_size(data)


# ---------------------------------------------------------------- SVG 部品

class B:
    def __init__(self, spec, base_dir):
        self.base = base_dir
        size = spec["size"]
        if isinstance(size, str):
            if size not in SIZES:
                sys.exit(f"size は {list(SIZES)} か {{\"w\":mm,\"h\":mm}}: {size}")
            self.tw, self.th = SIZES[size]
        else:
            self.tw, self.th = size["w"], size["h"]
        self.bleed = float(spec.get("bleed", 0))
        self.defs = []
        self.n = 0
        self.texts = []   # jsx 用：テキストの id・書体・最大長
        self.used_fonts = set()

    # 座標変換
    def X(self, v): return round((v + self.bleed) * K, 3)
    def Y(self, v): return round((v + self.bleed) * K, 3)
    def L(self, v): return round(v * K, 3)

    def nid(self, p):
        self.n += 1
        return f"{p}{self.n:03d}"

    def paint(self, v, bbox=None):
        if v is None or v == "none":
            return "none"
        if isinstance(v, str):
            return v
        gid = self.nid("g")
        stops = "".join(
            f'<stop offset="{o}" stop-color="{c}"' + (f' stop-opacity="{a}"' if a != 1 else "") + "/>"
            for o, c, a in ((s[0], s[1], s[2] if len(s) > 2 else 1) for s in v["stops"]))
        if v.get("type", "linear") == "radial":
            self.defs.append(f'<radialGradient id="{gid}" cx="0.5" cy="0.5" r="0.5">{stops}</radialGradient>')
        else:
            a = math.radians(v.get("angle", 90))
            dx, dy = math.cos(a) / 2, math.sin(a) / 2
            self.defs.append(
                f'<linearGradient id="{gid}" x1="{0.5 - dx:.4f}" y1="{0.5 - dy:.4f}" x2="{0.5 + dx:.4f}" y2="{0.5 + dy:.4f}">{stops}</linearGradient>')
        return f"url(#{gid})"

    def style(self, e, fill_default="none"):
        s = f' fill="{self.paint(e.get("fill", fill_default))}"'
        if e.get("stroke") and e.get("stroke") != "none":
            s += f' stroke="{e["stroke"]}" stroke-width="{self.L(e.get("strokeWidth", 0.5))}" stroke-linejoin="round"'
            if e.get("dash"):
                s += f' stroke-dasharray="{" ".join(str(self.L(d)) for d in e["dash"])}" stroke-linecap="round"'
        if e.get("opacity", 1) != 1:
            s += f' opacity="{e["opacity"]}"'
        return s

    def rot(self, e, cx, cy):
        r = e.get("rotate", 0)
        return f' transform="rotate({r} {self.X(cx)} {self.Y(cy)})"' if r else ""

    # ------------------------------------------------------------ 要素
    def el(self, e):
        t = e["type"]
        return getattr(self, "e_" + t.replace("-", "_"))(e)

    def e_group(self, e):
        gid = self.nid("e")
        inner = "".join(self.el(c) for c in e["items"])
        return f'<g id="{gid}"{self.style_op(e)}>{inner}</g>'

    def style_op(self, e):
        return f' opacity="{e["opacity"]}"' if e.get("opacity", 1) != 1 else ""

    def edge_extend(self, x, y, w, h):
        """仕上がり線に接している四角は塗り足し分だけ外へ伸ばす"""
        b, eps = self.bleed, 0.01
        if not b:
            return x, y, w, h
        if x <= eps: x, w = x - b, w + b
        if y <= eps: y, h = y - b, h + b
        if x + w >= self.tw - eps: w += b
        if y + h >= self.th - eps: h += b
        return x, y, w, h

    def e_rect(self, e):
        x, y, w, h = self.edge_extend(e["x"], e["y"], e["w"], e["h"])
        r = f' rx="{self.L(e["r"])}"' if e.get("r") else ""
        return (f'<rect id="{self.nid("e")}" x="{self.X(x)}" y="{self.Y(y)}" width="{self.L(w)}" height="{self.L(h)}"{r}'
                f'{self.style(e, "#000")}{self.rot(e, e["x"] + e["w"] / 2, e["y"] + e["h"] / 2)}/>')

    def e_ellipse(self, e):
        rx, ry = e.get("rx", e.get("r")), e.get("ry", e.get("r"))
        return (f'<ellipse id="{self.nid("e")}" cx="{self.X(e["cx"])}" cy="{self.Y(e["cy"])}" rx="{self.L(rx)}" ry="{self.L(ry)}"'
                f'{self.style(e, "#000")}{self.rot(e, e["cx"], e["cy"])}/>')

    e_circle = e_ellipse

    def poly(self, pts, e, cx=None, cy=None):
        p = " ".join(f"{self.X(x)},{self.Y(y)}" for x, y in pts)
        if cx is None:
            cx, cy = sum(q[0] for q in pts) / len(pts), sum(q[1] for q in pts) / len(pts)
        return f'<polygon id="{self.nid("e")}" points="{p}"{self.style(e, "#000")}{self.rot(e, cx, cy)}/>'

    def e_polygon(self, e):
        return self.poly(e["points"], e)

    def e_star(self, e):
        """ギザギザの爆発・バッジ。inner は外径に対する内径の比"""
        n, r, ri = e.get("n", 16), e["r"], e["r"] * e.get("inner", 0.8)
        ry = e.get("ry", r) / r
        pts = []
        for i in range(n * 2):
            a = math.pi * i / n - math.pi / 2
            rr = r if i % 2 == 0 else ri
            pts.append((e["cx"] + rr * math.cos(a), e["cy"] + rr * ry * math.sin(a)))
        return self.poly(pts, e, e["cx"], e["cy"])

    def e_rays(self, e):
        """集中線・放射。spread は 1 本の角度幅（度）"""
        n, sp = e.get("n", 24), math.radians(e.get("spread", 5))
        out = []
        for i in range(n):
            a = 2 * math.pi * i / n + math.radians(e.get("rotate", 0))
            r1, r2 = e.get("r1", 0), e["r2"]
            pts = [(e["cx"] + r1 * math.cos(a), e["cy"] + r1 * math.sin(a)),
                   (e["cx"] + r2 * math.cos(a - sp / 2), e["cy"] + r2 * math.sin(a - sp / 2)),
                   (e["cx"] + r2 * math.cos(a + sp / 2), e["cy"] + r2 * math.sin(a + sp / 2))]
            out.append(" ".join(f"{self.X(x)},{self.Y(y)}" for x, y in pts))
        polys = "".join(f'<polygon points="{p}"/>' for p in out)
        clip = ""
        if e.get("clip", True):
            cid = self.nid("c")
            self.defs.append(f'<clipPath id="{cid}"><rect x="0" y="0" width="{self.L(self.tw + 2 * self.bleed)}" '
                             f'height="{self.L(self.th + 2 * self.bleed)}"/></clipPath>')
            clip = f' clip-path="url(#{cid})"'
        return f'<g id="{self.nid("e")}"{clip}><g{self.style(e, "#fff")}>{polys}</g></g>'

    def e_ribbon(self, e):
        """冠リボン：中央の帯＋左右の切れ込み付きの端（端は一段下げて少し暗い色）"""
        x, y, w, h = e["x"], e["y"], e["w"], e["h"]
        tail, notch, drop = e.get("tail", h * 0.9), e.get("notch", h * 0.35), e.get("drop", h * 0.28)
        dark = e.get("tailFill", e.get("fill", "#063"))
        fold = e.get("foldFill", "#00000055")
        L = [(x - tail, y + drop), (x + h * 0.2, y + drop), (x + h * 0.2, y + h + drop), (x - tail, y + h + drop),
             (x - tail + notch, y + drop + h / 2)]
        R = [(x + w + tail, y + drop), (x + w - h * 0.2, y + drop), (x + w - h * 0.2, y + h + drop),
             (x + w + tail, y + h + drop), (x + w + tail - notch, y + drop + h / 2)]
        fl = [(x, y + h), (x + h * 0.2, y + h + drop), (x + h * 0.2, y + h)]
        fr = [(x + w, y + h), (x + w - h * 0.2, y + h + drop), (x + w - h * 0.2, y + h)]
        sub = {k: v for k, v in e.items() if k not in ("rotate",)}
        parts = [self.poly(L, {**sub, "fill": dark}), self.poly(R, {**sub, "fill": dark}),
                 self.poly(fl, {"fill": fold}), self.poly(fr, {"fill": fold}),
                 self.e_rect({**sub, "type": "rect", "r": 0})]
        return f'<g id="{self.nid("e")}"{self.rot(e, x + w / 2, y + h / 2)}>{"".join(parts)}</g>'

    def e_dots(self, e):
        """ドット（網点）。fade で片側に向けて小さくする"""
        x0, y0, w, h, st, r = e["x"], e["y"], e["w"], e["h"], e.get("step", 4), e.get("r", 1)
        fade = e.get("fade")
        cs = []
        j = 0
        yy = y0
        while yy <= y0 + h + 1e-6:
            xx = x0 + (st / 2 if j % 2 else 0)
            while xx <= x0 + w + 1e-6:
                t = 1
                if fade == "left": t = (xx - x0) / w
                elif fade == "right": t = 1 - (xx - x0) / w
                elif fade == "up": t = (yy - y0) / h
                elif fade == "down": t = 1 - (yy - y0) / h
                rr = r * max(t, 0)
                if rr > 0.05:
                    cs.append(f'<circle cx="{self.X(xx)}" cy="{self.Y(yy)}" r="{self.L(rr)}"/>')
                xx += st
            yy += st * 0.866
            j += 1
        return f'<g id="{self.nid("e")}"{self.style(e, "#fff")}>{"".join(cs)}</g>'

    def e_path(self, e):
        d = scale_path(e["d"], self)
        return f'<path id="{self.nid("e")}" d="{d}"{self.style(e, "#000")}/>'

    def e_image(self, e):
        src = e["src"] if os.path.isabs(e["src"]) else os.path.join(self.base, e["src"])
        x, y, w, h = e["x"], e["y"], e["w"], e["h"]
        fit = e.get("fit", "contain")
        if fit == "cover":
            x, y, w, h = self.edge_extend(x, y, w, h)
        data, mime, (iw, ih) = load_image(src, w)
        crop = e.get("crop")  # 元画像の px [sx, sy, sw, sh]
        sx, sy, sw, sh = crop if crop else (0, 0, iw, ih)
        if fit == "stretch":
            kx, ky = w / sw, h / sh
        else:
            s = (min if fit == "contain" else max)(w / sw, h / sh)
            kx = ky = s
        dw, dh = sw * kx, sh * ky
        ax = {"left": 0, "right": 1}.get(e.get("alignX"), 0.5)
        ay = {"top": 0, "bottom": 1}.get(e.get("alignY"), 0.5)
        px, py = x + (w - dw) * ax, y + (h - dh) * ay
        ix, iy = px - sx * kx, py - sy * ky
        b64 = base64.b64encode(data).decode()
        img = (f'<image id="{self.nid("i")}" x="{self.X(ix)}" y="{self.Y(iy)}" width="{self.L(iw * kx)}" '
               f'height="{self.L(ih * ky)}" preserveAspectRatio="none" xlink:href="data:{mime};base64,{b64}"'
               f'{self.style_op(e)}/>')
        need_clip = fit == "cover" or crop or e.get("r")
        if need_clip:
            cid = self.nid("c")
            cx0, cy0, cw, ch = (px, py, dw, dh) if fit == "contain" else (x, y, w, h)
            if fit == "cover":
                cx0, cy0, cw, ch = max(cx0, px), max(cy0, py), min(cw, dw), min(ch, dh)
            rr = f' rx="{self.L(e["r"])}"' if e.get("r") else ""
            self.defs.append(f'<clipPath id="{cid}"><rect x="{self.X(cx0)}" y="{self.Y(cy0)}" width="{self.L(cw)}" '
                             f'height="{self.L(ch)}"{rr}/></clipPath>')
            img = f'<g clip-path="url(#{cid})">{img}</g>'
        return f'<g id="{self.nid("e")}"{self.rot(e, x + w / 2, y + h / 2)}>{img}</g>'

    # ------------------------------------------------------------ 文字
    def font_attr(self, key):
        if key not in FONTS:
            sys.exit(f"font '{key}' は fonts.json にありません（{', '.join(FONTS)}）")
        self.used_fonts.add(key)
        f = FONTS[key]
        return f'font-family="{f["ps"]}, \'{f["ja"]}\'" class="f-{key}"'

    def e_text(self, e):
        """1 行 = 1 グループ（縁取りの重ね文字＋本体）。複数行は外側のグループにまとめる"""
        lines = e["lines"] if "lines" in e else e["text"].split("\n")
        size, font = e["size"], e.get("font", "kakugo-ub")
        lh, align = e.get("lineHeight", 1.2), e.get("align", "center")
        vertical = e.get("vertical", False)
        anchor = {"left": "start", "center": "middle", "right": "end",
                  "top": "start", "bottom": "end"}.get(align, "middle")
        color = e.get("color", "#000")
        outlines = e.get("outlines", [])      # 内側→外側 [{color, width(mm)}]
        shadow = e.get("shadow")               # {dx, dy, color}
        track = e.get("tracking", 0)
        sx = e.get("scaleX", 100)
        out_lines = []
        for i, line in enumerate(lines):
            runs = [{"t": line}] if isinstance(line, str) else line
            if vertical:
                bx, by = e["x"] - i * size * lh, e["y"]
            else:
                bx, by = e["x"], e["y"] + size * ASCENT + i * size * lh
            tid = self.nid("t")
            run_fonts = []
            for r in runs:
                run_fonts.append({"n": len(r["t"]), "font": r.get("font", font)})
                self.font_attr(r.get("font", font))

            def text_el(suffix, fill, stroke=None, sw=0, dx=0, dy=0):
                tsp = []
                for r in runs:
                    attrs = []
                    if r.get("font", font) != font:
                        attrs.append(self.font_attr(r["font"]))
                    if r.get("size"):
                        attrs.append(f'font-size="{self.L(r["size"])}"')
                    if r.get("color") and suffix == "f":
                        attrs.append(f'fill="{r["color"]}"')
                    if r.get("dy"):
                        attrs.append(f'dy="{self.L(r["dy"])}"')
                    tsp.append(f'<tspan {" ".join(attrs)}>{escape(r["t"])}</tspan>' if attrs else escape(r["t"]))
                st = (f' stroke="{stroke}" stroke-width="{self.L(sw)}" stroke-linejoin="round" stroke-miterlimit="2"'
                      if stroke else "")
                ls = f' letter-spacing="{round(track / 1000 * self.L(size), 3)}"' if track else ""
                wm = ' writing-mode="tb-rl"' if vertical else ""
                return (f'<text id="{tid}{suffix}" x="{self.X(bx + dx)}" y="{self.Y(by + dy)}" {self.font_attr(font)} '
                        f'font-size="{self.L(size)}" text-anchor="{anchor}" fill="{fill}"{st}{ls}{wm}>{"".join(tsp)}</text>')

            parts = []
            total = 0
            widths = []
            for o in outlines:
                total += o["width"]
                widths.append((o["color"], total))
            if shadow:
                sw = widths[-1][1] * 2 if widths else 0
                parts.append(text_el("s", shadow["color"], shadow["color"] if sw else None, sw,
                                     shadow.get("dx", 0.6), shadow.get("dy", 0.8)))
            for k, (c, wsum) in reversed(list(enumerate(widths))):
                parts.append(text_el(f"o{k + 1}", c, c, wsum * 2))
            parts.append(text_el("f", self.paint(color)))

            tf = []
            if e.get("rotate"):
                tf.append(f"rotate({e['rotate']} {self.X(e['x'])} {self.Y(e['y'])})")
            if sx != 100:
                tf.append(f"translate({self.X(bx)} 0) scale({sx / 100} 1) translate({-self.X(bx)} 0)")
            tfa = f' transform="{" ".join(tf)}"' if tf else ""
            maxw = e.get("maxWidth")
            mw = f' data-maxlen="{self.L(maxw)}"' if maxw else ""
            out_lines.append(f'<g id="{tid}"{tfa}{mw}>{"".join(parts)}</g>')
            self.texts.append({"id": tid, "text": "".join(r["t"] for r in runs), "runs": run_fonts,
                               "maxLen": self.L(maxw) if maxw else 0, "vertical": vertical,
                               "label": e.get("name", "")})
        if len(out_lines) == 1:
            return out_lines[0]
        return f'<g id="{self.nid("e")}">{"".join(out_lines)}</g>'


def scale_path(d, b):
    toks = re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", d)
    out, cmd, idx = [], None, 0
    for t in toks:
        if t.isalpha():
            cmd, idx = t, 0
            out.append(t)
            continue
        v = float(t)
        up, c = cmd.isupper(), cmd.upper()
        if c == "H":
            r = b.X(v) if up else b.L(v)
        elif c == "V":
            r = b.Y(v) if up else b.L(v)
        elif c == "A":
            j = idx % 7
            if j in (0, 1): r = b.L(v)
            elif j in (2, 3, 4): r = v
            elif j == 5: r = b.X(v) if up else b.L(v)
            else: r = b.Y(v) if up else b.L(v)
        else:
            r = (b.X(v) if idx % 2 == 0 else b.Y(v)) if up else b.L(v)
        idx += 1
        out.append(f"{r:g}" if isinstance(r, float) else str(r))
    return " ".join(out)


# ---------------------------------------------------------------- 出力

def build(spec_path, out_dir):
    spec = json.load(open(spec_path, encoding="utf-8"))
    b = B(spec, os.path.dirname(os.path.abspath(spec_path)))
    os.makedirs(out_dir, exist_ok=True)
    name = spec.get("name", "販促物")
    cw, ch = b.tw + 2 * b.bleed, b.th + 2 * b.bleed

    layers_svg, layers_map = [], []
    if spec.get("background"):
        spec["layers"].insert(0, {"name": "背景色", "items": [
            {"type": "rect", "x": 0, "y": 0, "w": b.tw, "h": b.th, "fill": spec["background"]}]})
    for i, layer in enumerate(spec["layers"]):
        lid = f"L{i + 1:02d}"
        body = "".join(b.el(e) for e in layer["items"])
        layers_svg.append(f'<g id="{lid}">{body}</g>')
        layers_map.append({"id": lid, "name": f'{i + 1:02d} {layer["name"]}'})

    svg = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
           f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
           f'width="{cw}mm" height="{ch}mm" viewBox="0 0 {b.L(cw)} {b.L(ch)}">'
           f'<title>{escape(name)}</title><defs>{"".join(b.defs)}</defs>{"".join(layers_svg)}</svg>')
    svg_name = f"{name}_編集用.svg"
    open(os.path.join(out_dir, svg_name), "w", encoding="utf-8").write(svg)

    fonts_used = {k: {"ps": FONTS[k]["ps"], "ja": FONTS[k]["ja"], "hints": FONTS[k]["hints"]}
                  for k in sorted(b.used_fonts)}
    m = {"svg": svg_name, "trimW": b.tw, "trimH": b.th, "bleed": b.bleed, "layers": layers_map,
         "texts": b.texts, "fonts": fonts_used}
    tpl = open(os.path.join(HERE, "ai_save.jsx.tpl"), encoding="utf-8").read()
    jsx = tpl.replace("/*MAP*/{}", json.dumps(m, ensure_ascii=True))
    write_jsx(os.path.join(out_dir, "AI保存.jsx"), jsx)
    write_jsx(os.path.join(out_dir, "縁取り文字変更.jsx"), open(os.path.join(HERE, "outline_edit.jsx"), encoding="utf-8").read())

    readme = make_readme(spec, b, svg_name)
    open(os.path.join(out_dir, "お読みください.txt"), "w", encoding="utf-8").write(readme)
    kb = os.path.getsize(os.path.join(out_dir, svg_name)) // 1024
    print(f"OK {out_dir}/{svg_name} ({kb} KB)  text lines={len(b.texts)} fonts={', '.join(sorted(b.used_fonts))}")


def write_jsx(path, s):
    # ExtendScript は文字コードで化けやすいので、非 ASCII はすべて \\uXXXX にして BOM 付き UTF-8 で書く
    s = "".join(c if ord(c) < 128 else f"\\u{ord(c):04x}" for c in s)
    open(path, "w", encoding="utf-8-sig").write(s)


def make_readme(spec, b, svg_name):
    size_label = spec["size"] if isinstance(spec["size"], str) else f'{b.tw}×{b.th}mm'
    fonts = "\n".join(f"・{FONTS[k]['ja']}（{FONTS[k]['ps']}）" for k in sorted(b.used_fonts))
    meta = "\n".join(f"{k}：{v}" for k, v in spec.get("meta", {}).items()) or "（依頼書の記載なし）"
    notes = "\n".join(f"・{n}" for n in spec.get("notes", []))
    bleed = f"塗り足し {b.bleed}mm（背景・端に接する図形と写真を延長済み）" if b.bleed else "塗り足しなし"
    return f"""{spec.get('name', '販促物')}

■ 仕上がり
{size_label}　幅{b.tw}×高さ{b.th}mm　{bleed}

■ 収録ファイル
・{svg_name}：編集用データ。文字はテキスト、装飾はベクトル、写真は埋め込み画像。レイヤー（グループ）ごとに名前付き。
・AI保存.jsx：SVG を開いて .ai で保存するスクリプト（下記）。
・縁取り文字変更.jsx：縁取り付きの文字を一括で打ち替えるスクリプト。
・プレビュー.png：仕上がりの確認用（代替フォントで描画。印刷原稿ではありません）。

■ Illustrator で .ai にする（おすすめ）
1. ZIP をすべて展開する（SVG と jsx を同じフォルダーに置く）
2. Illustrator で「ファイル → スクリプト → その他のスクリプト…」→「AI保存.jsx」を選ぶ
3. 自動で次を行い、同じフォルダーに .ai と確認用 PNG を保存します
   ・実寸（{b.tw}×{b.th}mm）のアートボードに合わせる
   ・グループを名前付きレイヤーに分ける
   ・書体を下記の HG フォント等に設定し直す（入っていない書体は最後に一覧表示）
   ・指定幅からはみ出した見出しを長体で幅内に収める
   ・CMYK モードに変換（jsx 冒頭の CONVERT_CMYK = false で無効）
   ・同名の .ai があれば _2, _3 … を付けて保存（上書きしません）
SVG を直接開いて「別名で保存」でも .ai にできますが、書体の再設定と長体調整は行われません。

■ 使用書体
{fonts}
フォント本体は同梱していません。

■ 文字の縁取り
白や黄色の縁取りは、同じ文字を太い線付きで後ろに重ねて作っています（1 行 = 1 グループ）。
打ち替えるときは、その行の文字を 1 つ選んで「縁取り文字変更.jsx」を実行すると、グループ内の全部の文字が一括で変わります。
1 行の中で大きさや色が違う文字（例：「松本さん」の「さん」）は、打ち替えると書式が 1 つにそろうので、あとで部分的に直してください。

■ 依頼書から（紙面外の運用情報）
{meta}

■ 確認済み／未確認
確認済み：SVG の実寸、全文字がテキストであること、画像の埋め込み、ブラウザーでの描画（プレビュー.png）。
未確認：Illustrator での読み込み結果・書体の置き換え・jsx の実行（作成環境に Illustrator がないため）。
プレビューは HG フォントの代わりに似た無料フォントで描いています。実際の HG フォントでは文字幅が少し変わります。
印刷前に、書体・文字の欠け・写真の解像度・色（RGB→CMYK での変化）を確認してください。
{notes}
"""


def pack(out_dir):
    out_dir = out_dir.rstrip("/")
    zpath = out_dir + ".zip"
    root = os.path.basename(out_dir)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(out_dir)):
            if f.startswith(".") or f.endswith(".conv.png"):
                continue
            z.write(os.path.join(out_dir, f), f"{root}/{f}")
    print(f"OK {zpath} ({os.path.getsize(zpath) // 1024} KB)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p1 = sp.add_parser("build")
    p1.add_argument("spec")
    p1.add_argument("--out", required=True)
    p2 = sp.add_parser("pack")
    p2.add_argument("out")
    a = ap.parse_args()
    build(a.spec, a.out) if a.cmd == "build" else pack(a.out)
