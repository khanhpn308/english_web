import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';
const root = new URL('.', import.meta.url).pathname.replace(/^\//,'').replaceAll('/','\\');
const out = path.resolve(root, '..');
const base = 'http://127.0.0.1:4179';
const cases = [
 ['uxr02-v1-alt-a-dashboard-1440-expanded-light','?variant=a&screen=dashboard'],
 ['uxr02-v1-alt-b-dashboard-1440-expanded-light','?variant=b&screen=dashboard'],
 ['uxr02-v1-alt-a-dashboard-1440-collapsed-light','?variant=a&screen=dashboard&collapsed=1'],
 ['uxr02-v1-alt-b-detail-1440-light','?variant=b&screen=detail'],
 ['uxr02-v1-alt-b-dashboard-1366-fold-light','?variant=b&screen=dashboard'],
 ['uxr02-v1-alt-b-dashboard-1024-light','?variant=b&screen=dashboard'],
 ['uxr02-v1-alt-b-focus-768-tablet-light','?variant=b&screen=focus'],
 ['uxr02-v1-alt-b-dashboard-390-closed-light','?variant=b&screen=dashboard'],
 ['uxr02-v1-alt-b-dashboard-390-open-light','?variant=b&screen=dashboard&drawer=1'],
 ['uxr02-v1-alt-b-dashboard-320-stress-light','?variant=b&screen=dashboard'],
 ['uxr02-v1-alt-b-dashboard-1440-expanded-dark','?variant=b&screen=dashboard&theme=dark'],
 ['uxr02-v1-alt-b-focus-1440-light','?variant=b&screen=focus'],
 ['uxr02-v1-alt-b-status-consent-1440-light','?variant=b&screen=status'],
 ['uxr02-v1-alt-b-status-consent-1440-dark','?variant=b&screen=status&theme=dark']
];
const sizes = { 'uxr02-v1-alt-a-dashboard-1440-expanded-light':[1440,900], 'uxr02-v1-alt-b-dashboard-1440-expanded-light':[1440,900], 'uxr02-v1-alt-a-dashboard-1440-collapsed-light':[1440,900], 'uxr02-v1-alt-b-detail-1440-light':[1440,900], 'uxr02-v1-alt-b-dashboard-1366-fold-light':[1366,768], 'uxr02-v1-alt-b-dashboard-1024-light':[1024,768], 'uxr02-v1-alt-b-focus-768-tablet-light':[768,1024], 'uxr02-v1-alt-b-dashboard-390-closed-light':[390,844], 'uxr02-v1-alt-b-dashboard-390-open-light':[390,844], 'uxr02-v1-alt-b-dashboard-320-stress-light':[320,568], 'uxr02-v1-alt-b-dashboard-1440-expanded-dark':[1440,900], 'uxr02-v1-alt-b-focus-1440-light':[1440,900], 'uxr02-v1-alt-b-status-consent-1440-light':[1440,900], 'uxr02-v1-alt-b-status-consent-1440-dark':[1440,900] };
const browser = await chromium.launch({headless:true, executablePath: process.env.UXR_CHROME || undefined});
for (const [name, query] of cases) { const page = await browser.newPage({viewport:{width:sizes[name][0],height:sizes[name][1]}, deviceScaleFactor:1}); await page.goto(base + query, {waitUntil:'networkidle'}); await page.screenshot({path:path.join(out,name+'.png'), fullPage:false}); await page.close(); }
await browser.close();
console.log(`rendered ${cases.length} screenshots to ${out}`);
