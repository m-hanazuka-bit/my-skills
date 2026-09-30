#!/usr/bin/env python3
"""ビートを数種類から選んで合成し、WAV と「ビートグリッド」JSON を書き出す。

外部音源は使わず numpy だけで合成するので、APIキーも著作権も不要。
JSON には拍・小節頭・キック・スネア・セクション（intro/build/drop/outro）の
時刻が入っていて、Blender と 2D の両方がこれを見て動きを合わせる。

usage:
  python make_beat.py --style cinematic --bpm 100 --duration 15 --out work/beat
  python make_beat.py --list
"""
import argparse
import json
import math
import wave

import numpy as np

SR = 48000

STYLES = {
    # name: (default bpm, swing 0-0.5, 説明)
    "house": (124, 0.0, "4つ打ち。明るく前向き。商品紹介・テック系"),
    "trap": (140, 0.0, "ハーフタイムの808とハイハットロール。ストリート・攻めた印象"),
    "lofi": (84, 0.18, "スウィングしたゆるいビート＋和音パッド。上質・落ち着き・和"),
    "cinematic": (100, 0.0, "インパクト音と太鼓、ライザー。高級感・壮大・CM/予告編"),
    "future": (128, 0.0, "ビルドアップからドロップへ。最もダイナミック。SNS広告"),
}


# ---------------------------------------------------------------- 音源
def env_exp(n, decay):
    t = np.arange(n) / SR
    return np.exp(-t / decay)


def kick(level=1.0):
    n = int(SR * 0.45)
    t = np.arange(n) / SR
    freq = 45 + 110 * np.exp(-t / 0.035)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    click = np.random.randn(n) * env_exp(n, 0.002) * 0.3
    return level * (np.sin(phase) * env_exp(n, 0.16) + click)


def snare(level=0.7):
    n = int(SR * 0.3)
    t = np.arange(n) / SR
    noise = np.random.randn(n)
    noise = noise - np.concatenate([[0], noise[:-1]]) * 0.6  # 軽いハイパス
    tone = np.sin(2 * np.pi * 185 * t) * env_exp(n, 0.05)
    return level * (noise * env_exp(n, 0.09) * 0.55 + tone * 0.6)


def clap(level=0.6):
    n = int(SR * 0.3)
    out = np.zeros(n)
    for off in (0, 0.011, 0.022):
        s = int(off * SR)
        m = n - s
        out[s:] += np.random.randn(m) * env_exp(m, 0.012 if off < 0.02 else 0.12)
    out = out - np.concatenate([[0], out[:-1]])
    return level * out * 0.5


def hat(level=0.25, open_=False):
    n = int(SR * (0.25 if open_ else 0.05))
    noise = np.random.randn(n)
    noise = np.diff(np.diff(noise, prepend=0), prepend=0)  # 強めのハイパス
    return level * noise * env_exp(n, 0.08 if open_ else 0.012) * 0.35


def tom(freq=110, level=0.8):
    n = int(SR * 0.6)
    t = np.arange(n) / SR
    f = freq * (1 + 0.6 * np.exp(-t / 0.03))
    phase = 2 * np.pi * np.cumsum(f) / SR
    return level * np.sin(phase) * env_exp(n, 0.22)


def sub808(freq=49.0, length=0.8, level=0.7):
    n = int(SR * length)
    t = np.arange(n) / SR
    f = freq * (1 + 0.5 * np.exp(-t / 0.02))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(n, length * 0.6)
    return level * np.tanh(x * 1.8) / np.tanh(1.8)


def impact(level=1.0):
    n = int(SR * 2.5)
    t = np.arange(n) / SR
    boom = np.sin(2 * np.pi * np.cumsum(38 + 60 * np.exp(-t / 0.08)) / SR) * env_exp(n, 0.7)
    noise = np.random.randn(n) * env_exp(n, 0.35) * 0.25
    return level * np.tanh((boom + noise) * 1.5)


