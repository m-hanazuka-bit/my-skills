#!/usr/bin/env python3
"""【モード②】作成済みの音声ファイルを行ごとに切り分け、char_tts.py と同じ voice.json を作る。

  # 1 本の音声を無音で区切る（台本の行数に合わせて自動で結合）
  python align_audio.py --audio narration.wav --script script.json --out work/voice
  # 行ごとに分かれた音声ファイルを渡す（台本の行の順番どおり）
  python align_audio.py --audio n01.wav n02.wav n03.wav --script script.json --out work/voice
  # 台本が無いときは Gemini で文字起こしして台本を作る
  python align_audio.py --audio narration.wav --transcribe --script script.json --out work/voice

- 対応形式：wav はそのまま。mp3 / m4a などは ffmpeg で wav に変換してから読む
- 区切りがずれたら --min-silence（秒）と --thresh-db を調整する。結果は必ず区切り秒数の一覧で確認する
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
import wave

import numpy as np

SR = 24000


def load_audio(path):
    if not path.lower().endswith(".wav"):
        tmp = tempfile.mktemp(suffix=".wav")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", str(SR), tmp], check=True)
        path = tmp
    with wave.open(path) as w:
        ch, rate, n, sw = w.getnchannels(), w.getframerate(), w.getnframes(), w.getsampwidth()
        raw = w.readframes(n)
    if sw != 2:
        sys.exit(f"{path}: 16bit PCM の wav にしてください（ffmpeg -i in -ac 1 -ar 24000 -sample_fmt s16 out.wav）")
    x = np.frombuffer(raw, dtype="<i2").astype(np.float32).reshape(-1, ch).mean(axis=1) / 32768
    if rate != SR:
        x = np.interp(np.arange(int(len(x) * SR / rate)) / SR, np.arange(len(x)) / rate, x).astype(np.float32)
    return x


def split_on_silence(x, min_silence=0.35, thresh_db=-38.0, min_len=0.25):
    hop = int(0.01 * SR)
    n = len(x) // hop
    rms = np.sqrt(np.mean(x[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms / (np.max(rms) + 1e-12))
    voiced = db > thresh_db
    segs, start, quiet = [], None, 0
    for i, v in enumerate(voiced):
        if v:
            if start is None:
                start = i
            quiet = 0
        elif start is not None:
            quiet += 1
            if quiet * 0.01 >= min_silence:
                segs.append([start, i - quiet + 1])
                start, quiet = None, 0
    if start is not None:
        segs.append([start, n])
    segs = [s for s in segs if (s[1] - s[0]) * 0.01 >= min_len]
    return [(s * 0.01, e * 0.01) for s, e in segs]


def merge_to(segs, k):
    """区間が多すぎるときは、間の無音が短い所から結合して k 個にする"""
    segs = list(segs)
    while len(segs) > k:
        gaps = [segs[i + 1][0] - segs[i][1] for i in range(len(segs) - 1)]
        i = int(np.argmin(gaps))
        segs[i] = (segs[i][0], segs[i + 1][1])
        del segs[i + 1]
    return segs


def transcribe(path, model):
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        sys.exit("--transcribe には GEMINI_API_KEY が必要です")
    data = base64.b64encode(open(path, "rb").read()).decode()
    body = {"contents": [{"parts": [
        {"inline_data": {"mime_type": "audio/wav", "data": data}},
        {"text": "この日本語音声を一字一句そのまま書き起こしてください。句読点を付け、書き起こし文だけを返してください。"}]}]}
    req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)["candidates"][0]["content"]["parts"][0]["text"].strip()


def save(path, x):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", nargs="+", required=True)
    ap.add_argument("--script", required=True, help="台本。--transcribe のときは書き起こし結果でここを作る/上書きする")
    ap.add_argument("--out", default="voice")
    ap.add_argument("--min-silence", type=float, default=0.35)
    ap.add_argument("--thresh-db", type=float, default=-38.0)
    ap.add_argument("--transcribe", action="store_true")
    ap.add_argument("--model", default=os.environ.get("GEMINI_TEXT_MODEL", "gemini-2.5-flash"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    script = json.load(open(a.script, encoding="utf-8")) if os.path.exists(a.script) else {"lines": []}
    lines = script.get("lines", [])

    clips = []
    if len(a.audio) > 1:
        clips = [load_audio(p) for p in a.audio]
    else:
        x = load_audio(a.audio[0])
        segs = split_on_silence(x, a.min_silence, a.thresh_db)
        if lines and len(segs) > len(lines):
            segs = merge_to(segs, len(lines))
        if lines and len(segs) < len(lines):
            print(f"[warn] 区切りが {len(segs)} 個で台本 {len(lines)} 行より少ない。--min-silence を小さく（例 0.2）して再実行を")
        pad = 0.05
        clips = [x[max(0, int((s - pad) * SR)): int((e + pad) * SR)] for s, e in segs]
        for i, (s, e) in enumerate(segs):
            print(f"  区間 {i + 1}: {s:6.2f} – {e:6.2f} 秒")

    manifest = []
    for i, c in enumerate(clips):
        lid = lines[i]["id"] if i < len(lines) else f"n{i + 1:02d}"
        path = os.path.abspath(os.path.join(a.out, f"{lid}.wav"))
        save(path, c)
        text = lines[i]["text"] if i < len(lines) else ""
        if a.transcribe:
            text = transcribe(path, a.model)
        manifest.append({"id": lid, "text": text, "tension": lines[i].get("emotion", "") if i < len(lines) else "",
                         "file": path, "duration": round(len(c) / SR, 3)})
        print(f"{lid} {len(c) / SR:.2f}s  {text}")
    json.dump(manifest, open(os.path.join(a.out, "voice.json"), "w"), ensure_ascii=False, indent=1)
    if a.transcribe:  # 書き起こしを台本に反映（scene などの演出指定は残す）
        for i, m in enumerate(manifest):
            if i < len(lines):
                lines[i]["text"] = m["text"]
            else:
                lines.append({"id": m["id"], "text": m["text"], "scene": "hook" if i == 0 else "point"})
        script["lines"] = lines
        json.dump(script, open(a.script, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"台本を更新しました: {a.script}（scene の割り当てを確認してください）")


if __name__ == "__main__":
    main()
