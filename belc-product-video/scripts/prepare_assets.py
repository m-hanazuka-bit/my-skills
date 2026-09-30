#!/usr/bin/env python3
"""画像の背景を抜いて透過 PNG にする（キャラ・商品パッケージ用）。

  python prepare_assets.py IN.jpg OUT.png [--crop x0,y0,x1,y1] [--no-cut] [--pad 0.04]

- 背景除去は rembg の BiRefNet（`pip install "rembg[cpu]"`、初回にモデルを自動ダウンロード）。
  BiRefNet が使えなければ isnet-general-use に落とす。
- --crop は元画像のピクセル座標で先に切り出す（三面図から正面だけ取る、など）。
- 最後に透明部分をトリミングし、周囲に少し余白を付ける。
- 商品画像は「実物の写真を切り抜いて使う」のが原則。生成 AI に商品を描かせない（文字が崩れて表示違反になる）。
"""
import argparse

from PIL import Image


def cutout(im):
    from rembg import new_session, remove
    for model in ("birefnet-general-lite", "isnet-general-use"):
        try:
            return remove(im, session=new_session(model))
        except Exception as e:  # モデル取得失敗など
            print(f"[warn] {model}: {e}")
    raise SystemExit("背景除去に失敗しました（rembg をインストールしてください）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--crop", help="x0,y0,x1,y1")
    ap.add_argument("--no-cut", action="store_true", help="背景除去しない（既に透過 or 白背景のまま使う）")
    ap.add_argument("--pad", type=float, default=0.04)
    ap.add_argument("--alpha-floor", type=int, default=24, help="これ未満の半透明は消す（背景の残りカス対策）")
    a = ap.parse_args()

    im = Image.open(a.src).convert("RGB")
    if a.crop:
        im = im.crop(tuple(int(v) for v in a.crop.split(",")))
    out = im.convert("RGBA") if a.no_cut else cutout(im)
    r, g, b, al = out.split()
    al = al.point(lambda v: 0 if v < a.alpha_floor else v)
    out = Image.merge("RGBA", (r, g, b, al))
    box = out.getbbox()
    if box:
        out = out.crop(box)
    p = int(max(out.size) * a.pad)
    canvas = Image.new("RGBA", (out.width + 2 * p, out.height + 2 * p), (0, 0, 0, 0))
    canvas.paste(out, (p, p))
    canvas.save(a.dst)
    print(f"{a.dst} {canvas.size}")


if __name__ == "__main__":
    main()
