#!/usr/bin/env python3
"""TTS ナレーションを参考CMの間・声の高さ・音色に合わせる後処理。

  1. 句ごとに切り出し、元CMと同じ開始時刻に並べ直す（間を合わせる）
     参考CMと違う台本を読ませたときは --script と --gaps で、台本の句読点ごとに決めた長さの間を入れる
  2. 声の高さの中央値を元CMに合わせる（PSOLA。声の響き＝フォルマントと抑揚の幅は保つ）
  3. ソフトクリップで濁り（ざらつき）を足す。--husk で息漏れのかすれも足せる
  4. 元CMの長時間平均スペクトルに合わせて EQ する（古いテレビCMの狭い帯域・中域の張り）

  python match_ref.py --profile work/profile.json work/tts/tts_*.wav --out-dir work/matched
  python match_ref.py --profile work/profile.json work/tts/tts_Algenib.wav --husk 0.5 --suffix _husk05
  python match_ref.py --profile 別のCMのprofile.json tts_Algenib.wav --script script.txt --gaps "、=0.5,。=1.0"

出力: <out-dir>/<元の名前><suffix>.wav（24kHz / 16bit / mono）
"""
import argparse, json, re
from pathlib import Path

import numpy as np
import audio_common as ac

SR = ac.SR


def place(x, pairs, labels=None):
    """[(TTS の区間 [開始, 終了], 置く時刻)] のとおりに句を並べる。前の句が長くて重なる場合は後ろへずらす。"""
    pre, post = int(0.04 * SR), int(0.12 * SR)  # 子音の立ち上がりと語尾の余韻を残す
    out = np.zeros(int((pairs[-1][1] + 10) * SR)); cursor = 0
    for k, ((a, b), t) in enumerate(pairs):
        clip = x[max(0, int(a * SR) - pre):int(b * SR) + post]
        i = max(int(t * SR) - pre, cursor)
        out[i:i + len(clip)] += clip; cursor = i + len(clip) - post
        print(f"   TTS {a:5.2f}-{b:5.2f}s → {i / SR + 0.04:5.2f}s（{labels[k] if labels else f'元CM {t:5.2f}s'}）")
    return out[:cursor + post + int(0.5 * SR)]


def retime(x, ref_phrases):
    """TTS の句を元CMの句の開始時刻に並べ直す。"""
    return place(x, ac.align(ac.segments(x), ref_phrases))


PUNCT = "、。，．,.！？!?"


def script_phrases(text):
    """台本を句読点で句に分け、[(句, 句末の記号)] を返す。"""
    return [(m.group(0), m.group(1)) for m in re.finditer(rf"[^{PUNCT}\s]+([{PUNCT}]?)", text)]


def mora_weight(s):
    """句のおおよその長さ（拍数の目安）。漢字は 2 拍、小さい「ゃゅょ」などは 0 拍として数える。"""
    return max(1, sum(0 if ch in PUNCT + "ゃゅょぁぃぅぇぉャュョァィゥェォ" else 2 if "\u4e00" <= ch <= "\u9fff" else 1
                      for ch in s))


def retime_by_gaps(x, text, gaps, lead=0.15):
    """台本の句読点ごとに決めた長さの間を入れて並べ直す（参考CMと違う台本を読ませたとき用）。
    TTS の区間と台本の句の対応は、拍数で按分した仮の長さを使って align() で決める。"""
    phrases = script_phrases(text)
    segs = ac.segments(x)
    voiced = sum(b - a for a, b in segs); w = [mora_weight(t) for t, _ in phrases]
    pseudo, t = [], 0.0
    for (_, p), wi in zip(phrases, w):
        d = voiced * wi / sum(w); pseudo.append([t, t + d]); t += d + gaps.get(p, 0.3)
    pairs = ac.align(segs, pseudo)
    starts = [[round(a, 6) for a, _ in pseudo].index(round(t0, 6)) for _, t0 in pairs] + [len(phrases)]
    out_pairs, labels, onset = [], [], lead
    for k, ((a, b), _) in enumerate(pairs):
        group = phrases[starts[k]:starts[k + 1]]
        gap = gaps.get(group[-1][1], 0.3) if k + 1 < len(pairs) else 0.0
        out_pairs.append(([a, b], onset))
        labels.append("".join(g for g, _ in group) + (f" ＋間 {gap:.2f}s" if k + 1 < len(pairs) else ""))
        if len(group) > 1:
            labels[-1] += "  ※TTS が句読点で区切らずに読んだので、この中には間を入れられない"
        onset += (b - a) + gap
    return place(x, out_pairs, labels)


def parse_gaps(spec):
    """'、=0.5,。=1.0' → {'、': 0.5, '。': 1.0, ...}。指定しなかった「！？」などは「。」と同じにする。"""
    g = {k.strip(): float(v) for k, v in (kv.split("=") for kv in spec.split(","))}
    for ch in "．.！？!?": g.setdefault(ch, g.get("。", 1.0))
    for ch in "，,": g.setdefault(ch, g.get("、", 0.5))
    g.setdefault("", 0.3)
    return g


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
    ap.add_argument("--script", help="--gaps と一緒に使う台本（TTS に読ませたもの）")
    ap.add_argument("--gaps", help="句読点ごとの間（秒）。例 '、=0.5,。=1.0'。指定すると元CMの時刻ではなく台本の句読点で間を決める")
    ap.add_argument("--eq-lo", type=float, default=90)
    ap.add_argument("--eq-hi", type=float, default=7000)
    a = ap.parse_args()
    if a.gaps and not a.script: ap.error("--gaps には --script も指定する")
    prof = json.loads(Path(a.profile).read_text())
    pitch = prof["f0_median_hz"] if a.pitch is None else a.pitch
    for p in a.inputs:
        print(Path(p).name)
        x = ac.load(p)
        if a.gaps: x = retime_by_gaps(x, Path(a.script).read_text(encoding="utf-8"), parse_gaps(a.gaps))
        elif not a.no_retime: x = retime(x, prof["phrases_sec"])
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
