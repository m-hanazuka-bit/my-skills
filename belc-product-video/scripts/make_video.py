#!/usr/bin/env python3
"""キャラクター商品紹介動画を 1 コマンドで作る（共通エンジン）。

  # モード①：台本（ナレーション案をキャラ口調に直したもの）から音声も作る
  python make_video.py --character gu --script script.json --out work/milk_gu
  # モード②：作成済みの音声ファイルを使う
  python make_video.py --character bellcook --script script.json --audio narration.wav --out work/milk_bc
  # 下書き（半分の解像度で速く）/ API キーなしでレイアウトだけ確認（仮の声）
  python make_video.py ... --draft
  python make_video.py ... --dummy-voice --draft

流れ： 台本チェック → 声（Gemini TTS or 持ち込み音声）→ セリフ尺から構成を自動計算 → ビート（尺に合わせた小節数）
      → ミックス → 2D アニメ（assets/product.html）を 1 フレームずつ撮影 → mp4
同じフォルダの ../beat-motion-video/scripts を使う（環境変数 BEAT_MOTION_DIR で変更可）。
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BMV = os.environ.get("BEAT_MOTION_DIR", os.path.join(os.path.dirname(ROOT), "beat-motion-video", "scripts"))
CACHE = os.path.expanduser(os.environ.get("BELC_CACHE", "~/.cache/belc-product-video"))
sys.path.insert(0, HERE)
from check_lines import check  # noqa: E402

FONTS = ["Dela Gothic One", "Zen Maru Gothic:wght@500;700;900", "Noto Sans JP:wght@400;700;900", "M PLUS Rounded 1c:wght@800"]


def run(cmd, **kw):
    print("$", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def char_path(cid):
    p = cid if cid.endswith(".json") else os.path.join(ROOT, "characters", cid, "character.json")
    if not os.path.exists(p):
        sys.exit(f"キャラクター設定が見つかりません: {p}")
    return p


def dummy_voice(script, out, char):
    """API キーなしで尺だけそれっぽい仮の声を作る（レイアウト確認用）"""
    os.makedirs(out, exist_ok=True)
    rate, man = 24000, []
    cps = 8.0 if char["id"] == "gu" else 6.0
    for ln in script["lines"]:
        text = ln["text"].replace("*", "")
        d = max(0.8, len(text) / cps)
        t = np.arange(int(rate * d)) / rate
        syll = 0.5 + 0.5 * np.sin(2 * np.pi * cps * t) ** 2  # 音節っぽい強弱
        x = 0.25 * np.sin(2 * np.pi * (180 if char["id"] == "gu" else 230) * t) * syll * np.minimum(1, np.minimum(t, d - t) * 20)
        path = os.path.abspath(os.path.join(out, f"{ln['id']}.wav"))
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes((x * 32767).astype("<i2").tobytes())
        man.append({"id": ln["id"], "text": ln["text"], "tension": ln.get("emotion", ""), "file": path, "duration": round(d, 3)})
    json.dump(man, open(os.path.join(out, "voice.json"), "w"), ensure_ascii=False, indent=1)


def copy_asset(src, base, out_assets):
    if not src:
        return None
    p = src if os.path.isabs(src) else os.path.join(base, src)
    if not os.path.exists(p):
        sys.exit(f"画像が見つかりません: {p}")
    os.makedirs(out_assets, exist_ok=True)
    dst = os.path.join(out_assets, os.path.basename(p))
    shutil.copy(p, dst)
    return "assets/" + os.path.basename(p)


def plan(char, script, voice, cdir, sdir, out, fps, size, hold):
    bpm = script.get("bpm") or char["beat"]["bpm"]
    spb = 60.0 / bpm
    q = spb / 2
    dur = {m["id"]: m["duration"] for m in voice}
    lines = [l for l in script["lines"] if l["id"] in dur]
    t = spb  # 最初のセリフの前に 1 拍（キャラの登場）
    placed = []
    for i, ln in enumerate(lines):
        start = math.ceil(t / q - 1e-6) * q
        end = start + dur[ln["id"]]
        placed.append((ln, start, end))
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        gap = spb if nxt and nxt.get("emotion") in ("tame", "sneaky") else ln.get("gap_beats", 0.5) * spb
        t = end + gap
    last_end = placed[-1][2]
    bar = 4 * spb
    if placed[-1][0].get("scene") == "closing":
        total = last_end + hold
    else:
        total = last_end + q + max(hold, 2.0)
    bars = math.ceil(total / bar - 1e-6)
    duration = bars * bar

    assets = os.path.join(out, "assets")
    product = dict(script["product"])
    product["image"] = copy_asset(product.get("image"), sdir, assets)
    scenes = []
    for i, (ln, start, end) in enumerate(placed):
        s0 = 0.0 if i == 0 else max(start - q, scenes[-1]["start"] + q)
        if scenes:
            scenes[-1]["end"] = s0
        sc = {"id": f"s{i + 1:02d}", "type": ln.get("scene", "point"), "line": ln["id"], "start": s0, "end": duration}
        sc.update({k: v for k, v in ln.get("scene_opts", {}).items()})
        if sc.get("image"):
            sc["image"] = copy_asset(sc["image"], sdir, assets)
        if sc.get("character_image"):
            sc["character_image"] = copy_asset(sc["character_image"], sdir, assets)
        scenes.append(sc)
    if placed[-1][0].get("scene") != "closing":
        cs = last_end + q
        scenes[-1]["end"] = cs
        scenes.append({"id": "s_close", "type": "closing", "start": cs, "end": duration})

    imgs = {k: copy_asset(v, cdir, assets) for k, v in char["images"].items() if isinstance(v, str)}
    imgs["scenes"] = {k: copy_asset(v, cdir, assets) for k, v in char["images"].get("scenes", {}).items()}
    board = {
        "title": f"{product.get('name', '')} × {char['name']}",
        "fps": fps,
        "size": size,
        "palette": char["look"]["palette"],
        "look": {"hud": False, "caption": "none"},
        "scenes": scenes,
        "narration": [{"id": ln["id"], "text": ln["text"], "caption": ln.get("caption", ln["text"]), "at": round(s, 4)} for ln, s, e in placed],
        "data": {
            "character": {"id": char["id"], "name": char["name"], "look": char["look"], "motion": char["motion"], "images": imgs},
            "product": product,
            "tagline": script.get("tagline", "くらしにベルク"),
            "emotions": {ln["id"]: ln.get("emotion", "") for ln in lines},
        },
    }
    json.dump(board, open(os.path.join(out, "storyboard.json"), "w"), ensure_ascii=False, indent=1)
    print(f"構成: {len(placed)} 行 / {bpm} BPM / {bars} 小節 = {duration:.2f} 秒")
    for sc in scenes:
        print(f"  {sc['start']:5.2f}–{sc['end']:5.2f}  {sc['type']:8s} {sc.get('line', '')}")
    return bpm, bars


def ensure_node(cache):
    nd = os.path.join(cache, "node")
    if not os.path.exists(os.path.join(nd, "node_modules", "playwright")):
        os.makedirs(nd, exist_ok=True)
        run(["npm", "init", "-y"], cwd=nd, stdout=subprocess.DEVNULL)
        run(["npm", "i", "playwright"], cwd=nd)
        if not os.path.exists("/opt/pw-browsers/chromium"):
            run(["npx", "playwright", "install", "chromium"], cwd=nd)
    shutil.copy(os.path.join(BMV, "render_frames.mjs"), nd)
    return os.path.join(nd, "render_frames.mjs")


def ensure_fonts(cache, out):
    fd = os.path.join(cache, "fonts")
    if not os.path.exists(os.path.join(fd, "fonts.css")):
        run([sys.executable, os.path.join(BMV, "fetch_fonts.py"), "--out", fd, *FONTS])
    dst = os.path.join(out, "fonts")
    if not os.path.exists(dst):
        shutil.copytree(fd, dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--character", required=True, help="gu / bellcook / character.json のパス")
    ap.add_argument("--script", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--audio", nargs="+", help="モード②：作成済みの音声ファイル")
    ap.add_argument("--dummy-voice", action="store_true", help="仮の声でレイアウトだけ確認")
    ap.add_argument("--retts", help="この id の行だけ音声を作り直す（カンマ区切り）")
    ap.add_argument("--draft", action="store_true", help="半分の解像度で書き出す")
    ap.add_argument("--vertical", action="store_true", help="縦型 1080x1920（ショート/リール用）")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--hold", type=float, default=1.8, help="最後のセリフの後に締めを見せる秒数")
    ap.add_argument("--skip-check", action="store_true")
    ap.add_argument("--stop-after", choices=["check", "voice", "plan", "frames"])
    a = ap.parse_args()

    cpath = char_path(a.character)
    char = json.load(open(cpath, encoding="utf-8"))
    script = json.load(open(a.script, encoding="utf-8"))
    cdir, sdir = os.path.dirname(os.path.abspath(cpath)), os.path.dirname(os.path.abspath(a.script))
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)

    # 1. 台本チェック（モード②は録音済みなので警告だけ）
    if not a.skip_check:
        errors, warns, est = check(char, script)
        for e in errors:
            print("ERROR", e)
        for w in warns:
            print("WARN ", w)
        if errors and not a.audio:
            sys.exit("台本にキャラのルール違反があります。直してから再実行してください（--skip-check で無視）")
    if a.stop_after == "check":
        return

    # 2. 声
    vdir = os.path.join(out, "voice")
    if a.audio:
        run([sys.executable, os.path.join(HERE, "align_audio.py"), "--audio", *a.audio, "--script", a.script, "--out", vdir])
        script = json.load(open(a.script, encoding="utf-8"))
    elif a.dummy_voice:
        dummy_voice(script, vdir, char)
    elif a.retts or not os.path.exists(os.path.join(vdir, "voice.json")):
        cmd = [sys.executable, os.path.join(HERE, "char_tts.py"), "--character", cpath, "--script", a.script, "--out", vdir]
        run(cmd + (["--only", a.retts] if a.retts else []))
    voice = json.load(open(os.path.join(vdir, "voice.json"), encoding="utf-8"))
    if a.stop_after == "voice":
        return

    # 3. 構成 → 4. ビート → 5. ミックス
    size = [1080, 1920] if a.vertical else [1920, 1080]
    bpm, bars = plan(char, script, voice, cdir, sdir, out, a.fps, size, a.hold)
    beat = os.path.join(out, "beat")
    run([sys.executable, os.path.join(BMV, "make_beat.py"), "--style", script.get("beat_style") or char["beat"]["style"],
         "--bpm", bpm, "--bars", bars, "--out", beat])
    run([sys.executable, os.path.join(BMV, "mix_audio.py"), "--plan", os.path.join(out, "storyboard.json"), "--beat", beat,
         "--voice", vdir, "--out", out, "--no-snap", "--duck", "0.35", "--beat-gain", "0.55"])
    shutil.copy(os.path.join(ROOT, "assets", "product.html"), os.path.join(out, "motion.html"))
    if a.stop_after == "plan":
        return

    # 6. 撮影 → 7. 書き出し
    ensure_fonts(CACHE, out)
    renderer = ensure_node(CACHE)
    frames = os.path.join(out, "frames")
    shutil.rmtree(frames, ignore_errors=True)
    run(["node", renderer, "--html", os.path.join(out, "motion.html"), "--timeline", os.path.join(out, "timeline.json"),
         "--out", frames, "--scale", "0.5" if a.draft else "1"])
    if a.stop_after == "frames":
        return
    mp4 = os.path.join(out, f"{os.path.basename(out)}{'_draft' if a.draft else ''}.mp4")
    run(["bash", os.path.join(BMV, "encode.sh"), frames, os.path.join(out, "mix.wav"), a.fps, mp4])
    print(f"完成: {mp4}")


if __name__ == "__main__":
    main()
