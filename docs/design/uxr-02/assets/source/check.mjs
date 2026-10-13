import { chromium } from 'playwright';
const qs=['?variant=a&screen=dashboard','?variant=b&screen=dashboard','?variant=a&screen=dashboard&collapsed=1','?variant=b&screen=detail','?variant=b&screen=dashboard','?variant=b&screen=focus','?variant=b&screen=dashboard&drawer=1','?variant=b&screen=status'];
const sizes=[[1440,900],[1366,768],[1024,768],[768,1024],[390,844],[320,568]];
const b=await chromium.launch({headless:true, executablePath:process.env.UXR_CHROME}); let bad=[];
for(const s of sizes) for(const q of qs){const p=await b.newPage({viewport:{width:s[0],height:s[1]}}); await p.goto('http://127.0.0.1:4179/'+q); const m=await p.evaluate(()=>({sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth,sh:document.documentElement.scrollHeight})); if(m.sw>m.cw+1) bad.push({s,q,m}); await p.close();}
await b.close(); console.log(JSON.stringify({cases:qs.length*sizes.length,horizontalOverflow:bad},null,2));
