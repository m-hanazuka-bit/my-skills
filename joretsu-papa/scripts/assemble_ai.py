#!/usr/bin/env python3
"""AIで作ったカット（動画）と行ごとの声をつなぎ、テロップを重ねて縦型ショートに仕上げる。

各行の声の長さから場面の長さを決め、カットが足りなければ最後のコマで止めて伸ばす。

usage:
  python assemble_ai.py --plan plan.json --clips <カットのフォルダ> --voice <声のフォルダ> --out out.mp4
  （テロップの PNG は caption_png.mjs で作る。Node と Playwright が要る）

plan.json:
  {
    "title": "パパなので。", "badge": "実話", "badge_until": 4.0,
    "hook": {"text": "パンツが<br>ないので<br>帰ります", "until": 2.5},
    "scenes": [
      {"clip": "c0.mp4", "clip_start": 0, "tail": 0.4,
       "lines": [{"id": "hook", "voice": "hook.wav", "gap": 0.2, "text": "…", "who": "パパ", "style": ""}]}
    ]
  }
"""
import argparse
import json
import os
import subprocess

W, H, FPS = 1080, 1920, 30
HERE = os.path.dirname(os.path.abspath(__file__))


def dur(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def run(cmd):
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--clips", required=True)
    ap.add_argument("--voice", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--work", default="work")
    a = ap.parse_args()
    plan = json.load(open(a.plan))
    os.makedirs(a.work, exist_ok=True)

    # 1. 時刻を決める
    t, lines, segs = 0.0, [], []
    for i, sc in enumerate(plan["scenes"]):
        start = t
        for ln in sc["lines"]:
            t += ln.get("gap", 0.2)
            d = dur(os.path.join(a.voice, ln["voice"]))
            lines.append({**ln, "start": round(t, 3), "dur": d})
            t += d
        t += sc.get("tail", 0.4)
        segs.append((i, sc, start, t - start))
    total = t
    hook = plan.get("hook")
    hook_until = hook.get("until", 2.5) if hook else 0.0
    for k, ln in enumerate(lines):
        ln["show_from"] = max(0.0, ln["start"] - 0.05) if k else 0.0
        # 冒頭の大きな文字が出ている間は、ふつうのテロップを出さない
        ln["show_from"] = max(ln["show_from"], hook_until)
        ln["show_to"] = lines[k + 1]["start"] - 0.05 if k + 1 < len(lines) else total
    json.dump({"total": total, "lines": lines}, open(os.path.join(a.work, "timeline.json"), "w"), ensure_ascii=False, indent=1)
    print(f"total {total:.2f}s, {len(lines)} lines, {len(segs)} scenes")

    # 2. 場面ごとにカットを切り出す（足りない分は最後のコマで止める）
    seg_files = []
    for i, sc, start, d in segs:
        f = os.path.join(a.work, f"seg_{i:02d}.mp4")
        vf = f"tpad=stop_mode=clone:stop_duration=30,scale={W}:-2,crop={W}:{H},fps={FPS},setsar=1"
        run(["ffmpeg", "-v", "error", "-y", "-ss", str(sc.get("clip_start", 0)), "-i", os.path.join(a.clips, sc["clip"]),
             "-vf", vf, "-t", f"{d:.3f}", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", f])
        seg_files.append(f)
    with open(os.path.join(a.work, "segs.txt"), "w") as fh:
        fh.writelines(f"file '{os.path.abspath(f)}'\n" for f in seg_files)
    body = os.path.join(a.work, "body.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", os.path.join(a.work, "segs.txt"), "-c", "copy", body])

    # 3. テロップの PNG
    caps = os.path.join(a.work, "caps")
    spec = {"title": plan.get("title"), "badge": plan.get("badge"), "hook": hook["text"] if hook else None,
            "lines": [{"id": ln["id"], "text": ln["text"], "who": ln.get("who"), "style": ln.get("style", "")} for ln in lines]}
    json.dump(spec, open(os.path.join(a.work, "captions.json"), "w"), ensure_ascii=False)
    env = dict(os.environ)
    env["NODE_PATH"] = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    subprocess.run(["node", os.path.join(HERE, "caption_png.mjs"), os.path.join(a.work, "captions.json"), caps], env=env, check=True)

    # 4. 重ねて、声を置いて、書き出す
    inputs = ["-i", body]
    overlays = []  # (png, from, to)
    if plan.get("title"):
        overlays.append((os.path.join(caps, "title.png"), 0, total))
    if plan.get("badge"):
        overlays.append((os.path.join(caps, "badge.png"), 0, plan.get("badge_until", 4.0)))
    if hook:
        overlays.append((os.path.join(caps, "hook.png"), 0, hook_until))
    for ln in lines:
        if ln["show_from"] >= ln["show_to"]:
            continue
        overlays.append((os.path.join(caps, f"cap_{ln['id']}.png"), ln["show_from"], ln["show_to"]))
    for png, _, _ in overlays:
        inputs += ["-loop", "1", "-i", png]
    for ln in lines:
        inputs += ["-i", os.path.join(a.voice, ln["voice"])]
    fc, last = [], "[0:v]"
    for k, (_, f0, f1) in enumerate(overlays):
        out = f"[v{k}]"
        fc.append(f"{last}[{k + 1}:v]overlay=0:0:enable='between(t,{f0:.3f},{f1:.3f})':shortest=1{out}")
        last = out
    base = 1 + len(overlays)
    for k, ln in enumerate(lines):
        fc.append(f"[{base + k}:a]aresample=48000,aformat=channel_layouts=mono,adelay={int(ln['start'] * 1000)}:all=1[a{k}]")
    fc.append("".join(f"[a{k}]" for k in range(len(lines))) +
              f"amix=inputs={len(lines)}:normalize=0,apad,atrim=0:{total:.3f},aformat=channel_layouts=stereo[aout]")
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", last, "-map", "[aout]",
         "-t", f"{total:.3f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", "-preset", "medium",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", a.out])
    print("done:", a.out)


if __name__ == "__main__":
    main()
