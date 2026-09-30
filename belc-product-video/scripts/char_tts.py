#!/usr/bin/env python3
"""キャラクター設定表（character.json）どおりの声で、台本を 1 行ずつ Gemini TTS にする。

  python char_tts.py --character ../characters/gu/character.json --script script.json --out work/voice

Gemini TTS のプロンプトは設定表と同じ構成（AUDIO PROFILE / SCENE / DIRECTOR'S NOTES / SAMPLE CONTEXT / TRANSCRIPT）で組み、
行ごとの emotion（例: ぐぅの tame＝ためる、hype＝全開）を DIRECTOR'S NOTES に足す。
キーは環境変数 GEMINI_API_KEY か .env（作業ディレクトリ → このスキル直下）。
出力：<out>/<id>.wav（前後の無音をカット）と <out>/voice.json
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
import wave

import numpy as np

MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
HERE = os.path.dirname(os.path.abspath(__file__))


def api_key():
    k = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    for p in (".env", os.path.join(HERE, "..", ".env")):
        if k:
            break
        if os.path.exists(p):
            for line in open(p):
                if line.strip().startswith(("GEMINI_API_KEY=", "GOOGLE_API_KEY=")):
                    k = line.split("=", 1)[1].strip().strip("\"'")
                    break
    if not k:
        sys.exit("GEMINI_API_KEY が未設定です（環境変数か belc-product-video/.env に書く）")
    return k


def build_prompt(char, text, emotion="", extra=""):
    v = char["voice"]
    act = char.get("emotions", {}).get(emotion, emotion)
    return "\n".join([
        f"# AUDIO PROFILE: {char['full_name']}",
        v["audio_profile"],
        "",
        "## THE SCENE",
        v["scene"],
        "",
        "### DIRECTOR'S NOTES",
        v["director_note"],
        *( [f"This line: {act}"] if act else [] ),
        *( [extra] if extra else [] ),
        "",
        "### SAMPLE CONTEXT",
        v["sample_context"],
        "",
        "#### TRANSCRIPT",
        text,
    ])


def synth(prompt, voice, model, retries=3):
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    req = urllib.request.Request(API.format(model=model), data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "x-goog-api-key": api_key()})
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                res = json.load(r)
            part = res["candidates"][0]["content"]["parts"][0]["inlineData"]
            rate = 24000
            for p in part.get("mimeType", "").split(";"):
                if p.strip().startswith("rate="):
                    rate = int(p.split("=")[1])
            return base64.b64decode(part["data"]), rate
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")
            if e.code in (429, 500, 503) and i < retries - 1:
                time.sleep(2 ** (i + 1))
                continue
            sys.exit(f"Gemini TTS error {e.code}: {msg[:400]}")
        except (KeyError, IndexError):
            sys.exit(f"音声が返りませんでした: {json.dumps(res, ensure_ascii=False)[:400]}")


def trim_silence(pcm, rate, thresh=0.012, pad=0.06):
    x = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
    loud = np.where(np.abs(x) > thresh)[0]
    if len(loud) == 0:
        return pcm
    s = max(0, loud[0] - int(pad * rate))
    e = min(len(x), loud[-1] + int(pad * rate))
    return (x[s:e] * 32768).astype("<i2").tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--character", required=True)
    ap.add_argument("--script", required=True)
    ap.add_argument("--out", default="voice")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--only", help="この id の行だけ作り直す（カンマ区切り）")
    ap.add_argument("--print-prompt", action="store_true", help="API を呼ばずにプロンプトだけ表示")
    a = ap.parse_args()
    char = json.load(open(a.character, encoding="utf-8"))
    script = json.load(open(a.script, encoding="utf-8"))
    os.makedirs(a.out, exist_ok=True)
    man_path = os.path.join(a.out, "voice.json")
    manifest = {m["id"]: m for m in json.load(open(man_path))} if os.path.exists(man_path) else {}
    only = set(a.only.split(",")) if a.only else None

    for ln in script["lines"]:
        lid = ln["id"]
        if only and lid not in only:
            continue
        text = ln["text"].replace("*", "")
        prompt = build_prompt(char, ln.get("read", text), ln.get("emotion", ""), ln.get("direction", ""))
        if a.print_prompt:
            print(f"----- {lid}\n{prompt}\n")
            continue
        pcm, rate = synth(prompt, ln.get("voice") or char["voice"]["name"], a.model)
        pcm = trim_silence(pcm, rate)
        path = os.path.join(a.out, f"{lid}.wav")
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(pcm)
        dur = len(pcm) / 2 / rate
        manifest[lid] = {"id": lid, "text": ln["text"], "tension": ln.get("emotion", ""), "file": os.path.abspath(path), "duration": round(dur, 3)}
        print(f"{lid} [{ln.get('emotion', '')}] {dur:.2f}s  {text}")
    if not a.print_prompt:
        order = [l["id"] for l in script["lines"]]
        json.dump([manifest[i] for i in order if i in manifest], open(man_path, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
