const { chromium } = await import(process.env.UXR_PLAYWRIGHT_PATH || 'playwright');
import { resolve } from 'node:path';
import { writeFile } from 'node:fs/promises';

const root = resolve(process.cwd());
const assetRoot = resolve(root, 'docs/design/uxr-01/assets');
const names = [
  'dashboard-first-run-desktop-1440x900.png','dashboard-populated-desktop-1440x900.png',
  'lookup-search-detail-desktop-1440x900.png','review-desktop-1440x900.png',
  'quiz-desktop-1440x900.png','status-consent-desktop-1440x900.png',
  'dashboard-populated-fold-1366x768.png','review-tablet-768x1024.png',
  'lookup-search-detail-narrow-320x568.png','status-consent-intermediate-1024x768.png',
  'dashboard-populated-dark-desktop-1440x900.png','status-error-unknown-mobile-390x844.png',
  'lookup-preview-long-vietnamese-intermediate-1024x768.png','edit-conflict-desktop-1440x900.png',
  'results-writing-feedback-source-backed-1440x900.png'
];

const html = (direction, subset, title) => `<!doctype html><meta charset="utf-8"><style>
body{margin:0;background:#111827;color:#f8fafc;font-family:Segoe UI,Arial,sans-serif}h1{font-size:22px;margin:0 0 14px}main{padding:24px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.item{background:#1f2937;border:1px solid #475569;border-radius:8px;padding:8px}.item img{width:100%;display:block;border-radius:4px;background:#fff}.cap{font-size:12px;color:#cbd5e1;padding-top:7px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}small{color:#94a3b8;font-weight:400}
</style><main><h1>${title} <small>DESIGN_MOCKUP · SYNTHETIC · v1.2</small></h1><div class="grid">${subset.map(name=>`<div class="item"><img src="../${direction}/${name}"><div class="cap">${direction.toUpperCase()} · ${name.replace('.png','')}</div></div>`).join('')}</div></main>`;

const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
for(const direction of ['a','b']){
  const page=await browser.newPage({viewport:{width:1800,height:1500},deviceScaleFactor:1});
  const out=resolve(assetRoot,'contact-sheets',`${direction}-gallery.html`);
  await writeFile(out,html(direction,names,`Direction ${direction.toUpperCase()} gallery`),'utf8');
  await page.goto(`file:///${out.replaceAll('\\','/')}`); await page.screenshot({path:resolve(assetRoot,'contact-sheets',`${direction}-gallery.png`),fullPage:true}); await page.close();
}
const compareNames=['dashboard-first-run-desktop-1440x900.png','dashboard-populated-desktop-1440x900.png','lookup-search-detail-desktop-1440x900.png','review-desktop-1440x900.png','quiz-desktop-1440x900.png','status-consent-desktop-1440x900.png'];
const compareHtml=`<!doctype html><meta charset="utf-8"><style>body{margin:0;background:#101827;color:#fff;font-family:Segoe UI,Arial}main{padding:24px}h1{font-size:22px}.row{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:12px 0 22px}.cell{background:#1f2937;padding:8px;border-radius:8px}.cell img{width:100%;display:block}.cap{font-size:12px;color:#cbd5e1;padding:6px 0}</style><main><h1>A/B comparison · six matched 1440×900 scenarios · DESIGN_MOCKUP / SYNTHETIC / v1.2</h1>${compareNames.map(n=>`<div class="row"><div class="cell"><img src="../a/${n}"><div class="cap">A · ${n}</div></div><div class="cell"><img src="../b/${n}"><div class="cap">B · ${n}</div></div></div>`).join('')}</main>`;
const page=await browser.newPage({viewport:{width:1800,height:1500},deviceScaleFactor:1});const out=resolve(assetRoot,'contact-sheets','ab-comparison.html');await writeFile(out,compareHtml,'utf8');await page.goto(`file:///${out.replaceAll('\\','/')}`);await page.screenshot({path:resolve(assetRoot,'contact-sheets','ab-comparison.png'),fullPage:true});await page.close();await browser.close();
console.log('Rendered contact sheets');
