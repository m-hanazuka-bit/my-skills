#!/usr/bin/env python3
"""参考CM（動画/音声）のナレーションを解析して profile.json と台本の下書きを作る。

  python analyze_ref.py 元CM.mp4 --out work
  python analyze_ref.py 元CM.mp4 --out work --start 7.0 --end 17.4   # ナレーションの範囲を手で指定

出力:
  <out>/ref_transcript.json  Gemini の書き起こし（フレーズごとの時刻、音楽・効果音の区間）
  <out>/script.txt           ナレーション台本の下書き（元CMの書き起こし。必ず人が見て確かめる）
  <out>/profile.json         句の時刻・声の高さ・声質・スペクトル（match_ref.py / voice_report.py が使う）
元CMの音声そのものは profile.json に入らないので、元CMファイルはコミットしなくてよい。
"""
import argparse, json
from pathlib import Path

import audio_common as ac


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ref", help="参考CMの動画か音声")
    ap.add_argument("--out", default="work")
    ap.add_argument("--start", type=float, help="ナレーション区間の開始秒（省略時は書き起こしから決める）")
    ap.add_argument("--end", type=float, help="ナレーション区間の終了秒")
    ap.add_argument("--pad", type=float, default=0.25, help="書き起こしの時刻の前後に足す余白（秒）")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

    full = ac.load(a.ref)
    print(f"参考CM: {Path(a.ref).name}（{len(full) / ac.SR:.1f} 秒）")
    tr = ac.transcribe(full, timestamps=True)
    (out / "ref_transcript.json").write_text(json.dumps(tr, ensure_ascii=False, indent=1))
    voice = [t for t in tr if not str(t["text"]).startswith("[")]
    print("\n書き起こし（Gemini、時刻は目安）:")
    for t in tr:
        print(f"  {t['start']:6.2f}-{t['end']:6.2f}  {t['text']}")
    if not voice:
        raise SystemExit("ナレーションが見つからない。--start/--end で範囲を指定する")

    start = a.start if a.start is not None else max(0.0, min(t["start"] for t in voice) - a.pad)
    end = a.end if a.end is not None else min(len(full) / ac.SR, max(t["end"] for t in voice) + a.pad)
    x = full[int(start * ac.SR):int(end * ac.SR)]
    segs, dropped = ac.drop_music_edges(x, ac.segments(x))
    for s, e in dropped:
        print(f"区間の端 {start + s:.2f}-{start + e:.2f}s は声と音程がかけ離れているので楽器とみなして外した")
    if a.start is None and a.end is None:
        # 書き起こしの時刻は目安なので、検出した声の前後に少しだけ余白を残して範囲を詰め直す
        start, end = start + max(0.0, segs[0][0] - 0.15), start + min(len(x) / ac.SR, segs[-1][1] + 0.3)
        x = full[int(start * ac.SR):int(end * ac.SR)]
        segs, _ = ac.drop_music_edges(x, ac.segments(x))

    (out / "script.txt").write_text("\n\n".join(t["text"] for t in voice) + "\n", encoding="utf-8")
    v = ac.voice_only(x, segs)
    m = ac.voice_metrics(v)
    prof = {
        "source": Path(a.ref).name,
        "range_sec": [round(start, 2), round(end, 2)],
        "phrases_sec": [[round(s, 2), round(e, 2)] for s, e in segs],
        "transcript": [t["text"] for t in voice],
        **m,
        "snr_db": ac.snr_db(x, segs),
        "ltas_centers_hz": [round(c, 1) for c in ac.CENTERS],
        "ltas_db": [round(d, 2) for d in ac.ltas(v)],
    }
    (out / "profile.json").write_text(json.dumps(prof, ensure_ascii=False, indent=1))

    print(f"\nナレーション区間: {start:.2f}〜{end:.2f} 秒（以下はこの区間の先頭を 0 秒とした時刻）")
    print("  #  開始   長さ   次の句までの間")
    for i, (s, e) in enumerate(segs):
        gap = f"{segs[i + 1][0] - e:.2f}" if i + 1 < len(segs) else "-"
        print(f"  {i + 1}  {s:5.2f}  {e - s:5.2f}  {gap}")
    print(f"\n声の高さ 中央値 {m['f0_median_hz']}Hz（10〜90% 範囲 {m['f0_p10_hz']}〜{m['f0_p90_hz']}Hz）")
    print(f"声のゆらぎ jitter {m['jitter_pct']}% / shimmer {m['shimmer_pct']}%  澄み具合 HNR {m['hnr_db']}dB"
          f"  明るさ（重心） {m['centroid_hz']:.0f}Hz")
    if prof["snr_db"] is not None:
        note = "  ← 30dB 未満。声の下の音楽で HNR・shimmer が実際より濁って出ている" if prof["snr_db"] < 30 else ""
        print(f"句の中と句の間の音量差 {prof['snr_db']}dB{note}")
    print(f"\n句の数: 区間検出 {len(segs)} / 書き起こし {len(voice)}。"
          "大きく違う・先頭や末尾に音楽が入っているときは --start/--end で範囲を詰めてやり直す")
    print("wrote", out / "profile.json", out / "script.txt", out / "ref_transcript.json")


if __name__ == "__main__":
    main()
