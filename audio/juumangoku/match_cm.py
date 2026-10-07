"""TTSナレーションを元CMの間・音色に合わせる後処理。

  1. 句ごとに切り出し、元CMと同じ開始時刻に並べ直す（間を合わせる）
  2. 声の高さ（F0中央値）を元CMに合わせる（フォルマントは保つ）
  3. 軽い歪みで濁りを足す
  4. 元CMの長時間平均スペクトルに合わせてEQする（古いテレビCMの帯域・中域の張り）

使い方:
  python3 match_cm.py narration_Algenib.wav ...            # cm_profile.json を使う
  python3 match_cm.py --ref 元CM.mp4 --ref-start 7.0 --ref-end 17.4 narration_*.wav
      # 元CM音声からプロファイルを測り直して cm_profile.json に保存する
出力: narration_<voice>_cm.wav（24kHz / 16bit / mono）
"""
import argparse, json, subprocess, wave
from pathlib import Path
import numpy as np
import parselmouth
from parselmouth.praat import call

HERE = Path(__file__).parent
PROFILE = HERE / "cm_profile.json"
SR = 24000
# 1/6オクターブ帯の中心周波数（EQカーブの評価点）
CENTERS = 50 * 2 ** (np.arange(0, 48) / 6)
CENTERS = CENTERS[CENTERS < SR / 2 * 0.95]


def load(path):
    """任意の音声/動画を 24kHz mono float で読む。"""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
        capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(float) / 32768


def save(path, x):
    x = x / np.max(np.abs(x)) * 0.89
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def bandpass(x, lo=100, hi=4000):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, len(x))


def segments(x, n_phrases=None):
    """声の区間 [(開始秒, 終了秒)] を返す。n_phrases を渡すと間の短い所から結合してその数にする。
    TTSは「風が、語りかけます」を読点で2つに割りやすいので、句が1つ多いときは先頭2つを結合する。"""
    y = bandpass(x); h = SR // 100
    e = np.array([20 * np.log10(np.sqrt((y[i:i + h] ** 2).mean()) + 1e-9) for i in range(0, len(y) - h, h)])
    on = e > e.max() - 25
    segs, st = [], None
    for i, v in enumerate(on):
        if v and st is None: st = i
        if not v and st is not None: segs.append([st, i]); st = None
    if st is not None: segs.append([st, len(on)])
    m = []
    for a, b in segs:
        if m and a - m[-1][1] < 15: m[-1][1] = b
        else: m.append([a, b])
    m = [[a / 100, b / 100] for a, b in m if b - a >= 15]  # 150ms未満は息・ノイズとして捨てる
    if n_phrases and len(m) == n_phrases + 1:
        m[0][1] = m.pop(1)[1]
    while n_phrases and len(m) > n_phrases:
        i = int(np.argmin([m[k + 1][0] - m[k][1] for k in range(len(m) - 1)]))
        m[i][1] = m.pop(i + 1)[1]
    return m


