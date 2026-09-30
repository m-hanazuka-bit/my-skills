#!/usr/bin/env node
// Pillow が無い環境用：webp などを Chromium で PNG に変換する。 usage: node img_convert.mjs in.webp out.png
import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';
import { createRequire } from 'node:module';

const [src, dst] = process.argv.slice(2);
let chromium;
try { chromium = (await import('playwright')).chromium; }
catch { chromium = createRequire(path.join(execSync('npm root -g').toString().trim(), 'noop.js'))('playwright').chromium; }
const ext = path.extname(src).slice(1).toLowerCase();
const mime = { webp: 'image/webp', gif: 'image/gif', bmp: 'image/bmp', avif: 'image/avif' }[ext] || 'image/' + ext;
const url = `data:${mime};base64,` + fs.readFileSync(src).toString('base64');
const browser = await chromium.launch();
const page = await browser.newPage();
const b64 = await page.evaluate(async (u) => {
  const img = new Image(); img.src = u; await img.decode();
  const c = document.createElement('canvas'); c.width = img.naturalWidth; c.height = img.naturalHeight;
  c.getContext('2d').drawImage(img, 0, 0);
  return c.toDataURL('image/png').split(',')[1];
}, url);
fs.writeFileSync(dst, Buffer.from(b64, 'base64'));
await browser.close();
