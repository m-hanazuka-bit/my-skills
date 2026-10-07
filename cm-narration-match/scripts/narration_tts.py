#!/usr/bin/env python3
"""台本を Gemini TTS で複数の声に読ませる（声の候補を聴き比べるため）。

  python narration_tts.py --script work/script.txt --style work/style.txt \
      --voices Algenib Gacrux Enceladus Rasalgethi Alnilam --out work/tts

出力: <out>/tts_<voice>.wav（24kHz / 16bit / mono）。--takes 2 なら tts_<voice>_2.wav も作る。
"""
import argparse, base64
from pathlib import Path

import numpy as np
import audio_common as ac


def prompt(style, text):
    # 演出メモと台本を見出しで分け「台本だけ読む」と明示する。
    # 分けずに続けて書くと、Gemini TTS は演出メモまで声に出して読んでしまう。
    return f"### 演出メモ（読み上げない）\n{style}\n\n### 台本（ここだけを読み上げる）\n{text}"


def synth(voice, style, text, model):
    res = ac.gemini(model, [{"text": prompt(style, text)}], {
        "responseModalities": ["AUDIO"],
        "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
    })
    pcm = base64.b64decode(ac.first_part(res)["inlineData"]["data"])
    return np.frombuffer(pcm, np.int16).astype(float) / 32768


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True, help="台本（UTF-8 テキスト。句ごとに空行で区切ると間を取りやすい）")
    ap.add_argument("--style", required=True, help="演出メモのテキストファイル")
    ap.add_argument("--voices", nargs="+", default=["Algenib", "Gacrux", "Enceladus", "Rasalgethi", "Alnilam"])
    ap.add_argument("--takes", type=int, default=1, help="1 声あたりの生成回数（同じ指示でも毎回少し違う）")
    ap.add_argument("--model", default=ac.TTS_MODEL)
    ap.add_argument("--out", default="work/tts")
    a = ap.parse_args()
    text = Path(a.script).read_text(encoding="utf-8").strip()
    style = Path(a.style).read_text(encoding="utf-8").strip()
    for v in a.voices:
        for k in range(1, a.takes + 1):
            out = Path(a.out) / (f"tts_{v}.wav" if k == 1 else f"tts_{v}_{k}.wav")
            x = synth(v, style, text, a.model)
            # 音量はそのまま保存（正規化は後処理でする）
            ac.save(out, x)
            print(f"wrote {out}（{len(x) / ac.SR:.1f} 秒）")


if __name__ == "__main__":
    main()
