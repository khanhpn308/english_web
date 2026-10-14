const q = new URLSearchParams(location.search);
const surface = q.get('surface') || 'dashboard';
const state = q.get('state') || 'first-run';
const variant = q.get('variant') || 'A';
const theme = q.get('theme') || 'light';
const heatMode = q.get('heatmap') || '';
const heatTarget = q.get('heatCell') || '';
document.documentElement.dataset.theme = theme;
document.documentElement.dataset.variant = variant;

const nav = [['⌂','Tổng quan','dashboard'],['◷','Ôn tập','review'],['◇','Quiz','quiz'],['⌕','Tra từ','lookup'],['≡','Tìm kiếm','search'],['●','Trạng thái','status']];
const pageHeader = (eyebrow,title,sub,cta='') => `<div class="title-row"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p class="sub">${sub}</p></div>${cta}</div>`;
function shell(crumb, content) {
  const learning = nav.slice(0,3).map(n => `<div class="nav-item ${surface===n[2]?'active':''}"><span class="ico">${n[0]}</span>${n[1]}</div>`).join('');
  const vocab = nav.slice(3,5).map(n => `<div class="nav-item ${surface===n[2]?'active':''}"><span class="ico">${n[0]}</span>${n[1]}</div>`).join('');
  return `<div class="app"><aside class="rail"><div class="brand"><strong>English Web</strong><span>Nhật ký học tập</span></div><nav class="nav-group"><div class="nav-label">Học tập</div>${learning}</nav><nav class="nav-group"><div class="nav-label">Từ vựng</div>${vocab}</nav><nav class="nav-group"><div class="nav-label">Hệ thống</div><div class="nav-item ${surface==='status'?'active':''}"><span class="ico">⚙</span>Trạng thái</div><div class="nav-item"><span class="ico">◉</span>AI consent</div></nav><div class="rail-foot">Bản R1 · UXR-02A<br/>DESIGN_MOCKUP · SYNTHETIC_DESIGN_FIXTURE</div></aside><section class="workspace"><header class="topbar"><div class="crumb"><button class="mobile-menu">☰</button><small>English Web /</small><b>${crumb}</b></div><div class="top-actions"><span class="status-pill">● Học cục bộ sẵn sàng</span><div class="avatar">K</div></div></header><main class="content">${content}</main></section></div>`;
}
const card = (title, body, extra='') => `<section class="card ${extra}"><h2>${title}</h2>${body}</section>`;

