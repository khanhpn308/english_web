# Spec: Ứng dụng học từ vựng học thuật cá nhân

**Trạng thái:** Ready for planning; implementation verification pending
**Ngày:** 29/09/2026 (`Asia/Bangkok`)
**Nguồn chính:** [`docs/interviews/product-discovery-001.md`](interviews/product-discovery-001.md)
**Nguồn tham chiếu:** [`docs/project-context.md`](project-context.md), [`docs/vocabularies/README.md`](vocabularies/README.md), [`docs/development/spec/vocabulary-platform-spec.md`](development/spec/vocabulary-platform-spec.md)

`docs/spec-draft.md` không tồn tại. Vì vậy, biên bản interview là nguồn yêu cầu lịch sử; ADR-0004 is the current v1 policy authority. Đặc tả cũ chỉ là tham chiếu và không được dùng để tự bổ sung tính năng hoặc chốt framework.

Các khác biệt giữa interview và đặc tả cũ đã được giải quyết trong interview: xử lý AI tự động trong app thay cho bridge thủ công; một thẻ riêng cho từng dạng từ thay cho một thẻ cho cả lemma; cho phép sửa trong app và ghi lại Markdown; file nguồn lỗi bị tạm ngừng sử dụng; không có sao lưu trong app. Đây là các quyết định mới của sản phẩm. Các câu hỏi ở mục **17. Open questions** được giữ lại như lịch sử phỏng vấn; quyết định hiện hành và các giá trị mặc định v1 nằm trong ADR-0004.

Trong bản spec này, **MUST** là yêu cầu đã có cơ sở; các câu hỏi cũ được giữ để truy nguyên nhưng quyết định hiện hành nằm ở ADR-0004. Capability map và thứ tự phụ thuộc là baseline để planning; implementation vẫn phải qua `CONSTRAINTS.md` và verification gates.

Các tài liệu architecture là planning baseline. ADR-0004 đóng OQ-01–OQ-14 cho v1; exact dependency versions/lockfiles vẫn do toolchain task pin.

[ADR-0005](adr/0005-contract-clarifications.md) là clarification authority của T013: khóa HARD/due theo lịch Bangkok, rubric, save ngày mới, external edit, submit/result, caps/session và retention/deadline. [Conformance 002](reviews/contract-conformance-002.md) ghi crosswalk và document probes; runtime verification vẫn do các task implementation cung cấp.

### Quyết định tích hợp AI sau smoke test

Đã chốt hướng **runtime local, inference cloud**: app và backend chạy trên máy Windows; backend gọi local API bridge tại `http://127.0.0.1:8045/v1`; mục tiêu tích hợp vẫn là Gemini cloud qua tài khoản/provider đã cấu hình. Đây là local-first về nơi chạy app, không phải local-only về dữ liệu: prompt và câu trả lời gửi tới cloud phải được người dùng chấp nhận.

