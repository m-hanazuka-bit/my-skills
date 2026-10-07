#!/usr/bin/env python3
"""生成したナレーションを参考CMと数値で比べる表を出す（Claude は音を聴けないので、判断材料はこれと人の耳）。

  python voice_report.py --profile work/profile.json work/matched/*.wav
  python voice_report.py --profile work/profile.json work/matched/*.wav --markdown   # ユーザーに見せる表

項目:
  高さ      声の高さの中央値と 10〜90% の範囲（Hz）
  jitter    周期のゆらぎ（%）。大きいほどガサガサ
  shimmer   振幅のゆらぎ（%）。大きいほどガサガサ
  HNR       声の澄み具合（dB）。小さいほど息や雑音が混じって濁る
  明るさ    スペクトル重心（Hz）。低いほどこもった音
  音色差    元CMとの 1/6 オクターブ平均スペクトルの差（90〜7000Hz の RMS、dB）。小さいほど近い
  間のずれ  元CMの句の開始時刻とのずれの平均（秒）
"""
import argparse, json
from pathlib import Path

import numpy as np
import audio_common as ac


def timing_error(x, ref_phrases):
    pairs = ac.align(ac.segments(x), ref_phrases)
    return float(np.mean([abs(seg[0] - t) for seg, t in pairs]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--profile", required=True)
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--no-timing", action="store_true", help="間のずれを出さない（元CMと違う台本のとき）")
    a = ap.parse_args()
    prof = json.loads(Path(a.profile).read_text())
    rows = [("元CM", prof, None, None, None)]
    for f in a.files:
        x = ac.load(f); v = ac.voice_only(x)
        rows.append((Path(f).stem, ac.voice_metrics(v), ac.ltas_distance(ac.ltas(v), prof["ltas_db"]),
                     None if a.no_timing else timing_error(x, prof["phrases_sec"]), len(x) / ac.SR))
    head = ["", "長さ", "高さ（範囲）", "jitter", "shimmer", "HNR", "明るさ", "音色差", "間のずれ"]
    body = []
    for name, m, dist, terr, dur in rows:
        body.append([name,
                     f"{dur:.1f}s" if dur else f"{prof['range_sec'][1] - prof['range_sec'][0]:.1f}s",
                     f"{m['f0_median_hz']:.0f}Hz（{m['f0_p10_hz']:.0f}〜{m['f0_p90_hz']:.0f}）",
                     f"{m['jitter_pct']:.2f}%", f"{m['shimmer_pct']:.1f}%", f"{m['hnr_db']:.1f}dB",
                     f"{m['centroid_hz']:.0f}Hz",
                     "-" if dist is None else f"{dist:.1f}dB", "-" if terr is None else f"{terr:.2f}s"])
    if a.markdown:
        print("| " + " | ".join(head) + " |"); print("|" + "---|" * len(head))
        for r in body: print("| " + " | ".join(r) + " |")
    else:
        w = [max(len(r[i]) for r in body + [head]) + 2 for i in range(len(head))]
        for r in [head] + body: print("".join(c.ljust(w[i]) for i, c in enumerate(r)))
    if prof.get("snr_db") is not None and prof["snr_db"] < 30:
        print(f"\n注: 元CMは句の中と句の間の音量差が {prof['snr_db']}dB しかなく、声の下に音楽が入っている。"
              "元CMの HNR・shimmer は実際の声より濁った値に出ているので、そこだけを追いかけすぎない。")


if __name__ == "__main__":
    main()