const HEAT_COUNTS = [[0,3,12,0,4,7,1,10,5,0,8,2,0,1,0],[2,10,5,1,0,8,6,3,9,4,0,7,2,0,3],[4,6,0,3,2,12,4,6,8,1,5,9,2,0,4],[1,8,5,0,3,7,2,11,5,4,0,6,3,1,2],[0,2,7,3,0,5,4,8,2,10,6,1,4,0,2],[3,5,2,0,6,9,3,4,7,2,0,5,1,3,0],[0,1,4,2,0,8,5,3,0,6,2,1,4,null,0]];
const HEAT_START = new Date(Date.UTC(2026,8,28));
const dateFromIndex = (index) => new Date(HEAT_START.getTime()+index*86400000);
const iso = (date) => date.toISOString().slice(0,10);
const viDate = (date) => new Intl.DateTimeFormat('vi-VN',{day:'2-digit',month:'2-digit',year:'numeric',timeZone:'UTC'}).format(date);
const level = (count) => count===null?-1:count===0?0:count<=2?1:count<=5?2:count<=9?3:4;
const allHeat = HEAT_COUNTS.flatMap((row,rowIndex)=>row.map((count,col)=>({count,row:rowIndex,col,index:col*7+rowIndex,date:dateFromIndex(col*7+rowIndex)})));
function heatDescription(cell){if(cell.count===null)return 'Dữ liệu lịch sử chưa xác minh';if(cell.count===0)return '0 hoạt động học tập';return `${cell.count} hoạt động học tập`;}
function heatTooltip(cell,mode){const unknown=cell.count===null;return `<div class="r1-heat-tooltip" role="status" data-tooltip-mode="${mode}"><strong>${unknown?'UNKNOWN · dữ liệu chưa xác minh':heatDescription(cell)}</strong><span>${viDate(cell.date)} · ${iso(cell.date)}</span><small>${unknown?'Không hiển thị như mức 0.':'Mức '+level(cell.count)+' · ngày thuộc fixture 105 ngày.'}</small><button type="button" data-heat-close>Đóng</button></div>`;}
function heatmapMarkup(detail=false){
  const chronological = [...allHeat].sort((a,b)=>a.index-b.index);
  const activeIndex = heatMode==='zero'?104:heatTarget?Number(heatTarget):heatMode?45:-1;
  const cells = chronological.map(cell=>{
    const originalIndex = allHeat.indexOf(cell);
    const cls = cell.count===null?'unknown':`level-${level(cell.count)}`;
    return `<span class="r1-heat-wrap"><button class="r1-heat-cell ${cls}" data-heat-index="${originalIndex}" data-date="${iso(cell.date)}" data-calendar-index="${cell.index}" aria-label="${viDate(cell.date)}. ${heatDescription(cell)}." aria-expanded="false" tabindex="${cell.index===0?0:-1}"></button></span>`;
  }).join('');
  return `<div class="r1-heat ${detail?'r1-heat-detail':''}" data-initial-index="${activeIndex}"><div class="r1-heat-grid" aria-label="Lịch sử học: 105 ngày liên tiếp, từ trái sang phải rồi xuống hàng">${cells}${'<span class="heat-padding" aria-hidden="true"></span>'.repeat(16)}</div><div class="r1-heat-legend"><span>Ít</span>${[0,1,2,3,4].map(n=>'<i class="l'+n+'" aria-label="Mức '+n+'"></i>').join('')}<span>Nhiều</span></div><p class="r1-full-note">28/09/2026–10/01/2027 · 105 ngày<br>Đọc từ trái sang phải, rồi xuống hàng. 16 ô cuối là khoảng trống bố cục, không phải ngày.<br>DESIGN_MOCKUP · SYNTHETIC_DESIGN_FIXTURE</p></div>`;
}

