#!/usr/bin/env python3
"""生成したナレーションを Gemini で書き起こし、台本どおりに読めているかを確かめる。

  python transcribe.py work/tts/*.wav --expect work/script.txt

演出メモまで読み上げていると、書き起こしが台本よりずっと長くなる（長さの比を表示して警告する）。
"""
import argparse, difflib, re
from pathlib import Path

import audio_common as ac


def norm(s):
    return re.sub(r"[\s、。，．,.！!？?「」『』…・ー〜]", "", s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--expect", help="台本ファイル。指定すると一致度を出す")
    a = ap.parse_args()
    exp = norm(Path(a.expect).read_text(encoding="utf-8")) if a.expect else None
    for f in a.files:
        x = ac.load(f)
        t = ac.transcribe(x)
        print(f"== {Path(f).name}（{len(x) / ac.SR:.1f} 秒）==\n{t}")
        if exp:
            got = norm(t)
            ratio = difflib.SequenceMatcher(None, exp, got).ratio()
            lr = len(got) / max(len(exp), 1)
            warn = ""
            if lr > 1.5: warn = "  ← 台本よりかなり長い。演出メモを読み上げている可能性"
            elif ratio < 0.8: warn = "  ← 台本と食い違いが大きい（漢字/かなの表記ゆれだけなら問題なし）"
            print(f"   一致度 {ratio:.2f} / 長さの比 {lr:.2f}{warn}")


if __name__ == "__main__":
    main()
