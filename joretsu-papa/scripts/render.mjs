#!/usr/bin/env node
// エピソードの HTML を 1 フレームずつ撮影して mp4 にする。
// HTML 側は window.seek(t) と window.__ready = true、window.EPISODE = {w, h, fps, duration} を用意する。
//
// usage:
//   NODE_PATH=$(npm root -g) node render.mjs --html episode.html --out out/ep.mp4          # 本番
//   NODE_PATH=$(npm root -g) node render.mjs --html episode.html --stills 1,5,12 --out out  # 確認用の静止画
//   オプション: --scale 0.5（下書き）  --from 10 --to 20（秒で範囲指定）
//             --voice-dir dir（EPISODE.audio の [{file, start}] を時刻どおりに並べて音声にする）  --audio file（1本の音声）
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";

const { chromium } = createRequire(import.meta.url)("playwright");

const argv = Object.fromEntries(
  process.argv.slice(2).reduce((acc, v, i, arr) => (v.startsWith("--") ? [...acc, [v.slice(2), arr[i + 1]?.startsWith("--") ? true : arr[i + 1] ?? true]] : acc), [])
);
const html = path.resolve(argv.html);
const scale = parseFloat(argv.scale || "1");

const launch = { args: ["--allow-file-access-from-files", "--font-render-hinting=none"] };
if (fs.existsSync("/opt/pw-browsers/chromium")) launch.executablePath = "/opt/pw-browsers/chromium";
const browser = await chromium.launch(launch).catch(() => chromium.launch({ args: launch.args }));
const probe = await browser.newPage();
await probe.goto("file://" + html);
await probe.waitForFunction(() => window.__ready === true, null, { timeout: 30000 });
const ep = await probe.evaluate(() => window.EPISODE);
await probe.close();

const page = await browser.newPage({ viewport: { width: ep.w, height: ep.h }, deviceScaleFactor: scale });
page.on("pageerror", e => console.error("[page error]", e.message));
await page.goto("file://" + html);
await page.waitForFunction(() => window.__ready === true, null, { timeout: 30000 });
await page.evaluate(() => document.fonts.ready);

if (argv.stills) {
  const out = path.resolve(argv.out || "stills");
  fs.mkdirSync(out, { recursive: true });
  for (const t of String(argv.stills).split(",").map(Number)) {
    await page.evaluate(t => window.seek(t), t);
    const f = path.join(out, `still_${String(t).replace(".", "_")}.png`);
    await page.screenshot({ path: f });
    console.log(f);
  }
  await browser.close();
  process.exit(0);
}

const outFile = path.resolve(argv.out || "out.mp4");
const tmp = outFile + ".frames";
fs.rmSync(tmp, { recursive: true, force: true });
fs.mkdirSync(tmp, { recursive: true });
const fps = ep.fps || 30;
const f0 = Math.round(parseFloat(argv.from || "0") * fps);
const f1 = Math.round(parseFloat(argv.to || String(ep.duration)) * fps) - 1;
const t0 = Date.now();
for (let f = f0; f <= f1; f++) {
  await page.evaluate(t => window.seek(t), f / fps);
  await page.screenshot({ path: path.join(tmp, `${String(f - f0).padStart(5, "0")}.jpg`), type: "jpeg", quality: 92 });
  if (f % fps === 0) process.stdout.write(`\rframe ${f}/${f1}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
}
await browser.close();
console.log("\nencoding...");
const args = ["-y", "-loglevel", "error", "-framerate", String(fps), "-i", path.join(tmp, "%05d.jpg")];
if (argv["voice-dir"] && ep.audio?.length) {
  // 行ごとの音声を EPISODE.audio の時刻に並べて重ねる
  const dir = path.resolve(argv["voice-dir"]);
  const dur = (f1 - f0 + 1) / fps;
  ep.audio.forEach(a => args.push("-i", path.join(dir, a.file)));
  const parts = ep.audio.map((a, i) => `[${i + 1}:a]aresample=48000,aformat=channel_layouts=mono,adelay=${Math.round((a.start - f0 / fps) * 1000)}:all=1[v${i}]`);
  const mix = `${ep.audio.map((_, i) => `[v${i}]`).join("")}amix=inputs=${ep.audio.length}:normalize=0,apad,atrim=0:${dur.toFixed(3)},aformat=channel_layouts=stereo[aout]`;
  args.push("-filter_complex", [...parts, mix].join(";"), "-map", "0:v", "-map", "[aout]", "-c:a", "aac", "-b:a", "192k");
} else if (argv.audio) args.push("-i", path.resolve(argv.audio), "-c:a", "aac", "-b:a", "192k", "-shortest");
else args.push("-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-c:a", "aac", "-shortest");
args.push("-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium", "-movflags", "+faststart", outFile);
execFileSync("ffmpeg", args, { stdio: "inherit" });
fs.rmSync(tmp, { recursive: true, force: true });
console.log("done:", outFile);
