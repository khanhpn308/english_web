import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const root=path.resolve(process.cwd());
const out=path.join(root,'docs/design/uxr-02a/assets/r1/frames');
const sheets=path.join(root,'docs/design/uxr-02a/assets/r1/contact-sheets');
const base='http://127.0.0.1:4173/docs/design/uxr-02a/assets/r1/source/preview.html';
const frames=[
  ['R1-A-populated-1366x768-light.png','dashboard','populated','A','light',1366,768,false],
  ['R1-B-populated-1366x768-light.png','dashboard','populated','B','light',1366,768,false],
  ['R1-A-first-run-1366x768-light.png','dashboard','first-run','A','light',1366,768,false],
  ['R1-B-first-run-1366x768-light.png','dashboard','first-run','B','light',1366,768,false],
  ['R1-mixed-null-zero-1366x768-light.png','dashboard','mixed','A','light',1366,768,false],
  ['R1-first-run-390x844-light.png','dashboard','first-run','A','light',390,844,false],
  ['R1-populated-390x844-light.png','dashboard','populated','A','light',390,844,false],
  ['R1-populated-390x844-full.png','dashboard','populated','A','light',390,844,true],
  ['R1-first-run-320x568-full.png','dashboard','first-run','A','light',320,568,true],
  ['R1-review-empty-1366x768-light.png','review','empty','A','light',1366,768,false],
  ['R1-review-empty-390x844-light.png','review','empty','A','light',390,844,false],
  ['R1-heatmap-detail-1366x768-light.png','heatmap','ready','A','light',1366,768,false],
  ['R1-heatmap-tooltip-1366x768-light.png','heatmap','ready','A','light',1366,768,false,'hover','45'],
  ['R1-heatmap-zero-390x844-light.png','heatmap','ready','A','light',390,844,false,'zero','100'],
  ['R1-populated-768x1024-light.png','dashboard','populated','A','light',768,1024,false],
  ['R1-populated-1024x768-light.png','dashboard','populated','A','light',1024,768,false],
  ['R1-populated-1366x768-dark.png','dashboard','populated','A','dark',1366,768,false],
];
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
const page=await browser.newPage();
await fs.mkdir(out,{recursive:true});await fs.mkdir(sheets,{recursive:true});
for(const [name,surface,state,variant,theme,w,h,full,heat,cell] of frames){
  await page.setViewportSize({width:w,height:h});
  const params=new URLSearchParams({surface,state,variant,theme});if(heat){params.set('heatmap',heat);params.set('heatCell',cell)}
  await page.goto(`${base}?${params.toString()}`,{waitUntil:'networkidle'});
  await page.screenshot({path:path.join(out,name),fullPage:full});
}
await page.setViewportSize({width:1500,height:1300});
await page.goto('http://127.0.0.1:4173/docs/design/uxr-02a/assets/r1/contact-sheets/ab.html',{waitUntil:'networkidle'});
await page.screenshot({path:path.join(sheets,'r1-ab-comparison.png'),fullPage:true});
await browser.close();
console.log(`Rendered ${frames.length} corrected R1 frames plus A/B contact sheet`);
