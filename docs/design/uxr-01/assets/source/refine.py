from pathlib import Path

base = Path(__file__).parent
p = base / 'direction-a.html'
s = p.read_text(encoding='utf-8')
s = s.replace('</style>', '''
    svg { width:18px; height:18px; flex-shrink:0; }
    .button svg { width:16px; height:16px; }
    .button { min-height:44px; white-space:normal; }
    .dark .button.primary { color:#172038; }
    .avatar { display:none; }
    .metric { min-height:0; }
    .metric-note { font-size:12px; }
    .content { padding-top:24px; }
    .section-head h1 { font-size:36px; }
    .ratings { grid-template-columns:repeat(2,1fr); }
    .rating { min-height:52px; }
    .rating strong { font-size:14px; }
    .rating span { font-size:12px; }
    .tag { white-space:normal; }
    .content p,.content li { overflow-wrap:anywhere; }
    textarea { width:100%; border:1px solid var(--line); border-radius:8px; padding:12px; font:inherit; background:var(--surface); color:var(--ink); min-height:100px; }
    details { padding:12px 0; border-top:1px solid var(--line); }
    summary { cursor:pointer; font-weight:600; min-height:32px; }
    label { display:block; font-weight:600; margin-bottom:6px; }
    .edit-fields { display:grid; gap:16px; }
    .edit-fields input { padding-left:12px; }
    .quiz-side { position:sticky; top:24px; }
    .question { font-size:27px; max-width:100%; }
    .consent-list { padding:0; list-style:none; }
    @media(max-width:740px) {
      .section-head h1 { font-size:29px; }
      .grid.three { grid-template-columns:repeat(2,minmax(0,1fr)); }
      .grid.three .metric { padding:14px; }
      .metric-value { font-size:25px; }
      .lookup-layout { display:flex; flex-direction:column; }
      .lookup-layout>article { order:-1; }
      .quiz-side { order:0; position:static; grid-template-columns:1fr; }
      .flashcard { min-height:0; padding:24px 16px; }
      .status-layout>aside { order:-1; }
      .provenance { font-size:10px; }
    }
    @media(max-width:345px) { h1,.section-head h1 { font-size:26px; } .word { font-size:34px; } }
  </style>''')