def riser(length, level=0.35):
    n = int(SR * length)
    t = np.arange(n) / SR
    ramp = (t / length) ** 2
    noise = np.random.randn(n)
    # 時間とともに高域が開くノイズ（簡易フィルタスイープ）
    out = np.zeros(n)
    acc = 0.0
    for i in range(0, n, 256):
        a = 0.02 + 0.9 * ramp[i]
        seg = noise[i:i + 256]
        y = np.empty_like(seg)
        for j, v in enumerate(seg):
            acc += a * (v - acc)
            y[j] = acc
        out[i:i + 256] = y
    sweep = np.sin(2 * np.pi * np.cumsum(200 + 1800 * ramp) / SR) * 0.3
    return level * (out * 1.5 + sweep) * ramp


def pad(freqs, length, level=0.12):
    n = int(SR * length)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for f in freqs:
        for det in (-0.12, 0.0, 0.12):
            x += np.sin(2 * np.pi * f * (1 + det / 100) * t + np.random.rand() * 6.28)
    fade = np.minimum(1, np.minimum(t / 0.3, (length - t) / 0.4))
    return level * x / (len(freqs) * 3) * np.clip(fade, 0, 1)


def pluck(freq, level=0.25):
    n = int(SR * 0.35)
    t = np.arange(n) / SR
    x = np.sign(np.sin(2 * np.pi * freq * t)) * 0.5 + np.sin(2 * np.pi * freq * 2 * t) * 0.3
    return level * x * env_exp(n, 0.07)


