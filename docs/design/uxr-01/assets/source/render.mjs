const playwrightPath = process.env.UXR_PLAYWRIGHT_PATH;
const { chromium } = await import(playwrightPath || 'playwright');
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';

const root = resolve(process.cwd());
const cases = [
  ['dashboard-first-run','light',1440,900,'dashboard-first-run-desktop-1440x900'],
  ['dashboard-first-run','light',390,844,'dashboard-first-run-mobile-390x844'],
  ['dashboard-populated','light',1440,900,'dashboard-populated-desktop-1440x900'],
  ['dashboard-populated','light',390,844,'dashboard-populated-mobile-390x844'],
  ['lookup-search-detail','light',1440,900,'lookup-search-detail-desktop-1440x900'],
  ['lookup-search-detail','light',390,844,'lookup-search-detail-mobile-390x844'],
  ['review','light',1440,900,'review-desktop-1440x900'],
  ['review','light',390,844,'review-mobile-390x844'],
  ['quiz','light',1440,900,'quiz-desktop-1440x900'],
  ['quiz','light',390,844,'quiz-mobile-390x844'],
  ['status-consent','light',1440,900,'status-consent-desktop-1440x900'],
  ['status-consent','light',390,844,'status-consent-mobile-390x844'],
  ['dashboard-populated','light',1366,768,'dashboard-populated-fold-1366x768'],
  ['review','light',768,1024,'review-tablet-768x1024'],
  ['lookup-search-detail','light',320,568,'lookup-search-detail-narrow-320x568'],
  ['status-consent','light',1024,768,'status-consent-intermediate-1024x768'],
  ['dashboard-populated','dark',1440,900,'dashboard-populated-dark-desktop-1440x900'],
  ['status-error','light',390,844,'status-error-unknown-mobile-390x844'],
  ['lookup-preview','light',1024,768,'lookup-preview-long-vietnamese-intermediate-1024x768'],
  ['edit-conflict','light',1440,900,'edit-conflict-desktop-1440x900'],
  ['results','light',1440,900,'results-writing-feedback-source-backed-1440x900'],
];

cases.push(['navigation-drawer','light',320,568,'navigation-drawer-narrow-320x568'],['edit-conflict','light',390,844,'edit-conflict-mobile-390x844'],['results','light',390,844,'results-writing-feedback-mobile-390x844'],['status-error','dark',1440,900,'status-error-consent-dark-desktop-1440x900'],['quiz-unknown','light',390,844,'quiz-autosave-unknown-mobile-390x844'],['review-unknown','light',390,844,'review-rating-unknown-mobile-390x844']);
const browser = await chromium.launch({ headless: true, executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
let rendered = 0;
for (const direction of ['a','b']) {
  const out = resolve(root, `docs/design/uxr-01/assets/${direction}`);
  await mkdir(out, { recursive:true });
  const html = `file:///${root.replaceAll('\\','/')}/docs/design/uxr-01/assets/source/direction-${direction}.html`;
  for (const [scenario,theme,width,height,name] of cases) {
    if (process.argv[2] === 'quiz-only' && !scenario.startsWith('quiz')) continue;
    const page = await browser.newPage({ viewport:{width,height}, deviceScaleFactor:1 });
    await page.goto(`${html}?scenario=${scenario}&theme=${theme}`);
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({path:resolve(out,`${name}.png`),fullPage:false});
    rendered += 1;
    await page.close();
  }
}
await browser.close();
console.log(`Rendered ${rendered} total frames; ${cases.length} scenarios available per direction.`);
