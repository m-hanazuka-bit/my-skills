#!/usr/bin/env python3
"""Google Fonts をローカルに保存し fonts/fonts.css を作る（レンダリング中のフォント化け防止）。

ヘッドレス Chromium がプロキシ等で Google Fonts を読めない環境でも、
template.html は先に fonts/fonts.css を読むので、ここで保存しておけば確実に同じ書体で描ける。

usage:
  python fetch_fonts.py --out work/fonts "Dela Gothic One" "Noto Sans JP:wght@400;700;900" "JetBrains Mono:wght@500"
"""
import argparse
import os
import re
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("families", nargs="+")
    ap.add_argument("--out", default="fonts")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    q = "&".join("family=" + urllib.parse.quote(f, safe=":;@,") for f in a.families)
    css = get(f"https://fonts.googleapis.com/css2?{q}&display=block").decode()
    urls = sorted(set(re.findall(r"url\((https://[^)]+)\)", css)))
    for i, u in enumerate(urls):
        name = f"f{i:03d}" + os.path.splitext(urllib.parse.urlparse(u).path)[1]
        with open(os.path.join(a.out, name), "wb") as f:
            f.write(get(u))
        css = css.replace(u, name)
    with open(os.path.join(a.out, "fonts.css"), "w") as f:
        f.write(css)
    print(f"{len(urls)} files -> {a.out}/fonts.css")


if __name__ == "__main__":
    main()
