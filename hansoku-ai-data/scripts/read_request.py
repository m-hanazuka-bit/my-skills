#!/usr/bin/env python3
"""依頼書（xlsx）を読む：シートごとの入力済みセルを「A1: 値」で一覧にし、貼り付け画像を取り出す。

様式は依頼元ごとに違うので項目の解釈は Claude がする。ここでは標準ライブラリだけで中身を全部出す。
チェック欄は ✓ / レ / ☑ / ■ などの文字、またはフォームのチェックボックス（checked）で入っている。

usage: python3 read_request.py 依頼書.xlsx [--images out/request_images]
"""
import argparse
import os
import posixpath
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "pr": "http://schemas.openxmlformats.org/package/2006/relationships"}
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
REMB = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"


def col_name(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def rels(z, path):
    d, b = posixpath.split(path)
    rp = posixpath.join(d, "_rels", b + ".rels")
    if rp not in z.namelist():
        return {}
    out = {}
    for r in ET.fromstring(z.read(rp)).findall("pr:Relationship", NS):
        out[r.get("Id")] = posixpath.normpath(posixpath.join(d, r.get("Target")))
    return out


def text_of(si):
    return "".join(t.text or "" for t in si.iter("{%s}t" % NS["m"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--images", help="貼り付け画像の保存先フォルダー")
    a = ap.parse_args()
    z = zipfile.ZipFile(a.xlsx)
    names = z.namelist()
    shared = []
    if "xl/sharedStrings.xml" in names:
        shared = [text_of(si) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS)]
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    wrels = rels(z, "xl/workbook.xml")
    img_no = 0
    for sh in wb.find("m:sheets", NS):
        title, path = sh.get("name"), wrels[sh.get(RID)]
        state = sh.get("state")
        print(f"\n## シート「{title}」" + (f"（{state}）" if state else ""))
        root = ET.fromstring(z.read(path))
        for c in root.iter("{%s}c" % NS["m"]):
            t, v = c.get("t"), c.find("m:v", NS)
            if t == "s" and v is not None:
                val = shared[int(v.text)]
            elif t == "inlineStr":
                val = text_of(c)
            elif v is not None:
                val = v.text
            else:
                continue
            val = val.strip()
            if val:
                print(f"{c.get('r')}: {val}")
        srels = rels(z, path)
        # フォームのチェックボックス
        for cp in root.iter("{%s}control" % NS["m"]):
            target = srels.get(cp.get(RID))
            if target and target in names:
                x = z.read(target).decode("utf-8", "ignore")
                if "CheckBox" in x:
                    checked = 'checked="Checked"' in x
                    link = re.search(r'fmlaLink="([^"]+)"', x)
                    print(f"[チェックボックス {cp.get('name', '')}] {'☑' if checked else '☐'}"
                          + (f" リンク={link.group(1)}" if link else ""))
        # 貼り付け画像（アンカーのセル付き）
        for d in root.findall("m:drawing", NS):
            dpath = srels.get(d.get(RID))
            if not dpath or dpath not in names:
                continue
            drels = rels(z, dpath)
            droot = ET.fromstring(z.read(dpath))
            for anc in list(droot):
                frm = anc.find("xdr:from", NS)
                cell = ""
                if frm is not None:
                    cell = col_name(int(frm.find("xdr:col", NS).text)) + str(int(frm.find("xdr:row", NS).text) + 1)
                for blip in anc.iter("{%s}blip" % NS["a"]):
                    media = drels.get(blip.get(REMB))
                    if not media or media not in names:
                        continue
                    img_no += 1
                    info = f"[画像{img_no}] アンカー {cell}  {posixpath.basename(media)} {len(z.read(media)) // 1024}KB"
                    if a.images:
                        os.makedirs(a.images, exist_ok=True)
                        ext = posixpath.splitext(media)[1]
                        out = os.path.join(a.images, f"{title}_{cell}_{img_no}{ext}")
                        open(out, "wb").write(z.read(media))
                        info += f" → {out}"
                    print(info)
    if not img_no:
        print("\n（貼り付け画像なし）")


if __name__ == "__main__":
    sys.exit(main())