const books=[['Oxford 4000 Essential English','Chương 3 / 12','Bài 18 / 42','42%'],['English Collocations in Use','Chương 2 / 10','Bài 7 / 30','28%'],['Academic Vocabulary','Chương 5 / 8','Bài 21 / 24','76%'],['Practical English Usage','Chương 1 / 14','Bài 4 / 36','12%'],['English Phrasal Verbs','Chương 7 / 9','Bài 16 / 20','81%']];
function bookCard(populated){
  if(!populated)return `<section class="card book-card"><div class="carousel-head"><div><div class="eyebrow">SÁCH GẦN ĐÂY</div><h2>Chưa có sách gần đây</h2></div><span class="tag info">EMPTY</span></div><div class="book-empty"><div><b>Danh sách sách sẽ xuất hiện sau phiên học đầu tiên.</b><p>Tra từ và lưu nội dung để tạo lịch sử học.</p><button class="secondary">Mở tra từ</button></div></div></section>`;
  const index=Math.max(0,Math.min(4,Number(q.get('book')||0)));const b=books[index];
  return `<section class="card book-card"><div class="carousel-head"><div><div class="eyebrow">SÁCH GẦN ĐÂY</div><h2>${b[0]}</h2><p class="meta">${b[1]} · ${b[2]}</p></div><div class="carousel-nav"><button class="round-arrow" data-book-prev aria-label="Sách trước">‹</button><span class="meta">${index+1} / 5</span><button class="round-arrow" data-book-next aria-label="Sách tiếp theo">›</button></div></div><div class="book-art"></div><p class="meta">Một cuốn sách hiển thị trong mỗi frame; không có sách lân cận bị cắt.</p><div class="book-progress"><span style="width:${b[3]}"></span></div><span class="meta">${b[3]} tiến độ</span><div class="carousel-dots">${books.map((_,i)=>i===index?'<b></b>':'<i></i>').join('')}</div></section>`;
}
function futureDue(){const buckets=[['15/10',12],['16/10',18],['17/10',9],['18/10',6],['19/10',4],['20/10',7],['21/10',10]];return `<div class="r1-future"><div class="r1-axis"><span>20</span><span>10</span><span>0</span></div><div class="r1-bars">${buckets.map((b,i)=>`<div class="r1-bar"><b>${b[1]}</b><i class="${i===0?'today':''}" style="height:${b[1]*3.7}px"></i><small>${b[0]}</small></div>`).join('')}</div></div><div class="r1-full-note">Fixture anchor: 14/10/2026 · all buckets are future due counts.</div>`;}
function progressPanel(populated,mixed){
  if(!populated&&!mixed)return card('Tiến độ 14 ngày','<div class="empty-surface"><div class="empty-icon">—</div><div><b>Chưa có lịch sử 14 ngày</b><p>Biểu đồ xuất hiện sau phiên học đầu tiên.</p></div></div>');
  const vals=mixed?[2,3,1,0,4,2,3,1,0,2,3,2,1,4]:[8,12,10,14,18,16,12,20,22,19,24,21,26,30];const points=vals.map((v,i)=>`${i*48},${145-v*4}`).join(' ');const area=`0,145 ${points} 624,145`;
  return card('Tiến độ 14 ngày',`<div class="r1-chart"><div class="r1-y"><span>30</span><span>20</span><span>10</span><span>0</span></div><div class="r1-plot"><svg class="r1-line-svg" viewBox="0 0 624 150" preserveAspectRatio="none" aria-label="Biểu đồ tiến độ 14 ngày"><polyline class="area" points="${area}"/><polyline points="${points}"/>${vals.map((v,i)=>`<circle cx="${i*48}" cy="${145-v*4}" r="3.3"/>`).join('')}</svg><div class="r1-x"><span>03/10</span><span>06/10</span><span>09/10</span><span>12/10</span><span>15/10</span><span>16/10</span></div></div></div><div class="r1-full-note">${mixed?'Lịch sử đã biết · một số ngày vẫn chưa xác minh':'Số thẻ học mới · SYNTHETIC_DESIGN_FIXTURE'}</div>`);
}
function resultPanel(populated,mixed){
  if(!populated&&!mixed)return card('Kết quả','<div class="empty-surface"><div class="empty-icon">?</div><div><b>Chưa có lần làm quiz</b><p>Không hiển thị 0% khi chưa có mẫu số.</p></div></div>');
  const counts=mixed?[5,1,0]:[78,24,8];const total=counts.reduce((a,b)=>a+b,0);const pct=counts.map(v=>Math.round(v*100/total));
  return card('Kết quả',`<div class="result-donut"><div class="result-ring" style="background:conic-gradient(var(--teal) 0 ${pct[0]}%,#e26b78 ${pct[0]}% ${pct[0]+pct[1]}%,#cfd9dc ${pct[0]+pct[1]}% 100%)"></div><div class="result-legend"><span><i></i>Đúng <b>${counts[0]} (${pct[0]}%)</b></span><span><i class="red"></i>Sai <b>${counts[1]} (${pct[1]}%)</b></span><span><i class="gray"></i>Bỏ trống <b>${counts[2]} (${pct[2]}%)</b></span></div></div><div class="r1-full-note">${mixed?'Đã biết: 6 câu quiz · dữ liệu khác vẫn UNKNOWN':'Tổng '+total+' câu · SYNTHETIC_DESIGN_FIXTURE'}</div>`);
}
function skillsPanel(populated){const rows=[['Cloze',populated?'67%':'UNKNOWN','orange','Luyện điền từ'],['Trắc nghiệm',populated?'78%':'UNKNOWN','green','Ôn câu sai'],['Writing',populated?'3.6 / 4':'UNKNOWN','blue','Luyện viết câu']];return card('Kỹ năng cần củng cố',`<div class="skill-list">${rows.map(r=>`<div class="skill-row"><b>${r[0]}</b><span class="skill-bar"><i class="${r[2]}" style="width:${r[1].includes('%')?r[1]:'36%'}"></i></span><strong>${r[1]}</strong><button>${r[3]}</button></div>`).join('')}</div>`);}
function dashboard(){
  const populated=state==='populated',mixed=state==='mixed',degraded=state==='degraded';const due=populated?'12':mixed?'0':'—';const streak=populated?'7 ngày':mixed?'currentDays = null':'—';
  const hero=populated?`<span class="tag ready">READY · Hôm nay</span><h2>Ôn 12 thẻ đến hạn</h2><p>Bắt đầu phiên 8 phút để giữ nhịp học. Đây là một CTA duy nhất cho phiên hôm nay.</p><button class="primary">Bắt đầu ôn tập</button>`:mixed?`<span class="tag info">MIXED DATA</span><h2>Tiếp tục xây nhịp học</h2><p>Không có thẻ đến hạn hôm nay; lịch sử quiz vẫn có dữ liệu và streak chưa xác định.</p><button class="primary">Tra từ mới</button>`:degraded?`<span class="tag warn">DEGRADED · Dữ liệu cũ</span><h2>Học cục bộ vẫn sẵn sàng</h2><p>Một số lịch sử đang cũ. Bạn có thể tiếp tục phiên học an toàn hoặc thử đồng bộ lại.</p><button class="primary">Mở phiên học</button>`:`<span class="tag info">BẮT ĐẦU</span><h2>Tạo nhịp học đầu tiên</h2><p>Chưa có lịch sử học được xác nhận. Tra từ đầu tiên để tạo phiên học; các panel giữ trạng thái chưa có dữ liệu riêng.</p><button class="primary">Tra từ đầu tiên</button>`;
  const row4=[progressPanel(populated,mixed),skillsPanel(populated),card('Hoạt động gần đây',`<div class="list"><div class="list-row"><span>${populated?'Quiz MCQ · 10:22':mixed?'Quiz MCQ · hôm qua':'Chưa có hoạt động'}</span><b>${populated?'8/10':mixed?'5/6':'—'}</b></div><div class="list-row"><span>${populated?'Lưu “resilient” · hôm qua':mixed?'Kết quả quiz đã lưu':'Sẽ xuất hiện sau khi học'}</span><span class="meta">${populated||mixed?'LOCAL':'—'}</span></div></div>`)];
  const historyMarkup=(!populated&&!mixed)?'<div class="empty-surface a12-empty"><div class="empty-icon">—</div><div><b>Chưa có lịch sử học</b><p>Heatmap giữ trạng thái trống cho first-run; không có điểm lịch sử được bịa.</p></div></div>':heatmapMarkup(false);
  const html=`<div class="dashboard"><div class="r1-full-tag">DESIGN_MOCKUP · SYNTHETIC_DESIGN_FIXTURE · R1 + A12 square geometry</div>${pageHeader('TỔNG QUAN','Hôm nay học gì?','Một màn hình gọn cho phiên học kế tiếp · '+(theme==='dark'?'DARK':'LIGHT')+' · VARIANT '+variant,populated?'<button class="secondary">Lọc 7 ngày</button>':'')}<div class="rows"><div class="row1"><section class="card hero-card"><div class="hero-top"><div>${hero}</div><span class="meta">08:40</span></div></section>${bookCard(populated)}</div><div class="row2"><section class="card kpi"><div class="kpi-top"><span class="eyebrow">THẺ ĐẾN HẠN</span><span class="symbol">◷</span></div><div class="metric-value">${due}</div><div class="metric-label">${mixed?'đã kiểm tra hôm nay':'cần ôn hôm nay'}</div><div class="metric-note">${populated?'12 thẻ trong phiên kế tiếp':mixed?'0 không có nghĩa là không có lịch sử':'Không suy diễn từ dữ liệu thiếu'}</div></section><section class="card kpi"><div class="kpi-top"><span class="eyebrow">STREAK</span><span class="symbol">✦</span></div><div class="metric-value">${streak}</div><div class="metric-label">${mixed?'ngày hiện tại chưa xác định':'ngày liên tiếp'}</div><div class="metric-note">${populated?'Mục tiêu tuần: 5 ngày':'currentDays null không phải số 0'}</div></section><section class="card kpi"><div class="kpi-top"><span class="eyebrow">QUIZ</span><span class="symbol">✓</span></div><div class="metric-value">${populated?'86%':mixed?'—':'—'}</div><div class="metric-label">độ chính xác mục tiêu</div><div class="metric-note">${mixed?'Cloze attempted 0 · accuracy null':'Trắc nghiệm khách quan'}</div></section><section class="card kpi"><div class="kpi-top"><span class="eyebrow">WRITING</span><span class="symbol">✎</span></div><div class="metric-value">${populated?'3.6 / 4':mixed?'Chưa chấm':'—'}</div><div class="metric-label">tự đánh giá viết</div><div class="metric-note">${populated?'Thang điểm 0–4 · không trộn với quiz':'Không có self-score xác nhận'}</div></section></div><div class="row3"><section class="card"><div class="panel-head"><div><h2>Thẻ đến hạn 7 ngày tới</h2><span class="meta">15/10–21/10 · phía trước</span></div><span class="tag info">FUTURE</span></div>${populated?futureDue():'<div class="empty-surface"><div class="empty-icon">—</div><div><b>Chưa có lịch sử đến hạn</b><p>Biểu đồ sẽ dùng các bucket tương lai khi dữ liệu sẵn sàng.</p></div></div>'}</section><section class="card"><div class="panel-head"><div><h2>Lịch sử học</h2><span class="meta">105 ngày · HM-FIX 5 mức</span></div><span class="tag ${mixed?'unknown':'info'}">${mixed?'UNKNOWN':'LOCAL'}</span></div>${historyMarkup}</section>${resultPanel(populated,mixed)}</div><div class="row4">${row4.join('')}</div></div></div>`;
  return shell('Tổng quan',html);
}
function heatmapPage(){return shell('Lịch sử học',`<div class="r1-heat-detail">${pageHeader('HM-FIX','Lịch sử học · 105 ngày','Approved synthetic range 28/09/2026–10/01/2027 · five levels · zero distinct from UNKNOWN.')}<section class="card"><div class="panel-head"><div><h2>Study history heatmap</h2><span class="meta">Cell focus, hover and tap proof in isolated preview</span></div><span class="tag info">105 DAYS</span></div>${heatmapMarkup(true)}<p class="r1-full-note">Legend swatches are real color levels: 0, 1–2, 3–5, 6–9, 10+. Tooltip content is date-specific and anchored to the active cell.</p></section></div>`);}
function review(){const unknown=state==='unknown';const body=unknown?`<div><div class="pending"><strong>Chưa thể xác nhận đánh giá</strong>Thao tác trước đó chưa có biên nhận cuối. Không gửi lại để tránh chấm trùng.</div><button class="primary" style="margin-top:14px">Kiểm tra trạng thái</button><button class="quiet" style="display:block;margin:7px auto 0">Giữ nguyên và quay lại sau</button></div>`:`<div><div class="empty-icon">✓</div><h2>Không có thẻ cần ôn</h2><p>Hàng đợi của ngày này đang trống. Bạn có thể tra từ mới hoặc chọn một ngày khác để tiếp tục.</p><button class="primary">Tra từ mới</button></div>`;return shell('Ôn tập',`<div class="review-layout">${pageHeader('ÔN TẬP','Ôn tập theo ngày','Lọc hàng đợi bằng noteDate mà không đổi URL ngoài hợp đồng.')}<div class="toolbar"><div class="field"><label for="date">Ngày học</label><input id="date" value="2026-10-14" /></div><button class="secondary">Xoá bộ lọc</button><div class="queue-summary"><span class="tag ${unknown?'unknown':'info'}">${unknown?'UNKNOWN':'EMPTY'}</span><span>${unknown?'Trạng thái đang chờ xác nhận':'0 thẻ trong hàng đợi'}</span></div></div><section class="card review-empty">${body}</section><p class="meta" style="text-align:center;margin-top:11px">Live region: ${unknown?'Đang chờ đối soát thao tác đánh giá.':'Đã tải hàng đợi ngày 14/10/2026.'}</p></div>`);}
function status(){const degraded=state==='degraded';return shell('Trạng thái & AI consent',`<div class="status-layout">${pageHeader('HỆ THỐNG','Trạng thái học tập','Local-first: việc học cục bộ không phụ thuộc vào AI bên ngoài.')}<div class="status-grid"><section class="card"><div class="panel-head"><div><h2>Tóm tắt sẵn sàng</h2><span class="meta">Cập nhật an toàn · 10:42</span></div><span class="tag ${degraded?'warn':'ready'}">${degraded?'DEGRADED':'READY'}</span></div><div class="status-summary"><div class="status-cell"><b>Học cục bộ</b><p><span class="tag ready">READY</span><br/>Tra từ, lưu từ, ôn tập và xem lịch sử vẫn dùng được.</p></div><div class="status-cell"><b>AI bên ngoài</b><p><span class="tag ${degraded?'unknown':'info'}">${degraded?'UNKNOWN':'NOT_REQUIRED'}</span><br/>Không chặn các phiên học cục bộ.</p></div></div><div class="consent-link"><div><b>Quản lý AI consent</b><span style="display:block">Chính sách và quyền cấp/thu hồi</span></div><span>⌁ /status#ai-consent</span></div>${degraded?'<div class="alert" style="margin-top:10px"><b>Đồng bộ chậm</b><br/>Số liệu lịch sử có thể cũ. Thử lại khi bạn sẵn sàng.</div>':''}<details class="disclosure"><summary>Chi tiết nguồn & lưu trữ</summary><p>Markdown revision, SQLite journal, local timestamps và phiên bản nguồn — xem được khi cần, không lấn át tóm tắt.</p></details><details class="disclosure"><summary>Khả năng offline</summary><p>Lookup · Save · Review · History: cục bộ. AI lookup/feedback: phụ thuộc consent và bridge.</p></details></section><section class="card"><div class="panel-head"><div><h2>Cảnh báo đang hoạt động</h2><span class="meta">Không ẩn trạng thái quan trọng</span></div><span class="tag ${degraded?'warn':'ready'}">${degraded?'1 cảnh báo':'0 cảnh báo'}</span></div>${degraded?'<div class="alert critical" style="margin-top:12px"><b>UNKNOWN · AI consent chưa xác định</b><br/>Không gửi provider request. Mở consent để xác nhận chính sách.</div><button class="secondary" style="margin-top:10px">Mở AI consent</button>':'<div class="empty-surface"><div class="empty-icon">✓</div><div><b>Không có cảnh báo ưu tiên</b><p>Chi tiết kỹ thuật vẫn ở các mục mở rộng bên trái.</p></div></div>'}<details class="disclosure"><summary>Bridge diagnostics</summary><p>Loopback 127.0.0.1:8045 · request id ẩn · không hiển thị prompt, token hay response body.</p></details><details class="disclosure"><summary>Performance & runbook</summary><p>p50/p95/p99 và mã chẩn đoán được giữ cho operator; không xuất hiện trong summary.</p></details></section></div><p class="meta" style="margin-top:12px">Deep-link focus: khi mở <b>/status#ai-consent</b>, focus đặt vào tiêu đề consent và cuộn trong main region; mobile disclosure giữ thứ tự DOM và không khoá việc học cục bộ.</p></div>`);}
function board(){return shell('Bảng so sánh mật độ',`<div class="board">${pageHeader('G1–G9','Density contract board','Một primary action · nhóm chỉ báo gọn · chi tiết kỹ thuật đi sau disclosure.')}<div class="board-grid">${[['G1','AppShell','Đi vào route hiện tại','Navigate','Skip + h1 + local/AI state'],['G2','Lookup','Tìm một từ','Tra từ','Input + provenance disclosure'],['G3','Search / Detail','Xác minh nghĩa','Mở chi tiết','Source badge always visible'],['G4','Save / Edit','Lưu bản nháp','Lưu thay đổi','Conflict / ETag visible'],['G5','Review','Bắt đầu hàng đợi','Tra từ mới','EMPTY/UNKNOWN distinct'],['G6','Quiz','Tạo phiên','Bắt đầu quiz','Selected total + autosave'],['G7','Results','Hiểu kết quả','Xem phản hồi','Objective vs writing split'],['G8','Status','Xác nhận readiness','Mở AI consent','Critical alert always visible'],['G9','Dashboard','Tiếp tục học','Bắt đầu ôn tập','Due/streak + 4 locked rows']].map(x=>`<section class="board-item"><h3>${x[0]} · ${x[1]}</h3><p><b>${x[2]}</b><br/>Dominant: ${x[3]}<br/>First viewport: ${x[4]}</p><div class="rule"></div></section>`).join('')}</div></div>`);}

document.getElementById('app').innerHTML=surface==='review'?review():surface==='status'?status():surface==='heatmap'?heatmapPage():surface==='board'?board():dashboard();
function wireInteractions(){
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
  const prev=document.querySelector('[data-book-prev]'),next=document.querySelector('[data-book-next]');const go=(delta)=>{const current=Number(q.get('book')||0);const url=new URL(location.href);url.searchParams.set('book',String((current+delta+5)%5));location.href=url.toString();};prev?.addEventListener('click',()=>go(-1));next?.addEventListener('click',()=>go(1));
}
wireInteractions();
