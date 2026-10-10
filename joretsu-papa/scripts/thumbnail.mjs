#!/usr/bin/env node
// ショートのサムネ（1080x1920）を作る。場面の絵の下半分に、大きな黄色い文字を3行で重ねる。
// usage: NODE_PATH=$(npm root -g) node thumbnail.mjs <背景の絵.png> <out.png> "パンツが" "ないので" "帰ります"
// 背景は 1080x1920 に切り抜いてから渡す（例：convert k0.png -resize 1080x1920^ -gravity center -extent 1080x1920 bg.png）。
// 1行は4〜5文字まで。動画の最後に 0.1 秒入れておくと、アプリのコマ選びでサムネに選べる。
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const { chromium } = createRequire(import.meta.url)("playwright");
const [, , bgFile, outFile, ...lines] = process.argv;
const bg = "data:image/png;base64," + fs.readFileSync(bgFile).toString("base64");

const html = `<!doctype html><html><head><meta charset="utf-8"><style>
@import url('https://fonts.googleapis.com/css2?family=Dela+Gothic+One&display=block');
html,body{margin:0;width:1080px;height:1920px}
body{background:url(${bg});position:relative;overflow:hidden}
.shade{position:absolute;left:0;right:0;bottom:0;height:900px;background:linear-gradient(to bottom,rgba(20,18,24,0),rgba(20,18,24,.55) 35%,rgba(20,18,24,.8))}
.band{position:absolute;left:0;top:0;width:1080px;height:128px;background:rgba(45,42,50,.82);display:flex;align-items:center;padding-left:44px;box-sizing:border-box;font:400 54px "Dela Gothic One";color:#fff;letter-spacing:2px}
.badge{position:absolute;left:40px;top:170px;width:170px;height:170px;border-radius:50%;background:#d6312b;border:7px solid #fff;transform:rotate(-12deg);display:flex;align-items:center;justify-content:center;font:400 64px "Dela Gothic One";color:#fff;box-shadow:0 6px 0 rgba(0,0,0,.25)}
.big{position:absolute;left:0;width:1080px;bottom:90px;text-align:center;font:400 250px/1.08 "Dela Gothic One";color:#ffd84a;letter-spacing:-4px;-webkit-text-stroke:26px #2d2a32;paint-order:stroke fill;text-shadow:0 14px 0 #2d2a32}
</style></head><body><div class="shade"></div><div class="band">パパなので。</div><div class="badge">実話</div>
<div class="big">${lines.join("<br>")}</div></body></html>`;

const launch = {};
if (fs.existsSync("/opt/pw-browsers/chromium")) launch.executablePath = "/opt/pw-browsers/chromium";
const browser = await chromium.launch(launch);
const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
await page.setContent(html);
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(300);
await page.screenshot({ path: path.resolve(outFile) });
await browser.close();
console.log("thumbnail:", outFile);
