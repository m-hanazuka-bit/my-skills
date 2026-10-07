"""Gemini TTS でナレーションを生成する。

使い方:
  GEMINI_API_KEY を環境変数に設定してから
  python3 narration_tts.py [--model gemini-3.8-flash-tts] [--voice Charon Algenib ...] [--text narration.txt]

声ごとに narration_<voice>.wav を出力する（24kHz / 16bit / mono）。
"""
import argparse, base64, json, os, urllib.request, wave
from pathlib import Path

HERE = Path(__file__).parent

# 元CMのナレーション解析結果に合わせた演出指示
# （男性・地声の中央値 約113Hz、句の長さと間は下の数値、全体で約10秒）
STYLE = (
    "60代以上の年配の男性ナレーターとして、渋く、しゃがれてざらついた濁りのある地声で読んでください。"
    "澄んだきれいな声やアナウンサー的な発声ではなく、喉の奥から出る枯れた味のある声で。"
    "派手な抑揚はつけず、古いテレビCMのような素朴で淡々とした語り口で。"
    "間の取り方: 「風が、語りかけます。」は約1.6秒かけて読み、そのあと1.2秒ほど間を空ける。"
    "「うまい、」と「うますぎる。」の間は0.4秒ほど。「うますぎる。」のあと0.6秒ほど間を空ける。"
    "「十万石まんじゅう。」のあと1秒ほど間を空ける。「埼玉銘菓、」と「十万石まんじゅう。」はほぼ続けて読む。"
)


def synth(api_key, model, voice, text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        # 演出指示ごと読み上げられないよう、指示と台本を見出しで分け「台本だけ読む」と明示する
        "contents": [{"parts": [{"text": (
            f"### 演出メモ（読み上げない）\n{STYLE}\n\n"
            f"### 台本（ここだけを読み上げる）\n{text}"
        )}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    req = urllib.request.Request(
        url, json.dumps(body).encode(),
        {"Content-Type": "application/json", "x-goog-api-key": api_key},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        res = json.load(r)
    return base64.b64decode(res["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemini-3.8-flash-tts", help="使用するTTSモデルID")
    ap.add_argument("--voice", nargs="+", default=["Algenib", "Gacrux", "Enceladus", "Rasalgethi", "Alnilam"])
    ap.add_argument("--text", default=HERE / "narration.txt")
    a = ap.parse_args()
    key = os.environ["GEMINI_API_KEY"]
    text = Path(a.text).read_text(encoding="utf-8").strip()
    for v in a.voice:
        pcm = synth(key, a.model, v, text)
        out = HERE / f"narration_{v}.wav"
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
        print("wrote", out)


if __name__ == "__main__":
    main()
