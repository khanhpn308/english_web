import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
const dir='docs/design/uxr-02a/assets/r1/a12';
const base='http://127.0.0.1:4175/'+dir+'/source/preview.html';
const server=spawn('python',['-m','http.server','4175','--bind','127.0.0.1'],{stdio:'ignore',windowsHide:true});
let browser;
const report={engine:'Installed Chrome via Playwright',scope:'Isolated DESIGN_MOCKUP / SYNTHETIC_DESIGN_FIXTURE',geometry:[],interactions:{},images:[]};
try {
  await new Promise(resolve=>setTimeout(resolve,500));
  browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const page=await browser.newPage();
  page.on('pageerror',e=>{throw e;});
  for(const [w,h] of [[1366,768],[1024,768],[768,1024],[390,844],[320,568]]) {
    for(const theme of ['light','dark']) for(const variant of ['A','B']) {
      await page.setViewportSize({width:w,height:h});
      await page.goto(base+'?state=populated&variant='+variant+'&theme='+theme);
      const measured=await page.evaluate(()=>{
        const grid=document.querySelector('.r1-heat-grid'),rect=grid.getBoundingClientRect();
        const card=grid.closest('.card').getBoundingClientRect();
        const cells=[...grid.querySelectorAll('button')];
        return {width:innerWidth,theme:document.documentElement.dataset.theme,variant:document.documentElement.dataset.variant,
          gridWidth:rect.width,gridHeight:rect.height,ratio:rect.width/rect.height,
          gap:getComputedStyle(grid).gap,cellCount:cells.length,padding:document.querySelectorAll('.heat-padding').length,
          maxCellDifference:Math.max(...cells.map(b=>{const r=b.getBoundingClientRect();return Math.abs(r.width-r.height)})),
          cellSize:[cells[0].getBoundingClientRect().width,cells[0].getBoundingClientRect().height],
          centeredError:Math.abs((rect.left+rect.right)/2-(card.left+card.right)/2),
          borders:cells.every(b=>getComputedStyle(b).borderTopWidth==='0px'),
          horizontalOverflow:document.documentElement.scrollWidth>innerWidth,
          dates:cells.map(b=>b.dataset.date), levels:[...new Set(cells.map(b=>b.className))]};
      });
      assert.equal(measured.cellCount,105);assert.equal(new Set(measured.dates).size,105);
      assert.equal(measured.dates[0],'2026-09-28');assert.equal(measured.dates.at(-1),'2027-01-10');
      assert(measured.dates.every((d,i)=>i===0||Date.parse(d)-Date.parse(measured.dates[i-1])===86400000));
      assert.equal(measured.padding,16);
      assert(measured.maxCellDifference<=0.05);assert(Math.abs(measured.gridWidth-measured.gridHeight)<=0.1);
      assert(measured.centeredError<=1);assert(measured.borders);assert(!measured.horizontalOverflow);
      delete measured.dates;report.geometry.push(measured);
    }
  }
  async function capture(name,w,h,query,{full=false,card=false}={}) {
    await page.setViewportSize({width:w,height:h});await page.goto(base+'?'+query);
    const path=dir+'/frames/'+name;
    if(card)await page.locator('.r1-heat').locator('xpath=..').screenshot({path});
    else await page.screenshot({path,fullPage:full});
    report.images.push({name,cssViewport:[w,h],capture:card?'heatmap card at native resolution':full?'full page':'viewport'});
  }
  await capture('A12-dashboard-A-desktop.png',1366,768,'state=populated');
  await capture('A12-dashboard-B-desktop.png',1366,768,'state=populated&variant=B');
  await capture('A12-desktop-default.png',1366,768,'state=populated',{card:true});
  await capture('A12-desktop-tooltip.png',1366,768,'state=populated&heatmap=hover&heatCell=45');
  await capture('A12-desktop-dark.png',1366,768,'state=populated&theme=dark',{card:true});
  await capture('A12-tablet-default.png',768,1024,'state=populated',{card:true});
  await capture('A12-mobile-390-default.png',390,844,'state=populated',{card:true});
  await capture('A12-mobile-390-tooltip.png',390,844,'state=populated&heatmap=tap&heatCell=103',{card:true});
  await capture('A12-mobile-320-default.png',320,568,'state=populated',{card:true});
  await capture('A12-mobile-320-dark.png',320,568,'state=populated&theme=dark',{card:true});
  await capture('A12-dashboard-390-full.png',390,844,'state=populated',{full:true});
  await capture('A12-dashboard-320-full.png',320,568,'state=populated',{full:true});
  await page.setViewportSize({width:1366,height:768});await page.goto(base+'?state=populated');
  const first=page.locator('[data-calendar-index="0"]');
  await first.hover();assert.equal(await page.locator('[data-tooltip-mode="hover"]').count(),1);
  assert((await page.locator('.r1-heat-tooltip').innerText()).includes('2026-09-28'));
  await page.mouse.move(220,50);assert.equal(await page.locator('.r1-heat-tooltip').count(),0);
  await first.focus();assert.equal(await page.locator('[data-tooltip-mode="keyboard"]').count(),1);
  await first.press('ArrowRight');assert.equal(await page.evaluate(()=>document.activeElement.dataset.date),'2026-09-29');
  assert.equal(await page.evaluate(()=>getComputedStyle(document.activeElement).outlineWidth),'2px');
  await page.keyboard.press('Escape');assert.equal(await page.locator('.r1-heat-tooltip').count(),0);
  report.interactions={hover:true,pointerExit:true,keyboardFocus:true,arrowMovement:true,focusOutline:'2px',escape:true};
  const touchContext=await browser.newContext({viewport:{width:390,height:844},hasTouch:true,isMobile:true});
  const touchPage=await touchContext.newPage();await touchPage.goto(base+'?state=populated');
  await touchPage.locator('[data-calendar-index="97"]').tap();
  assert.equal(await touchPage.locator('[data-tooltip-mode="tap"]').count(),1);
  const tip=await touchPage.locator('.r1-heat-tooltip').boundingBox();assert(tip.x>=0&&tip.x+tip.width<=390);
  await touchPage.locator('[data-heat-close]').tap();assert.equal(await touchPage.locator('.r1-heat-tooltip').count(),0);
  report.interactions.emulatedTouchTap=true;report.interactions.close=true;report.interactions.mobileTooltipInViewport=true;
  await touchContext.close();
  await page.goto(base+'?state=first-run');
  assert.equal(await page.locator('[data-heat-index]').count(),0);
  const empty=await page.locator('.a12-empty').boundingBox();
  assert(Math.abs(empty.width-empty.height)<=0.1);
  report.firstRun={noFabricatedCells:true,squareEnvelope:[empty.width,empty.height]};
  const tiles=['A12-desktop-default.png','A12-desktop-dark.png','A12-mobile-390-default.png','A12-mobile-390-tooltip.png','A12-mobile-320-default.png','A12-mobile-320-dark.png'];
  const sheet=dir+'/contact-sheet.html';
  await fs.writeFile(sheet,'<!doctype html><meta charset="utf-8"><style>body{font:14px Segoe UI,Arial;margin:24px;background:#eff5f6;color:#182d52}.tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}figure{margin:0;background:white;padding:14px;border-radius:8px}img{width:100%;height:auto}figcaption{margin-bottom:12px;font-weight:600}</style><h1>A12 · Square heatmap review</h1><p>DESIGN_MOCKUP · SYNTHETIC_DESIGN_FIXTURE · 105 dates, 16 non-data padding slots.</p><div class="tiles">'+tiles.map(n=>'<figure><figcaption>'+n.replace('A12-','').replace('.png','')+'</figcaption><img src="frames/'+n+'"></figure>').join('')+'</div>');
  await page.setViewportSize({width:1280,height:1000});
  await page.goto('http://127.0.0.1:4175/'+sheet);
  await page.locator('img').evaluateAll(imgs=>Promise.all(imgs.map(i=>i.decode())));
  await page.screenshot({path:dir+'/contact-sheet.png',fullPage:true});
  const files=await fs.readdir(dir+'/frames');
  for(const name of files.filter(n=>n.endsWith('.png'))){
    const png=await fs.readFile(dir+'/frames/'+name);const entry=report.images.find(e=>e.name===name);
    if(entry){entry.pixels=[png.readUInt32BE(16),png.readUInt32BE(20)];}
  }
  report.status='PASS';await fs.writeFile(dir+'/verification.json',JSON.stringify(report,null,2));
  console.log(JSON.stringify({status:report.status,geometryCases:report.geometry.length,images:report.images.length,interaction:report.interactions}));
} finally {await browser?.close();server.kill();}