s = s.replace('vA.1.0','v1.1').replace('Oxford Learner’s Dictionaries','Cambridge · SYNTHETIC')
start = s.index('    const dashboardFirst')
end = s.index('    const lookup =')
s = s[:start] + '''    const dashboardFirst = () => shell('dashboard', 'Tổng quan', `
      <section class="section-head"><div><h1>Bắt đầu với một từ hữu ích.</h1><p>Chưa có lịch sử học. Không cần lặp lại thông báo trống trong từng chỉ số.</p></div></section>
      <div class="card elevated empty-hero"><div class="empty-copy"><h2>Tạo kho từ đầu tiên của bạn</h2><p>Tra cứu bằng AI khi chính sách và quyền cho phép, kiểm tra bản xem trước rồi lưu để ôn tập. Đây là dữ liệu minh họa.</p><button class="button primary sp-16">Tra cứu từ đầu tiên ${icons.arrow}</button></div><div class="quiet-ornament">${icons.book}</div></div>
      <section class="grid three sp-26">${metric('Thẻ đến hạn','0','Không có thẻ đến hạn')}${metric('Chuỗi học','—','Chưa xác định · không phải 0')}${metric('Trắc nghiệm MCQ','—','0 câu đã trả lời')}${metric('Điền từ Cloze','—','0 câu đã trả lời')}${metric('Flashcard tự đánh giá','—','0 lượt đánh giá')}${metric('Writing tự chấm','— / 4','0 câu có điểm')}</section>
      <p class="muted sp-20">Tìm kiếm từ đã lưu và đọc kết quả cũ hoạt động khi API cục bộ sẵn sàng. Tạo quiz mới cần AI.</p>`);
    const dashboardPopulated = () => shell('dashboard','Tổng quan',`
      <section class="section-head"><div><h1>Hôm nay, bắt đầu từ ôn tập.</h1><p>Chỉ số độc lập · cập nhật 12/10/2026 · Asia/Bangkok</p></div><button class="button primary">Ôn 12 thẻ đến hạn ${icons.arrow}</button></section>
      <section class="grid three sp-26">${metric('Thẻ đến hạn','12','Theo lịch SRS')}${metric('Chuỗi học','6 ngày','Tính đến 12/10/2026')}${metric('Flashcard tự đánh giá','Tốt','38 lượt · không phải độ chính xác')}</section>
      <section class="grid two sp-26"><div class="card"><div class="card-title"><h3>Kết quả khách quan</h3><span class="tag indigo">Chấm cục bộ</span></div><div class="list"><div class="list-row"><div><div class="row-title">MCQ · 80%</div><div class="row-sub">8 đúng / 10 đã trả lời · tổng 12 câu · 2 bỏ trống</div></div></div><div class="list-row"><div><div class="row-title">Cloze · 75%</div><div class="row-sub">6 đúng / 8 đã trả lời · tổng 10 câu · 2 bỏ trống</div></div></div></div><details><summary>Cách đọc độ chính xác</summary><p>Đúng / đã trả lời. Bỏ trống được hiển thị riêng.</p></details></div><div class="card soft"><div class="card-title"><h3>Writing · tự chấm</h3><span class="tag amber">Tự đánh giá</span></div><span class="metric-value">3 / 4</span><p class="muted sp-16">5 câu có điểm. Không gộp với MCQ/Cloze hoặc nhận xét AI.</p><details><summary>Ý nghĩa chỉ số</summary><p>Trung bình điểm người học tự chọn theo writing-rubric-v1.</p></details></div></section>
      <div class="notice info sp-26">${icons.info}<div>Các chỉ số phản ánh lịch sử đã lưu. Không có biểu đồ thời gian, mục tiêu hay chứng nhận trình độ trong hợp đồng hiện tại.</div></div>`);
''' + s[end:]
start=s.index('    const quiz =')
end=s.index('    const status =')
s=s[:start]+'''    const quiz = () => shell('quiz','Bài kiểm tra',`
      <section class="section-head"><div><h1>Tập trung vào câu trả lời.</h1><p>Nguồn ngày 12/10/2026 · 5 câu: MCQ 2 + Cloze 2 + Writing 1</p></div><span class="tag teal">Đã lưu bản nháp · 09:42</span></section>
      <div class="quiz-layout sp-20"><section><article class="card"><div class="tag indigo">Câu 1 · MCQ</div><div class="question sp-16">The researcher was meticulous when documenting each change.</div><p class="muted sp-16">Chọn nghĩa gần nhất.</p><div class="choices"><button class="choice selected"><span class="choice-letter">A</span>Very careful and precise about details</button><button class="choice"><span class="choice-letter">B</span>Quick to change an opinion</button><button class="choice"><span class="choice-letter">C</span>Likely to happen without warning</button></div></article><article class="card sp-20"><h3>Câu 2 · Cloze</h3><p class="sp-16">She kept ______ notes of each experiment.</p><label class="sp-16">Câu trả lời</label><input value="meticulous"></article><article class="card sp-20"><h3>Câu 5 · Writing</h3><p class="sp-16">Viết một câu sử dụng meticulous.</p><textarea class="sp-16">The meticulous researcher checked every source before drawing a conclusion.</textarea><label class="sp-16">Tự chấm theo writing-rubric-v1</label><p>3 / 4 · Đúng nghĩa và dạng từ; lỗi nhỏ không cản trở hiểu.</p><details><summary>Xem mô tả 0–4</summary><p>0: không có câu có nghĩa; 1: sai nghĩa/lỗi lớn; 2: cần sửa đáng kể; 3: đúng và hiểu được; 4: tự nhiên, chính xác.</p></details></article></section><aside class="quiz-side"><div class="card"><h3>Bản nháp cục bộ</h3><div class="side-stat"><span>Đã trả lời</span><strong>3 / 5</strong></div><p class="muted sp-16">Chỉ bản nháp đã được backend xác nhận mới được bảo đảm lưu.</p><button class="button primary sp-16">Nộp bài</button><p class="metric-note">Còn câu 3–4 ở phần tiếp theo. Cuộn để kiểm tra trước khi nộp.</p></div><div class="notice warn">${icons.info}<div>D5 cách điều hướng chi tiết chưa quyết định. Giữ luồng nhiều câu hiện tại; UXR-06 sẽ thiết kế.</div></div></aside></div>`);
''' + s[end:]
start=s.index('    const status =')
end=s.index('    const page =')
s=s[:start]+'''    const status = (error=false) => shell('status','Trạng thái & quyền AI',`
      <section class="section-head"><div><h1>Học cục bộ. AI là lựa chọn.</h1><p>Trạng thái hiện tại và điều kiện cảnh báo được hiển thị riêng.</p></div><button class="button secondary">Làm mới</button></section>
      <div class="status-layout sp-20"><section class="card"><h3>Khả năng học hiện tại</h3><div class="status-row sp-16"><div><div class="status-name">API và dữ liệu cục bộ</div><div class="status-copy">Tìm từ đã lưu, ôn tập, trả lời và đọc kết quả quiz.</div></div><span class="tag teal">Sẵn sàng</span></div><div class="status-row"><div><div class="status-name">AI Bridge</div><div class="status-copy">Tra cứu mới, tạo quiz và nhận xét Writing cần bridge và mạng.</div></div><span class="tag amber">${error?'Ngoại tuyến':'Chưa xác định'}</span></div><div class="notice warn">${icons.alert}<div><strong>${error?'AI tạm không khả dụng.':'Chưa xác định khả năng AI.'}</strong><br>Không tự gửi lại. Các chức năng cục bộ vẫn dùng được khi API cục bộ sẵn sàng.</div></div></section>
      <aside class="card consent-card" id="ai-consent"><h3>Quyền gửi dữ liệu AI</h3><span class="tag amber sp-16">Chưa cấp quyền</span><p>Chính sách chưa đầy đủ. Chưa cho phép cấp quyền hay gửi nội dung học.</p><ul class="consent-list"><li>${icons.check}<span>Ba phạm vi: tra cứu, tạo quiz, nhận xét Writing.</span></li><li>${icons.info}<span>Bên nhận, lưu giữ, vùng xử lý, chi phí/hạn mức phải được khai báo trước khi cấp quyền.</span></li></ul><button class="button primary">Xem chính sách hiện tại</button><p>Rút quyền chặn yêu cầu AI mới. Yêu cầu đã gửi có thể hoàn tất; không thu hồi hoặc xóa dữ liệu đã gửi.</p><button class="button secondary sp-16">Rút quyền gửi AI</button></aside></div>
      ${error?'<div class="notice error sp-20"><strong>Chưa xác nhận rút quyền · UNKNOWN</strong><p>Giữ thao tác hiện tại. Kiểm tra lại trạng thái trước khi báo thành công.</p><button class="button secondary">Kiểm tra kết quả rút quyền</button></div>':''}
      <section class="card soft sp-20"><details><summary>Chẩn đoán: dữ liệu, nguồn Markdown, AI Bridge</summary><p>Mã trạng thái, request ID và thông tin kỹ thuật chỉ hiển thị trong mục này.</p></details><details><summary>Cảnh báo hiện tại và điều kiện kích hoạt</summary><p>API không phản hồi: trạng thái UNKNOWN. Mức nghiêm trọng khi kích hoạt không có nghĩa cảnh báo đang hoạt động.</p></details><details><summary>Runbooks & khả năng ngoại tuyến</summary><p>Không ghi nội dung học hoặc khóa vào thông tin chẩn đoán.</p></details></section>`);
    const edit = () => shell('lookup','Chỉnh sửa từ',`<section class="section-head"><div><h1>Chỉnh sửa meticulous</h1><p>/word-forms/:id · nguồn VALID · bản nháp được giữ</p></div><span class="tag indigo">Revision conflict</span></section><div class="notice warn">${icons.alert}<div><strong>Nguồn đã thay đổi.</strong><br>Revision yêu cầu 2; hiện tại 3. Không ghi đè. Đọc lại và xác nhận lưu mới.</div></div><section class="card sp-20"><div class="edit-fields"><div><label>Nghĩa tiếng Anh</label><textarea>Very careful and precise about details.</textarea></div><div><label>Nghĩa tiếng Việt</label><textarea>Cẩn thận, tỉ mỉ và chú ý đến từng chi tiết khi kiểm tra nguồn và ghi chép kết quả nghiên cứu.</textarea></div><div><label>Ví dụ tiếng Anh</label><textarea>She kept meticulous notes while comparing the two editions.</textarea></div></div><button class="button primary sp-16">Đọc lại nguồn</button><button class="button secondary sp-16">Giữ bản nháp</button><details class="sp-16"><summary>Chi tiết nguồn / ETag</summary><p>ETag được đọc từ backend; không dùng nhãn giả làm precondition.</p></details></section>`);
    const results = () => shell('quiz','Kết quả',`<section class="section-head"><div><h1>Hiểu kết quả, chọn bước tiếp theo.</h1><p>/quiz/:attemptId/result · SUBMITTED · dữ liệu minh họa</p></div><button class="button primary">Ôn tập</button></section><section class="grid three sp-20">${metric('MCQ khách quan','1 / 2','1 đúng / 2 trả lời · 50%')}${metric('Cloze khách quan','1 / 1','Tổng 2 câu · 1 bỏ trống · 100%')}${metric('Writing tự chấm','3 / 4','1 câu · người học chọn')}</section><article class="card sp-20"><h3>Câu Writing đã nộp · không chỉnh sửa</h3><p class="example sp-16">The meticulous researcher checked every source before drawing a conclusion.</p><p class="muted sp-16">Tự chấm 3/4 không bị AI thay đổi.</p><details><summary>MCQ / Cloze: câu trả lời và giải thích</summary><p>Đáp án và giải thích chỉ xuất hiện sau khi nộp. Bỏ trống phân biệt với sai.</p></details></article><article class="card soft sp-20"><h3>Nhận xét AI tùy chọn</h3><span class="tag amber sp-16">Chưa yêu cầu · cần quyền AI</span><p class="sp-16">Nhận xét về dùng từ, ngữ pháp và độ rõ ràng; không phải điểm khách quan và không thay tự chấm.</p><button class="button secondary sp-16">Xem quyền AI</button><details class="sp-16"><summary>Lịch sử nhận xét</summary><p>REQUESTED, VALIDATED hoặc FAILED được giữ riêng. Đây là concept SOURCE_BACKED, hiện trạng G7 NOT_VERIFIED.</p></details></article>`);
    const preview = () => shell('lookup','Tra cứu AI',`<section class="section-head"><div><h1>Từ mới, trong ngữ cảnh.</h1><p>/lookup · bản xem trước SYNTHETIC · chưa lưu</p></div><span class="tag amber">AI tùy chọn</span></section><label>Từ tiếng Anh</label><div class="search-bar"><div class="input-wrap">${icons.search}<input value="meticulous"></div><button class="button secondary">Tra cứu AI</button></div><article class="card sp-20"><div class="detail-header"><div><div class="word">meticulous</div><div class="ipa">/məˈtɪk.jə.ləs/ · adjective</div></div><span class="tag amber">PREVIEW · Chưa lưu</span></div><p class="word-meaning">Very careful and precise about details.</p><p class="sp-16">Tỉ mỉ, chú ý kỹ đến từng chi tiết.</p><p class="example sp-16">She kept meticulous notes of each experiment.</p><div class="source-line"><span class="tag amber">Cambridge · UNVERIFIED</span><span>Không tự nâng cấp xác minh</span></div><details class="sp-16"><summary>Dạng từ và thông tin nguồn</summary><p>meticulously · meticulousness · toàn bộ dạng từ được lưu cùng nhau.</p></details><label class="sp-16">Ngày học</label><input type="date" value="2026-10-12"><p class="muted sp-16">Nguồn ngày đã đọc: chưa có nguồn. Lưu mới dùng precondition xác nhận không tồn tại.</p><button class="button primary sp-16">Lưu tất cả dạng từ để ôn</button><p class="metric-note">Chỉ hiển thị đã lưu khi backend xác nhận biên nhận.</p></article>`);
''' + s[end:]
s=s.replace("scenario === 'status-error' ? status(true) : dashboardPopulated()", "scenario === 'status-error' ? status(true) : scenario === 'edit-conflict' ? edit() : scenario === 'results' ? results() : scenario === 'lookup-preview' ? preview() : dashboardPopulated()")
s=s.replace('Start a review','Tra cứu từ đầu tiên').replace('Oxford','Cambridge')
s=s.replace('Local lookup, review and quiz remain available.','Tìm từ đã lưu, ôn tập và làm quiz có sẵn hoạt động khi API cục bộ sẵn sàng.')
s=s.replace('1 minute','Cần học lại').replace('6 minutes','Giữ mức hiện tại').replace('1 day','Theo lịch backend').replace('4 days','Theo lịch backend')
s=s.replace('Rating is saved with the review receipt.','Chỉ xác nhận sau biên nhận; UNKNOWN khóa đánh giá và cho kiểm tra cùng thao tác.')
s=s.replace('Save to vocabulary','Chỉnh sửa từ đã lưu').replace('source verified · 12 Oct 2026','VERIFIED · nguồn VALID · 12/10/2026')
s=s.replace('Search ${icons.arrow}','Tìm từ đã lưu ${icons.arrow}')
s=s.replace('<span>Dashboard</span>','<span>Tổng quan</span>').replace('<span>Review</span>','<span>Ôn tập</span>').replace('<span>Quiz</span>','<span>Tạo bài kiểm tra</span>').replace('<span>Lookup</span>','<span>Tra cứu AI</span>').replace('<span>My words</span>','<span>Kho từ</span>').replace('<span>Status & consent</span>','<span>Trạng thái & quyền AI</span>').replace('<span>Home</span>','<span>Tổng quan</span>').replace('<span>More</span>','<span>Menu</span>')
s=s.replace('Source verified','Đã xác minh').replace('v1.1 · static owner preview','UXR-01 · v1.1 · SYNTHETIC')
p.write_text(s,encoding='utf-8')

