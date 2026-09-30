#!/usr/bin/env python3
"""Gemini TTS でナレーションを1行ずつ生成する（声のテンション設計つき）。

APIキーは環境変数 GEMINI_API_KEY（または GOOGLE_API_KEY）から読む。
スキルやプランファイルにキーを書き込まないこと。

usage:
  python gemini_tts.py --plan storyboard.json --out work/voice
  python gemini_tts.py --text "一芯二葉。" --tension whisper --out work/voice
  python gemini_tts.py --list-tensions

出力: <out>/<id>.wav（24kHz mono 16bit）と <out>/voice.json（各行の長さ）
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

# Gemini 3.x の TTS モデルが使えるならそれを --model / GEMINI_TTS_MODEL で指定する
DEFAULT_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# 声のテンション設計。Gemini TTS は自然文の演技指示で声色が変わる。
# level は 1(最も静か)〜5(最も高い)。ビートのセクションと対応させる。
TENSIONS = {
    "whisper":   (1, "Kore",   "耳元でささやくように、息を多めに、とてもゆっくり静かに"),
    "calm":      (2, "Kore",   "落ち着いた低めの声で、上品に、間をたっぷり取って"),
    "warm":      (2, "Sulafat", "やわらかく温かい声で、微笑みながら親しみを込めて"),
    "narrator":  (3, "Charon", "ドキュメンタリーのナレーターのように、明瞭で信頼感のある声で"),
    "build":     (4, "Fenrir", "期待感を高めるように、少しずつ力強く、前のめりに"),
    "bright":    (4, "Puck",   "明るく弾むように、元気よく、テンポ良く"),
    "hype":      (5, "Fenrir", "ライブのMCのように、エネルギー全開で力強く叫ぶように"),
    "trailer":   (5, "Algenib", "映画の予告編のように、低く太い声で、一語一語に重みを込めて"),
    "tagline":   (3, "Kore",   "締めのキャッチコピーとして、自信をもってきっぱりと、余韻を残して"),
}

# セクション → おすすめテンション（プランで未指定の行に使う）
SECTION_DEFAULT = {"intro": "calm", "build": "build", "drop": "hype", "outro": "tagline"}


def api_key():
    k = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    # 環境変数が無ければ .env（作業ディレクトリ → スキル直下）を読む。.env は git に入れない
    for p in (".env", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")):
        if k:
            break
        if os.path.exists(p):
            for line in open(p):
                if line.strip().startswith(("GEMINI_API_KEY=", "GOOGLE_API_KEY=")):
                    k = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not k:
        sys.exit("GEMINI_API_KEY が未設定です。export GEMINI_API_KEY=... か、スキル直下の .env に書いてください。")
    return k


def synth(text, tension, voice=None, model=DEFAULT_MODEL, extra_style="", retries=3):
    level, default_voice, style = TENSIONS[tension]
    prompt = f"次のセリフを、{style}{('。' + extra_style) if extra_style else ''}読み上げてください：\n{text}"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice or default_voice}}},
        },
    }
    req = urllib.request.Request(
        API.format(model=model),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key()},
    )
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                res = json.load(r)
            part = res["candidates"][0]["content"]["parts"][0]["inlineData"]
            return base64.b64decode(part["data"]), part.get("mimeType", "")
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")
            if e.code in (429, 500, 503) and i < retries - 1:
                time.sleep(2 ** (i + 1))
                continue
            sys.exit(f"Gemini TTS error {e.code}: {msg[:500]}")
        except (KeyError, IndexError):
            sys.exit(f"音声が返りませんでした: {json.dumps(res)[:500]}")


def save_pcm(path, pcm, rate=24000):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return len(pcm) / 2 / rate


def rate_from_mime(mime):
    # 例: "audio/L16;codec=pcm;rate=24000"
    for p in mime.split(";"):
        if p.strip().startswith("rate="):
            return int(p.split("=")[1])
    return 24000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", help="storyboard.json（narration 配列を読む）")
    ap.add_argument("--text")
    ap.add_argument("--tension", default="narrator", choices=TENSIONS)
    ap.add_argument("--voice", help="声を固定したいとき（例: Kore, Puck, Charon, Fenrir, Aoede）")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--out", default="voice")
    ap.add_argument("--list-tensions", action="store_true")
    a = ap.parse_args()

    if a.list_tensions:
        for k, (lv, v, s) in TENSIONS.items():
            print(f"{k:9s} Lv{lv} {v:8s} {s}")
        return

    os.makedirs(a.out, exist_ok=True)
    lines = []
    voice = a.voice
    if a.plan:
        plan = json.load(open(a.plan))
        voice = voice or plan.get("voice", {}).get("name")
        model = plan.get("voice", {}).get("model") or a.model
        for i, n in enumerate(plan.get("narration", [])):
            t = n.get("tension") or SECTION_DEFAULT.get(n.get("section", ""), "narrator")
            text = n["text"].replace("*", "")  # 字幕用の強調記法は読ませない
            lines.append((n.get("id", f"n{i+1:02d}"), text, t, n.get("style", ""), n.get("voice")))
    elif a.text:
        model = a.model
        lines.append(("n01", a.text, a.tension, "", None))
    else:
        sys.exit("--plan か --text を指定してください")

    manifest = []
    for lid, text, tension, extra, v in lines:
        pcm, mime = synth(text, tension, v or voice, model, extra)
        path = os.path.join(a.out, f"{lid}.wav")
        dur = save_pcm(path, pcm, rate_from_mime(mime))
        manifest.append({"id": lid, "text": text, "tension": tension, "file": path, "duration": round(dur, 3)})
        print(f"{lid} [{tension}] {dur:.2f}s  {text}")
    json.dump(manifest, open(os.path.join(a.out, "voice.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
