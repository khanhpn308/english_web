from pathlib import Path

folder = Path(__file__).parent
for direction in ('a', 'b'):
    p=folder/f'direction-{direction}.html'
    s=p.read_text(encoding='utf-8')
    s=s.replace('v1.1','v1.2').replace('Georgia, "Times New Roman", serif','Cambria, "Times New Roman", serif')
    s=s.replace('Workspace','Không gian học').replace('Local data ready','Cục bộ sẵn sàng')
    s=s.replace('Review with room to think.','Ôn tập với không gian để suy nghĩ.')
    s=s.replace('A small queue, one word at a time. Your rating controls the next due date.','Một từ mỗi lần. Chọn mức nhớ sau khi xem đáp án; lịch do backend quyết định.')
    s=s.replace('Card 4 of 12','Hàng đợi phiên: còn 12 thẻ')
    s=s.replace('style="width:34%"','style="width:0%"')
    s=s.replace('NEW · adjective','Đáp án đã mở · adjective')
    s=s.replace('source verified</span>','VERIFIED · nguồn VALID</span>')
    s=s.replace('Keyboard: 1 Again · 2 Hard · 3 Good · 4 Easy.','Bốn mức nhớ: Again · Hard · Good · Easy.')
    s=s.replace('Keep the word in context.','Tìm từ đã lưu, đọc trong ngữ cảnh.')
    s=s.replace('Search a word, check its source, and save a meaning that will still make sense when you review it later.','/search → /word-forms/:id · dữ liệu cục bộ minh họa. Tra cứu AI và bản xem trước thuộc /lookup.')
    s=s.replace("shell('lookup', 'Lookup',", "shell('search', 'Kho từ / chi tiết',")
    s=s.replace('<a class="nav-item" href="#">${icons.book}<span>Kho từ</span></a>', '<a class="nav-item ${active === \'search\' ? \'active\' : \'\'}" href="#">${icons.book}<span>Kho từ</span></a>')
    s=s.replace('source verified · 12 Oct 2026','VERIFIED · nguồn VALID · 12/10/2026')
    s=s.replace('Search results','Kết quả tìm kiếm').replace('3 exact matches','3 dạng từ phù hợp').replace('Filters','Bộ lọc nâng cao')
    s=s.replace('Advanced filters stay here until needed.','Bộ lọc nâng cao và nhãn đang chọn luôn có đường truy cập.')
    s=s.replace('AI preview · optional','Tra cứu AI · tùy chọn').replace('Consent required','Cần quyền AI')
    s=s.replace('A short learner-friendly distinction can appear here after you review AI consent. It never saves automatically.','Tra cứu AI có bản xem trước riêng. Cần chính sách, quyền và khả năng bridge; không tự gửi sau khi cấp quyền và không tự lưu.')
    s=s.replace('Review consent settings','Xem quyền AI').replace('Example in context','Ví dụ trong ngữ cảnh')
    s=s.replace('Local-first study','Học cục bộ').replace('Progress is kept on this device. AI preview is always optional.','Lịch sử đã lưu ở máy này. AI luôn là tùy chọn.')
    s=s.replace('<div class="nav-label">Learning</div>','<div class="nav-label">Học tập</div>')
    s=s.replace('<div class="nav-label">Vocabulary</div>','<div class="nav-label">Từ vựng</div>')
    s=s.replace('<div class="nav-label">System</div>','<div class="nav-label">Hệ thống</div>')
    s=s.replace('study journal','NHẬT KÝ HỌC TẬP')
    # Remove implementation commentary from product space; provenance remains separate.
    s=s.replace('Các chỉ số phản ánh lịch sử đã lưu. Không có biểu đồ thời gian, mục tiêu hay chứng nhận trình độ trong hợp đồng hiện tại.','MCQ, Cloze và Writing được theo dõi riêng. Các chỉ số phản ánh lịch sử đã lưu.')
    s=s.replace('<div class="notice warn">${icons.info}<div>D5 cách điều hướng chi tiết chưa quyết định. Giữ luồng nhiều câu hiện tại; UXR-06 sẽ thiết kế.</div></div>','<div class="notice info">${icons.info}<div>Nộp bài chấm khách quan cục bộ. Nhận xét AI là tùy chọn sau khi nộp.</div></div>')
    s=s.replace('Còn câu 3–4 ở phần tiếp theo. Cuộn để kiểm tra trước khi nộp.','Cuộn để kiểm tra mọi câu trả lời trước khi nộp.')
    s=s.replace('<article class="card sp-20"><h3>Câu 5 · Writing</h3>', '<article class="card sp-20"><h3>Câu 3 · MCQ</h3><p class="sp-16">Choose the word closest to careful and precise.</p><div class="choices"><button class="choice">meticulous</button><button class="choice">casual</button><button class="choice">uncertain</button></div></article><article class="card sp-20"><h3>Câu 4 · Cloze</h3><label class="sp-16">The team performed a ______ review of the sources.</label><input placeholder="Chưa trả lời"></article><article class="card sp-20"><h3>Câu 5 · Writing</h3>')
    s=s.replace('<label class="sp-16">Tự chấm theo writing-rubric-v1</label><p>3 / 4 · Đúng nghĩa và dạng từ; lỗi nhỏ không cản trở hiểu.</p>', '<label class="sp-16">Tự chấm theo writing-rubric-v1</label><div class="score-controls"><button>0</button><button>1</button><button>2</button><button class="selected">3</button><button>4</button></div><p class="sp-16">3 / 4 · Đúng nghĩa và dạng từ; lỗi nhỏ không cản trở hiểu.</p>')
    # Drawers are static mockup overlays, not claimed Radix implementation.
    s=s.replace("scenario === 'lookup-preview' ? preview() : dashboardPopulated()", "scenario === 'lookup-preview' ? preview() : scenario === 'navigation-drawer' ? dashboardPopulated() : scenario === 'quiz-unknown' ? quiz() : scenario === 'review-unknown' ? review() : dashboardPopulated()")
    s=s.replace("document.getElementById('app').innerHTML = page;", '''document.getElementById('app').innerHTML = page;
    if (scenario === 'status-error') {
      const errorBox=document.querySelector('.notice.error');
      document.querySelector('.content').insertBefore(errorBox,document.querySelector('.status-layout'));
    }
    if (scenario === 'quiz-unknown') {
      document.querySelector('.content').insertAdjacentHTML('afterbegin','<div class="notice error"><div><strong>Chưa xác nhận lưu · UNKNOWN</strong><p>Giữ câu trả lời và thao tác hiện tại. Kiểm tra cùng thao tác trước khi nộp.</p><button class="button secondary">Kiểm tra kết quả lưu</button></div></div>');
      document.querySelector('.section-head .tag').textContent='Chưa xác nhận bản nháp';
      document.querySelector('.section-head .tag').className='tag amber';
      document.querySelector('.quiz-side .button.primary').disabled=true;
    }
    if (scenario === 'review-unknown') {
      document.querySelector('.flash-wrap').insertAdjacentHTML('afterbegin','<div class="notice warn"><div><strong>Chưa xác nhận đánh giá · UNKNOWN</strong><p>Giữ thẻ hiện tại. Kiểm tra cùng thao tác; chưa gửi đánh giá mới.</p><button class="button secondary">Kiểm tra kết quả</button></div></div>');
      document.querySelectorAll('.rating').forEach(b=>b.disabled=true);
    }
    if (scenario === 'navigation-drawer') {
      document.body.insertAdjacentHTML('beforeend','<div class="scrim"><section class="drawer" role="dialog" aria-modal="true" aria-label="Điều hướng"><div class="drawer-title"><strong>English Web · Điều hướng</strong><button aria-label="Đóng điều hướng">×</button></div><h3>Học tập</h3><a href="#">Tổng quan · /</a><a href="#">Ôn tập · /review</a><h3>Từ vựng</h3><a href="#">Tra cứu AI · /lookup</a><a href="#">Kho từ · /search</a><p>Chi tiết từ mở từ Kho từ · /word-forms/:id</p><h3>Luyện tập</h3><a href="#">Tạo bài kiểm tra · /quiz/new</a><p>Bài làm và kết quả mở theo attempt ID.</p><h3>Hệ thống</h3><a href="#">Trạng thái · /status</a><a href="#">Quyền gửi dữ liệu AI · /status#ai-consent</a><p class="drawer-note">MOCKUP: Escape đóng, focus trở về nút Menu là yêu cầu thiết kế; chưa kiểm chứng hành vi.</p></section></div>');
    }
    ''')
    s=s.replace('</style>', '''
    .notice.error { display:block; }
    .notice.error p { margin:8px 0; }
    .notice.error .button { margin-top:8px; }
    .score-controls { display:flex; gap:8px; }
    .score-controls button { min-width:44px;min-height:44px;background:var(--surface);border:1px solid var(--line);color:var(--ink);border-radius:6px; }
    .score-controls button.selected { background:var(--accent-soft);border-color:var(--accent); }
    :focus-visible { outline:3px solid var(--accent);outline-offset:3px; }
    button:disabled { opacity:.6;cursor:default; }
    .scrim { position:fixed;inset:0;background:#17203880;z-index:10; }
    .drawer { position:absolute;inset:0 auto 0 0;width:min(92%,360px);background:var(--surface);padding:20px;overflow:auto;color:var(--ink); }
    .drawer-title { display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:16px; }
    .drawer-title button { width:44px;height:44px;border:1px solid var(--line);background:var(--surface);color:var(--ink);font-size:24px; }
    .drawer h3 { margin:20px 0 6px;color:var(--muted);font-size:13px; }
    .drawer a { display:block;min-height:44px;padding:10px 8px;color:var(--ink);text-decoration:none;border-bottom:1px solid var(--line);font-size:14px; }
    .drawer p { font-size:12px;line-height:1.5;margin:8px 0; }
    .drawer-note { color:var(--muted); }
    .review-top { flex-wrap:wrap; }
    @media(min-width:741px) and (max-width:900px) { .sidebar { display:none; } .mobile-header { display:flex;min-height:54px;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line); } .mobile-brand { display:flex;gap:9px;align-items:center; } .menu-btn { min-width:44px;min-height:44px;background:var(--surface);border:1px solid var(--line);color:var(--ink); } .topbar { display:none; } }
    @media(max-width:740px) { .menu-btn { width:44px;height:44px; } .word { overflow-wrap:anywhere; } .search-bar { margin-top:14px; } .content>.section-head h1 { line-height:1.2; } .quiz-progress { flex-wrap:wrap; } }
    </style>''')
    if direction=='b':
        # Distinct desktop console: single summary strip above one result ledger.
        s=s.replace('</style>', '''
        @media(min-width:901px) {
          .content:has(.metric)>.grid.three { display:flex;background:var(--surface);border:1px solid var(--line);gap:0;border-radius:6px; }
          .content:has(.metric)>.grid.three>.metric { flex:1;border:0;border-radius:0;border-right:1px solid var(--line);background:transparent; }
          .content:has(.metric)>.grid.three>.metric:last-child { border-right:0; }
          .content>.grid.two:has(.list) { display:block;background:var(--surface);border:1px solid var(--line);border-radius:6px; }
          .content>.grid.two:has(.list)>div { border:0;border-radius:0; }
          .content>.grid.two:has(.list)>div:last-child { border-top:1px solid var(--line);display:grid;grid-template-columns:220px 120px 1fr;align-items:center;gap:16px; }
          .content>.grid.two:has(.list)>div:last-child .card-title,.content>.grid.two:has(.list)>div:last-child .sp-16 { margin:0; }
          .content>.grid.two:has(.list)>div:last-child details { grid-column:1/-1; }
          .flash-wrap>.notice { grid-column:1/-1; }
        }
        </style>''')
    p.write_text(s,encoding='utf-8')