**Làm rõ của owner ngày 29/09/2026:** bridge là [Antigravity Tools / Antigravity-Manager](https://github.com/lbjlaq/Antigravity-Manager), một API proxy nội bộ quản lý token/session các tài khoản Google để chuyển tiếp yêu cầu model. App từ vựng là client của proxy, không phải công cụ đọc/nhập/quản lý token/session Google. API key cấp cho client proxy khác với credential tài khoản upstream; frontend không nhận loại credential nào. Khả năng proxy hỗ trợ Flash/Pro/Claude không tự mở rộng model được phép của sản phẩm. Owner xác nhận phiên bản đang dùng là **v4.8.4**; [release upstream](https://github.com/lbjlaq/Antigravity-Manager/releases/tag/v4.8.4) trỏ commit `0269f045f4e35f34b9ee3b3bcd6c0ff1e741378f`. Cơ chế auth đã được chấp thuận theo ADR-0002; binary/cấu hình trên máy và key rotation vẫn phải kiểm chứng trước release. Model, route, fallback và disclosure v1 dùng các giá trị cụ thể trong ADR-0004; retention/region vẫn là thuộc tính do provider kiểm soát mà app không bảo đảm. Đây không phải xác nhận proxy là API chính thức của Google hoặc gói hiện có bảo đảm mọi request miễn phí.

Smoke test ngày 29/09/2026 đã xác nhận service trả `200 OK` cho `GET /health`, liệt kê model qua `GET /v1/models`, và chấp nhận `POST /v1/chat/completions` với model `gemini-3.8-flash-high`, trả lại nội dung dự kiến. Hợp đồng OpenAI-compatible này đủ để bắt đầu thiết kế adapter; triển khai vẫn phải kiểm chứng entitlement/quota và profile thực tế, trong khi policy v1, route và fallback được định nghĩa trong ADR-0004.

**Quyết định bridge được owner chấp thuận:** dùng HTTP loopback `127.0.0.1:8045` + API key bắt buộc cho inference, tắt LAN, tin cậy máy/tài khoản Windows và chấp nhận không có bảo đảm chống tiến trình độc hại cục bộ giả mạo proxy. [ADR-0002](adr/0002-antigravity-loopback-trust-boundary.md) thay yêu cầu process authentication/per-launch secret/IPC trước đây; browser session không đổi. Việc kiểm chứng cấu hình/key rotation vẫn là điều kiện trước release. Consent, model, route, fallback, quota/billing disclosure và retention/region boundary v1 đã được chốt trong ADR-0003/0004; implementation chỉ được fail closed khi policy/entitlement thiếu.

API key của bridge MUST chỉ được backend/local process sử dụng, không đưa vào frontend, Markdown, database feedback hoặc Git. Key xuất hiện trong screenshot trước đó đã được xem là bị lộ và phải rotate; implementation chỉ dùng key mới qua cấu hình local/secret store phù hợp.

Prompt cho từng tác vụ MUST được render từ template có version và placeholder có cấu trúc. Backend MUST yêu cầu response theo JSON schema, validate trước khi trả frontend hoặc ghi feedback vào database. Feedback lịch sử MUST gắn với quiz attempt, question/answer, model/provider, prompt version và thời điểm; điểm cuối cùng của câu viết vẫn do người dùng tự chấm.

**Consent được owner chấp thuận:** app hỏi trước lần gửi dữ liệu AI đầu tiên, lưu lựa chọn trên máy và cho phép rút lại để chặn yêu cầu AI mới mà vẫn học cục bộ. [ADR-0003](adr/0003-ai-consent-and-revocation.md) mô tả luồng này; phê duyệt thiết kế không tự cấp consent trong app. Policy v1 hiển thị model/route/billing, quota/entitlement failure và provider-controlled retention/region theo ADR-0004; paid fallback chỉ có thể bật bằng policy version mới và fresh consent.

## 1. Problem statement

Khi đọc báo khoa học hoặc học IELTS Academic, người dùng gặp nhiều từ mới nhưng khó tra cứu và lưu lại theo cách có thể học tiếp. Sau khi lưu, việc tìm lại theo nghĩa tiếng Việt, phân biệt các dạng từ, ôn đúng thời điểm và theo dõi tiến bộ đều khó duy trì. Việc thiếu một dashboard phản ánh quá trình học làm cho thói quen ôn thường xuyên bị gián đoạn.

Sản phẩm cần giải quyết vòng lặp sau trên một máy cá nhân: **nhập từ → xem nội dung học thuật đầy đủ → chọn lưu → tìm lại → ôn theo SRS → kiểm tra khả năng vận dụng → theo dõi tiến bộ**.

## 2. Product goals

1. Cho phép nhập một từ để tra tự động trong app, không buộc người dùng chạy lệnh hoặc nhập kết quả thủ công trong luồng hằng ngày.
2. Cung cấp word family theo từ loại, tất cả nghĩa thường dùng trong ngữ cảnh học thuật, ví dụ tiếng Anh, bản dịch tiếng Việt, IPA Mỹ và liên kết Cambridge cho từng dạng từ.
3. Cho phép người dùng chỉ đưa nội dung vào bộ học sau khi bấm **Lưu để ôn**.
4. Giúp tìm lại từ bằng một phần nghĩa tiếng Việt và phục vụ kho ít nhất 100.000 dạng từ ở mốc kiểm thử đã chốt.
5. Duy trì ôn bằng flashcard có SRS riêng theo từng dạng từ, đồng thời cho phép lọc theo ngày ghi chú.
6. Cung cấp bài kiểm tra trắc nghiệm, điền từ và tự viết câu; đề bằng tiếng Anh, giải thích bằng tiếng Việt.
7. Ghi nhận riêng mức nhớ flashcard, độ chính xác trắc nghiệm/điền từ và điểm tự chấm viết câu trên dashboard.
8. Hỗ trợ mục tiêu sử dụng ít nhất 6 ngày mỗi tuần; không đặt giới hạn thời lượng học mỗi ngày.
9. Giữ dữ liệu từ vựng trong Markdown theo ngày, có thể chỉnh sửa từ app hoặc editor bên ngoài, và tiếp tục dùng dữ liệu học đã lưu khi offline.

Chỉ số và thời gian quan sát để đánh giá mục tiêu 6 ngày/tuần vẫn là câu hỏi mở, không được suy diễn thành cam kết tự động đạt mục tiêu.

## 3. Target users

- **Người dùng chính:** một cá nhân đọc báo khoa học và học IELTS Academic.
- **Môi trường:** một máy Windows cá nhân, local-first.
- **Cách mở:** bấm biểu tượng Windows; app khởi động và mở một tab trình duyệt.
- **Tài khoản:** không có tài khoản, đăng nhập hoặc mật khẩu riêng của app.
- **Thiết bị khác:** không thuộc v1; không có truy cập từ điện thoại hoặc máy khác trong mạng nội bộ.

## 4. User journeys

### J1 — Mở app và xem việc cần học

1. Người dùng bấm biểu tượng trên Windows.
2. App mở tab trình duyệt mà không yêu cầu đăng nhập.
3. Dashboard hiển thị thẻ đến hạn, streak và kết quả học tách riêng.
4. Người dùng chọn ôn theo SRS hoặc chọn ngày ghi chú để ôn/kiểm tra.

### J2 — Tra và lưu một từ

1. Người dùng nhập từ cần tra; không cần nhập câu gốc hay nguồn bài đọc.
2. Backend tự gọi API proxy Antigravity Tools; người dùng không chạy CLI trong luồng này. Nếu entitlement/quota của tài khoản không đáp ứng policy v1, backend fail closed và giữ các luồng học cục bộ khả dụng.
3. App hiển thị word family, nghĩa học thuật, ví dụ/bản dịch, IPA Mỹ và liên kết Cambridge.
4. Nội dung chưa đối chiếu được được gắn nhãn **chưa xác minh** nhưng vẫn có thể lưu.
5. Người dùng có thể bấm nút loa cạnh từ tiếng Anh khi browser có local voice; không cần mạng.
6. Người dùng chọn ngày và bấm **Lưu để ôn**; backend cấp sourceId/tạo Markdown nếu ngày chưa có nguồn, hoặc kiểm tra revision/ETag của nguồn đã có. Mỗi dạng từ tạo hoặc liên kết với một thẻ riêng.
7. Nếu dạng từ đã xuất hiện ở ngày khác với cùng nội dung, thẻ và tiến độ được dùng chung, còn ngày ghi chú mới được liên kết thêm. Identity và reset khi nội dung đổi tuân theo ADR-0004.

### J3 — Tìm và sửa dữ liệu

1. Người dùng tìm bằng một phần nghĩa tiếng Việt.
2. Người dùng mở dạng từ và xem nội dung liên quan.
3. Người dùng sửa ngay trong app; app ghi thay đổi vào Markdown.
4. Người dùng cũng có thể sửa Markdown bằng editor bên ngoài; app nhận biết thay đổi.
5. Editor bên ngoài được phát hiện bằng hash/watcher và không nhận HTTP response. Nếu một API write dùng revision/ETag/hash cũ, app nhận `409 REVISION_CONFLICT`, hiển thị bản hiện tại và bản local để người dùng chọn thao tác tiếp; không tự động ghi đè hoặc áp dụng last-write-wins.
6. Sửa nghĩa hoặc ví dụ đưa thẻ tương ứng về trạng thái chưa học.

### J4 — Ôn flashcard

1. Người dùng mở hàng đợi SRS hoặc chọn ngày ghi chú.
2. Khi lọc theo ngày, app chỉ lấy thẻ đến hạn hoặc chưa học của ngày đó.
3. Mặt trước hiển thị từ tiếng Anh; người dùng tự nhớ nghĩa tiếng Việt rồi lật thẻ.
4. Người dùng tự đánh giá sau khi lật; không bắt buộc nhập đáp án.
5. Đánh giá được ghi vào lịch sử và dùng để cập nhật lịch SRS của dạng từ.

### J5 — Tạo và làm bài kiểm tra

1. Người dùng chọn một ngày ghi chú và số câu cho từng dạng: trắc nghiệm, điền từ, tự viết câu.
2. Đề lấy tất cả từ của ngày đó, kể cả thẻ chưa đến hạn.
3. Đề bằng tiếng Anh; đáp án/giải thích tiếng Việt chỉ được trả sau khi nộp thành công. Rubric tự chấm câu viết hiện sẵn trong lúc làm.
4. Câu trả lời được tự lưu để người dùng đóng tab/tắt app rồi tiếp tục.
5. Trắc nghiệm và điền từ được chấm tự động; viết câu do người dùng tự chấm theo tiêu chí, AI nhận xét hỗ trợ. Backend gửi prompt template tới local bridge, parse JSON response rồi lưu feedback theo attempt/question.
6. Nộp bài dùng aggregate submissionRevision hiện hành; hệ thống commit kết quả và SRS cùng receipt, mỗi dạng từ hoạt động nhận mức yếu nhất đúng một lần. GET attempt đọc lại kết quả terminal sau reload/offline; bài đã nộp không sửa lại đáp án/điểm.

### J6 — Học khi offline hoặc khi nguồn lỗi

- Khi mất mạng, người dùng vẫn tìm từ đã lưu, ôn flashcard, xem dashboard và làm bài đã tạo sẵn.
- Tra từ mới, tạo đề và nhận xét AI cần bridge/network; nút loa dùng local SpeechSynthesis khi có voice.
- File Markdown lỗi bị tạm ngừng làm nguồn học cho đến khi hợp lệ trở lại.
- Nếu dạng từ còn xuất hiện trong file Markdown hợp lệ khác, thẻ vẫn được ôn.
- Nếu dạng từ bị xóa khỏi mọi file, thẻ ngừng được đưa vào ôn nhưng lịch sử và kết quả cũ vẫn giữ.

## 5. Capability map

| User need ID | Nhu cầu đã xác nhận | Goal |
|---|---|---|
| `UN-01` | Nhập từ nhanh khi đọc, xem nội dung đủ để học rồi tự quyết định lưu | 1–3 |
| `UN-02` | Tìm lại từ khi chỉ nhớ một phần nghĩa tiếng Việt; sửa nội dung sai và giữ Markdown | 4, 9 |
| `UN-03` | Ôn từng dạng từ đúng thời điểm và theo ngày đã ghi chú | 5 |
| `UN-04` | Kiểm tra khả năng nhớ và dùng từ trong IELTS Academic | 6 |
| `UN-05` | Biết hôm nay cần học gì và theo dõi việc duy trì ôn | 7–8 |
| `UN-06` | Mở dễ dàng trên Windows, dùng trên một máy và học dữ liệu đã có khi offline | 9; môi trường ở mục 3 |

| Capability ID | Trách nhiệm và ranh giới dữ liệu | User need | Depends on | Requirement / AC chính |
|---|---|---|---|---|
| `offline-local-runtime` | Khởi động Windows/tab trình duyệt, khả năng lưu dữ liệu cục bộ và phân biệt tác vụ cần mạng | `UN-06` | — | FR-RUN; AC-01, AC-06, AC-23, AC-29 |
| `vocabulary-search-edit` | Quản lý kho từ/quan hệ ngày/nguồn Markdown; tìm và sửa hai chiều. Cung cấp dạng từ cùng trạng thái nguồn hợp lệ cho các capability học | `UN-02` | `offline-local-runtime` | FR-VOC; AC-07–AC-11, AC-28, AC-31 |
| `capture-enrich-save` | Nhận từ, lấy nội dung AI, phát âm; chỉ yêu cầu lưu vào kho sau thao tác của người dùng | `UN-01` | `vocabulary-search-edit` | FR-CAP; AC-02–AC-05, AC-25, AC-27, AC-33, AC-34 |
| `review-srs` | Quản lý thẻ/lịch/đánh giá; nhận kết quả quiz làm đầu vào SRS, không phụ thuộc dữ liệu nội bộ của quiz | `UN-03` | `vocabulary-search-edit` | FR-REV; AC-08, AC-11–AC-13, AC-19 |
| `assessment` | Tạo đề, lưu bài đang làm, chấm, lưu kết quả; gửi kết quả theo dạng từ sang SRS; nhận xét viết câu qua local bridge và lưu feedback đã validate | `UN-04` | `vocabulary-search-edit`, `review-srs` | FR-ASM; AC-14–AC-19, AC-23, AC-30, AC-35 |
| `progress-dashboard` | Đọc dữ liệu học, tính/hiển thị due cards, streak và chỉ số tách riêng | `UN-05` | `vocabulary-search-edit`, `review-srs`, `assessment` | FR-DASH; AC-20–AC-22 |

Thứ tự xây dựng **đề xuất**: `offline-local-runtime` → `vocabulary-search-edit` → `capture-enrich-save` và `review-srs` → `assessment` → `progress-dashboard`. Kiểm tra offline xuyên suốt các capability, không đợi đến cuối mới bổ sung. Quan hệ phụ thuộc trên không có chu kỳ; việc tái sử dụng tích hợp AI là quyết định thiết kế kỹ thuật, không thêm capability sản phẩm. Hợp đồng dữ liệu tại các ranh giới sẽ dựa trên mục 8 và các open questions, chưa chốt route/API schema hoặc framework.

## 6. Functional requirements

### 6.1. `capture-enrich-save`

- **FR-CAP-01:** App MUST nhận từ tiếng Anh người dùng nhập; luồng v1 không thu thập câu gốc hay nguồn bài đọc mới.
- **FR-CAP-02:** Backend MUST gọi Antigravity v4.8.4 qua `http://127.0.0.1:8045/v1` theo [ADR-0002](adr/0002-antigravity-loopback-trust-boundary.md): tắt LAN, bật `all_except_health`, dùng proxy API key mới chỉ ở backend. HTTP chỉ được phép trên chặng loopback này; remote, redirect, proxy trung gian theo môi trường và endpoint ngoài allowlist bị từ chối. Kiểm tra auth theo API §6 trước dispatch; lỗi cấu hình/auth phải chặn inference nhưng không chặn chức năng học cục bộ. Không yêu cầu per-launch bridge secret/IPC hoặc tuyên bố xác thực danh tính process. V1 chỉ dispatch `gemini-3.8-flash-high` theo policy ADR-0004; không tự chọn model/route/fallback khác.
- **FR-CAP-03:** Kết quả MUST có word family theo từ loại và tất cả nghĩa thường dùng trong ngữ cảnh học thuật.
- **FR-CAP-04:** Mỗi dạng từ MUST có nghĩa, câu ví dụ tiếng Anh và bản dịch tiếng Việt; IPA giọng Mỹ và liên kết Cambridge phải có khi provider trả về, nếu thiếu phải lưu trạng thái `MISSING`/`UNVERIFIED` thay vì bịa hoặc chặn lưu.
- **FR-CAP-05:** Nội dung nghĩa/từ loại chưa đối chiếu được MUST có nhãn **chưa xác minh** và vẫn cho lưu. Nhãn áp dụng ở mức trường theo ADR-0004; IPA hoặc Cambridge link thiếu được lưu với trạng thái `MISSING`.
- **FR-CAP-06:** App MUST tách trạng thái tra cứu khỏi trạng thái lưu; không được đưa kết quả vào bộ học trước khi người dùng bấm **Lưu để ôn**.
- **FR-CAP-07:** Khi lưu, app MUST liên kết dữ liệu với ngày ghi chú gửi rõ trong request và tạo một thẻ riêng cho từng dạng từ. Ngày mới dùng conditional create; backend cấp sourceId và path an toàn theo ngày, trả source revision/ETag trong receipt. Nguồn đã có cần revision/ETag hiện hành theo ADR-0005 C013-04.
- **FR-CAP-08:** Khi một dạng từ được lưu ở nhiều ngày, app MUST dùng chung thẻ và lịch SRS, đồng thời giữ quan hệ với từng ngày ghi chú. Lưu trùng cùng nội dung giữ tiến độ; identity và reset khi sửa nghĩa/ví dụ tuân theo ADR-0004.
- **FR-CAP-09:** Khi tra cứu thất bại do bridge/network, app MUST báo lỗi để người dùng thử lại và MUST không giữ yêu cầu trong hàng đợi chờ.
- **FR-CAP-10:** App MUST cung cấp nút loa cạnh từ tiếng Anh bằng local `SpeechSynthesis` khi có voice; khi không có voice, nút báo unavailable và không gọi mạng.

### 6.2. `vocabulary-search-edit`

- **FR-VOC-01:** App MUST tìm được dạng từ dựa trên một phần nghĩa tiếng Việt được lưu ở trường nghĩa Việt chuẩn hóa; không được suy ra trường tìm kiếm từ bản dịch ví dụ nếu không có projection được định nghĩa.
- **FR-VOC-02:** App MUST hiển thị chi tiết word family và các ngày ghi chú liên quan.
- **FR-VOC-03:** Người dùng MUST sửa được nội dung từ vựng trong app.
- **FR-VOC-04:** Thay đổi từ app MUST được ghi vào Markdown theo ngày.
- **FR-VOC-05:** App MUST nhận biết thay đổi từ editor bên ngoài.
- **FR-VOC-06:** Khi thay đổi từ app và editor xung đột, app MUST require the current source revision/ETag; stale writes return `409 REVISION_CONFLICT` and never silently overwrite the other edit.
- **FR-VOC-07:** Sửa nghĩa hoặc ví dụ MUST đưa thẻ của dạng từ tương ứng về trạng thái chưa học.
- **FR-VOC-08:** File Markdown lỗi MUST bị tạm ngừng làm nguồn nội dung đang dùng; app MUST vẫn dùng dạng từ nếu còn nguồn Markdown hợp lệ khác. Không dùng bản nội dung cũ của chính file đang lỗi để tiếp tục ôn. Lịch sử đã học vẫn được giữ; quiz snapshot đang làm vẫn bất biến theo ADR-0004.
- **FR-VOC-09:** Khi dạng từ bị xóa khỏi mọi file, app MUST ngừng đưa thẻ vào ôn nhưng MUST giữ lịch sử và kết quả cũ. Đây là trường hợp khác với nguồn tạm lỗi ở FR-VOC-08; re-add identity tuân theo ADR-0004.

### 6.3. `review-srs`

- **FR-REV-01:** App MUST có một thẻ và lịch SRS riêng cho từng dạng từ.
- **FR-REV-02:** Mặt trước mặc định MUST là từ tiếng Anh; mục tiêu gọi lại là nghĩa tiếng Việt.
- **FR-REV-03:** Người dùng MUST có thể lật thẻ và tự đánh giá mà không cần nhập câu trả lời.
- **FR-REV-04:** App MUST có hàng đợi SRS mặc định và bộ lọc theo ngày ghi chú.
- **FR-REV-05:** Bộ lọc theo ngày MUST chỉ trả thẻ đến hạn hoặc chưa học của ngày đó.
- **FR-REV-06:** Đánh giá flashcard MUST được lưu trong lịch sử học và cập nhật theo deterministic five-box SRS in ADR-0004.
- **FR-REV-07:** Dữ liệu ôn MUST xác định due cards và completed-in-day using the `Asia/Bangkok` and invalid-source rules in ADR-0004.

### 6.4. `assessment`

- **FR-ASM-01:** App MUST hỗ trợ trắc nghiệm, điền từ và tự viết câu trong v1.
- **FR-ASM-02:** Người dùng MUST tự chọn số câu cho từng dạng.
- **FR-ASM-03:** Khi tạo theo ngày, tập nguồn được phép sử dụng MUST gồm tất cả từ có nguồn hợp lệ của ngày được chọn, kể cả thẻ chưa đến hạn. Số câu do người dùng chọn quyết định dung lượng đề; điều này không buộc mỗi bài chứa toàn bộ tập nguồn.
- **FR-ASM-04:** Đề MUST bằng tiếng Anh và phần giải thích đáp án MUST bằng tiếng Việt. Correct keys và explanationVi MUST chỉ trả trong result sau terminal submission commit; IN_PROGRESS reads/creation không chứa chúng. Rubric câu viết vẫn hiện trước nộp.
- **FR-ASM-05:** Trắc nghiệm MUST được chấm tự động.
- **FR-ASM-06:** Điền từ MUST yêu cầu đúng chính tả; chỉ bỏ qua khác biệt hoa/thường và khoảng trắng thừa.
- **FR-ASM-07:** Viết câu MUST cho phép người dùng tự chấm 0–4 theo descriptors `writing-rubric-v1` trong ADR-0005 C013-03; AI chỉ cung cấp nhận xét hỗ trợ và không tự quyết định điểm cuối cùng. null là chưa chấm và chặn nộp, không tự thành 0.
- **FR-ASM-08:** Hệ thống MUST tự quy đổi kết quả bài kiểm tra để cập nhật SRS. Nếu một dạng từ có nhiều kết quả trong cùng bài, kết quả yếu nhất MUST được ưu tiên.
- **FR-ASM-09:** Câu trả lời của bài đang làm MUST tự lưu để có thể tiếp tục sau khi đóng tab hoặc tắt app.
- **FR-ASM-10:** Nội dung bài đã tạo và kết quả đã lưu MUST dùng được khi offline.
- **FR-ASM-11:** Backend MUST render prompt từ template có version và placeholder cấu trúc, tối thiểu gồm attempt/question identifier, từ mục tiêu, câu trả lời, rubric và yêu cầu ngôn ngữ phản hồi; không nối chuỗi input không kiểm soát.
- **FR-ASM-12:** Prompt nhận xét viết câu MUST yêu cầu response JSON theo schema đã định nghĩa, tách feedback/criteria comments khỏi điểm cuối cùng do người dùng tự chấm.
- **FR-ASM-13:** Backend MUST parse và validate response JSON trước khi trả feedback cho frontend hoặc lưu vào database; response sai schema MUST không được hiển thị như thành công.
- **FR-ASM-14:** Feedback đã validate MUST được lưu cùng attempt, question, answer, provider/model, prompt version và timestamp để truy xuất lịch sử làm bài.
- **FR-ASM-15:** Nếu request cloud timeout, lỗi auth/quota hoặc response không hợp lệ, backend MUST giữ câu trả lời/điểm người dùng đã lưu, hiển thị lỗi feedback và không tự tạo điểm cuối cùng thay người dùng.

Giới hạn 5–30 câu, mỗi loại 0–20 và đủ dạng từ nguồn theo từng loại, rubric/blank policy, đáp án biến thể và submit-result lifecycle được khóa trong ADR-0004/0005. Cùng dạng từ có thể xuất hiện ở các loại khác nhau; mỗi cặp (loại, dạng từ) chỉ xuất hiện một lần. Schema JSON vẫn phải được kiểm tra từ generated OpenAPI.

### 6.5. `progress-dashboard`

- **FR-DASH-01:** Dashboard MUST hiển thị số thẻ đến hạn.
- **FR-DASH-02:** Dashboard MUST hiển thị streak theo timezone `Asia/Bangkok`: ngày có thẻ đến hạn cần hoàn thành toàn bộ thẻ hợp lệ; ngày không có thẻ đến hạn cần một thẻ mới hoặc quiz hoàn tất; nguồn lỗi bị loại khỏi mẫu số.
- **FR-DASH-03:** Dashboard MUST tách ít nhất ba nhóm kết quả: tự đánh giá flashcard; độ chính xác trắc nghiệm/điền từ; điểm tự chấm viết câu.
- **FR-DASH-04:** Số từ đã thêm MAY hiển thị như chỉ số phụ và MUST không được dùng thay cho các chỉ số kết quả học.
- **FR-DASH-05:** Dashboard MUST hoạt động khi offline với dữ liệu đã lưu.

Dashboard formulas, no-attempt null accuracy and four-week success measurement follow ADR-0004; source invalidation never erases historical result counts.

### 6.6. `offline-local-runtime`

- **FR-RUN-01:** App MUST hoạt động trên một máy Windows và mở bằng biểu tượng vào tab trình duyệt.
- **FR-RUN-02:** Không có luồng tài khoản, đăng nhập hoặc mật khẩu riêng trong v1.
- **FR-RUN-03:** Tìm kiếm, flashcard, dashboard và bài kiểm tra đã tạo MUST hoạt động khi mất mạng.
- **FR-RUN-04:** Tra cứu mới, tạo đề và nhận xét AI MUST được báo là cần bridge/network khi offline; phát âm dùng local `SpeechSynthesis` khi khả dụng và nếu không thì báo unavailable mà không gọi mạng.
- **FR-RUN-05:** App MUST không có chức năng sao lưu trong app ở v1; người dùng tự quản lý sao lưu.

Chi tiết cài đặt, tiến trình nền, thoát app và phục hồi sau sự cố tuân theo ADR-0004 và runbook vận hành; implementation evidence vẫn là gate trước release.

## 7. Business rules

| Rule ID | Business rule |
|---|---|
| `BR-01` | Chỉ bấm **Lưu để ôn** mới đưa kết quả tra vào bộ học. |
| `BR-02` | Phạm vi làm giàu là word family theo từ loại và nghĩa thường dùng trong ngữ cảnh học thuật; không tự thêm collocations, synonyms/antonyms hoặc nghĩa hiếm. |
| `BR-03` | Nội dung chưa xác minh vẫn được lưu, nhưng phải có nhãn rõ ràng. |
| `BR-04` | Mỗi dạng từ có một thẻ/lịch SRS riêng; cùng dạng ở nhiều ngày dùng chung thẻ. |
| `BR-05` | Flashcard mặc định đi từ tiếng Anh đến nghĩa tiếng Việt bằng cách lật và tự đánh giá. |
| `BR-06` | Ôn theo ngày chỉ lấy thẻ đến hạn hoặc chưa học; tạo quiz theo ngày lấy tất cả từ của ngày. |
| `BR-07` | Điền từ đúng chính tả là bắt buộc; chỉ không phân biệt hoa/thường và bỏ qua khoảng trắng thừa. |
| `BR-08` | Kết quả quiz cập nhật SRS tự động; kết quả yếu nhất của cùng dạng từ được dùng khi có nhiều kết quả. |
| `BR-09` | Điểm viết câu do người dùng tự chấm; AI chỉ nhận xét hỗ trợ. |
| `BR-10` | Ngày có thẻ đến hạn chỉ đạt streak khi hoàn thành toàn bộ thẻ đến hạn. |
| `BR-11` | Ngày không có thẻ đến hạn chỉ đạt streak khi học ít nhất một thẻ mới hoặc hoàn tất một bài kiểm tra. |
| `BR-12` | Sửa nghĩa hoặc ví dụ reset thẻ tương ứng về chưa học. |
| `BR-13` | Xung đột sửa app/editor dùng source revision/ETag; stale write trả `409 REVISION_CONFLICT`, không tự động last-write-wins. |
| `BR-14` | File Markdown lỗi bị loại khỏi nguồn học; nguồn hợp lệ khác của cùng dạng từ vẫn có hiệu lực. |
| `BR-15` | Xóa dạng từ khỏi mọi file ngừng ôn nhưng giữ lịch sử và kết quả cũ. |
| `BR-16` | Tra cứu thất bại báo lỗi và cho thử lại; không giữ hàng đợi thất bại. |
| `BR-17` | Chỉ gửi dữ liệu cần thiết cho tác vụ AI hiện tại; lịch sử học và dữ liệu không liên quan ở lại trên máy. |
| `BR-18` | Không có tài khoản/mật khẩu app, truy cập thiết bị khác hoặc backup trong app ở v1. |

### 7.1. Deterministic contract oracles — T013

| Boundary | Oracle hiện hành | Authority / task áp dụng |
|---|---|---|
| SRS | AGAIN→1; HARD giữ box (NEW→1); GOOD+1/EASY+2 capped5. Interval 1/3/7/14/30 ngày; due là 00:00 Bangkok của local review date + interval, serialize UTC. NEW dueAt=null và eligible ngay. GOOD từ NEW tại `2026-09-29T10:20:30Z` → due `2026-09-29T17:00:00Z`. | ADR-0005 C013-02; T031/T032/T059 |
| Rubric / blank | 0–1 AGAIN, 2 HARD, 3 GOOD, 4 EASY. Writing null chặn nộp; blank writing chỉ nộp với explicit 0. Blank objective giữ outcome BLANK và map AGAIN khi nộp; accuracy dùng correct/attempted với null nếu chưa attempted. | C013-03; T059/T048 |
| Save / source | Ngày mới `{lookupId,noteDate}` + `If-None-Match: *`; backend cấp ID, revision1 và `DD-MM-YYYY.md`. Nguồn đã có dùng sourceId/revision/If-Match; hash stale bị 409. Receipt/replay không tạo thêm source/card. | C013-04/05; T021–T024/T029 |
| Quiz result | IN_PROGRESS có public questions, answers/revisions và result=null. Submit current aggregate revision commit một lần; terminal GET attempt có stored result/keys/explanations. Source inactive giữ lịch sử và skip SRS. | C013-06/07; T034/T035/T047/T048/T051 |
| Caps | JSON 1 MiB; Markdown 8 MiB; bridge response 4 MiB; content string ≤4096 code points; collection ≤100, tighter term/quiz/page limits thắng. Không truncate. | CONSTRAINTS/C013-08; T006/T007/T041 |
| Session | Bootstrap one-time <60s; browser session <8h không sliding, hết hiệu lực khi backend shutdown/restart. Rebootstrap giữ acknowledged durable drafts/consent/receipts, không tự dispatch AI. | CONSTRAINTS/C013-09; T006/T066 |
| Deadlines / retention | Monotonic lookup120/quiz60/feedback30s từ server admission, không reset/retry; elapsed≥budget trả typed timeout. Idempotency intents/receipts/fingerprints giữ suốt lifetime DB; referenced consent/policy giữ với history. | CONSTRAINTS/C013-10; T007/T014/T016 |

## 8. Data requirements

### 8.1. Dữ liệu phải được lưu

| Data ID | Dữ liệu | Quy tắc sử dụng |
|---|---|---|
| `DATA-01` | Dạng từ, từ loại và quan hệ word family | Định danh từng thẻ và hiển thị nhóm từ. |
| `DATA-02` | Tất cả nghĩa học thuật thường dùng theo dạng từ, gồm projection nghĩa tiếng Anh và nghĩa/bản dịch tiếng Việt chuẩn hóa | Tìm kiếm và ôn; nghĩa chưa xác minh phải có trạng thái. Trường `meaningVi` là nguồn chính cho tìm kiếm một phần nghĩa tiếng Việt. |
| `DATA-03` | Ví dụ tiếng Anh và bản dịch tiếng Việt theo dạng từ | Hiển thị mặt sau và giải thích. |
| `DATA-04` | IPA Mỹ và liên kết Cambridge theo dạng từ | Hiển thị tra cứu; trạng thái thiếu/chưa xác minh phải bảo toàn. |
| `DATA-05` | Ngày ghi chú và quan hệ tới Markdown file | Lọc ôn theo ngày và tạo quiz theo ngày. |
| `DATA-06` | Trạng thái parse/sync của từng file Markdown | Loại nguồn lỗi và giữ nguồn hợp lệ khác. |
| `DATA-07` | Thẻ, lịch SRS, trạng thái chưa học/đã học, due state và đánh giá | Xây hàng đợi và tính streak. |
| `DATA-08` | Lịch sử flashcard và quiz | Dashboard, SRS và giữ kết quả sau khi xóa nguồn. |
| `DATA-09` | Nội dung bài kiểm tra, câu hỏi, đáp án/giải thích, tiêu chí tự chấm, ngày nguồn, số câu từng loại và câu trả lời đang dở | Immutable snapshot at creation; continue and complete offline; source changes do not mutate the attempt. |
| `DATA-10` | Điểm tự chấm viết câu và nhận xét AI khi có | Tách chỉ số viết câu và xem lại feedback. |
| `DATA-11` | Feedback JSON đã validate, attempt/question/answer reference, provider/model, prompt version, status lỗi và timestamp | Trả feedback cho UI, truy xuất lịch sử và phân biệt lỗi cloud với điểm người dùng. |
| `DATA-12` | Lựa chọn consent AI cục bộ, revision, policy version và thời điểm server; metadata policy không chứa nội dung học hay secret | Backend làm nguồn sự thật qua reload/restart; mặc định chưa cấp, revoke không xóa dữ liệu học. Retention/export/backup theo ADR-0004 và runbook; không coi log là bản ghi consent chuẩn. |

### 8.2. Dữ liệu Markdown và đồng bộ

- Markdown theo ngày là định dạng nguồn mà sản phẩm phải tiếp tục hỗ trợ.
- Khả năng đọc toàn bộ định dạng cũ là giả định A3 ở mục 18; `docs/vocabularies/README.md` và mapping trong ADR-0004 là hợp đồng v1, không được mặc định các trường cũ đều là input bắt buộc.
- App không được xem lịch SRS, lịch sử học hoặc bài làm là có thể dựng lại hoàn toàn từ Markdown; cách lưu bền vững các dữ liệu này là SQLite theo ADR-0004.
- Khi cập nhật từ app, Markdown phải được ghi lại; khi file thay đổi bên ngoài, app phải đồng bộ lại.
- Source revisions/ETags decide conflicts; stale writes fail closed. The durable journal/hash state and startup reconciliation are defined in ADR-0004.

Để tránh mất dữ liệu khi triển khai, parser/serializer MUST có fixture round-trip cho file `DD-MM-YYYY.md` hiện có, giữ `relativePath` legacy hoặc thực hiện migration được người dùng xác nhận; unknown/context fields không được tự xóa. Sync MUST phát ra `sourceRevision` để invalidates search/detail/queue/dashboard projection. PATCH trên source `INVALID`/`MISSING` phải bị từ chối hoặc đi qua một repair/relink flow riêng, chưa được tự động sửa file lỗi.

Autosave quiz MUST lưu một `draftRevision` và có thể truy hồi câu trả lời đã lưu sau reload; request bị hủy sau khi server đã commit phải được đối soát qua operation status. Quiz submit và cập nhật SRS phải có định danh/idempotency để không tính trùng khi retry.

Bridge AI MUST tuân theo ranh giới HTTP loopback + client API key được chấp thuận trong ADR-0002, consent/policy gate in ADR-0003 and the v1 provider/route policy in ADR-0004; không suy ra danh tính server từ key hoặc `health=200`. Backend giữ correlation trong log/span cục bộ và loại bỏ `X-Request-ID`, `traceparent`, `tracestate`, `baggage` trước chặng app→proxy; không gửi browser cookie/bootstrap token.

Quan hệ nghiệp vụ cần giữ: một word family có nhiều dạng từ; một dạng từ liên kết với nhiều ngày/file nhưng dùng chung một thẻ/lịch; một bài kiểm tra có nhiều câu và câu trả lời; kết quả cần liên kết tới dạng từ để cập nhật SRS. Khi reset thẻ hoặc loại nguồn khỏi sử dụng, lịch sử học là dữ liệu riêng cần bảo toàn. Khóa định danh, số lần làm bài, revision và transaction cụ thể được đặc tả ở API/ADR-0004; implementation phải kiểm chứng bằng contract và migration tests.

### 8.3. Dữ liệu không cần lưu trong v1

- Câu gốc, tên bài báo hoặc đường dẫn bài báo do người dùng gặp từ.
- Bản backup do app tạo tự động hoặc theo nút backup.

Lịch sử học vẫn phải lưu cục bộ; việc không gửi lịch sử ra dịch vụ AI là giới hạn truyền dữ liệu ở mục 12, không phải lý do để loại bỏ lịch sử khỏi dữ liệu cần lưu.

## 9. Authentication và authorization requirements

- **AUTH-01:** App MUST không yêu cầu tài khoản, đăng nhập hoặc mật khẩu riêng.
- **AUTH-02:** V1 chỉ có một người dùng cục bộ; không cần mô hình vai trò hoặc phân quyền nhiều người dùng.
- **AUTH-03:** App MUST không cung cấp truy cập từ thiết bị khác trong mạng nội bộ.
- **AUTH-04:** Mọi thao tác trong app được coi là do người dùng cục bộ đã mở app thực hiện; mức bảo vệ file, process và secret store tuân ADR-0004 mà không thêm luồng tài khoản sản phẩm.

Việc đăng nhập vào dịch vụ AI/provider là vấn đề tích hợp bên ngoài, khác với đăng nhập app đã loại khỏi phạm vi. API key của local bridge MUST chỉ được backend/local process gửi tới bridge; frontend không được nhận key và database feedback không được lưu key. Cơ chế lưu key dùng secret store/config local theo ADR-0004; implementation phải chứng minh không rò rỉ.

## 10. Loading, empty, error và success states

Trạng thái dưới đây mô tả loading/empty/error/success theo yêu cầu của bản spec. Không thêm bộ đếm, thông báo hệ điều hành hoặc tính năng ngoài luồng đã chốt. Lỗi không được hiển thị như thành công; chưa có kết quả học không được trình bày như độ chính xác 0% của một bài đã chấm.

| Capability | Loading | Empty | Error | Success |
|---|---|---|---|---|
| Tra cứu | Cho biết đang tra | Chưa nhập từ hoặc chưa có kết quả; thiếu trường tùy chọn hiển thị `MISSING` theo ADR-0004 | Nêu không tra được, cho **Thử lại**, không tạo hàng đợi | Hiển thị kết quả, trạng thái kiểm chứng và **Lưu để ôn** |
| Lưu/sync Markdown | Cho biết đang ghi và đồng bộ | Chưa có file/ngày ghi chú phù hợp | Nêu file/nguồn lỗi và không đưa nguồn lỗi vào ôn | Hiển thị đã lưu, ngày ghi chú và trạng thái sync |
| Tìm kiếm | Cho biết đang tìm | Nêu không có kết quả cho phần nghĩa đã nhập | Nêu lỗi tìm | Hiển thị những dạng từ khớp |
| Sửa | Cho biết đang ghi thay đổi | Không có nội dung để sửa | Nêu lỗi ghi/sync hoặc conflict và không báo thành công giả | Hiển thị bản đã xác nhận cùng source revision và trạng thái thẻ reset nếu áp dụng |
| Flashcard | Cho biết đang tải hàng đợi | Nêu không có thẻ đến hạn/chưa học theo bộ lọc | Nêu lỗi tải/lưu đánh giá | Hiển thị thẻ để ôn; sau đánh giá cho biết đã ghi nhận |
| Tạo quiz | Cho biết đang tạo đề và cần mạng | Nêu ngày không có từ hoặc không tạo được số câu hợp lệ theo giới hạn ADR-0004 | Nêu lỗi tạo/không hợp lệ, giữ giới hạn 5–30 và max 20 mỗi loại | Hiển thị đề và trạng thái có thể bắt đầu |
| Làm quiz | Cho biết đang tải bài hoặc ghi câu trả lời | Chưa có câu trả lời; bài không có câu hợp lệ theo giới hạn ADR-0004 | Nêu lỗi lưu cục bộ; lỗi mạng chỉ ảnh hưởng nhận xét AI, không chặn làm bài đã có | Cho biết câu trả lời đã lưu; bài hoàn tất hiển thị kết quả/giải thích và điểm tự chấm |
| Dashboard | Cho biết đang tải dữ liệu cục bộ | Nêu chưa có lịch sử; không có thẻ đến hạn là giá trị 0 hợp lệ | Nêu phần dữ liệu không tải được | Hiển thị due cards, streak và chỉ số tách riêng |
| Offline | Nêu app đang offline và tác vụ nào bị giới hạn | Nêu chưa có dữ liệu cục bộ cho tác vụ | Nêu tác vụ cần mạng | Cho phép các luồng dữ liệu đã lưu tiếp tục |

## 11. Accessibility requirements

- **A11Y-01:** Toàn bộ app MUST sử dụng được bằng bàn phím, gồm tra cứu, lưu, sửa, điều hướng, lọc ngày, flashcard, quiz và cài đặt nếu có.
- **A11Y-02:** Trạng thái MUST có chữ hoặc biểu tượng có ý nghĩa, không chỉ dựa vào màu.
- **A11Y-03:** Target WCAG 2.2 AA: normal text 4.5:1, large text 3:1, controls/focus 3:1, visible focus and focus not obscured.
- **A11Y-04:** Every control, including local SpeechSynthesis button, is keyboard accessible with a text label and status.
- **A11Y-05:** At 200% browser zoom no required content or control is hidden; manual keyboard and screen-reader smoke checks are release gates.
- **A11Y-06:** WCAG 2.2 AA is a target to verify, not a claim before testing.

## 12. Security requirements

- **SEC-01:** Chỉ dữ liệu cần cho tác vụ AI hiện tại được gửi tới dịch vụ AI: từ đang tra, nhóm từ được chọn tạo đề hoặc câu người dùng viết cần nhận xét.
- **SEC-02:** Lịch sử học, tiến độ SRS và dữ liệu không liên quan MUST ở trên máy, trừ khi có quyết định mở mới được người dùng chốt.
- **SEC-03:** App MUST không tự thêm billing project, silently enable a paid route, hoặc hide cost/quota behavior. Paid fallback is **not prohibited in principle**, but it is allowed only when the approved cloud policy explicitly names provider/model/route/billing mode, the disclosure states the cost/quota implication, consent covers that policy version, and backend dispatch authorization matches it. Proxy support is not evidence of entitlement; v1 defaults and fail-closed behavior are in ADR-0004.
- **SEC-04:** Luồng v1 không thu thập câu gốc/nguồn bài đọc mới. Những trường ngữ cảnh đã có trong Markdown cũ không mặc nhiên được phép gửi ra ngoài; mapping tương thích dữ liệu cũ tuân ADR-0004.
- **SEC-05:** Không được thêm xác thực người dùng, chia sẻ mạng hoặc cloud sync để giải quyết vấn đề bảo mật; bảo vệ process/file/credential kỹ thuật tuân ADR-0002/0004.
- **SEC-06:** Dữ liệu AI chưa xác minh phải được gắn nhãn, không được trình bày như dữ liệu đã kiểm chứng.
- **SEC-07:** Backend MUST giới hạn payload cloud cho tác vụ hiện tại, không gửi toàn bộ lịch sử học; vì inference cloud, UI/settings MUST biểu thị rằng câu trả lời đang được gửi tới provider bên ngoài máy.
- **SEC-08:** Trước lần tra/tạo quiz AI/nhận xét câu viết đầu tiên, app MUST hiển thị policy đầy đủ và yêu cầu người dùng bấm đồng ý; đóng/từ chối không gửi dữ liệu. Backend MUST có consent đúng policy version và policy đã được duyệt trước khi gọi AI. Policy thay đổi phạm vi/recipient/model/routing/chi phí/lưu dữ liệu phải yêu cầu đồng ý lại; audio và export telemetry không được cấp quyền ngầm.
- **SEC-09:** Người dùng MUST có thể xem/rút lại consent tại `/status`, không cần bridge/network. Sau commit revoke, backend chặn mọi dispatch mới cho tới khi có grant hợp lệ; request đã được nhận vào HTTP transport trước đó có thể hoàn tất và không thu hồi được dữ liệu đã gửi. Revoke không xóa từ, bài làm, điểm hoặc feedback; pending request chưa dispatch không được tự sống lại khi grant lại. Không báo success nếu chưa lưu được lựa chọn.

## 13. Performance requirements

- **PERF-01:** Với điều kiện thử được ghi lại trước khi nghiệm thu, một lần tra từ mới MUST trả đủ nội dung để người dùng xem và bấm lưu trong tối đa **120 giây**.
- **PERF-02:** Tìm kiếm theo một phần nghĩa tiếng Việt MUST hiển thị kết quả trong tối đa **1 giây** trên kho **100.000 dạng từ**.
- **PERF-03:** Hồ sơ benchmark ghi Windows 11, Python 3.12, SQLite build, dataset/query, network, cache and monotonic start/end; search uses p95 ≤1s on the named 100k fixture.
- **PERF-04:** V1 phải phục vụ kho vài chục nghìn dạng từ hoặc lớn hơn; 100.000 là mốc kiểm thử đã đồng ý, không phải cam kết vô hạn cho mọi quy mô.
- **PERF-05:** Quiz generation p95 ≤60s and feedback p95 ≤30s on the named fixture; both are cancellable and bounded. Lookup remains p95 ≤120s end-to-end.

**Giao thức đo:** Với tìm kiếm, đo từ thao tác gửi truy vấn đến khi danh sách kết quả được vẽ xong trên trình duyệt; với tra từ mới, đo từ thao tác gửi đến khi nội dung tra hiển thị và có thể lưu. Dùng đồng hồ đơn điệu cùng máy đo, ghi từng thời gian thực tế, không thay ngưỡng tối đa bằng thời gian trung bình. Đây là cách kiểm chứng cho AC-07/AC-27; fixture Windows 11/Python 3.12/SQLite, bộ dữ liệu/truy vấn, cache và điều kiện mạng/quota phải dùng đúng baseline ADR-0004 trước nghiệm thu.

## 14. Scope

V1 bao gồm sáu capability trong capability map: tra/làm giàu/lưu; tìm/sửa/sync Markdown; flashcard/SRS; ba dạng bài kiểm tra; dashboard/streak; runtime local/offline trên Windows. V1 giữ Markdown theo ngày, tìm theo nghĩa tiếng Việt, SRS theo từng dạng từ, tự lưu bài làm, local SpeechSynthesis khi khả dụng, keyboard navigation toàn app và các trạng thái UI được liệt kê.

Framework, package manager, database schema, API routes và thuật toán SRS cụ thể follow ADR-0004; bootstrap tasks must pin exact versions/lockfiles before implementation.

## 15. Non-goals

- Multi-user, tài khoản, đăng nhập, mật khẩu app hoặc authorization theo vai trò.
- Cloud sync, truy cập từ thiết bị khác và mobile native app.
- Silent paid API/project creation or unapproved paid fallback.
- Luồng CLI thủ công/import thủ công như trải nghiệm thường ngày.
- Lưu câu gốc, nguồn bài đọc, tên bài đọc.
- Collocations, synonyms/antonyms và nghĩa ít gặp.
- Tự chấm điểm cuối cùng cho câu viết bằng AI.
- Bắt buộc nhập đáp án cho flashcard.
- Backup trong app.
- Audio provider/network speech service.
- Cam kết hỗ trợ trình đọc màn hình toàn diện.
- Cửa sổ desktop riêng thay cho tab trình duyệt.

## 16. Acceptance criteria

Mỗi AC có đầu vào/điều kiện, hành động và kết quả quan sát được. Dữ liệu thử là fixture để kiểm chứng, không thêm thiết lập hoặc tính năng cho người dùng. Test dùng kết quả AI giả lập chỉ chứng minh hành vi của app; không chứng minh chất lượng nội dung AI thật, khả thi của CLI hoặc hiệu năng mạng.

Các công thức/edge cases chưa chốt không được đưa vào AC dưới dạng “đúng theo quy tắc sẽ quyết định sau”. AC dưới đây chỉ kiểm tra phần đã biết; phần còn thiếu được liệt kê riêng sau bảng. Hai AC hiệu năng dùng giao thức đo đề xuất ở mục 13 và phải ghi môi trường thử để có thể chạy lại.

| ID | Đầu vào và thao tác → kết quả bắt buộc | Requirement / cách kiểm chứng |
|---|---|---|
| `AC-01` | Trên Windows đã cài app, app chưa chạy: bấm biểu tượng → app khởi động, tab trình duyệt hiển thị giao diện và không có yêu cầu đăng nhập app. | FR-RUN-01/02; kiểm thử khởi động thực tế. |
| `AC-02` | Cấp một kết quả tra fixture có danh sách dạng từ, nghĩa, ví dụ/bản dịch, IPA Mỹ và Cambridge link đã đối chiếu → app hiển thị đủ từng dạng và từng mục nội dung trong fixture, không bỏ nghĩa hoặc gộp mất từ loại. | FR-CAP-03/04; so UI và dữ liệu với fixture. Chất lượng ngữ nghĩa AI thật chưa được nghiệm thu bằng test này. |
| `AC-03` | Kho chưa có dạng từ X; tra X thành công nhưng không bấm **Lưu để ôn**, sau đó mở bộ học → không có X hoặc thẻ mới của X. | FR-CAP-06; so kho/thẻ trước và sau. |
| `AC-04` | Clean install không có nguồn/ngày D; tra fixture ba dạng từ mới, chọn D và bấm **Lưu để ôn** với conditional create → backend cấp sourceId, tạo Markdown `DD-MM-YYYY.md` revision1 và ba NEW cards đúng quan hệ D; receipt có sourceId/revision/ETag. Replay cùng key không tạo thêm source/card. | FR-CAP-07, FR-REV-01; ADR-0005 C013-04; kiểm tra journal/file/receipt và quan hệ thẻ. |
| `AC-05` | Mô phỏng bridge trả lỗi cho một lần tra → UI báo không tra được và cho người dùng thử lại; không có hàng đợi retry. Người dùng thử lại thì có một lần tra mới. | FR-CAP-09; quan sát UI, dữ liệu job và lời gọi tích hợp. |
| `AC-06` | Với kho đã lưu, ngắt mạng rồi thử tra mới, tạo đề và nhận xét AI → báo cần mạng; nút loa vẫn đọc bằng local SpeechSynthesis nếu voice có sẵn, hoặc báo unavailable nếu không. Dữ liệu học đã lưu không bị xóa. | FR-RUN-04/FR-CAP-10; test offline và voice available/unavailable. |
| `AC-07` | Trên fixture 100.000 dạng từ, tìm chuỗi con có dấu tiếng Việt được cài duy nhất trong nghĩa của X → danh sách có X; thời gian gửi truy vấn đến vẽ kết quả ≤ 1.000 ms. Ghi cấu hình máy, truy vấn, dữ liệu và cache để chạy lại. | FR-VOC-01, PERF-02; đo theo mục 13. Việc đạt trên môi trường thử không thay thế xác nhận môi trường nghiệm thu. |
| `AC-08` | Với thẻ X đã học và chỉ có một nguồn hợp lệ: sửa nghĩa trong app, rồi thử độc lập với sửa ví dụ → mỗi lần lưu làm Markdown và UI phản ánh nội dung mới; trạng thái thẻ X là chưa học, lịch sử cũ vẫn còn. | FR-VOC-03/04/07; đọc lại file và trạng thái thẻ. |
| `AC-09` | File F chứa X, Y; file G hợp lệ chỉ chứa Y; X/Y đang đủ điều kiện ôn. Làm F sai định dạng rồi đồng bộ → X không được đưa vào ôn; Y vẫn được ôn từ G, không dùng nội dung lỗi của F. | FR-VOC-08; kiểm tra trạng thái nguồn và hàng đợi. |
| `AC-10` | X có lịch sử review/quiz; xóa X khỏi tất cả file rồi đồng bộ → hàng đợi mới không có X; các kết quả/lịch sử đã ghi trước đó giữ nguyên. | FR-VOC-09; so dữ liệu trước/sau và hàng đợi. |
| `AC-11` | Lưu lại chính dạng X với cùng nội dung ở ngày D2 sau khi đã học X từ D1 → X có quan hệ với D1 và D2, chỉ một thẻ/lịch SRS, tiến độ trước lần lưu lại được giữ. | FR-CAP-08; kiểm tra số thẻ, quan hệ ngày và trạng thái lịch. |
| `AC-12` | Mở một thẻ từ hàng đợi → mặt trước hiển thị từ tiếng Anh và che nghĩa; lật rồi tự đánh giá không cần ô nhập đáp án → dữ liệu lưu đánh giá gắn đúng thẻ. | FR-REV-02/03/06; kiểm tra UI và bản ghi học. |
| `AC-13` | D1 có X đến hạn, Y chưa học, Z đã học/chưa đến hạn; D2 có W đến hạn → chọn D1 thì tập thẻ có thể ôn là X, Y, không có Z, W. | FR-REV-04/05; so toàn bộ tập hàng đợi, không phụ thuộc số thẻ hiển thị mỗi lần. |
| `AC-14` | Ngày D có ba dạng từ A/B/C hợp lệ với thẻ chưa đến hạn; chọn 2 MCQ, 2 cloze, 1 writing → payload có cả A/B/C, snapshot gồm MCQ A/B, cloze A/C, writing B, đúng năm câu. Thử 1/1/1 độc lập → `422 VALIDATION_ERROR` vì total3<5, zero bridge calls. Thử count vượt eligible forms của một loại → validation error trước dispatch. | FR-ASM-01/02/03; C013-01; positive5/negative3/per-type/source oracle. |
| `AC-15` | Tạo/mở IN_PROGRESS fixture năm câu → public questions bằng tiếng Anh, không có correct keys/explanationVi; nộp thành công rồi GET attempt → result có đáp án và giải thích tiếng Việt đã lưu. | FR-ASM-04; C013-06/07; kiểm tra response fields trước/sau, không chỉ CSS. |
| `AC-16` | Với một câu điền từ có duy nhất đáp án `robust`, chấm độc lập các đáp án `robust`, `ROBUST`, ` robust ` và `robuts` → ba đáp án đầu đúng, đáp án cuối sai. | FR-ASM-06; kiểm thử chấm tự động với input/output cụ thể. |
| `AC-17` | Với `writing-rubric-v1`, chọn P∈{0,1,2,3,4}, lưu và nhận AI feedback → P giữ nguyên, comments hiển thị riêng. Thử nộp với selfScore=null → 422, không có result/SRS mới; blank writing chỉ nộp với explicit0. | FR-ASM-07; C013-03; descriptors/mapping và điểm trước/sau AI. |
| `AC-18` | Nhập quiz answer, đợi durable autosave acknowledgement và đóng tab/app → reload/rebootstrap GET attempt phục hồi đáp án cùng revision. Submit flush drafts rồi dùng aggregate revision hiện hành; mất response sau commit → GET terminal result hoặc same-key replay, không thêm handoff. Chỉ acknowledged drafts được bảo đảm qua crash. | FR-ASM-09; C013-07/09; kiểm tra draft/operation/attempt reads và failure injection. |
| `AC-19` | X ở box2 có MCQ đúng và cloze sai trong cùng quiz; submit tại `2026-09-29T10:20:30Z` → weakest AGAIN, một review event, box1/due `2026-09-29T17:00:00Z`. Replay không thêm event; new submit key →409 ALREADY_SUBMITTED. X inactive giữ result/history và SKIPPED_INACTIVE, không schedule mới. | FR-ASM-08; C013-02/03/07; scoring và atomic/replay oracle. |
| `AC-20` | Với dữ liệu có hoạt động flashcard, MCQ/cloze và viết câu → dashboard có các nhóm kết quả tách biệt cùng due cards/streak; không thay ba nhóm kết quả bằng một điểm tổng. | FR-DASH-01/02/03; kiểm tra nội dung và phân nhóm UI, chưa kiểm chứng công thức chưa chốt. |
| `AC-21` | Trong một ngày thử không qua nửa đêm, không có nguồn lỗi và không phát sinh hạn mới, chỉ có hai thẻ đến hạn X/Y. Khi mới hoàn thành X → ngày chưa đạt streak; khi cả X/Y đã hoàn thành và không còn thẻ đến hạn → ngày đạt. | FR-DASH-02, BR-10; kiểm thử hai trạng thái ngày cố định. |
| `AC-22` | Ngày thử không có thẻ đến hạn: không hoạt động → ngày chưa đạt streak; trên hai bản sao trạng thái, học một thẻ mới hoặc hoàn tất một quiz → mỗi bản sao đều đạt ngày đó. | BR-11; kiểm thử ba trạng thái độc lập cùng ngày. |
| `AC-23` | Chuẩn bị kho/thẻ và một đề đã tạo, sau đó ngắt mạng → tìm được từ, lật/đánh giá được thẻ, đọc dashboard và nhập/tự lưu câu trả lời trong đề. Mở lại vẫn thấy dữ liệu học đã lưu. | FR-RUN-03, FR-ASM-10; chạy các luồng offline thực tế. |
| `AC-24` | Chỉ dùng bàn phím, thực hiện J1–J5 và kích hoạt mọi điều khiển có trong v1, gồm nút loa → không có bước bắt buộc dùng chuột hoặc mắc kẹt không điều hướng ra được. | A11Y-01/04; checklist điều khiển và kiểm thử bàn phím thủ công. |
| `AC-25` | Khi browser có voice phù hợp, bấm loa cạnh một dạng từ → `SpeechSynthesis` đọc đúng từ; nếu không có voice, nút bị disabled và không phát sinh request mạng. | FR-CAP-10; test voice available/unavailable/offline-equivalent. Audio không dùng AI consent hay provider network. |
| `AC-26` | Cài chuỗi đánh dấu vào lịch sử học và một từ không thuộc tác vụ; thực hiện tra từ, tạo đề cho tập đã chọn và nhận xét câu viết → payload AI không chứa hai chuỗi đánh dấu, chỉ chứa nội dung tác vụ cùng prompt cần thiết. | SEC-01/02; kiểm tra payload trước khi gửi, không xuất credential trong báo cáo. |
| `AC-27` | Chạy app thật với consent/policy/profile đã được duyệt, gọi `POST /api/v1/lookups` qua backend tới Antigravity v4.8.4 (không gọi CLI trực tiếp), đo từ thao tác gửi đến khi nội dung hiển thị và có thể lưu → p95 ≤ 120 giây, hard timeout/cancellation ở 120 giây; hồ sơ thử ghi app/bridge version, selected provider/model/route, auth-profile result, trạng thái mạng/quota và cấu hình máy. | PERF-01, FR-CAP-02, SEC-08/09; đo toàn luồng theo baseline ADR-0004, không dùng AI giả lập để chứng minh tốc độ. |
| `AC-28` | API đọc source revision1/ETag E1/hash H1; editor ghi H2, hash/watcher sync tạo revision2/E2 (editor không nhận HTTP response). API write với revision1/E1 →409 REVISION_CONFLICT và giữ H2; reload2/E2 rồi xác nhận write →revision3. Hash stale cũng bị chặn khi watcher chưa hoàn tất. | FR-VOC-06; C013-05; revision/ETag/hash, conflict dialog, file và UI; không dùng timestamp để chọn bản thắng. |
| `AC-29` | Dùng toàn bộ J1–J5 bằng phiên app cục bộ → không gặp tạo tài khoản, mật khẩu app hoặc phân vai; thử truy cập từ máy khác cùng mạng → không mở được app. | AUTH-01/02/03; kiểm thử cục bộ và truy cập từ máy thứ hai. Không chốt cơ chế kỹ thuật. |
| `AC-30` | Với MCQ fixture có một đáp án đúng xác định, nộp đáp án đúng rồi thử trên bản độc lập với đáp án sai → hệ thống tự trả đúng/sai tương ứng, không yêu cầu người dùng tự chấm MCQ. | FR-ASM-05; kiểm thử chấm kết quả. |
| `AC-31` | Sửa nghĩa trong một file hợp lệ bằng editor rồi hoàn tất đồng bộ → app hiển thị nghĩa mới, tìm được theo nghĩa mới và thẻ tương ứng trở về chưa học. | FR-VOC-05/07; kiểm tra file, UI, tìm kiếm và thẻ. |
| `AC-32` | Với mỗi tác vụ ở mục 10: trì hoãn phản hồi → có trạng thái đang xử lý; cung cấp tập rỗng → có trạng thái không có dữ liệu; gây lỗi → báo lỗi, không báo thành công; trả thành công → hiển thị kết quả. Các trạng thái và đúng/sai đều có nhãn/biểu tượng khi bỏ màu khỏi giao diện. | Mục 10, A11Y-02; kiểm thử từng trạng thái bằng fixture và xem giao diện không màu. |
| `AC-33` | Cấp kết quả tra có nghĩa/từ loại được đánh dấu chưa đối chiếu → UI hiện **chưa xác minh**; bấm lưu thành công và mở lại → nhãn vẫn còn, từ được lưu để ôn. | FR-CAP-05; kiểm tra UI/lưu/đọc lại. Không áp dụng mặc định cho trường hợp thiếu IPA/link. |
| `AC-34` | Compatibility-only fixture: bridge trả `200` cho `GET /health`, models list hợp lệ và chat response hợp lệ → backend adapter parse/records request/response without terminal/import. This does **not** prove auth profile, LAN isolation, route/model authorization, consent, billing/quota or content quality. | FR-CAP-02; historical smoke result `LOCAL_API_OK` is compatibility evidence only. Installed v4.8.4 profile must separately pass `BR-AUTH-01`–`09` and policy/consent tests before release. |
| `AC-35` | Cấp prompt fixture cho nhận xét câu viết và response JSON fixture hợp lệ → backend parse được, trả feedback đã validate cho frontend và lưu bản ghi gắn attempt/question/answer/model/prompt version; cấp response thiếu trường bắt buộc → backend không trả success và không ghi feedback không hợp lệ. | FR-ASM-11–15, DATA-11; integration test parser/storage với hai response fixture. |
| `AC-36` | Với proxy fixture theo ADR-0002: no-key/wrong-key bị từ chối, key hợp lệ được chấp nhận; no-key models trả success hoặc cấu hình remote/redirect/route/model không được policy cho phép → app không gửi inference/key tới đích ngoài allowlist và báo lỗi cấu hình/dependency. Browser/log/DB không có key; outbound proxy không có app trace/cookie; chức năng học cục bộ vẫn hoạt động khi bridge bị chặn. | FR-CAP-02, SEC-01/02/07; `BR-AUTH-01`–`09` trong API, fake upstream + credential giả. LAN/admin isolation kiểm chứng riêng trên bản cài trước release. Không dùng test này để tuyên bố chống proxy giả mạo trên máy đã bị xâm nhập. |

**Evidence còn phải thu thập:** ADR-0004/0005 đã khóa due/rubric/retention/source/snapshot/session và các boundary oracles. Generated-schema, crash/filesystem, real AI semantic completeness, Windows/browser, contrast/zoom và performance vẫn cần verification ở task owner; document conformance không thay thế các kiểm thử này. Mục tiêu 6 ngày/tuần cần quan sát dùng thử theo ADR-0004.

### Acceptance bổ sung — consent AI

| ID | Điều kiện/thao tác → kết quả cần kiểm chứng | Traceability |
|---|---|---|
| `AC-37` | App mới hoặc consent bị revoke/stale: gọi trực tiếp từng endpoint lookup/AI quiz/feedback → backend từ chối, số lời gọi bridge cho tác vụ bằng 0; đóng/từ chối dialog không grant và vẫn học cục bộ. | SEC-08; CONSENT-01/03/07 |
| `AC-38` | Policy fixture đã duyệt: đọc disclosure, bấm đồng ý → backend lưu version/revision/time; reload và restart vẫn đọc được. Không tự gửi tác vụ đang nhập; chỉ thao tác AI tiếp theo mới được kiểm tra và dispatch. | DATA-12, SEC-08; CONSENT-02/04 |
| `AC-39` | Giữ request ở barrier trước dispatch, revoke rồi thả barrier → không gọi inference. Thử thứ tự dispatch trước revoke → chỉ request đã in-flight có thể hoàn tất; mọi admission sau revoke bị chặn. Từ/bài làm/điểm/feedback cũ không bị xóa. | SEC-09; CONSENT-05/06 |
| `AC-40` | Grant stale từ tab khác hoặc response mutation bị mất → không bật AI nhầm; đối soát GET/idempotency lấy trạng thái mới nhất. Policy thiếu/đổi version chặn grant/dispatch nhưng không chặn revoke; thao tác bằng bàn phím và trạng thái lỗi/unknown có nhãn rõ. | SEC-08/09; CONSENT-03/04/08/09/10 |

## 17. Open questions

Các nhóm câu hỏi dưới đây giữ ID tương ứng Q01–Q14 của interview. Chúng được giữ nguyên để truy nguyên; không còn là product blockers sau overlay/ADR-0004. Không cần tự mở rộng thành tính năng nếu câu hỏi chỉ nhằm xác định ranh giới v1.

### `OQ-01` — Provider cloud, quota, billing và policy dữ liệu (kiến trúc đã giải quyết)

**Đã chốt:** app/backend gọi Antigravity Tools / Antigravity-Manager **v4.8.4 theo xác nhận của owner**, HTTP loopback + key với ranh giới tin cậy Windows (ADR-0002); cơ chế xin phép/lưu/rút consent và giữ học cục bộ (ADR-0003). Proxy quản lý token/session Google; app không gọi CLI hay đọc token. Mục tiêu model vẫn là Gemini. Owner xác nhận **không cấm paid fallback về nguyên tắc**; điều đó chưa chọn route/provider, chưa xác nhận entitlement hay cấp phép fallback tự động. Smoke test chỉ xác nhận endpoint/response cơ bản. **Còn mở:** quyền sử dụng/quota, model mapping/fallback và model production được phép, route/billing mode cụ thể, policy dữ liệu/retention/region và phát hiện lỗi quota. Chỉ fallback được ghi rõ trong READY policy + disclosure + consent mới được dispatch; policy chưa đầy đủ phải chặn grant/AI. Cấu hình auth thật còn kiểm chứng trước release. Local bridge không chứng minh request miễn phí hoặc dữ liệu không rời máy.

### `OQ-02` — Thuật toán và quy đổi SRS

Chọn thuật toán, các mức đánh giá, thang điểm viết câu và quy tắc chuyển điểm quiz sang SRS như thế nào? Quy tắc “kết quả yếu nhất” được so sánh ra sao giữa câu đúng/sai và điểm viết câu? Cập nhật SRS khi quiz có thẻ chưa đến hạn hoặc được làm nhiều lần thế nào? Một dạng từ có tất cả nghĩa học thuật trên cùng thẻ: khi chỉ nhớ được một phần, hướng dẫn tự đánh giá mức nhớ ra sao?

Thời điểm nào bài đã đủ điểm để cập nhật SRS, và làm thế nào để tiếp tục/nộp lại một bài không tính trùng kết quả? FR-ASM-08 đã chốt tác động lên SRS, chưa chốt cơ chế này.

### `OQ-03` — Đáp án và chấm bài

Biến thể Anh–Mỹ, dạng biến đổi của từ, dấu câu, nhiều đáp án đúng và chuẩn hóa khoảng trắng được xử lý ra sao? Tiêu chí viết câu và thang điểm là gì? Người dùng có thể sửa điểm sau khi hoàn tất không?

### `OQ-04` — Cấu hình và vòng đời quiz

Số câu tối thiểu/tối đa, tổng số câu bằng 0, nguồn từ không đủ, đề AI sai cấu trúc/thiếu câu, chọn nhiều ngày và bài đang làm khi dữ liệu từ đổi được xử lý thế nào? Quiz có cần snapshot bất biến theo nội dung tại thời điểm tạo không?

### `OQ-05` — Định danh dạng từ

Cùng cách viết khác từ loại được định danh thế nào? Word family giao nhau hợp nhất ra sao? Lưu lại cùng dạng ở ngày mới nhưng AI trả nghĩa/ví dụ khác áp dụng giữ lịch như lưu trùng hay reset như sửa nội dung? Thêm lại dạng từ đã xóa có khôi phục SRS cũ không? Thay IPA, từ loại hoặc nội dung khác ngoài nghĩa/ví dụ có reset thẻ không?

### `OQ-06` — Cambridge, IPA và âm thanh

Nhãn chưa xác minh áp dụng ở mức trường, dạng từ hay toàn bộ kết quả? Khi thiếu IPA Mỹ hoặc không tìm được Cambridge link, phần thiếu có cho phép lưu không và được biểu diễn thế nào? Việc cho lưu nghĩa/từ loại chưa xác minh không tự giải quyết trường hợp thiếu các trường này. Nguồn audio, giọng đọc, cách gọi audio và lỗi audio được xử lý ra sao?

Danh sách/rubric đối chiếu nào xác định word family và “tất cả nghĩa học thuật thường dùng” là đầy đủ và đúng? Đây là phương pháp nghiệm thu yêu cầu nội dung đã có, không bổ sung loại nội dung mới.

### `OQ-07` — Streak và thẻ bị tạm ngừng

Thẻ bị loại vì file lỗi có được loại khỏi mẫu số due cards không? “Hoàn thành” khi thẻ lặp lại trong ngày hoặc quiz cập nhật SRS được tính ra sao? Xác nhận timezone và lịch sử streak.

### `OQ-08` — Đồng bộ và bản lưu sau cùng

Bản lưu sau cùng được xác định bằng timestamp/version nào? Xử lý cùng timestamp, file ghi dở, nhiều file có cùng dạng từ và việc app cập nhật một hay nhiều file ra sao?

Mức trễ đồng bộ chấp nhận được là bao nhiêu; có cần thao tác xóa/đổi tên từ hoặc file trực tiếp trong app không? Hiện chỉ hành vi sau khi nguồn bị xóa đã được chốt, chưa mặc định phải xây thêm giao diện xóa.

### `OQ-09` — Tự lưu và vận hành Windows

Tần suất/điểm tự lưu, `draftRevision`, flush-on-blur/submit, chỉ báo đã lưu, bảo toàn khi mất điện, cài biểu tượng, single-instance mutex, xử lý mở trùng, bootstrap/session TTL, đóng tiến trình và phục hồi sau crash là gì? Khi backend không khởi động, launcher/native fallback nào hiển thị trạng thái thay cho route `/status`?

### `OQ-10` — Chi tiết accessibility và Sci-Link

Nguồn Sci-Link nào dùng để nghiệm thu? Có cần phóng to chữ không và nếu có thì tới mức nào? Tiêu chí tương phản, focus keyboard và ngôn ngữ UI là gì? Hỗ trợ trình đọc màn hình toàn diện chưa được yêu cầu, không dùng việc cần nút loa để suy ra yêu cầu này.

### `OQ-11` — Điều kiện hiệu năng

Máy Windows, SQLite build, fixture 100.000 dạng từ, trường nghĩa Việt, normalization exact/folded, n-gram/index strategy, loại truy vấn và cách đo giới hạn 1 giây là gì? Mốc 2 phút tính từ thao tác nào? Có timeout/cancellation cho tạo quiz/nhận xét AI và trần quy mô lớn hơn 100.000 không?

### `OQ-12` — Dashboard và success measurement

Công thức, kỳ thống kê và mẫu số cho từng chỉ số là gì? Dữ liệu reset, nguồn lỗi và lịch sử xóa được phản ánh thế nào? Theo dõi mục tiêu 6 ngày/tuần trong bao lâu, với ngưỡng thành công nào?

### `OQ-13` — Lưu trữ, bảo vệ dữ liệu và kỹ thuật

Chọn runtime, framework, package manager và mô hình lưu trữ nào sau khi kiểm chứng? SRS/lịch sử/bài làm được lưu ở đâu để người dùng tự sao lưu? Xác định giới hạn file, process, single-instance, secret-store packaging và dữ liệu cục bộ thế nào? Không có cơ sở để chốt Python/FastAPI, React/Vite, SQLite hay SM-2 từ interview này; architecture baseline hiện tại vẫn là đề xuất, không phải quyết định sản phẩm đã đóng.

**Đã trả lời riêng phần bridge:** ADR-0002 chốt HTTP/API-key với Antigravity v4.8.4, không phải tích hợp CLI hoặc xác thực process bằng IPC. Các phần launcher/session, secret-store packaging, runtime, lưu trữ và recovery còn mở; không yêu cầu owner phê duyệt lại bridge boundary này.

Đặc tả cũ gọi database là bản chiếu có thể dựng lại, nhưng đồng thời lưu lịch sử học/quiz không có đủ trong Markdown. Thiết kế mới phải phân biệt dữ liệu tái tạo được và dữ liệu bền vững; không mang thao tác xóa toàn bộ database để rebuild sang v1 như một chức năng đã được phê duyệt.

### `OQ-14` — Tương thích Markdown hiện có

Đọc ngược file cũ và bảo toàn các trường ngữ cảnh hiện có ra sao khi v1 không thu thập câu gốc mới? Có thay đổi định dạng không? Ngày mặc định/chọn ngày qua nửa đêm, tìm kiếm không dấu, dung sai lỗi gõ và nghĩa tương đương có được hỗ trợ không?

### 17.0. Owner-authorized v1 decision overlay

The owner authorized conservative defaults to close the previous review blockers. These decisions are normative for v1 and are recorded in [ADR-0004](adr/0004-v1-product-policy-and-operational-baseline.md); the question text above is retained as interview history only. `OQ-01`–`OQ-14` no longer block planning.

| OQ | Resolved v1 decision |
|---|---|
| `OQ-01` | Antigravity v4.8.4; Gemini `gemini-3.8-flash-high` only; automatic paid fallback disabled by default but a future policy may enable an explicitly disclosed route. Provider retention/region are disclosed as provider-controlled with no guarantee; missing policy/entitlement/quota fails closed. |
| `OQ-02` | Five-box SRS; HARD preserves box (NEW→1), GOOD+1/EASY+2 capped5; local-midnight due at intervals 1/3/7/14/30 calendar days. ADR-0005 has exact fixtures and weakest mapping. |
| `OQ-03` | NFC + trim/collapse ASCII whitespace/case-fold cloze; strict spelling/punctuation. writing-rubric-v1 self-score0–4, null pending blocks submit; AI never overwrites it. |
| `OQ-04` | Quiz total5–30, each0–20 with sufficient distinct forms/type; 1/1/1 rejected. Immutable snapshot, terminal result read and one-time submit/SRS receipt in ADR-0005. |
| `OQ-05` | Identity is normalized lemma + POS + family; date-only saves reuse a card; meaning/example changes reset it; re-add reuses historical card. |
| `OQ-06` | Per-field verification; missing IPA/link can save as `MISSING`; audio uses local browser `SpeechSynthesis` when available and otherwise disables without network. Content quality uses a fixed human-reviewed fixture. |
| `OQ-07` | `Asia/Bangkok`; due day completes when all eligible due cards are done; no-due day completes after one new-card review or terminal quiz; invalid sources are excluded. |
| `OQ-08` | Revision/ETag conflict wins over silent LWW; durable source journal and startup reconciliation use hash/state rules in ADR-0004. |
| `OQ-09` | Windows named mutex, 10-second readiness wait, 60-second one-time bootstrap, non-sliding8h session invalidated by shutdown/restart, duplicate-launch focus, 500ms autosave plus blur/submit flush; acknowledged drafts persist. |
| `OQ-10` | WCAG 2.2 AA target with 200% zoom, contrast/focus/keyboard matrix and Sci-Link as visual reference, not a runtime dependency. |
| `OQ-11` | Named Windows 11/Python 3.12/SQLite fixture: search p95 ≤1s at 100k forms; lookup p95 ≤120s; quiz ≤60s; feedback ≤30s, all cancellable. |
| `OQ-12` | Dashboard formulas and four-week 6-days/week success measurement are fixed in ADR-0004; no-attempt accuracy is null, not zero. |
| `OQ-13` | React/TypeScript/Vite + Python 3.12/FastAPI + SQLite/SQLAlchemy/Alembic; current-user protected secret store; no in-app backup/sync; user-managed closed-directory copy. |
| `OQ-14` | Preserve legacy paths/unknown fields/round-trip; `Asia/Bangkok` date authority; NFC/case-fold/accent-fold search; no typo tolerance or semantic-equivalence matching. |

These decisions intentionally accept provider-controlled retention/region, local impersonation risk, user-managed backup and a simple non-adaptive SRS. They do not authorize application code or runtime verification to be skipped.

### 17.1. Readiness check: API, UI và task design

**Kết luận:** ADR-0004 closes the product-policy questions; the spec/API/UI are ready for planning. Generated-contract, runtime, benchmark and accessibility evidence remain implementation gates.

| Đầu ra tiếp theo | Đã có cơ sở | Còn chặn việc chốt |
|---|---|---|
| API | Các thao tác nghiệp vụ, quan hệ dữ liệu, trách nhiệm capability, local bridge contract, prompt/JSON feedback contract và hành vi lỗi/offline | ADR-0004 defaults; implementation must verify generated schema, profile and fixtures |
| UI | J1–J6, cấu trúc tra/lưu/ôn/quiz, trạng thái loading/empty/error/success, keyboard/WCAG target | ADR-0004 defaults; implementation must run browser/manual matrix |
| Tasks | Capability IDs, dependency direction đề xuất, FR và các AC có thể chuyển thành nhóm kiểm chứng | Có thể lập kế hoạch; `CONSTRAINTS.md` và runtime manifests là planning/implementation inputs |

**Kiểm tra nhất quán nguồn:** ADR-0004 là authority cho các OQ đã từng mở; các câu hỏi cũ giữ lại để truy nguyên interview. Nếu tài liệu cũ còn nói “OQ chưa chốt”, overlay/ADR-0004 thắng và phải được đồng bộ khi tạo task.

**Giới hạn kỹ thuật của tài liệu:** T001/T002/T058 và T003–T005 đã có foundation code/toolchain evidence; business contracts vẫn chờ implementation. Commands/versions thực tế theo thẻ task/toolchain locks, quality bar theo CONSTRAINTS. ADR-0004/0005 cung cấp policy/oracles; generated schema, rule fixtures, source/crash tests, Windows journeys, keyboard và benchmark do task owner kiểm chứng. T013 chỉ xác nhận document conformance.

**Review-applied implementation gates:** ADR-0004 supplies the owner-authorized answers for OQ-01–OQ-14. Before implementation, create `CONSTRAINTS.md`, pin runtime/lockfiles and verify the generated API, Windows profile, journal recovery, SRS/quiz fixtures, benchmark, browser accessibility and telemetry/security tests. These are evidence gates, not unanswered product policy.

Phần bridge authentication trong danh sách trên đã được quyết định bằng ADR-0002; còn kiểm chứng khi triển khai, không còn là câu hỏi sản phẩm chưa trả lời. Các gate khác giữ nguyên.

## 18. Assumptions

Các giả định sau không phải quyết định đã chốt; nếu sai phải cập nhật spec trước khi triển khai phần liên quan.

| ID | Giả định | Nguồn và điểm cần xác nhận |
|---|---|---|
| A1 | Ngày ghi chú và ngày học dùng `Asia/Bangkok` | Chốt trong ADR-0004. |
| A2 | Luyện IELTS Academic ở mức từ vựng và dùng từ trong câu học thuật | Các dạng bài đã chọn; chưa yêu cầu mô phỏng toàn bộ kỳ thi. |
| A3 | Các file Markdown hiện có cần tiếp tục đọc được | Round-trip/path/unknown-field policy chốt trong ADR-0004. |

Local bridge and OpenAI-compatible chat request have a compatibility smoke result; entitlement/provider terms remain an explicit disclosed limitation in ADR-0004. Framework/runtime/database/SRS defaults are recorded in ADR-0004 and must be pinned before implementation.

SPEC_STATUS: READY_FOR_PLANNING
