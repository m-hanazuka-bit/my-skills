#!/usr/bin/env python3
"""TTS ナレーションを参考CMの間・声の高さ・音色に合わせる後処理。

  1. 句ごとに切り出し、元CMと同じ開始時刻に並べ直す（間を合わせる）
  2. 声の高さの中央値を元CMに合わせる（PSOLA。声の響き＝フォルマントと抑揚の幅は保つ）
  3. ソフトクリップで濁り（ざらつき）を足す。--husk で息漏れのかすれも足せる
  4. 元CMの長時間平均スペクトルに合わせて EQ する（古いテレビCMの狭い帯域・中域の張り）

  python match_ref.py --profile work/profile.json work/tts/tts_*.wav --out-dir work/matched
  python match_ref.py --profile work/profile.json work/tts/tts_Algenib.wav --husk 0.5 --suffix _husk05

出力: <out-dir>/<元の名前><suffix>.wav（24kHz / 16bit / mono）
"""
import argparse, json
from pathlib import Path

import numpy as np
import audio_common as ac

SR = ac.SR


def retime(x, ref_phrases, verbose=True):
    """TTS の句を元CMの句の開始時刻に並べ直す。前の句が長くて重なる場合は後ろへずらす。"""
    pairs = ac.align(ac.segments(x), ref_phrases)
    pre, post = int(0.04 * SR), int(0.12 * SR)  # 子音の立ち上がりと語尾の余韻を残す
    out = np.zeros(int((ref_phrases[-1][1] + 6) * SR)); cursor = 0
    for (a, b), t in pairs:
        clip = x[max(0, int(a * SR) - pre):int(b * SR) + post]
        i = max(int(t * SR) - pre, cursor)
        out[i:i + len(clip)] += clip; cursor = i + len(clip) - post
        if verbose: print(f"   TTS {a:5.2f}-{b:5.2f}s → {i / SR + 0.04:5.2f}s（元CM {t:5.2f}s）")
    return out[:cursor + post + int(0.5 * SR)]


def match_pitch(x, target_hz):
    import parselmouth
    from parselmouth.praat import call
    y = call(parselmouth.Sound(x, SR), "Change gender", 50, 300, 1.0, target_hz, 1.0, 1.0)
    return y.values[0]


def grit(x, drive):
    """ソフトクリップで倍音と濁りを足す。drive=0 で素通し。"""
    if drive <= 0: return x
    x = x / np.max(np.abs(x))
    return np.tanh(drive * x) / np.tanh(drive)


def lpc(frame, order):
    """自己相関法＋Levinson-Durbin で LPC 係数 [1, a1..ap] を返す。"""
    r = np.correlate(frame, frame, "full")[len(frame) - 1:len(frame) + order]
    if r[0] <= 0: return np.r_[1.0, np.zeros(order)]
    r[0] *= 1 + 1e-9
    a = np.zeros(order + 1); a[0] = 1.0; err = r[0]
    for i in range(1, order + 1):
        k = -(r[i] + a[1:i] @ r[i - 1:0:-1]) / err
        a[1:i + 1] = a[1:i + 1] + k * np.r_[a[i - 1:0:-1], 1.0]
        err *= 1 - k * k
    return a


def husk(x, amount, order=20, seed=0):
    """かすれ（息漏れ）を足す。声の母音の響き（LPC 包絡）で白色雑音を色付けした「ささやき声」を作り、
    声の音量に沿わせて混ぜる。句の間の無音には入らない。amount は声に対する息成分の比（0 で無効）。"""
    if amount <= 0: return x
    n, hop = 1024, 256; win = np.hanning(n)
    noise = np.random.default_rng(seed).standard_normal(len(x) + n)
    pre = np.r_[x[0], x[1:] - 0.9 * x[:-1]]  # プリエンファシスで高域の包絡も拾う
    out = np.zeros(len(x) + n); norm = np.zeros(len(x) + n)
    for i in range(0, len(x) - n, hop):
        a = lpc(pre[i:i + n] * win, order)
        w = np.fft.irfft(np.fft.rfft(noise[i:i + n] * win) / np.abs(np.fft.rfft(a, n)), n)
        e = np.sqrt((x[i:i + n] ** 2 * win).mean())
        out[i:i + n] += w / (np.sqrt((w * w).mean()) + 1e-12) * e * win
        norm[i:i + n] += win ** 2
    breath = out[:len(x)] / np.maximum(norm[:len(x)], 1e-3)
    breath = breath - np.convolve(breath, np.ones(24) / 24, "same")  # 息は高めの帯域に多いので 1kHz 以下を弱める
    breath *= np.sqrt((x * x).mean()) / (np.sqrt((breath * breath).mean()) + 1e-12)
    return x + amount * breath


def match_eq(x, target_db, lo=90, hi=7000, max_db=15):
    """元CMとのスペクトル差を FIR フィルタにしてかける。
    lo〜hi Hz の外は、元CMの低いうなりや高域ノイズまで真似ないよう、削る方向だけにする。"""
    c = ac.CENTERS
    diff = np.clip(np.asarray(target_db) - ac.ltas(ac.voice_only(x)), -max_db, max_db)
    outside = (c < lo) | (c > hi)
    diff[outside] = np.minimum(diff[outside], 0)
    diff = np.convolve(np.pad(diff, 2, mode="edge"), np.ones(5) / 5, "valid")  # 細かい凹凸をならす
    n = 1025; f = np.fft.rfftfreq(2 * (n - 1), 1 / SR)
    g = 10 ** (np.interp(np.log(np.maximum(f, 1)), np.log(c), diff) / 20)
    h = np.fft.irfft(g); h = np.roll(h, len(h) // 2) * np.hanning(len(h))
    return np.convolve(x, h, "same")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--profile", required=True, help="analyze_ref.py が作った profile.json")
    ap.add_argument("--out-dir", help="出力先（省略時は入力と同じフォルダ）")
    ap.add_argument("--suffix", default="_matched")
    ap.add_argument("--drive", type=float, default=3.0, help="濁り（ざらつき）の強さ。0 で無効、目安 0〜6")
    ap.add_argument("--husk", type=float, default=0.0, help="かすれ（息漏れ）の強さ。0 で無効、目安 0.3〜1.2")
    ap.add_argument("--pitch", type=float, help="声の高さの中央値（Hz）。省略時は元CMに合わせる、0 で変えない")
    ap.add_argument("--no-retime", action="store_true", help="間を並べ直さない")
    ap.add_argument("--eq-lo", type=float, default=90)
    ap.add_argument("--eq-hi", type=float, default=7000)
    a = ap.parse_args()
    prof = json.loads(Path(a.profile).read_text())
    pitch = prof["f0_median_hz"] if a.pitch is None else a.pitch
    for p in a.inputs:
        print(Path(p).name)
        x = ac.load(p)
        if not a.no_retime: x = retime(x, prof["phrases_sec"])
        if pitch > 0: x = match_pitch(x, pitch)
        x = grit(x, a.drive)
        x = husk(x, a.husk)
        x = match_eq(x, prof["ltas_db"], a.eq_lo, a.eq_hi)
        x = match_eq(x, prof["ltas_db"], a.eq_lo, a.eq_hi)  # 歪みと EQ の相互作用を詰めるため 2 回
        out = Path(a.out_dir or Path(p).parent) / (Path(p).stem + a.suffix + ".wav")
        ac.save(out, x)
        print("wrote", out)


if __name__ == "__main__":
    main()
