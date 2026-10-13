import { chromium } from 'playwright';
import path from 'node:path';
import fs from 'node:fs';
const out=path.resolve('docs/design/uxr-02/assets/final'); fs.mkdirSync(out,{recursive:true});
const base='http://127.0.0.1:4182/index-final.html';
const browser=await chromium.launch({headless:true,executablePath:process.env.UXR_CHROME});
async function open(query,width,height){const page=await browser.newPage({viewport:{width,height},deviceScaleFactor:1});await page.goto(`${base}?${query}`,{waitUntil:'networkidle'});return page;}
const primary=await open('heatmap=default',1440,900);console.log('primary');await primary.screenshot({path:path.join(out,'uxr02-final-dashboard-1440-light.png'),fullPage:false});await primary.close();
const defaults=await open('heatmap=default',900,700);console.log('default');await defaults.locator('.final-heat-panel').screenshot({path:path.join(out,'uxr02-final-heatmap-default.png')});await defaults.close();
const hover=await open('heatmap=default',900,700);console.log('hover');await hover.locator('[data-heat-key="w2-d0"]').hover();await hover.locator('.final-heat-panel').screenshot({path:path.join(out,'uxr02-final-heatmap-hover.png')});await hover.close();
const zero=await open('heatmap=zero',900,700);console.log('zero');await zero.locator('.final-heat-panel').screenshot({path:path.join(out,'uxr02-final-heatmap-zero-activity.png')});await zero.close();
const dark=await open('theme=dark&heatmap=hover',900,700);console.log('dark');await dark.locator('.final-heat-panel').screenshot({path:path.join(out,'uxr02-final-heatmap-dark.png')});await dark.close();
await browser.close();console.log('rendered final heatmap packet');
