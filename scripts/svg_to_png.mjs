// Render an SVG to PNG with the frontend's Playwright Chromium: node scripts/svg_to_png.mjs in.svg out.png [scale]
import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import { readFileSync } from 'node:fs';
const [,, svgPath, pngPath, scale = '2'] = process.argv;
const svg = readFileSync(svgPath, 'utf8');
const [, w, h] = svg.match(/width="(\d+)" height="(\d+)"/);
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: +w, height: +h }, deviceScaleFactor: +scale });
await page.setContent(`<html><body style="margin:0">${svg}</body></html>`);
await page.locator('svg').first().screenshot({ path: pngPath });
await browser.close();
