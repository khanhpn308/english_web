import { chromium } from 'playwright';
import path from 'node:path';
const out=path.resolve('docs/design/uxr-02/assets/r2'); const base='http://127.0.0.1:4181/index-r2.html';
const cases=[
 ['uxr02-r2-dashboard-1440-expanded-light',[1440,900],'',false],
 ['uxr02-r2-dashboard-1440-collapsed-light',[1440,900],'&collapsed=1',false],
 ['uxr02-r2-dashboard-1440-expanded-dark',[1440,900],'&theme=dark',false],
 ['uxr02-r2-dashboard-390-closed-light-top',[390,844],'',false],
 ['uxr02-r2-dashboard-390-closed-light-full',[390,844],'',true],
 ['uxr02-r2-dashboard-390-open-light',[390,844],'&drawer=1',false],
 ['uxr02-r2-dashboard-320-stress-light-full',[320,568],'',true],
 ['uxr02-r2-dashboard-1440-expanded-light-full',[1440,900],'',true]
];
const b=await chromium.launch({headless:true,executablePath:process.env.UXR_CHROME});
for(const [name,[w,h],extra,fullPage] of cases){const p=await b.newPage({viewport:{width:w,height:h},deviceScaleFactor:1});await p.goto(base+'?'+extra,{waitUntil:'networkidle'});await p.screenshot({path:path.join(out,name+'.png'),fullPage});await p.close();}
await b.close(); console.log('rendered',cases.length,'R2 screenshots');
