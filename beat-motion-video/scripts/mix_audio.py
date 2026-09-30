#!/usr/bin/env python3
"""ビートとナレーションをミックスし、映像側が読む timeline.json を作る。

- ナレーションは storyboard.json の narration[].at_bar（小節、小数可）で配置し、
  直近の拍にスナップする（--no-snap で無効）。
- 声が鳴っている間はビートを自動で下げる（ダッキング）。
- timeline.json = ビートグリッド + 各セリフの開始/終了秒 + scenes の秒換算。
  Blender と HTML はこのファイル1つを見れば同期できる。

usage:
  python mix_audio.py --plan storyboard.json --beat work/beat --voice work/voice --out work
"""
import argparse
import json
import os
import wave

import numpy as np

SR = 48000


def read_wav(path):
    with wave.open(path) as w:
        ch, rate, n = w.getnchannels(), w.getframerate(), w.getnframes()
        x = np.frombuffer(w.readframes(n), dtype="<i2").astype(np.float64) / 32768
    x = x.reshape(-1, ch).mean(axis=1)
    if rate != SR:
        t_src = np.arange(len(x)) / rate
        t_dst = np.arange(int(len(x) * SR / rate)) / SR
        x = np.interp(t_dst, t_src, x)
    return x


def bar_to_time(grid, bar):
    return bar * 4 * grid["seconds_per_beat"]


def snap(grid, t, div=2):
    """div=2 なら8分音符単位でスナップ"""
    q = grid["seconds_per_beat"] / div
    return round(t / q) * q


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--beat", required=True, help="make_beat.py の --out と同じパス（拡張子なし）")
    ap.add_argument("--voice", help="gemini_tts.py の出力ディレクトリ")
    ap.add_argument("--out", default=".")
    ap.add_argument("--voice-gain", type=float, default=1.0)
    ap.add_argument("--beat-gain", type=float, default=0.8)
    ap.add_argument("--duck", type=float, default=0.45, help="声の間のビート音量倍率")
    ap.add_argument("--no-snap", action="store_true")
    a = ap.parse_args()

    plan = json.load(open(a.plan))
    grid = json.load(open(a.beat + ".json"))
    beat = read_wav(a.beat + ".wav") * a.beat_gain
    voice_track = np.zeros_like(beat)
    duck_env = np.ones_like(beat)

    manifest = {}
    if a.voice and os.path.exists(os.path.join(a.voice, "voice.json")):
        manifest = {m["id"]: m for m in json.load(open(os.path.join(a.voice, "voice.json")))}

    narration = []
    for i, n in enumerate(plan.get("narration", [])):
        lid = n.get("id", f"n{i+1:02d}")
        if lid not in manifest:
            continue
        t = bar_to_time(grid, n.get("at_bar", 0)) if "at" not in n else n["at"]
        if not a.no_snap:
            t = snap(grid, t)
        v = read_wav(manifest[lid]["file"]) * a.voice_gain
        s = int(t * SR)
        e = min(len(voice_track), s + len(v))
        voice_track[s:e] += v[: e - s]
        # ダッキング（50ms で下げ、300ms で戻す）
        att, rel = int(0.05 * SR), int(0.3 * SR)
        lo, hi = max(0, s - att), min(len(duck_env), e + rel)
        env = np.ones(hi - lo)
        env[: s - lo] = np.linspace(1, a.duck, s - lo)
        env[s - lo: e - lo] = a.duck
        env[e - lo:] = np.linspace(a.duck, 1, hi - e)
        duck_env[lo:hi] = np.minimum(duck_env[lo:hi], env)
        narration.append({"id": lid, "text": n["text"], "caption": n.get("caption", n["text"]),
                          "tension": manifest[lid]["tension"],
                          "start": round(t, 4), "end": round(t + len(v) / SR, 4)})

    mix = beat * duck_env + voice_track
    mix = np.tanh(mix * 1.1)
    mix = mix / (np.max(np.abs(mix)) + 1e-9) * 0.9
    data = (np.stack([mix, mix], 1) * 32767).astype("<i2")
    os.makedirs(a.out, exist_ok=True)
    with wave.open(os.path.join(a.out, "mix.wav"), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())

    scenes = []
    for sc in plan.get("scenes", []):
        sc = dict(sc)
        sc["start"] = bar_to_time(grid, sc.get("start_bar", 0))
        sc["end"] = bar_to_time(grid, sc.get("end_bar", grid["bars"]))
        scenes.append(sc)

    timeline = dict(grid)
    timeline.update({
        "fps": plan.get("fps", 30),
        "size": plan.get("size", [1920, 1080]),
        "video_duration": grid["duration"],
        "narration": narration,
        "scenes": scenes,
        "palette": plan.get("palette", {}),
        "look": plan.get("look", {}),
        "title": plan.get("title", ""),
    })
    json.dump(timeline, open(os.path.join(a.out, "timeline.json"), "w"), ensure_ascii=False, indent=1)
    late = [n for n in narration if n["end"] > grid["duration"]]
    print(f"mix.wav {len(mix)/SR:.2f}s / timeline.json ({len(narration)} lines, {len(scenes)} scenes)")
    for n in late:
        print(f"  ! {n['id']} が動画尺を {n['end']-grid['duration']:.2f}s はみ出しています。at_bar を前へ")


if __name__ == "__main__":
    main()
