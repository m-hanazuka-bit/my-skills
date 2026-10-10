#!/usr/bin/env node
// テロップ・タイトル帯・バッジを、動画に重ねる透過 PNG（1080x1920）として書き出す。
// usage: NODE_PATH=$(npm root -g) node caption_png.mjs captions.json outdir
// captions.json: { title, badge, lines: [{ id, text, who, style }] }  style: "" | "fixed"（決め台詞は黄色）
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const { chromium } = createRequire(import.meta.url)("playwright");
const [, , specFile, outDir] = process.argv;
const spec = JSON.parse(fs.readFileSync(specFile, "utf8"));
fs.mkdirSync(outDir, { recursive: true });

const css = `
  @import url('https://fonts.googleapis.com/css2?family=Zen+Maru+Gothic:wght@700;900&family=Dela+Gothic+One&display=block');
  html, body { margin: 0; width: 1080px; height: 1920px; background: transparent; }
  .title { position: absolute; left: 0; top: 0; width: 1080px; height: 128px; background: rgba(45, 42, 50, .82);
    display: flex; align-items: center; padding-left: 44px; box-sizing: border-box;
    font: 400 54px "Dela Gothic One"; color: #fff; letter-spacing: 2px; }
  .badge { position: absolute; left: 40px; top: 170px; width: 150px; height: 150px; border-radius: 50%;
    background: #d6312b; border: 6px solid #fff; transform: rotate(-12deg); display: flex; align-items: center; justify-content: center;
    font: 400 56px "Dela Gothic One"; color: #fff; box-shadow: 0 6px 0 rgba(0,0,0,.25); }
  .cap { position: absolute; left: 40px; top: 1430px; width: 860px; min-height: 190px; box-sizing: border-box;
    padding: 30px 30px; background: #fff; border: 6px solid #2d2a32; border-radius: 32px; box-shadow: 0 10px 0 #2d2a32;
    font: 900 50px/1.4 "Zen Maru Gothic"; color: #2d2a32; text-align: center; display: flex; align-items: center; justify-content: center; }
  .cap.fixed { background: #ffd84a; }
  .who { position: absolute; left: 28px; top: -28px; background: #2d2a32; color: #fff; font: 700 28px "Zen Maru Gothic"; padding: 4px 18px; border-radius: 20px; }
`;

const launch = { args: ["--font-render-hinting=none"] };
if (fs.existsSync("/opt/pw-browsers/chromium")) launch.executablePath = "/opt/pw-browsers/chromium";
const browser = await chromium.launch(launch);
const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });

async function shot(html, file) {
  await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>${css}</style></head><body>${html}</body></html>`);
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(150);
  await page.screenshot({ path: path.join(outDir, file), omitBackground: true });
}

if (spec.title) await shot(`<div class="title">${spec.title}</div>`, "title.png");
if (spec.badge) await shot(`<div class="badge">${spec.badge}</div>`, "badge.png");
for (const l of spec.lines) await shot(`<div class="cap ${l.style || ""}"><span class="who">${l.who || "パパ"}</span><span>${l.text}</span></div>`, `cap_${l.id}.png`);
await browser.close();
console.log("captions:", spec.lines.length);
