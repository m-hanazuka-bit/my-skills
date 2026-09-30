#!/usr/bin/env python3
"""台本（script.json）の各セリフがキャラの話し方ルールを守っているか確認する。

  python check_lines.py --character ../characters/gu/character.json --script script.json

- ERROR（必ず直す）：禁止語・禁止の一人称・長すぎる行
- WARN（なるべく直す）：関西弁／丁寧語の割合が足りない、感嘆符の連発 など
ERROR が 1 つでもあれば終了コード 1。音声を作る前に必ず通す。
"""
import argparse
import json
import re
import sys


def load(p):
    return json.load(open(p, encoding="utf-8"))


def strip_mark(t):
    return t.replace("*", "")


def check(char, script):
    r = char["speech_rules"]
    errors, warns = [], []
    lines = script.get("lines", [])
    if not lines:
        errors.append("lines が空です")
    kansai_hits = polite_hits = 0
    for ln in lines:
        lid, text = ln.get("id", "?"), strip_mark(ln.get("text", ""))
        for w in r.get("forbid", []):
            if w in text:
                errors.append(f"{lid}: 禁止表現「{w}」→ {text}")
        for w in r.get("first_person_forbid", []):
            if re.search(rf"(^|[、。！？\s]){re.escape(w)}(は|が|も|の|を|、)", text):
                errors.append(f"{lid}: 一人称は「{r['first_person']}」（「{w}」は使わない）→ {text}")
        n = len(re.sub(r"[、。！？!?…\s「」]", "", text))
        if n > r.get("max_chars_per_line", 30):
            errors.append(f"{lid}: 長すぎます（{n} 文字 > {r['max_chars_per_line']}）。2 行に分けるか削る → {text}")
        if re.search(r"[！!]{2,}", text) and char["id"] == "bellcook":
            warns.append(f"{lid}: 感嘆符の連発は彼女らしくありません → {text}")
        if any(m in text for m in r.get("kansai_markers", [])):
            kansai_hits += 1
        sentences = [s for s in re.split(r"[。！？!?]", text) if s.strip()]
        if sentences and all(any(s.rstrip("ね よ").endswith(e) or e in s[-6:] for e in r.get("polite_endings", [])) for s in sentences):
            polite_hits += 1
        if ln.get("emotion") and ln["emotion"] not in char.get("emotions", {}):
            warns.append(f"{lid}: emotion「{ln['emotion']}」は未定義（使える: {', '.join(char['emotions'])}）")
    if lines and "kansai_min_ratio" in r and kansai_hits / len(lines) < r["kansai_min_ratio"]:
        warns.append(f"関西弁らしい語尾が少なめです（{kansai_hits}/{len(lines)} 行）。〜やで／ほんま／〜やん などを足す")
    if lines and "polite_min_ratio" in r and polite_hits / len(lines) < r["polite_min_ratio"]:
        warns.append(f"丁寧語で終わっていない行があります（{polite_hits}/{len(lines)} 行が〜です／〜ます）")
    if r.get("first_person") and not any(r["first_person"] in strip_mark(l.get("text", "")) for l in lines):
        warns.append(f"一人称「{r['first_person']}」が 1 回も出てきません（無理に入れなくてもよいが、入るとキャラが立つ）")
    total_chars = sum(len(strip_mark(l.get("text", ""))) for l in lines)
    est = total_chars / (8.0 if char["id"] == "gu" else 6.0)
    return errors, warns, est


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--character", required=True)
    ap.add_argument("--script", required=True)
    ap.add_argument("--target", type=float, default=15.0, help="目標秒数")
    a = ap.parse_args()
    char, script = load(a.character), load(a.script)
    errors, warns, est = check(char, script)
    for e in errors:
        print("ERROR", e)
    for w in warns:
        print("WARN ", w)
    print(f"推定の読み上げ時間 {est:.1f} 秒（目標 {a.target:.0f} 秒。最後に 1.5〜2 秒の締めが付く）")
    if est > a.target - 1.5:
        print("WARN  長めです。セリフを削るか行数を減らす")
    if not errors:
        print("OK")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