def note(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


# ---------------------------------------------------------------- 配置
class Track:
    def __init__(self, length_s):
        self.buf = np.zeros(int(SR * (length_s + 3)))

    def add(self, sample, at):
        s = int(at * SR)
        if s < 0:
            sample = sample[-s:]
            s = 0
        e = min(len(self.buf), s + len(sample))
        self.buf[s:e] += sample[: e - s]


def sections_for(bars):
    """小節数から intro/build/drop/outro を割り振る。"""
    if bars <= 4:
        spec = [("intro", 1), ("build", 1), ("drop", bars - 3), ("outro", 1)]
    else:
        intro = max(1, round(bars * 0.25))
        build = max(1, round(bars * 0.2))
        outro = 1
        drop = bars - intro - build - outro
        spec = [("intro", intro), ("build", build), ("drop", drop), ("outro", outro)]
    out, b = [], 0
    for name, n in spec:
        if n > 0:
            out.append((name, b, b + n))
            b += n
    return out


def build(style, bpm, bars, seed):
    np.random.seed(seed)
    spb = 60.0 / bpm  # sec per beat
    step = spb / 4  # 16分
    swing = STYLES[style][1]
    length = bars * 4 * spb
    tr = Track(length)
    ev = {"kicks": [], "snares": [], "hats": [], "impacts": []}
    secs = sections_for(bars)

    def st(bar, s):  # bar, 16分ステップ -> 秒
        t = (bar * 16 + s) * step
        if swing and s % 2 == 1:
            t += step * swing
        return t

    def sec_of(bar):
        for name, a, b in secs:
            if a <= bar < b:
                return name
        return "outro"

    # 和音進行（マイナー寄り）
    prog = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]
    bass_root = [45, 41, 36, 43]

    for bar in range(bars):
        sec = sec_of(bar)
        chord = prog[bar % 4]
        root = bass_root[bar % 4]
        last_of_build = sec == "build" and sec_of(bar + 1) == "drop"

        def K(s, lvl=1.0):
            t = st(bar, s)
            tr.add(kick(lvl), t)
            ev["kicks"].append(t)

        def S(s, fn=snare, lvl=None):
            t = st(bar, s)
            tr.add(fn() if lvl is None else fn(lvl), t)
            ev["snares"].append(t)

        def H(s, lvl=0.25, o=False):
            t = st(bar, s)
            tr.add(hat(lvl, o), t)
            ev["hats"].append(t)

        def I(s=0, lvl=1.0):
            t = st(bar, s)
            tr.add(impact(lvl), t)
            ev["impacts"].append(t)

        if style in ("house", "future"):
            if sec in ("intro",):
                for s in (2, 6, 10, 14):
                    H(s, 0.2)
                if bar == 0:
                    tr.add(pad([note(m) for m in chord], 4 * spb), st(bar, 0))
            elif sec == "build":
                n = 16 if last_of_build else 8
                for i in range(n):
                    S(i * (16 // n), snare, 0.25 + 0.5 * i / n)
                if last_of_build or bars <= 4:
                    tr.add(riser(4 * spb), st(bar, 0))
            elif sec == "drop":
                if sec_of(bar - 1) != "drop":
                    I(0, 0.8)
                for s in (0, 4, 8, 12):
                    K(s)
                for s in (4, 12):
                    S(s, clap)
                for s in (2, 6, 10, 14):
                    H(s, 0.3, o=style == "house")
                for s in (2, 6, 10, 14):
                    tr.add(sub808(note(root - 12), 0.2, 0.45), st(bar, s))
                tr.add(pad([note(m) for m in chord], 4 * spb, 0.1), st(bar, 0))
                if style == "future":
                    for s in (0, 3, 6, 10, 12):
                        tr.add(pluck(note(chord[s % 3] + 12)), st(bar, s))
            else:  # outro
                I(0, 0.9)
                tr.add(pad([note(m) for m in prog[0]], 4 * spb, 0.12), st(bar, 0))

        elif style == "trap":
            if sec == "intro":
                tr.add(pad([note(m) for m in chord], 4 * spb, 0.14), st(bar, 0))
                for s in range(0, 16, 4):
                    H(s, 0.15)
            elif sec == "build":
                for s in range(0, 16, 2):
                    H(s, 0.22)
                if last_of_build:
                    for s in range(12, 16):
                        S(s, snare, 0.3 + 0.1 * (s - 12))
                    tr.add(riser(4 * spb, 0.3), st(bar, 0))
            elif sec == "drop":
                if sec_of(bar - 1) != "drop":
                    I(0, 0.7)
                for s in (0, 7, 10):
                    K(s, 0.9)
                    tr.add(sub808(note(root - 12), 0.5), st(bar, s))
                S(8, clap, 0.75)
                for s in range(0, 16, 2):
                    H(s, 0.22)
                for s in (13, 14, 15):  # ロール
                    for k in range(2):
                        t = st(bar, s) + k * step / 2
                        tr.add(hat(0.18), t)
                tr.add(pad([note(m) for m in chord], 4 * spb, 0.08), st(bar, 0))
            else:
                I(0, 0.8)
                tr.add(sub808(note(bass_root[0] - 12), 2.0, 0.6), st(bar, 0))

        elif style == "lofi":
            tr.add(pad([note(m) for m in chord + [chord[0] + 11]], 4 * spb, 0.15), st(bar, 0))
            if sec == "intro":
                for s in range(0, 16, 2):
                    H(s, 0.12)
            elif sec in ("build", "drop"):
                K(0, 0.8)
                K(10, 0.7)
                if sec == "drop":
                    K(7, 0.5)
                S(4, snare, 0.5)
                S(12, snare, 0.5)
                for s in range(0, 16, 2):
                    H(s, 0.16 if s % 4 else 0.2)
                tr.add(sub808(note(root - 12), 1.0, 0.35), st(bar, 0))
                if last_of_build:
                    tr.add(riser(2 * spb, 0.15), st(bar, 8))
            else:
                K(0, 0.6)
            # レコードノイズ
            n = int(4 * spb * SR)
            crackle = (np.random.rand(n) > 0.9993) * np.random.randn(n) * 0.25
            crackle += np.random.randn(n) * 0.004
            tr.add(crackle, st(bar, 0))

        elif style == "cinematic":
            if sec == "intro":
                if bar == 0:
                    I(0, 0.9)
                tr.add(pad([note(m - 12) for m in chord], 4 * spb, 0.16), st(bar, 0))
                for s in (0, 8):
                    tr.add(tom(55, 0.5), st(bar, s))
                    ev["kicks"].append(st(bar, s))
            elif sec == "build":
                for i, s in enumerate(range(0, 16, 2 if not last_of_build else 1)):
                    tr.add(tom(90 + i * 3, 0.35 + i * 0.03), st(bar, s))
                    ev["snares"].append(st(bar, s))
                if last_of_build or bars <= 4:
                    tr.add(riser(4 * spb, 0.4), st(bar, 0))
                tr.add(pad([note(m - 12) for m in chord], 4 * spb, 0.16), st(bar, 0))
            elif sec == "drop":
                I(0, 1.0)
                for s in (0, 3, 6, 10, 12, 14):
                    tr.add(tom(65 if s in (0, 6, 12) else 110, 0.8), st(bar, s))
                    (ev["kicks"] if s in (0, 6, 12) else ev["snares"]).append(st(bar, s))
                for s in range(0, 16, 2):  # 8分のパルスベース
                    tr.add(sub808(note(root - 12), 0.18, 0.4), st(bar, s))
                tr.add(pad([note(m) for m in chord], 4 * spb, 0.12), st(bar, 0))
            else:
                I(0, 1.0)
                tr.add(pad([note(m - 12) for m in prog[0]], 4 * spb, 0.14), st(bar, 0))

    # マスター：簡易リバーブ（フィードバックディレイ×2）→ ソフトクリップ
    x = tr.buf
    wet = np.zeros_like(x)
    for d, g in ((0.043, 0.28), (0.071, 0.22), (0.113, 0.16)):
        k = int(d * SR)
        w = np.zeros_like(x)
        w[k:] = x[:-k] * g
        wet += w
    x = x + wet * 0.5
    end = int((length + 1.5) * SR)
    x = x[:end]
    fade = int(1.5 * SR)
    x[-fade:] *= np.linspace(1, 0, fade)
    x = np.tanh(x * 0.9)
    x = x / (np.max(np.abs(x)) + 1e-9) * 0.89

    beats = [i * spb for i in range(bars * 4)]
    grid = {
        "style": style,
        "bpm": bpm,
        "bars": bars,
        "seconds_per_beat": spb,
        "duration": length,
        "audio_duration": len(x) / SR,
        "beats": beats,
        "downbeats": [b * 4 * spb for b in range(bars)],
        "sections": [{"name": n, "start_bar": a, "end_bar": b, "start": a * 4 * spb, "end": b * 4 * spb}
                     for n, a, b in secs],
        "drop_time": next((a * 4 * spb for n, a, b in secs if n == "drop"), None),
    }
    for k in ev:
        grid[k] = sorted(round(t, 4) for t in set(round(v, 4) for v in ev[k]))
    return x, grid


def write_wav(path, mono):
    stereo = np.stack([mono, mono], axis=1)
    data = (np.clip(stereo, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", choices=STYLES, default="future")
    ap.add_argument("--bpm", type=float)
    ap.add_argument("--duration", type=float, default=15.0, help="目標秒数（小節単位に丸める）")
    ap.add_argument("--bars", type=int, help="小節数を直接指定（--duration より優先）")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="beat", help="出力パス（拡張子なし）→ .wav と .json")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        for k, (bpm, _, d) in STYLES.items():
            print(f"{k:10s} {bpm:>4} BPM  {d}")
        return
    bpm = a.bpm or STYLES[a.style][0]
    bars = a.bars or max(4, round(a.duration * bpm / 240))
    audio, grid = build(a.style, bpm, bars, a.seed)
    write_wav(a.out + ".wav", audio)
    with open(a.out + ".json", "w") as f:
        json.dump(grid, f, ensure_ascii=False, indent=1)
    print(f"{a.style} {bpm}BPM {bars}bars = {grid['duration']:.2f}s  drop@{grid['drop_time']:.2f}s")
    print("sections:", ", ".join(f"{s['name']} {s['start']:.2f}-{s['end']:.2f}" for s in grid["sections"]))


if __name__ == "__main__":
    main()