def ltas(x):
    """有声部の長時間平均スペクトルを1/6オクターブ帯で返す（dB、最大0）。"""
    n = 2048; win = np.hanning(n)
    fr = [x[i:i + n] * win for i in range(0, len(x) - n, n // 2)]
    rms = np.array([np.sqrt((v * v).mean()) for v in fr])
    P = np.mean([np.abs(np.fft.rfft(v)) ** 2 for v, r in zip(fr, rms) if r > rms.max() * 0.1], 0)
    f = np.fft.rfftfreq(n, 1 / SR)
    e = np.array([P[(f >= c / 2 ** (1 / 12)) & (f < c * 2 ** (1 / 12))].sum() for c in CENTERS])
    e = 10 * np.log10(e + 1e-12)
    return e - e.max()


def measure_profile(ref, start, end):
    x = load(ref)[int(start * SR):int(end * SR)]
    segs = segments(x)
    onsets = [round(a, 2) for a, _ in segments(x, n_phrases=6)]
    prof = {"source": Path(ref).name, "range_sec": [start, end], "phrase_onsets_sec": onsets,
            "f0_median_hz": round(f0_median(x), 1),
            "ltas_centers_hz": [round(c, 1) for c in CENTERS], "ltas_db": [round(v, 2) for v in ltas(x)],
            "voice_segments_sec": segs}
    PROFILE.write_text(json.dumps(prof, ensure_ascii=False, indent=1))
    print("wrote", PROFILE, "onsets", onsets)
    return prof


def retime(x, onsets):
    """句を元CMの開始時刻に並べ直す。前の句が長くて重なる場合は後ろへずらす。"""
    segs = segments(x, n_phrases=len(onsets))
    if len(segs) != len(onsets):
        raise SystemExit(f"句が {len(segs)} 個しか検出できない（{len(onsets)} 個必要）")
    pre, post = int(0.04 * SR), int(0.12 * SR)  # 子音の立ち上がりと語尾の余韻を残す
    out = np.zeros(int((onsets[-1] + 4) * SR)); cursor = 0
    for (a, b), t in zip(segs, onsets):
        clip = x[max(0, int(a * SR) - pre):int(b * SR) + post]
        i = max(int(t * SR) - pre, cursor)
        out[i:i + len(clip)] += clip; cursor = i + len(clip) - post
    return out[:cursor + post + int(0.5 * SR)]


def f0_median(x):
    p = parselmouth.Sound(x, SR).to_pitch_ac(0.01, 50, 300).selected_array["frequency"]
    return float(np.median(p[p > 0]))


def match_pitch(x, target_hz):
    """PSOLAで声の高さの中央値を target_hz に移す（抑揚の幅とフォルマントは保つ）。"""
    s = parselmouth.Sound(x, SR)
    y = call(s, "Change gender", 50, 300, 1.0, target_hz, 1.0, 1.0)
    return y.values[0]


def match_eq(x, target_db, max_db=15, lo=90, hi=7000):
    """元CMとのスペクトル差をFIRフィルタにしてかける。
    lo〜hi Hz の外は元CMの低いうなりや高域ノイズを真似ないよう、削る方向だけにする。"""
    diff = np.clip(np.asarray(target_db) - ltas(x), -max_db, max_db)
    out = (CENTERS < lo) | (CENTERS > hi)
    diff[out] = np.minimum(diff[out], 0)
    diff = np.convolve(np.pad(diff, 2, mode="edge"), np.ones(5) / 5, "valid")  # 細かい凹凸をならす
    n = 1025; f = np.fft.rfftfreq(2 * (n - 1), 1 / SR)
    g = 10 ** (np.interp(np.log(np.maximum(f, 1)), np.log(CENTERS), diff) / 20)
    h = np.fft.irfft(g); h = np.roll(h, len(h) // 2) * np.hanning(len(h))
    return np.convolve(x, h, "same")


def grit(x, drive):
    """ソフトクリップで倍音と濁りを足す。drive=0 で素通し。"""
    if drive <= 0: return x
    x = x / np.max(np.abs(x))
    return np.tanh(drive * x) / np.tanh(drive)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--ref", help="元CMの音声/動画。指定するとプロファイルを測り直す")
    ap.add_argument("--ref-start", type=float, default=7.0)
    ap.add_argument("--ref-end", type=float, default=17.4)
    ap.add_argument("--drive", type=float, default=3.0, help="濁りの強さ（0で無効）")
    a = ap.parse_args()
    prof = measure_profile(a.ref, a.ref_start, a.ref_end) if a.ref else json.loads(PROFILE.read_text())
    for p in a.inputs:
        x = retime(load(p), prof["phrase_onsets_sec"])
        x = match_pitch(x, prof["f0_median_hz"])
        x = grit(x, a.drive)
        x = match_eq(x, prof["ltas_db"])
        x = match_eq(x, prof["ltas_db"])  # 歪みとEQの相互作用を詰めるため2回
        out = HERE / (Path(p).stem + "_cm.wav")
        save(out, x)
        print("wrote", out)


if __name__ == "__main__":
    main()
