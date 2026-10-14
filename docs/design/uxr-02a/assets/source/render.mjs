import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const root = path.resolve(process.cwd());
const out = path.join(root, 'docs/design/uxr-02a/assets/frames');
const base = 'http://127.0.0.1:4173/docs/design/uxr-02a/assets/source/preview.html';

const frames = [
  ['D1-dashboard-first-run-1366x768-light.png','dashboard','first-run','A','light',1366,768],
  ['D2-dashboard-first-run-390x844-light.png','dashboard','first-run','A','light',390,844],
  ['D3-dashboard-populated-1366x768-light.png','dashboard','populated','A','light',1366,768],
  ['D4-dashboard-populated-390x844-light.png','dashboard','populated','A','light',390,844],
  ['D5-dashboard-mixed-1366x768-light.png','dashboard','mixed','A','light',1366,768],
  ['D6-dashboard-first-run-320x568-light.png','dashboard','first-run','A','light',320,568],
  ['R1-review-empty-1366x768-light.png','review','empty','A','light',1366,768],
  ['R2-review-empty-390x844-light.png','review','empty','A','light',390,844],
  ['R3-review-unknown-pending-390x844-light.png','review','unknown','A','light',390,844],
  ['S1-status-consent-summary-1366x768-light.png','status','ready','A','light',1366,768],
  ['S2-status-consent-summary-390x844-light.png','status','ready','A','light',390,844],
  ['S3-status-degraded-1366x768-light.png','status','degraded','A','light',1366,768],
  ['D1-dashboard-first-run-1366x768-annotated.png','dashboard','first-run','A','light',1366,768,'1'],
  ['D1-dashboard-first-run-1366x768-dark.png','dashboard','first-run','A','dark',1366,768],
  ['D3-dashboard-populated-1366x768-dark.png','dashboard','populated','A','dark',1366,768],
  ['VB-dashboard-first-run-1366x768-light.png','dashboard','first-run','B','light',1366,768],
  ['VB-dashboard-populated-390x844-light.png','dashboard','populated','B','light',390,844],
  ['tablet-dashboard-populated-768x1024-light.png','dashboard','populated','A','light',768,1024],
  ['intermediate-dashboard-populated-1024x768-light.png','dashboard','populated','A','light',1024,768],
  ['board-g1-g9-1366x768-light.png','board','ready','A','light',1366,768],
];

const browser = await chromium.launch({headless:true, executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
const page = await browser.newPage();
await fs.mkdir(out,{recursive:true});
for (const [name,surface,state,variant,theme,w,h,annotated='0'] of frames) {
  await page.setViewportSize({width:w,height:h});
  await page.goto(`${base}?surface=${surface}&state=${state}&variant=${variant}&theme=${theme}&annotated=${annotated}`,{waitUntil:'networkidle'});
  await page.screenshot({path:path.join(out,name),fullPage:false});
}
const sheets = path.join(root,'docs/design/uxr-02a/assets/contact-sheets');
await page.setViewportSize({width:1400,height:1800});
await page.goto('http://127.0.0.1:4173/docs/design/uxr-02a/assets/contact-sheets/gallery.html',{waitUntil:'networkidle'});
await page.screenshot({path:path.join(sheets,'gallery.png'),fullPage:true});
await page.setViewportSize({width:1400,height:1800});
await page.goto('http://127.0.0.1:4173/docs/design/uxr-02a/assets/contact-sheets/before-proposed.html',{waitUntil:'networkidle'});
await page.screenshot({path:path.join(sheets,'before-proposed.png'),fullPage:true});
await browser.close();
console.log(`Rendered ${frames.length} frames plus contact sheets`);
