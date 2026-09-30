#!/usr/bin/env node
// 編集用 SVG をヘッドレス Chromium で PNG にする（HG フォントの代わりに fonts.json の preview 書体で描く）。
// あわせて、指定幅（maxWidth）からのはみ出しと、紙面外・安全域外への文字のはみ出しを報告する。
//
// usage: node preview.mjs <out_dir> [--px 1600] [--safe 5]
//   先に python3 fetch_fonts.py でプレビュー用フォントを取ってくる（SKILL.md 参照）
import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const outDir = args[0];
const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? Number(args[i + 1]) : d; };
const longPx = opt('--px', 1600), safeMm = opt('--safe', 5);

async function loadChromium() {
  try { return (await import('playwright')).chromium; } catch {}
  const root = execSync('npm root -g').toString().trim();
  return createRequire(path.join(root, 'noop.js'))('playwright').chromium;
}

const svgFile = fs.readdirSync(outDir).find(f => f.endsWith('.svg'));
if (!svgFile) { console.error('SVG がありません: ' + outDir); process.exit(1); }
const svg = fs.readFileSync(path.join(outDir, svgFile), 'utf8').replace(/^<\?xml[^>]*>/, '');
const fonts = JSON.parse(fs.readFileSync(path.join(HERE, 'fonts.json'), 'utf8'));
const fontDir = process.env.HANSOKU_FONT_DIR || path.join(process.env.HOME, '.cache/hansoku-ai-data/fonts');
const fontCss = fs.existsSync(path.join(fontDir, 'fonts.css'))
  ? `<link rel="stylesheet" href="file://${path.join(fontDir, 'fonts.css')}">` : '';
if (!fontCss) console.warn('! プレビュー用フォントがありません（IPA ゴシック等で描画）。fetch_fonts.py を先に実行してください');
const map = Object.entries(fonts).map(([k, f]) =>
  `.f-${k}{font-family:'${f.preview.family}','IPAPGothic',sans-serif !important;font-weight:${f.preview.weight} !important}`).join('\n');

const vb = /viewBox="0 0 ([\d.]+) ([\d.]+)"/.exec(svg);
const [vw, vh] = [Number(vb[1]), Number(vb[2])];
const scale = longPx / Math.max(vw, vh);
const W = Math.round(vw * scale), H = Math.round(vh * scale);
const html = `<!doctype html><meta charset="utf-8">${fontCss}<style>html,body{margin:0;background:#888}
svg{display:block;width:${W}px;height:${H}px}${map}</style>${svg}`;
const tmp = path.join(outDir, '.preview.html');
fs.writeFileSync(tmp, html);

const chromium = await loadChromium();
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: W, height: H } });
await page.goto('file://' + path.resolve(tmp));
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(300);
const K = 72 / 25.4;
const issues = await page.evaluate(({ K, safeMm, vw, vh }) => {
  const out = [];
  const svgEl = document.querySelector('svg');
  const toUser = svgEl.getScreenCTM().inverse();
  const box = el => {
    const r = el.getBoundingClientRect();
    const a = new DOMPoint(r.left, r.top).matrixTransform(toUser), b = new DOMPoint(r.right, r.bottom).matrixTransform(toUser);
    return { x: a.x, y: a.y, w: b.x - a.x, h: b.y - a.y };
  };
  const fonts = new Set();
  for (const g of document.querySelectorAll('g[id^="t"]')) {
    const f = g.querySelector('text[id$="f"]');
    if (!f) continue;
    const b = box(f), txt = f.textContent;
    fonts.add(getComputedStyle(f).fontFamily.split(',')[0]);
    const vertical = f.getAttribute('writing-mode');
    const len = vertical ? b.h : b.w;
    const max = Number(g.dataset.maxlen || 0);
    if (max && len > max * 1.001 && !vertical) {
      // Illustrator の AI保存.jsx と同じく長体で幅に収めて描く（anchor を軸に横だけ縮める）
      const s = Math.max(0.5, max / len);
      const anchor = f.getAttribute('text-anchor');
      const ax = anchor === 'middle' ? b.x + b.w / 2 : anchor === 'end' ? b.x + b.w : b.x;
      const inner = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      inner.setAttribute('transform', `translate(${ax} 0) scale(${s} 1) translate(${-ax} 0)`);
      while (g.firstChild) inner.appendChild(g.firstChild);
      g.appendChild(inner);
      out.push(`長体 ${Math.round(s * 100)}%「${txt}」 ${(len / K).toFixed(1)}mm → 指定幅 ${(max / K).toFixed(1)}mm（jsx も同じく長体をかける）${s < 0.75 ? ' ※75%未満。文字サイズを下げるか改行を検討' : ''}`);
    }
    const s = safeMm * K;
    const ob = box(g);
    if (ob.x < 0 || ob.y < 0 || ob.x + ob.w > vw || ob.y + ob.h > vh) out.push(`紙面外にはみ出し「${txt}」`);
    else if (ob.x < s || ob.y < s || ob.x + ob.w > vw - s || ob.y + ob.h > vh - s) out.push(`端から${safeMm}mm以内「${txt}」`);
  }
  return { out, fonts: [...fonts] };
}, { K, safeMm, vw, vh });
const pngPath = path.join(outDir, 'プレビュー.png');
await page.locator('svg').screenshot({ path: pngPath });
await browser.close();
fs.unlinkSync(tmp);
console.log(`OK ${pngPath} (${W}x${H}px)  preview fonts: ${issues.fonts.join(', ')}`);
for (const s of issues.out) console.log('! ' + s);
