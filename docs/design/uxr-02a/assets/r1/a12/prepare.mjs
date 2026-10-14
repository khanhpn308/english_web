import fs from 'node:fs/promises';
const original = 'docs/design/uxr-02a/assets/r1/source/';
const target = 'docs/design/uxr-02a/assets/r1/a12/';
await fs.mkdir(target + 'source', { recursive: true });
await fs.mkdir(target + 'frames', { recursive: true });
let html = await fs.readFile(original + 'preview.html', 'utf8');
html = html.replace('</head>', '<link rel="stylesheet" href="square.css"></head>');
await fs.writeFile(target + 'source/preview.html', html);
let js = await fs.readFile(original + 'preview.js', 'utf8');
const begin = js.indexOf('function heatmapMarkup(');
const end = js.indexOf('\nconst books=', begin);
if (begin < 0 || end < 0) throw new Error('Missing heatmap function boundary');
const heatmap = `function heatmapMarkup(detail=false){
  const chronological = [...allHeat].sort((a,b)=>a.index-b.index);
  const activeIndex = heatMode==='zero'?104:heatTarget?Number(heatTarget):heatMode?45:-1;
  const cells = chronological.map(cell=>{
    const originalIndex = allHeat.indexOf(cell);
    const cls = cell.count===null?'unknown':\`level-\${level(cell.count)}\`;
    return \`<span class="r1-heat-wrap"><button class="r1-heat-cell \${cls}" data-heat-index="\${originalIndex}" data-date="\${iso(cell.date)}" data-calendar-index="\${cell.index}" aria-label="\${viDate(cell.date)}. \${heatDescription(cell)}." aria-expanded="false" tabindex="\${cell.index===0?0:-1}"></button></span>\`;
  }).join('');
  return \`<div class="r1-heat \${detail?'r1-heat-detail':''}" data-initial-index="\${activeIndex}"><div class="r1-heat-grid" aria-label="Lịch sử học: 105 ngày liên tiếp, từ trái sang phải rồi xuống hàng">\${cells}\${'<span class="heat-padding" aria-hidden="true"></span>'.repeat(16)}</div><div class="r1-heat-legend"><span>Ít</span>\${[0,1,2,3,4].map(n=>'<i class="l'+n+'" aria-label="Mức '+n+'"></i>').join('')}<span>Nhiều</span></div><p class="r1-full-note">28/09/2026–10/01/2027 · 105 ngày<br>Đọc từ trái sang phải, rồi xuống hàng. 16 ô cuối là khoảng trống bố cục, không phải ngày.<br>DESIGN_MOCKUP · SYNTHETIC_DESIGN_FIXTURE</p></div>\`;
}
`;
js = js.slice(0, begin) + heatmap + js.slice(end);
const wireBegin = js.indexOf('function wireInteractions(){');
const carouselBegin = js.indexOf("  const prev=document.querySelector('[data-book-prev]')", wireBegin);
if (wireBegin < 0 || carouselBegin < 0) throw new Error('Missing interaction boundary');
const wire = `function wireInteractions(){
  const heat = document.querySelector('.r1-heat');
  if (heat) {
    const grid = heat.querySelector('.r1-heat-grid');
    const buttons = [...heat.querySelectorAll('[data-heat-index]')];
    let mode = null, suppressed = false;
    const dismiss = () => {
      heat.querySelector('.r1-heat-tooltip')?.remove();
      buttons.forEach(b=>{b.classList.remove('active');b.setAttribute('aria-expanded','false');b.removeAttribute('aria-describedby');});
      mode=null;
    };
    const show = (button, interaction) => {
      if(interaction==='hover' && suppressed) return;
      dismiss(); mode=interaction;
      const cell=allHeat[Number(button.dataset.heatIndex)];
      const wrap=button.parentElement;
      wrap.insertAdjacentHTML('beforeend',heatTooltip(cell,interaction));
      const tip=wrap.querySelector('.r1-heat-tooltip');tip.id='heat-active-tip';
      button.classList.add('active');button.setAttribute('aria-expanded','true');button.setAttribute('aria-describedby',tip.id);
      const br=button.getBoundingClientRect(), tr=tip.getBoundingClientRect(), gr=grid.getBoundingClientRect();
      const left=Math.max(gr.left+2,Math.min(br.left,gr.right-tr.width-2));
      tip.style.left=(left-br.left)+'px';
      tip.style.top=(br.top+br.height+tr.height>gr.bottom ? -tr.height-6 : br.height+6)+'px';
      tip.querySelector('button').addEventListener('mousedown',e=>e.preventDefault());
      tip.querySelector('button').addEventListener('click',e=>{e.stopPropagation();suppressed=true;dismiss();});
    };
    buttons.forEach((button,i)=>{
      button.addEventListener('mouseenter',()=>show(button,'hover'));
      button.addEventListener('focus',()=>{suppressed=false;show(button,'keyboard');});
      button.addEventListener('click',()=>{suppressed=false;show(button,'tap');});
      button.addEventListener('keydown',e=>{
        if(e.key==='Escape'){e.preventDefault();suppressed=true;dismiss();return;}
        let next=i;
        if(e.key==='ArrowRight')next=Math.min(buttons.length-1,i+1);
        if(e.key==='ArrowLeft')next=Math.max(0,i-1);
        if(e.key==='ArrowDown')next=Math.min(buttons.length-1,i+11);
        if(e.key==='ArrowUp')next=Math.max(0,i-11);
        if(e.key==='Home')next=0;if(e.key==='End')next=buttons.length-1;
        if(next!==i){e.preventDefault();buttons.forEach(b=>b.tabIndex=-1);buttons[next].tabIndex=0;buttons[next].focus();}
      });
    });
    heat.addEventListener('mouseleave',()=>{if(mode==='hover')dismiss();suppressed=false;});
    document.addEventListener('click',e=>{if(!heat.contains(e.target))dismiss();});
    document.addEventListener('keydown',e=>{if(e.key==='Escape'){suppressed=true;dismiss();}});
    const initial=buttons.find(b=>Number(b.dataset.heatIndex)===Number(heat.dataset.initialIndex));
    if(initial)show(initial,heatMode||'hover');
  }
`;
js = js.slice(0,wireBegin) + wire + js.slice(carouselBegin);
js = js.replace('R1 corrected','R1 + A12 square geometry');
// Keep the no-history envelope square without manufacturing dated activity cells.
js = js.replace("const historyMarkup=(!populated&&!mixed)?'<div class=\"empty-surface\">", "const historyMarkup=(!populated&&!mixed)?'<div class=\"empty-surface a12-empty\">");
await fs.writeFile(target+'source/preview.js',js);
console.log('Created versioned A12 preview; original R1 source untouched.');