# B shares contract-shaped synthetic content, with different structure and density.
b=s.replace('Direction A','Direction B').replace('Direction A static','Direction B static')
b=b.replace('--paper: #f7f6f2','--paper: #f0f3f4').replace('--paper-deep: #efeee9','--paper-deep: #e4eaed').replace('--ink: #172038','--ink: #182a31').replace('--accent: #3f4c9b','--accent: #0d696a').replace('--accent-strong: #2f3d86','--accent-strong: #095354').replace('--accent-soft: #e8eafa','--accent-soft: #d9eeeb').replace('--radius: 14px','--radius: 6px').replace('--font-display: Georgia, "Times New Roman", serif','--font-display: "Segoe UI", ui-sans-serif, system-ui, sans-serif')
b=b.replace('</style>', '''
  /* Direction B: fixed narrow console navigation, command header, tabular scan rows. */
  .sidebar { width:184px; padding:16px 10px; background:#173239; color:#e8f1f2; }
  .brand-name { color:#fff; font-weight:700; font-size:16px; }
  .brand-sub,.nav-label,.side-note { color:#a3bbc2; }
  .nav-item { color:#d4e4e8; border-radius:4px; min-height:40px; font-size:13px; }
  .nav-item.active { background:#31545d; color:white; }
  .main { padding-inline:24px; }
  .topbar { height:48px; }
  .provenance { margin-top:12px; border-radius:3px; }
  .content { padding-top:18px; max-width:1240px; }
  h1,.section-head h1 { font-size:28px; font-weight:700; letter-spacing:-.025em; }
  h2 { font-size:24px; font-weight:700; }
  .card { padding:18px; border-radius:6px; }
  .card.elevated { box-shadow:none; border:1px solid var(--line); }
  .grid.three { grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; }
  .metric { padding:16px 18px; }
  .metric-value { font-size:28px; font-weight:700; font-variant-numeric:tabular-nums; }
  .metric-note { margin-top:7px; }
  .sp-26 { margin-top:18px; }
  .sp-20 { margin-top:16px; }
  .empty-hero { padding:24px; }
  .empty-hero .quiet-ornament { display:none; }
  .button { border-radius:5px; }
  .button.primary { box-shadow:none; }
  .lookup-layout { grid-template-columns:225px minmax(0,1fr); gap:12px; margin-top:16px; }
  .word { font-size:35px; font-weight:700; }
  .word-meaning { font-size:17px; }
  .flash-wrap { max-width:none; display:grid; grid-template-columns:minmax(0,1fr) 300px; gap:18px; }
  .flash-wrap .review-top { grid-column:1/-1; }
  .flash-wrap>.progress { grid-column:1/-1; }
  .flash-wrap>.flashcard { margin-top:0; }
  .flash-wrap>.ratings { display:flex; flex-direction:column; margin-top:0; }
  .flashcard .word { font-size:54px; }
  .flashcard { min-height:320px; text-align:left; }
  .rating { text-align:left; padding:12px 18px; }
  .quiz-layout { grid-template-columns:minmax(0,1fr) 240px; gap:12px; }
  .status-layout { grid-template-columns:minmax(0,.85fr) minmax(0,1.15fr); gap:12px; }
  .consent-card { background:var(--surface); border:1px solid var(--line); }
  .bottom-nav { display:none!important; }
  @media(max-width:1100px) and (min-width:741px) { .sidebar { width:156px; } .main { padding-inline:18px; } .flash-wrap { grid-template-columns:1fr 220px; } }
  @media(max-width:740px) { .sidebar { display:none; } .main { padding:0 14px 30px; } .mobile-header { min-height:52px; } h1,.section-head h1 { font-size:25px; } .content { padding-top:18px; } .grid.three { grid-template-columns:repeat(2,minmax(0,1fr)); } .lookup-layout { display:flex; } .flash-wrap { display:block; } .ratings { display:grid!important; grid-template-columns:repeat(2,minmax(0,1fr)); margin-top:14px!important; } .quiz-layout,.status-layout { grid-template-columns:1fr; } .flashcard { min-height:0; } .flashcard .word { font-size:44px; } .card { padding:16px; } .tag { font-size:11px; } }
  </style>''')
b=b.replace('Hôm nay, bắt đầu từ ôn tập.','Tổng quan học tập').replace('Bắt đầu với một từ hữu ích.','Khởi tạo kho từ').replace('Học cục bộ. AI là lựa chọn.','Trạng thái vận hành').replace('Tập trung vào câu trả lời.','Bài kiểm tra · bản nháp').replace('Review with room to think.','Ôn tập · bàn học tập').replace('Make a little room for English.','Khởi tạo kho từ')
(base/'direction-b.html').write_text(b,encoding='utf-8')
