import { chromium } from 'playwright';
import path from 'node:path';
const out=path.resolve('docs/design/uxr-02/assets/r1'); const base='http://127.0.0.1:4180/index-r1.html';
const cases=[
 ['uxr02-r1-dashboard-1440-expanded-light',[1440,900],''],
 ['uxr02-r1-dashboard-1440-collapsed-light',[1440,900],'&collapsed=1'],
 ['uxr02-r1-dashboard-1440-expanded-dark',[1440,900],'&theme=dark'],
 ['uxr02-r1-dashboard-390-closed-light',[390,844],''],
 ['uxr02-r1-dashboard-390-open-light',[390,844],'&drawer=1'],
 ['uxr02-r1-dashboard-320-stress-light',[320,568],'']
];
const b=await chromium.launch({headless:true,executablePath:process.env.UXR_CHROME});
for(const [name,[w,h],extra] of cases){const p=await b.newPage({viewport:{width:w,height:h},deviceScaleFactor:1});await p.goto(base+'?'+extra,{waitUntil:'networkidle'});await p.screenshot({path:path.join(out,name+'.png'),fullPage:false});await p.close();}
await b.close(); console.log('rendered',cases.length,'R1 screenshots');
