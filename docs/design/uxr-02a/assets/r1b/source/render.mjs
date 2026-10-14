import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';

const root=path.resolve(process.cwd());
const base='http://127.0.0.1:4176/docs/design/uxr-02a/assets/r1b/source/preview.html';
const out=path.join(root,'docs/design/uxr-02a/assets/r1b/frames');
const sheet=path.join(root,'docs/design/uxr-02a/assets/r1b/contact-sheets');
await fs.mkdir(out,{recursive:true});await fs.mkdir(sheet,{recursive:true});
const server=spawn('python',['-m','http.server','4176','--bind','127.0.0.1'],{stdio:'ignore',windowsHide:true});
const frames=[
 ['R1B-A-first-run-1366x768.png',1366,768,'state=first-run&variant=A'],
 ['R1B-B-first-run-1366x768.png',1366,768,'state=first-run&variant=B'],
 ['R1B-mixed-1366x768.png',1366,768,'state=mixed&variant=A'],
 ['R1B-populated-1366x768.png',1366,768,'state=populated&variant=A'],
 ['R1B-heatmap-default-1366x768.png',1366,768,'state=populated&variant=A'],
 ['R1B-heatmap-keyboard-1366x768.png',1366,768,'state=populated&heatmap=keyboard&heatCell=0'],
 ['R1B-heatmap-tooltip-1366x768.png',1366,768,'state=populated&heatmap=hover&heatCell=45'],
 ['R1B-heatmap-mobile-tap-390x844.png',390,844,'state=populated&heatmap=tap&heatCell=97'],
 ['R1B-first-run-390x844.png',390,844,'state=first-run&variant=A'],
 ['R1B-heatmap-dark-1366x768.png',1366,768,'state=populated&theme=dark'],
];
try{
 await new Promise(r=>setTimeout(r,500));
 const b=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});const p=await b.newPage();
 for(const [name,w,h,query] of frames){await p.setViewportSize({width:w,height:h});await p.goto(`${base}?${query}`,{waitUntil:'networkidle'});await p.screenshot({path:path.join(out,name),fullPage:false});}
 const html=`<!doctype html><meta charset="utf-8"><style>body{font:14px Segoe UI,Arial;margin:24px;background:#eff5f6;color:#182d52}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:18px}figure{margin:0;background:white;padding:12px;border-radius:8px}img{display:block;width:100%;height:auto}figcaption{font-weight:700;margin-bottom:9px}@media(max-width:800px){.grid{grid-template-columns:1fr}}</style><h1>UXR-02A-R1B final targeted correction packet</h1><p>DESIGN_MOCKUP · SYNTHETIC_DESIGN_FIXTURE · A04/A02/A08 corrected; A12 preserved.</p><div class="grid">${frames.map(([n])=>`<figure><figcaption>${n}</figcaption><img src="../frames/${n}"></figure>`).join('')}</div>`;
 await fs.writeFile(path.join(sheet,'r1b-final.html'),html);await p.setViewportSize({width:1400,height:1200});await p.goto('http://127.0.0.1:4176/docs/design/uxr-02a/assets/r1b/contact-sheets/r1b-final.html',{waitUntil:'networkidle'});await p.screenshot({path:path.join(sheet,'r1b-final.png'),fullPage:true});await b.close();console.log(`Rendered ${frames.length} R1B frames plus contact sheet`);
}finally{server.kill();}
