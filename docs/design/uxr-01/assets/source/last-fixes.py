from pathlib import Path
folder=Path(__file__).parent
for direction in ('a','b'):
    p=folder/f'direction-{direction}.html'
    s=p.read_text(encoding='utf-8')
    s=s.replace('Chưa có lịch sử học. Không cần lặp lại thông báo trống trong từng chỉ số.','Chưa có lịch sử học. Lưu một từ hữu ích để bắt đầu ôn tập.')
    s=s.replace('/search → /word-forms/:id · dữ liệu cục bộ minh họa. Tra cứu AI và bản xem trước thuộc /lookup.','Tìm trong kho từ cục bộ. Nghĩa, ví dụ và thông tin nguồn đi cùng nhau.')
    s=s.replace('/word-forms/:id · nguồn VALID · bản nháp được giữ','Nguồn VALID · bản nháp được giữ')
    s=s.replace('/lookup · bản xem trước SYNTHETIC · chưa lưu','Bản xem trước SYNTHETIC · chưa lưu')
    s=s.replace('/quiz/:attemptId/result · SUBMITTED · dữ liệu minh họa','SUBMITTED · dữ liệu minh họa')
    s=s.replace('</style>', '''
    .content p, .content li, .row-sub, .metric-label, .metric-note, .status-copy { font-size:14px; }
    .metric-value { margin-top:10px; }
    .result-meta { font-size:12px; }
    .footer-note { font-size:11px; }
    .dark .side-note strong { color:var(--ink); }
    @media(max-width:345px) { .content h1,.section-head h1 { font-size:24px; } .content .section-head p,.content .lead { font-size:13px; } .content { padding-top:16px; } .search-bar .button { margin-top:8px; } }
    </style>''')
    if direction=='b':
        s=s.replace('</style>','''
        .sidebar .side-note strong { color:#e8f1f2; }
        @media(min-width:901px) { .content>.grid.two:has(.list) .list { grid-template-columns:1fr 1fr;gap:20px; } .content>.grid.two:has(.list) .list-row { border-top:0; } .content>.grid.two:has(.list) .card { padding:16px 18px; } }
        </style>''')
    p.write_text(s,encoding='utf-8')
