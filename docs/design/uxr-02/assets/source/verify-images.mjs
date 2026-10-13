import fs from 'node:fs';
import {chromium} from 'playwright';
const root='docs/design/uxr-02/'; const manifest=JSON.parse(fs.readFileSync(root+'UXR-02-ARTIFACT-MANIFEST.json','utf8'));
const browser=await chromium.launch({headless:true,executablePath:process.env.UXR_CHROME}); const page=await browser.newPage();let count=0;
for(const x of manifest.artifacts.filter(x=>'width' in x)){const url='data:image/png;base64,'+fs.readFileSync(root+x.path).toString('base64');const dimensions=await page.evaluate(async url=>{const img=new Image();img.src=url;await img.decode();return [img.naturalWidth,img.naturalHeight]},url);if(dimensions[0]!==x.width||dimensions[1]!==x.height)throw Error('Decode mismatch: '+x.path);count++;}
await browser.close();console.log(JSON.stringify({decoded_pngs:count,errors:0}));