p=folder/'render.mjs'
s=p.read_text(encoding='utf-8').replace("import { chromium } from 'playwright';", "const playwrightPath = process.env.UXR_PLAYWRIGHT_PATH;\nconst { chromium } = await import(playwrightPath || 'playwright');")
s=s.replace("const browser = await chromium.launch", "cases.push(['navigation-drawer','light',320,568,'navigation-drawer-narrow-320x568'],['edit-conflict','light',390,844,'edit-conflict-mobile-390x844'],['results','light',390,844,'results-writing-feedback-mobile-390x844'],['status-error','dark',1440,900,'status-error-consent-dark-desktop-1440x900'],['quiz-unknown','light',390,844,'quiz-autosave-unknown-mobile-390x844'],['review-unknown','light',390,844,'review-rating-unknown-mobile-390x844']);\nconst browser = await chromium.launch")
s=s.replace("await page.goto(`${html}?scenario=${scenario}&theme=${theme}`);", "await page.goto(`${html}?scenario=${scenario}&theme=${theme}`);\n    await page.evaluate(() => document.fonts.ready);" )
p.write_text(s,encoding='utf-8')
p=folder/'contact-sheet.mjs'
s=p.read_text(encoding='utf-8').replace("import { chromium } from 'playwright';", "const { chromium } = await import(process.env.UXR_PLAYWRIGHT_PATH || 'playwright');")
s=s.replace("const root = resolve('C:/Users/khanh/projects/english-web-uxr01');", "const root = resolve(process.cwd());").replace('v1.1','v1.2')
p.write_text(s,encoding='utf-8')
