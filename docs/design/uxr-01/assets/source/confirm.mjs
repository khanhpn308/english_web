const { chromium } = await import(process.env.UXR_PLAYWRIGHT_PATH || 'playwright');
import { resolve } from 'node:path';
import { writeFile } from 'node:fs/promises';
const root=resolve(process.cwd());
const cases=[
 ['dashboard-first-run',1440,900],['dashboard-first-run',390,844],
 ['dashboard-populated',1440,900],['dashboard-populated',390,844],['dashboard-populated',1366,768],
 ['lookup-search-detail',1440,900],['lookup-search-detail',390,844],['lookup-search-detail',320,568],
 ['review',1440,900],['review',390,844],['review',768,1024],
 ['quiz',1440,900],['quiz',390,844],['status-consent',1440,900],['status-consent',390,844],['status-consent',1024,768],
 ['status-error',390,844],['edit-conflict',1440,900],['edit-conflict',390,844],['results',1440,900],['results',390,844],
 ['lookup-preview',1024,768],['navigation-drawer',320,568],['quiz-unknown',390,844],['review-unknown',390,844]
];
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
const checks=[];
for(const direction of ['a','b']){
 for(const [scenario,width,height] of cases){
  const p=await browser.newPage({viewport:{width,height},deviceScaleFactor:1});
  const errors=[];p.on('pageerror',e=>errors.push(e.message));
  await p.goto(`file:///${root.replaceAll('\\','/')}/docs/design/uxr-01/assets/source/direction-${direction}.html?scenario=${scenario}`);
  const metrics=await p.evaluate(()=>({pageWidth:document.documentElement.scrollWidth,viewportWidth:innerWidth,heading:document.querySelector('h1')?.innerText,mainCount:document.querySelectorAll('main').length,provenance:document.querySelector('.provenance')?.innerText,largestButtonHeight:Math.max(...Array.from(document.querySelectorAll('button')).filter(b=>b.offsetParent).map(b=>b.getBoundingClientRect().height))}));
  checks.push({direction,scenario,width,height,errors,...metrics});await p.close();
 }
}
await browser.close();
await writeFile(resolve(root,'docs/design/uxr-01/research/static-render-checks.json'),JSON.stringify(checks,null,2));
console.log(JSON.stringify({frames:checks.length,overflow:checks.filter(c=>c.pageWidth>c.width).map(c=>[c.direction,c.scenario,c.width,c.pageWidth]),scriptErrors:checks.filter(c=>c.errors.length).length,oversizedButtons:checks.filter(c=>c.largestButtonHeight>90).map(c=>[c.direction,c.scenario,c.largestButtonHeight])}));
