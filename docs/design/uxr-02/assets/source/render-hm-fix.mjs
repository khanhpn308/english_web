import { chromium } from 'playwright';
import path from 'node:path';
import fs from 'node:fs';
const out=path.resolve('docs/design/uxr-02/assets/final/hm-fix'); fs.mkdirSync(out,{recursive:true});
const base='http://127.0.0.1:4183/index-hm-fix.html';
const b=await chromium.launch({headless:true,executablePath:process.env.UXR_CHROME});
async function open(query,w,h){const p=await b.newPage({viewport:{width:w,height:h},deviceScaleFactor:1});await p.goto(`${base}?${query}`,{waitUntil:'networkidle'});return p;}
const dash=await open('heatmap=default',1440,900);await dash.screenshot({path:path.join(out,'uxr02-hm-fix-dashboard-1440-light.png'),fullPage:false});await dash.close();
const def=await open('heatmap=default',1440,900);await def.locator('.final-heat-panel').screenshot({path:path.join(out,'uxr02-hm-fix-heatmap-default.png')});await def.close();
const left=await open('heatmap=default',1440,900);await left.locator('[data-heat-key="2026-09-30"]').hover();await left.locator('.final-heat-panel').screenshot({path:path.join(out,'uxr02-hm-fix-hover-left.png')});await left.close();
const center=await open('heatmap=default',1440,900);await center.locator('[data-heat-key="2026-10-12"]').hover();await center.locator('.final-heat-panel').screenshot({path:path.join(out,'uxr02-hm-fix-hover-center.png')});await center.close();
const edge=await open('heatmap=default',1440,900);await edge.locator('[data-heat-key="2027-01-01"]').hover();await edge.locator('.final-heat-panel').screenshot({path:path.join(out,'uxr02-hm-fix-hover-right-bottom.png')});await edge.close();
const zero=await open('heatmap=zero',1440,900);await zero.locator('.final-heat-panel').screenshot({path:path.join(out,'uxr02-hm-fix-zero-activity.png')});await zero.close();
const dark=await open('theme=dark&heatmap=hover',1440,900);await dark.locator('.final-heat-panel').screenshot({path:path.join(out,'uxr02-hm-fix-dark.png')});await dark.close();
const mobile=await open('heatmap=default',390,844);const panel=mobile.locator('.final-heat-panel');await panel.scrollIntoViewIfNeeded();await mobile.locator('[data-heat-key="2026-10-12"]').click();await panel.screenshot({path:path.join(out,'uxr02-hm-fix-mobile-tap.png')});await mobile.close();
await b.close();console.log('rendered HM-FIX evidence');
