#!/usr/bin/env python3
"""尺八 →「風が語りかけます。」→ 鳥のさえずり → 清水ナレーション を 1 本の音声にする。

  python3 audio/shimizu/build_cm.py
  python3 audio/shimizu/build_cm.py --shimizu audio/shimizu/tts_Algenib_cm.wav   # 清水の別テイクで作る

出力: audio/shimizu/shimizu_cm_full.wav（44.1kHz / 16bit / stereo）と .mp3
"""
import argparse, subprocess, wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
AUDIO = HERE.parent
SR = 44100


def load(path, channels=2):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", str(channels), "-ar", str(SR),
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(float).reshape(-1, channels) / 32768


def rms_db(x):
    return 20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-12)


def voice_rms_db(x):
    """無音を除いた部分の音量（dB）。"""
    m = x.mean(1); h = SR // 50
    fr = np.array([np.sqrt((m[i:i + h] ** 2).mean()) for i in range(0, len(m) - h, h)])
    return 20 * np.log10(fr[fr > fr.max() * 0.1].mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shimizu", default=HERE / "tts_Algenib_3_cm.wav", help="清水ナレーションのファイル")
    ap.add_argument("--kaze", default=AUDIO / "juumangoku/narration_Algenib_cm.wav",
                    help="「風が語りかけます」を切り出す元（十万石の採用版）")
    ap.add_argument("--kaze-range", default="0.54,2.84", help="切り出す範囲（秒）")
    ap.add_argument("--out", default=HERE / "shimizu_cm_full.wav")
    a = ap.parse_args()

    shaku = load(AUDIO / "juumangoku/shakuhachi.wav")
    birds = load(AUDIO / "juumangoku/birds.wav")
    k0, k1 = map(float, a.kaze_range.split(","))
    kaze = load(a.kaze)[int(k0 * SR):int(k1 * SR)]
    kaze[:int(0.02 * SR)] *= np.linspace(0, 1, int(0.02 * SR))[:, None]  # 切り口のプチッを防ぐ
    kaze[-int(0.08 * SR):] *= np.linspace(1, 0, int(0.08 * SR))[:, None]
    shimizu = load(a.shimizu)

    # 音量：声を基準に、尺八は声より 2dB、鳥は声より 4dB 控えめ（鳴っている所の音量で比べる）
    v = voice_rms_db(np.vstack([kaze, shimizu]))
    shaku *= 10 ** ((v - 2 - voice_rms_db(shaku)) / 20)
    birds *= 10 ** ((v - 4 - voice_rms_db(birds)) / 20)

    # 並べる時刻（秒）。尺八は 3.3 秒ほどで消えはじめるので、余韻に声をかぶせる
    parts = [(0.0, shaku, "尺八"), (3.6, kaze, "風が語りかけます。"),
             (6.6, birds, "鳥のさえずり"), (10.1, shimizu, "清水ナレーション")]
    end = max(t + len(x) / SR for t, x, _ in parts) + 0.5
    mix = np.zeros((int(end * SR), 2))
    for t, x, name in parts:
        i = int(t * SR); mix[i:i + len(x)] += x
        print(f"{t:5.1f}〜{t + len(x) / SR:5.1f}s  {name}")
    mix[-int(0.3 * SR):] *= np.linspace(1, 0, int(0.3 * SR))[:, None]
    mix *= 10 ** (-1 / 20) / np.max(np.abs(mix))  # ピーク -1dBFS

    out = Path(a.out)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-b:a", "192k", str(out.with_suffix(".mp3"))],
                   check=True)
    print(f"wrote {out}（{len(mix) / SR:.1f} 秒）と {out.with_suffix('.mp3').name}")


if __name__ == "__main__":
    main()
