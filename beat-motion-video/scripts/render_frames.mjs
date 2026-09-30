#!/usr/bin/env node
// HTML(2D) + Blender の透過PNG(3D) を 1 フレームずつ撮影して最終フレームを作る。
//
// usage:
//   node render_frames.mjs --html work/motion.html --timeline work/timeline.json \
//        --frames3d work/3d --out work/frames [--from 0 --to 449] [--scale 0.5]
//
// 必要: npm i playwright （Chromium は npx playwright install chromium。
//        クラウド環境で /opt/pw-browsers がある場合はインストール不要）
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const argv = Object.fromEntries(
  process.argv.slice(2).reduce((acc, v, i, arr) => (v.startsWith("--") ? [...acc, [v.slice(2), arr[i + 1]?.startsWith("--") ? true : arr[i + 1] ?? true]] : acc), [])
);
const html = path.resolve(argv.html);
const timeline = JSON.parse(fs.readFileSync(argv.timeline, "utf8"));
const out = path.resolve(argv.out || "frames");
const fps = timeline.fps || 30;
const [W, H] = timeline.size || [1920, 1080];
const scale = parseFloat(argv.scale || "1");
const total = Math.round(timeline.video_duration * fps);
const from = parseInt(argv.from ?? "0");
const to = Math.min(parseInt(argv.to ?? String(total - 1)), total - 1);
const step = parseInt(argv.step || "1");

let frames3d = null;
if (argv.frames3d && fs.existsSync(argv.frames3d)) {
  const nums = fs.readdirSync(argv.frames3d).filter(f => /^\d+\.png$/.test(f)).map(f => parseInt(f)).sort((a, b) => a - b);
  if (nums.length) frames3d = { dir: path.relative(path.dirname(html), path.resolve(argv.frames3d)).split(path.sep).join("/"), start: nums[0], end: nums[nums.length - 1] };
}

fs.mkdirSync(out, { recursive: true });
const launch = { args: ["--allow-file-access-from-files", "--font-render-hinting=none"] };
if (fs.existsSync("/opt/pw-browsers/chromium")) launch.executablePath = "/opt/pw-browsers/chromium";
const browser = await chromium.launch(launch).catch(() => chromium.launch({ args: launch.args }));
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: scale });
await page.addInitScript(([tl, f3d]) => { window.TIMELINE = tl; window.FRAMES3D = f3d; }, [timeline, frames3d]);
page.on("pageerror", e => console.error("[page error]", e.message));
await page.goto("file://" + html + "?t=0");
await page.waitForFunction(() => window.__ready === true, null, { timeout: 30000 });
// Webフォントが読めていないと太字タイポが別フォントに化ける。オフライン環境ではフォントをローカルに置いて @font-face で読む
const missing = await page.evaluate(async () => {
  const fams = getComputedStyle(document.documentElement).getPropertyValue("--display").split(",").map(x => x.trim().replace(/"/g, ""));
  const c = document.createElement("canvas").getContext("2d");
  const w = f => { c.font = `100px ${f}`; return c.measureText("あAbc漢字123").width; };
  for (const f of fams) await document.fonts.load(`100px "${f}"`, "あAbc漢字123").catch(() => {});
  return fams.filter(f => !/^(sans-serif|serif|monospace)$/.test(f) && w(`"${f}", monospace`) === w("monospace"));
});
if (missing.length) console.warn("[warn] 読み込めていないフォント:", missing.join(", "), "（オフラインならローカルの @font-face に差し替える）");

const t0 = Date.now();
for (let f = from; f <= to; f += step) {
  await page.evaluate(t => window.seek(t), f / fps);
  await page.screenshot({ path: path.join(out, `${String(f).padStart(5, "0")}.png`) });
  if (f % (fps * 2) === 0) process.stdout.write(`\rframe ${f}/${to}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
}
await browser.close();
console.log(`\ndone: ${out} (${frames3d ? "3D " + frames3d.start + "-" + frames3d.end : "no 3D"})`);
