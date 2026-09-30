# Product discovery 001 — Ứng dụng học từ vựng cá nhân

- **Ngày hoàn tất:** 29/09/2026, múi giờ ghi tài liệu `Asia/Bangkok`.
- **Trạng thái:** Interview đã được người dùng cho phép hoàn tất bằng `FINALIZE INTERVIEW`.
- **Mục đích tài liệu:** Ghi lại nhu cầu, phạm vi và các quyết định sản phẩm để làm đầu vào viết spec; chưa phải đặc tả triển khai.
- **Mức hiểu tại thời điểm tổng kết:** Khoảng 95% về mục tiêu và phạm vi. Những điểm chưa chốt được giữ trong mục **Câu hỏi còn mở**; việc hoàn tất interview không biến chúng hoặc các giả định thành quyết định đã chốt.

## 1. Nguồn và cách đọc tài liệu

Nguồn quyết định chính là câu trả lời của người dùng trong interview. Các tài liệu đã đọc:

- [Project context](../project-context.md).
- [Vocabulary platform spec hiện có](../development/spec/vocabulary-platform-spec.md).
- [Quy ước Markdown hiện có](../vocabularies/README.md), đối chiếu khi ghi tài liệu cuối phiên.

`docs/spec-draft.md` không tồn tại tại thời điểm kiểm tra. Đặc tả hiện có được dùng làm tham chiếu, không mặc định mọi nội dung trong đó là yêu cầu đã được xác nhận lại. Những điểm khác biệt quan trọng được ghi ở mục 11. Interview không sửa đặc tả cũ, dữ liệu từ vựng hoặc triển khai mã ứng dụng.

Trong tài liệu này, **dạng từ** chỉ một thành phần trong word family theo từ loại. Quy tắc định danh những trường hợp cùng cách viết nhưng khác từ loại còn mở ở Q05.

## 2. Mục tiêu

Người dùng muốn tra từ khi đọc báo khoa học và học IELTS Academic, lưu nội dung đủ để học lại, tìm được từ ngay cả khi chỉ nhớ một phần nghĩa tiếng Việt, và duy trì ôn tập đều đặn.

Vấn đề hiện tại là khó tìm lại từ, khó tổ chức việc ôn và thiếu dashboard ghi nhận quá trình học. Dashboard phục vụ việc biết cần ôn gì và theo dõi kết quả. Số từ đã thêm là thông tin theo dõi phụ, không phải mục tiêu chính.

Kết quả mong muốn:

- Tra từ thuận tiện trong lúc đọc; không phải tự chạy CLI rồi import kết quả cho mỗi lần tra.
- Xây dựng kho word family có nghĩa học thuật, phát âm và ví dụ để học lại.
- SRS giúp xác định những thẻ cần ôn, kết hợp khả năng chọn theo ngày ghi chú.
- Có bài kiểm tra nhớ từ và vận dụng từ trong ngữ cảnh IELTS Academic ngay trong v1.
- Duy trì học ít nhất **6 ngày mỗi tuần**; không đặt giới hạn thời lượng học mỗi ngày.

Khoảng thời gian dùng thử và cách đánh giá mục tiêu 6 ngày/tuần chưa được chốt; xem Q12.

## 3. Người dùng và quyền truy cập

- Chỉ phục vụ chính người dùng này, trên một máy cá nhân.
- Nền tảng mục tiêu là **Windows**, theo hướng **local-first**.
- Bấm biểu tượng để khởi động ứng dụng và mở trong **tab trình duyệt**.
- Không cần tài khoản, đăng nhập hoặc mật khẩu riêng của app.
- Không yêu cầu truy cập từ điện thoại hoặc thiết bị khác trong mạng nội bộ.

Yêu cầu không đăng nhập xác định trải nghiệm truy cập của sản phẩm; các cơ chế bảo vệ xử lý file và gọi CLI vẫn thuộc phần thiết kế kỹ thuật cần làm rõ ở Q13.

## 4. Phạm vi v1 và non-goals

### 4.1. Trong phạm vi

- Tra cứu tự động từ một từ nhập vào; xem kết quả trước khi quyết định lưu để ôn.
- Word family theo từ loại, tập trung vào **tất cả nghĩa thường dùng trong ngữ cảnh học thuật**.
- Nghĩa, câu ví dụ tiếng Anh và bản dịch tiếng Việt theo từng dạng từ; IPA giọng Mỹ và liên kết Cambridge cho mỗi dạng.
- Nút loa cạnh từ tiếng Anh để nghe phát âm khi có mạng.
- Lưu Markdown theo ngày; đọc/sửa bằng editor bên ngoài và chỉnh sửa trực tiếp trong app, có đồng bộ thay đổi.
- Tìm lại từ qua một phần nghĩa tiếng Việt.
- Flashcard, lịch SRS riêng cho từng dạng từ, lọc theo ngày ghi chú.
- Bài kiểm tra gồm trắc nghiệm, điền từ và tự viết câu; tùy chọn số câu từng dạng.
- Tự lưu câu trả lời của bài kiểm tra đang làm để tiếp tục sau.
- Dashboard về thẻ đến hạn, streak và kết quả học; giữ lịch sử đã học.
- Dùng Google AI Pro và Antigravity CLI sẵn có, tự động trong app và không phát sinh phí API.

### 4.2. Ngoài phạm vi hoặc chưa được yêu cầu trong v1

- Nhiều người dùng, tài khoản/đăng nhập, truy cập từ thiết bị khác.
- Chạy CLI và import kết quả thủ công như luồng sử dụng thường ngày.
- API trả phí phát sinh ngoài gói/CLI sẵn có.
- Lưu câu gốc, tên bài đọc hoặc đường dẫn bài đọc nơi gặp từ.
- Mở rộng nội dung học sang collocations, synonyms/antonyms và nghĩa ít gặp.
- Bắt buộc gõ câu trả lời cho mọi flashcard.
- Chức năng sao lưu trong app; người dùng tự quản lý sao lưu.
- Hàng đợi giữ yêu cầu tra cứu thất bại để xử lý sau.
- Phát âm khi offline; hỗ trợ trình đọc màn hình toàn diện chưa được yêu cầu.
- Đóng gói giao diện thành cửa sổ desktop riêng; lựa chọn đã chốt là tab trình duyệt.

## 5. User journeys

### J01 — Mở ứng dụng và chọn việc cần học

1. Người dùng bấm biểu tượng trên Windows.
2. App khởi động và mở tab trình duyệt, không yêu cầu đăng nhập.
3. Người dùng xem thẻ đến hạn, streak và các chỉ số học tách riêng trên dashboard.
4. Người dùng bắt đầu ôn theo SRS hoặc chọn ngày ghi chú để ôn/kiểm tra.

### J02 — Tra một từ và lưu để ôn

1. Khi gặp từ lúc đọc, người dùng nhập từ vào app; không cần nhập câu gốc hoặc thông tin bài đọc.
2. App tự xử lý yêu cầu qua tích hợp AI dự kiến dùng Antigravity CLI và gói Google AI Pro hiện có.
3. Người dùng xem word family, nghĩa học thuật, ví dụ/bản dịch, IPA Mỹ và liên kết Cambridge.
4. Nghĩa hoặc từ loại chưa đối chiếu được vẫn có thể hiển thị và lưu, nhưng phải có nhãn **chưa xác minh**.
5. Người dùng có thể nghe phát âm bằng nút loa khi có mạng.
6. Chỉ khi người dùng bấm **Lưu để ôn**, nội dung mới được đưa vào kho học và gắn với ngày ghi chú.
7. Mỗi dạng từ có thẻ riêng. Nếu dạng từ đã tồn tại ở ngày khác, dùng chung thẻ và tiến độ, đồng thời ghi nhận ngày mới.

Thời gian chờ chấp nhận cho từ mới là tối đa 2 phút để có nội dung xem và lưu. Đây là yêu cầu hiệu năng, chưa phải quyết định về cơ chế timeout. Nếu mất mạng hoặc CLI không trả kết quả, app báo chưa tra được để người dùng tự thử lại; không giữ yêu cầu chờ xử lý.

### J03 — Tìm và sửa từ đã lưu

1. Người dùng nhập phần nghĩa tiếng Việt còn nhớ để tìm từ.
2. Người dùng mở nội dung từ và xem các dạng liên quan.
3. Khi phát hiện nội dung sai, người dùng sửa ngay trong app; thay đổi được ghi vào Markdown.
4. Người dùng cũng có thể sửa bằng editor bên ngoài; app cập nhật theo file đã sửa.
5. Nếu hai nơi sửa cùng nội dung trước khi đồng bộ, dùng bản lưu sau cùng.
6. Sửa nghĩa hoặc ví dụ đưa thẻ tương ứng về trạng thái **chưa học**.

### J04 — Ôn flashcard

1. Người dùng bắt đầu từ hàng đợi SRS mặc định hoặc chọn ngày ghi chú.
2. Trong ngày đã chọn, chỉ lấy thẻ đến hạn hoặc chưa học.
3. Mặt trước hiển thị từ tiếng Anh để người dùng tự nhớ nghĩa tiếng Việt.
4. Người dùng lật thẻ rồi tự đánh giá mức nhớ; không bắt buộc nhập đáp án.
5. Đánh giá được dùng để cập nhật lịch SRS của dạng từ đó và ghi nhận hoạt động học.

### J05 — Tạo và làm bài kiểm tra

1. Người dùng chọn ngày ghi chú và số câu cho từng dạng: trắc nghiệm, điền từ, tự viết câu.
2. Nguồn đề là **tất cả từ của ngày đã chọn**, kể cả những từ chưa đến hạn SRS.
3. App tạo đề tự động bằng AI. Đề bằng tiếng Anh, phần giải thích đáp án bằng tiếng Việt.
4. Người dùng làm bài; câu trả lời được tự lưu để có thể đóng tab/tắt app rồi tiếp tục sau.
5. Trắc nghiệm và điền từ cung cấp kết quả đúng/sai; điền từ yêu cầu đúng chính tả, chỉ bỏ qua khác biệt hoa/thường và khoảng trắng thừa.
6. Với tự viết câu, người dùng tự chấm theo tiêu chí; AI nhận xét hỗ trợ, không quyết định điểm cuối cùng.
7. Hệ thống tự quy đổi kết quả bài kiểm tra để cập nhật SRS. Nếu một dạng từ có nhiều kết quả trong cùng bài, lấy kết quả yếu nhất.
8. Kết quả được lưu vào lịch sử và các chỉ số tương ứng trên dashboard.

Thang điểm, công thức quy đổi, thời điểm hoàn tất bài có phần tự chấm và việc cập nhật SRS sau khi tiếp tục một bài dở chưa chốt; xem Q02–Q04.

### J06 — Tiếp tục học khi offline hoặc dữ liệu có lỗi

- Khi mất mạng, vẫn tìm từ đã lưu, ôn flashcard, xem dashboard và làm bài kiểm tra đã tạo sẵn.
- Tra từ mới, tạo đề, nhận xét AI và nút loa cần mạng.
- File Markdown sai định dạng bị tạm ngừng dùng làm nguồn học đến khi sửa hợp lệ.
- Một thẻ vẫn được ôn nếu còn ít nhất một nguồn Markdown khác hợp lệ.
- Khi một dạng từ bị xóa khỏi tất cả file, ngừng đưa vào ôn nhưng giữ lịch sử và kết quả cũ.

## 6. Dữ liệu cần lưu

Đây là nhu cầu dữ liệu ở mức sản phẩm, không phải schema database đã chọn.

| Nhóm dữ liệu | Nội dung cần lưu | Lý do |
|---|---|---|
| Từ và word family | Dạng từ, từ loại, quan hệ trong word family, nghĩa tiếng Việt thường dùng trong học thuật | Tra cứu và ôn riêng từng dạng |
| Ví dụ | Câu ví dụ tiếng Anh và bản dịch tiếng Việt theo từng dạng | Hiểu cách dùng khi học lại |
| Phát âm và đối chiếu | IPA Mỹ, liên kết Cambridge, trạng thái chưa xác minh khi cần | Tra phát âm và nhận biết mức độ kiểm chứng |
| Ngày ghi chú và file | Liên hệ giữa dạng từ, các ngày đã lưu và những file Markdown chứa nội dung | Lọc theo ngày, dùng chung thẻ, xác định nguồn còn hợp lệ |
| Trạng thái nguồn | File đọc được hoặc đang lỗi, sự hiện diện của dạng từ trong các nguồn hợp lệ | Loại nguồn lỗi và ngừng ôn khi không còn nguồn |
| Thẻ và tiến độ | Một thẻ/lịch SRS cho từng dạng từ, trạng thái chưa học/đã học, thời điểm đến hạn, đánh giá học | Xây dựng hàng đợi ôn và cập nhật tiến độ |
| Lịch sử học | Hoạt động ôn và kết quả theo thời gian | Dashboard, streak và giữ lại những gì từng học |
| Bài kiểm tra | Ngày nguồn, số câu từng dạng, nội dung đề, đáp án/giải thích và tiêu chí viết câu | Làm bài, đánh giá và sử dụng đề đã tạo khi offline |
| Bài làm | Câu trả lời đang dở, kết quả, điểm tự chấm viết câu và nhận xét AI khi có | Tiếp tục bài sau gián đoạn và xem kết quả cũ |

Nội dung từ vựng phải được lưu thành Markdown theo ngày và chỉnh sửa được từ hai phía. Vị trí/công nghệ lưu lịch SRS, bài làm, lịch sử và các dữ liệu vận hành khác chưa được chốt. Không mặc định các dữ liệu học có thể dựng lại chỉ từ Markdown; xem Q13.

Không có nhu cầu lưu câu gốc hoặc nguồn bài đọc mới. Cách tương thích với những trường ngữ cảnh đã có trong file cũ còn ở Q14. Cơ chế phát âm chưa được chọn, nên tài liệu không mặc định phải lưu file âm thanh.

## 7. Business rules

| ID | Quy tắc đã chốt |
|---|---|
| BR01 | Tra cứu không tự thêm từ vào bộ học; người dùng phải bấm **Lưu để ôn**. |
| BR02 | Phạm vi nội dung là word family theo từ loại và các nghĩa thường dùng trong ngữ cảnh học thuật. |
| BR03 | Nội dung chưa đối chiếu được vẫn được lưu để học, với nhãn **chưa xác minh**. |
| BR04 | Mỗi dạng từ có thẻ và lịch SRS riêng; lưu lại ở nhiều ngày dùng chung thẻ và giữ tiến độ. |
| BR05 | SRS là mặc định; lọc flashcard theo ngày chỉ lấy thẻ đến hạn hoặc chưa học. |
| BR06 | Chiều flashcard mặc định là tiếng Anh → nhớ nghĩa tiếng Việt; lật rồi tự đánh giá. |
| BR07 | Bài kiểm tra lấy tất cả từ của ngày chọn, không áp dụng bộ lọc đến hạn như flashcard. |
| BR08 | Người dùng chọn số câu cho từng dạng bài; đề tiếng Anh và giải thích tiếng Việt. |
| BR09 | Điểm viết câu do người dùng quyết định theo tiêu chí, có AI nhận xét hỗ trợ. |
| BR10 | Điền từ sai chính tả tính sai; không phân biệt hoa/thường và bỏ qua khoảng trắng thừa. Các biến thể đáp án khác chưa chốt ở Q03. |
| BR11 | Kết quả kiểm tra tự động cập nhật SRS; kết quả yếu nhất của cùng dạng từ trong một bài quyết định mức quy đổi. |
| BR12 | Bài đang làm tự lưu câu trả lời để tiếp tục sau khi đóng tab hoặc tắt app. |
| BR13 | Dashboard tách kết quả tự đánh giá flashcard, độ chính xác trắc nghiệm/điền từ và điểm tự chấm viết câu; số từ đã thêm là thông tin phụ. |
| BR14 | Ngày có thẻ đến hạn chỉ đạt streak khi hoàn thành toàn bộ thẻ đến hạn trong ngày. |
| BR15 | Ngày không có thẻ đến hạn chỉ đạt streak khi học ít nhất một thẻ mới hoặc hoàn tất một bài kiểm tra. |
| BR16 | Sửa nghĩa hoặc ví dụ đưa thẻ tương ứng về trạng thái chưa học. |
| BR17 | Xung đột sửa cùng nội dung trong app và editor được giải quyết bằng bản lưu sau cùng. |
| BR18 | File Markdown lỗi bị tạm ngừng sử dụng; thẻ còn nguồn hợp lệ khác vẫn được ôn. |
| BR19 | Xóa dạng từ khỏi mọi file thì ngừng ôn, nhưng không xóa lịch sử và kết quả cũ. |
| BR20 | Tra cứu AI thất bại thì báo lỗi để người dùng tự thử lại; không giữ hàng đợi yêu cầu thất bại. |
| BR21 | Chỉ dữ liệu liên quan đến tác vụ AI hiện tại được gửi ra ngoài; lịch sử học và dữ liệu không liên quan giữ trên máy. |
| BR22 | Không cần tài khoản/mật khẩu riêng và không có chức năng sao lưu trong app ở v1. |

## 8. Edge cases

| Tình huống | Xử lý đã chốt hoặc trạng thái còn mở |
|---|---|
| Một từ có nhiều nghĩa học thuật thường dùng | Lưu các nghĩa đó, không bắt người dùng chọn riêng một nghĩa trước khi lưu. |
| Nghĩa hoặc từ loại chưa xác minh được | Vẫn cho lưu, có nhãn chưa xác minh. |
| Chưa lấy được IPA hoặc chưa tìm thấy mục Cambridge | IPA Mỹ/link Cambridge là yêu cầu nội dung; chính sách khi thiếu một phần chưa chốt đầy đủ, xem Q06. |
| Cùng một dạng từ được lưu ở ngày khác | Dùng chung thẻ/lịch SRS, giữ các ngày ghi chú để lọc. |
| Trắc nghiệm đúng nhưng điền từ sai cho cùng từ trong một bài | Ưu tiên kết quả yếu nhất khi cập nhật SRS. |
| Điền từ mắc lỗi chính tả nhỏ | Vẫn tính sai và ảnh hưởng SRS. |
| Đóng tab/tắt app khi bài chưa nộp | Lưu câu trả lời để mở lại làm tiếp. Chi tiết thời điểm tự lưu còn ở Q09. |
| Ngày không có thẻ đến hạn | Cần ít nhất một thẻ mới đã học hoặc một bài kiểm tra hoàn tất để tính streak. |
| Mất mạng hoặc CLI không trả kết quả tra từ | Báo lỗi, người dùng tự thử lại; không xếp hàng xử lý sau. |
| Mất mạng khi học nội dung đã có | Các luồng dùng dữ liệu đã lưu tiếp tục hoạt động; AI và phát âm cần mạng. |
| Markdown sai định dạng | Loại nguồn lỗi khỏi sử dụng đến khi sửa hợp lệ; không dùng bản cũ của chính nguồn lỗi để tiếp tục ôn. |
| Từ trong file lỗi vẫn có ở file hợp lệ khác | Tiếp tục ôn từ nguồn hợp lệ. |
| Từ bị xóa khỏi toàn bộ file | Ngừng ôn, giữ lịch sử và kết quả. Việc thêm lại về sau chưa chốt ở Q05. |
| Sửa nghĩa/ví dụ của thẻ đã học | Thẻ tương ứng trở về chưa học. |
| Sửa cùng nội dung trong app và editor trước khi đồng bộ | Dùng bản lưu sau cùng. Cách xác định thứ tự và xung đột giữa nhiều file ngày còn ở Q08. |
| Yêu cầu số câu vượt khả năng của nguồn từ, hoặc tổng số câu bằng 0 | Chưa chốt, xem Q04. |
| Từ gốc bị sửa/xóa/tạm ngừng trong lúc bài đang làm | Chưa chốt cách xử lý bài dở và ảnh hưởng SRS, xem Q04. |
| Một số thẻ đến hạn bị tạm ngừng do nguồn lỗi | Chưa chốt ảnh hưởng đến điều kiện streak, xem Q07. |

## 9. Yêu cầu phi chức năng

### 9.1. Accessibility và thiết kế

- Giao diện bám theo **Sci-Link**; interview không chọn một hướng thiết kế thay thế.
- Toàn bộ app phải dùng được bằng bàn phím: tra cứu, lưu/sửa, điều hướng, bộ lọc, ôn flashcard, làm bài và cài đặt nếu có.
- Chữ phải dễ đọc, tương phản rõ với nền.
- Trạng thái cần có nhãn hoặc biểu tượng để không chỉ phân biệt bằng màu.
- Nút loa cạnh từ tiếng Anh phục vụ nghe phát âm. Đây là nhu cầu đã xác nhận; chưa yêu cầu hỗ trợ trình đọc màn hình toàn diện.
- Phóng to chữ và mức định lượng về tương phản chưa chốt; xem Q10.

### 9.2. Security và riêng tư

- Phạm vi truy cập là một người dùng trên một máy; không có luồng tài khoản/đăng nhập.
- Dữ liệu gửi tới dịch vụ AI qua CLI chỉ phục vụ tác vụ hiện tại: từ đang tra, nhóm từ được chọn để tạo đề, hoặc câu viết cần nhận xét.
- Không gửi lịch sử học và dữ liệu không liên quan ra ngoài.
- Sử dụng gói/CLI hiện có và không phát sinh phí API là ràng buộc bắt buộc, không phải tùy chọn có thể tự thay thế bằng API trả phí.
- Khả năng tự động hóa và cơ chế xác thực của tích hợp Antigravity CLI chưa được xác minh trong interview; xem Q01.

### 9.3. Performance

| Hoạt động | Mục tiêu đã chốt | Điều kiện còn cần xác định |
|---|---|---|
| Tra một từ mới | Tối đa **2 phút** để có đủ nội dung xem và lưu | Phạm vi word family, mạng/quota CLI, cách xử lý vượt ngưỡng |
| Tìm từ đã lưu qua nghĩa tiếng Việt | Hiển thị kết quả trong tối đa **1 giây** với **100.000 dạng từ** trên máy người dùng | Cấu hình máy, dữ liệu thử, cách đo và tình trạng cache |
| Quy mô kho | Vài chục nghìn dạng từ hoặc lớn hơn; 100.000 là mốc kiểm thử đã đồng ý | Chưa chốt trần dữ liệu hoặc cam kết cho mọi quy mô lớn hơn |

Đây là các tiêu chí cần kiểm chứng khi triển khai, chưa có benchmark hoặc bằng chứng đã đạt. Chưa có giới hạn thời gian cho tạo đề/nhận xét AI; xem Q11.

### 9.4. Vận hành và độ bền dữ liệu

- Mở bằng biểu tượng Windows, tự khởi động và mở tab trình duyệt; không yêu cầu chạy lệnh mỗi buổi học.
- Chạy các luồng với dữ liệu đã lưu khi offline; tác vụ AI và phát âm cần mạng.
- Tự lưu bài đang làm, duy trì lịch sử học và giữ kết quả cũ khi từ bị xóa khỏi kho đang dùng.
- Đồng bộ chỉnh sửa từ app và Markdown, dùng bản lưu sau cùng khi xung đột.
- File nguồn lỗi không được tiếp tục cung cấp nội dung học, trừ khi thẻ còn nguồn khác hợp lệ.
- Không có sao lưu trong app; người dùng tự quản lý. Cách bố trí dữ liệu để sao lưu đầy đủ chưa được thiết kế.
- Cách khởi chạy/đóng tiến trình nền, cài CLI và phục hồi sau sự cố còn ở Q09 và Q13.

## 10. Acceptance criteria sơ bộ

Các tiêu chí sau chuyển câu trả lời đã chốt thành tình huống nghiệm thu ban đầu. Đây chưa phải kết quả kiểm thử; những điểm có Q đi kèm cần làm rõ trước khi hoàn thiện spec/test case.

| ID | Tình huống và kết quả mong đợi |
|---|---|
| AC01 | Bấm biểu tượng trên máy Windows mục tiêu thì app khởi động và mở tab trình duyệt, không hỏi tài khoản hoặc mật khẩu app. |
| AC02 | Nhập một từ thì app tự xử lý tra cứu, không yêu cầu người dùng chạy CLI/import thủ công; chưa bấm **Lưu để ôn** thì từ chưa vào bộ học. Khả thi của tích hợp phải được xác minh theo Q01. |
| AC03 | Nội dung học có word family theo từ loại, nghĩa học thuật thường dùng, ví dụ tiếng Anh và bản dịch; mỗi dạng có IPA Mỹ và link Cambridge theo yêu cầu, với trường hợp thiếu được giải quyết ở Q06. |
| AC04 | Khi nghĩa/từ loại chưa đối chiếu được, người dùng vẫn lưu được và nhìn thấy nhãn **chưa xác minh**. |
| AC05 | Khi tra từ thất bại do mạng/CLI, app thông báo lỗi để người dùng thử lại; không giữ yêu cầu chờ chạy sau. |
| AC06 | Một lần tra từ mới đáp ứng mốc tối đa 2 phút theo điều kiện thử sẽ chốt ở Q11. |
| AC07 | Tìm bằng một phần nghĩa tiếng Việt trả kết quả trong tối đa 1 giây trên kho 100.000 dạng từ, theo môi trường/cách đo Q11. |
| AC08 | Một word family có nhiều dạng tạo các thẻ riêng; lưu lại cùng dạng ở ngày khác không tạo lịch SRS độc lập và vẫn liên kết được các ngày. |
| AC09 | Khi lọc ngày để ôn flashcard, chỉ xuất hiện thẻ đến hạn hoặc chưa học của ngày đó; mặt trước là từ tiếng Anh, người dùng lật và tự đánh giá. |
| AC10 | Tạo bài kiểm tra cho ngày đã chọn sử dụng được cả từ chưa đến hạn; người dùng chọn số câu của ba dạng; đề tiếng Anh và giải thích tiếng Việt. Các giới hạn còn ở Q04. |
| AC11 | Điền từ sai chính tả tính sai; cùng đáp án chỉ khác hoa/thường hoặc khoảng trắng thừa được coi tương đương. |
| AC12 | Phần viết câu có tiêu chí để tự chấm; AI nhận xét hỗ trợ, điểm cuối cùng do người dùng quyết định. |
| AC13 | Kết quả bài kiểm tra được tự quy đổi để cập nhật SRS; khi cùng từ có kết quả mạnh/yếu khác nhau, dùng kết quả yếu nhất theo quy tắc sẽ chốt ở Q02. |
| AC14 | Đóng tab/tắt app khi bài chưa nộp rồi mở lại thì tiếp tục được với câu trả lời đã tự lưu; mốc bảo đảm lưu cần xác định ở Q09. |
| AC15 | Dashboard hiển thị riêng kết quả tự đánh giá flashcard, tỷ lệ đúng trắc nghiệm/điền từ và điểm viết câu; có thẻ đến hạn và streak. Công thức thống kê ở Q12. |
| AC16 | Ngày vẫn còn thẻ đến hạn chưa hoàn thành không đạt streak; ngày hoàn thành toàn bộ thẻ đến hạn đạt streak. Các ngoại lệ nguồn lỗi/thẻ học lại trong ngày ở Q07. |
| AC17 | Ngày không có thẻ đến hạn chỉ đạt streak sau ít nhất một thẻ mới đã học hoặc một bài kiểm tra hoàn tất. |
| AC18 | Sửa nội dung trong app được ghi vào Markdown; sửa bằng editor được app cập nhật; khi xung đột dùng bản lưu sau cùng theo cách xác định ở Q08. |
| AC19 | Sửa nghĩa hoặc ví dụ làm thẻ tương ứng trở về trạng thái chưa học. |
| AC20 | File Markdown lỗi bị loại khỏi nguồn đang dùng; từ chỉ có trong file đó ngừng ôn, nhưng từ có nguồn hợp lệ khác vẫn được ôn. |
| AC21 | Xóa một dạng từ khỏi mọi file thì từ ngừng vào ôn; lịch sử và kết quả cũ vẫn còn. |
| AC22 | Khi ngắt mạng, vẫn tìm từ đã lưu, ôn flashcard, xem dashboard và làm đề đã tạo sẵn; không phụ thuộc nhận xét AI hoặc nút loa cho các thao tác cục bộ đó. |
| AC23 | Có nút loa cạnh từ tiếng Anh và nghe được phát âm khi có mạng, theo nguồn âm thanh sẽ chọn ở Q06. |
| AC24 | Dùng bàn phím thực hiện được các luồng chính và phần còn lại của app; giao diện bám Sci-Link, chữ rõ và trạng thái có nhãn/biểu tượng. Cách đánh giá chi tiết ở Q10. |
| AC25 | Mỗi tác vụ AI chỉ gửi nội dung cần thiết đã được cho phép, không gửi lịch sử học hoặc dữ liệu không liên quan; tích hợp không phát sinh phí API. Cơ chế xác minh ở Q01/Q13. |

Mục tiêu **6 ngày/tuần** là tiêu chí kết quả sử dụng cần quan sát trong giai đoạn dùng thử, không phải điều mà riêng một test chức năng có thể bảo đảm đạt.

## 11. Quyết định đã chốt và khác biệt với tài liệu tham chiếu

Các BR ở mục 7 và yêu cầu ở mục 4/9 là những quyết định đã chốt. Bảng dưới ghi lại các lựa chọn quan trọng, lý do/đánh đổi và điểm cần cập nhật khi viết spec mới.

| Quyết định | Lý do hoặc đánh đổi được xác nhận | Quan hệ với tài liệu tham chiếu |
|---|---|---|
| Tự động trong app, dùng Google AI Pro + Antigravity CLI, không phí API phát sinh | Giữ luồng tra cứu liền mạch; người dùng xác nhận đã dùng Antigravity cả giao diện lẫn CLI, nhưng tích hợp chưa được kiểm chứng | Thay luồng Gemini CLI chạy tay/import thủ công mặc định |
| Chỉ lưu khi bấm **Lưu để ôn** | Kiểm soát từ đưa vào lịch học, chấp nhận thêm thao tác lưu | Luồng tra cứu phải tách khỏi quyết định lưu |
| Mỗi dạng từ một thẻ; dùng chung thẻ giữa các ngày | Theo dõi dạng còn yếu, chấp nhận tăng số thẻ nhưng tránh lặp theo ngày | Thay cách gom một thẻ lịch theo lemma trong đặc tả cũ |
| Vận dụng IELTS có ngay trong v1, đủ ba dạng bài | Cần cả nhớ nghĩa/word family và vận dụng bằng câu | Không để toàn bộ phần vận dụng sang phiên bản sau |
| Người dùng tự chấm viết câu; AI hỗ trợ nhận xét | Người dùng kiểm soát điểm cuối cùng | Giữ hướng tự chấm, chưa xác nhận lại thang điểm 0–4 của đặc tả cũ |
| Quiz tự cập nhật SRS theo kết quả yếu nhất | Không để câu đúng bù cho phần chưa nhớ của cùng từ | Bổ sung quy tắc sản phẩm cần đặc tả chi tiết |
| Streak dựa trên hoàn thành toàn bộ thẻ đến hạn | Theo sát lịch ôn, chấp nhận điều kiện khó hơn chỉ có hoạt động học | Thay định nghĩa chỉ cần có review hoặc quiz submit |
| Sửa trong app và ghi lại Markdown | Thuận tiện sửa ngay khi học | Thay non-goal không chỉnh Markdown trong trình duyệt |
| Sửa nghĩa/ví dụ đưa thẻ về chưa học | Đánh giá lại với nội dung mới, kể cả khi thay đổi nhỏ | Không giữ nguyên lịch thẻ chỉ vì đã tồn tại trước đó |
| Xung đột dùng bản lưu sau cùng | Ít thao tác; chấp nhận khả năng mất thay đổi của bản trước | Cần bổ sung quy tắc đồng bộ hai phía |
| Không tiếp tục dùng nguồn Markdown lỗi | Tránh ôn bằng nội dung cũ của nguồn đang lỗi; chấp nhận gián đoạn nhóm từ bị ảnh hưởng | Thay hành vi tiếp tục dùng bản đọc hợp lệ cũ; thẻ có nguồn hợp lệ khác vẫn dùng được |
| Xóa từ khỏi kho đang dùng vẫn giữ lịch sử/kết quả | Dashboard phản ánh việc từng học | Bảo toàn lịch sử; việc lưu/khôi phục cần thiết kế rõ |
| Không cần nguồn bài đọc và sao lưu trong app | Phạm vi v1 tập trung vào tra, học và ôn | Loại nhu cầu nhập câu nguồn/tên bài đọc và nút backup trong đề xuất cũ |
| Có nút loa online; giữ thiết kế Sci-Link và hỗ trợ bàn phím toàn app | Người dùng cần nghe từ, không phải trình đọc màn hình toàn diện | Bổ sung yêu cầu phát âm và làm rõ accessibility |
| Biểu tượng Windows mở tab trình duyệt | Tiện mở hằng ngày; không cần cửa sổ desktop riêng | Cần đặc tả cách cài đặt/khởi động, chưa chọn công nghệ đóng gói |

Trong interview, câu trả lời “đồng ý với guess” về tự động/thủ công từng bị diễn giải là chấp nhận CLI thủ công. Điểm này đã được hỏi lại và thay bằng lựa chọn rõ ràng **tự động trong app**. Không giữ diễn giải cũ như một quyết định có hiệu lực.

## 12. Giả định chưa được xác nhận riêng

| ID | Giả định | Căn cứ và giới hạn |
|---|---|---|
| A01 | Ngày ghi chú và ngày học tính theo `Asia/Bangkok` | Có trong tài liệu hiện có và môi trường làm việc; chưa hỏi riêng về timezone của sản phẩm. |
| A02 | Luyện IELTS trong phạm vi từ vựng và sử dụng từ trong câu học thuật | Các dạng bài đã chọn là trắc nghiệm, điền từ và tự viết câu; chưa yêu cầu mô phỏng đầy đủ kỳ thi. |
| A03 | Các file Markdown hiện có cần tiếp tục đọc được | Người dùng muốn tiếp tục dùng Markdown và đã có dữ liệu; chưa chốt thay đổi hợp đồng định dạng, cách di trú hoặc xử lý trường ngữ cảnh cũ. |

Các giả định này phải giữ nhãn khi chuyển sang spec cho đến khi được xác nhận. Python/FastAPI, React/TypeScript/Vite, SQLite, SM-2 và các lựa chọn thư viện trong đặc tả cũ **chưa được xác nhận lại bởi interview này**.

## 13. Câu hỏi còn mở

Các mục dưới đây chưa có câu trả lời được chốt. Không dùng chúng như yêu cầu đã thống nhất, và không tự chọn một phương án chỉ vì đã xuất hiện trong đặc tả tham chiếu.

### Q01 — Khả thi của tích hợp AI bắt buộc

- Chính xác tên lệnh, phiên bản, chế độ chạy và cơ chế đăng nhập của Antigravity CLI người dùng đang có là gì?
- Có thể tích hợp tự động trong app bằng gói Google AI Pro hiện có mà không phát sinh phí API hay không, và có những điều kiện sử dụng/quota nào áp dụng?
- Nếu tích hợp không đáp ứng đồng thời hai ràng buộc, cần quay lại quyết định với người dùng; không tự đổi sang API trả phí hoặc luồng CLI thủ công.
- Chưa có xác minh kỹ thuật hoặc tài liệu nhà cung cấp trong interview; thông tin người dùng đã dùng CLI không tự chứng minh khả năng nhúng vào app.

### Q02 — Thuật toán và quy đổi SRS

- Chọn thuật toán, các mức đánh giá flashcard và quy tắc tính lịch cụ thể nào?
- Thang điểm/tiêu chí viết câu và cách quy đổi từng loại kết quả sang cùng một mức SRS là gì?
- So sánh “yếu nhất” giữa đúng/sai và điểm viết câu như thế nào?
- Quiz có thể chứa thẻ chưa đến hạn: cần quy tắc cập nhật cho ôn sớm, nhiều câu cùng từ và nhiều lần làm bài.
- Khi bài chưa được tự chấm xong hoặc được tiếp tục từ bản lưu dở, thời điểm nào cập nhật SRS và bảo đảm không tính trùng?

### Q03 — Đáp án hợp lệ và phản hồi chấm bài

- Chính tả phải đúng đã chốt; chưa chốt việc chấp nhận biến thể Anh–Mỹ, dạng biến đổi của từ, dấu câu hoặc nhiều đáp án đúng.
- Thế nào là khoảng trắng thừa được bỏ qua với đáp án gồm nhiều thành phần?
- Tiêu chí viết câu đánh giá những mặt nào và dùng thang điểm nào?
- Hiển thị lời giải/nhận xét ở thời điểm nào; người dùng có được sửa điểm tự chấm sau khi hoàn tất bài không?

### Q04 — Cấu hình, tính hợp lệ và vòng đời bài kiểm tra

- Số câu tối thiểu/tối đa từng dạng, trường hợp tổng bằng 0 hoặc nguồn từ không đủ được xử lý thế nào?
- Mức độ khó và việc chọn một ngày hay nhiều ngày/khoảng ngày có cần cấu hình thêm không?
- Khi AI trả đề thiếu câu, sai cấu trúc hoặc không phù hợp nguồn, app báo lỗi hay cho phép sửa/chạy lại theo cách nào?
- Đề đang làm được xử lý ra sao nếu từ gốc bị sửa, xóa hoặc tạm ngừng do nguồn lỗi?
- Cần chốt quy tắc giữ nội dung đề/đáp án cũ khi dữ liệu từ vựng thay đổi; người dùng đã yêu cầu giữ lịch sử và kết quả nhưng chưa chốt toàn bộ cơ chế snapshot.

### Q05 — Định danh và vòng đời dạng từ

- Cùng cách viết nhưng khác từ loại là một hay nhiều đơn vị thẻ?
- Word family giao nhau được hợp nhất và xác định trùng bằng quy tắc nào?
- Khi lưu lại một dạng từ ở ngày mới nhưng AI trả nội dung khác, áp dụng giữ tiến độ như lần lưu trùng hay reset như sửa nghĩa/ví dụ?
- Khi thêm lại từ đã bị xóa khỏi mọi file, khôi phục lịch SRS cũ hay bắt đầu từ chưa học?
- Đổi từ loại, IPA hoặc nội dung khác ngoài nghĩa/ví dụ có làm thẻ trở về chưa học không?

### Q06 — Cambridge, IPA và âm thanh

- Xử lý thế nào khi chưa tìm được mục Cambridge hoặc IPA Mỹ cho một dạng từ, trong khi vẫn cần giữ rõ trạng thái kiểm chứng?
- Nhãn chưa xác minh áp dụng chi tiết đến từng trường, dạng từ hay toàn bộ kết quả?
- Nguồn phát âm, giọng đọc, cách gọi phát âm và hành vi khi nguồn âm thanh lỗi là gì? IPA Mỹ đã chốt, giọng audio chưa được chọn riêng.

### Q07 — Chi tiết điều kiện streak

- Thẻ tạm ngừng do nguồn lỗi có được loại khỏi số thẻ đến hạn cần hoàn thành không?
- “Hoàn thành” được tính thế nào khi một thẻ cần học lại nhiều lần trong cùng ngày hoặc phát sinh thêm thẻ đến hạn trong ngày?
- Khi bài kiểm tra cập nhật SRS cho thẻ đến hạn, khi nào thẻ được coi là đã hoàn thành trong ngày?
- Xác nhận timezone của ngày học và cách giữ lịch sử streak khi nguồn/nội dung thay đổi.

### Q08 — Đồng bộ Markdown và xung đột

- Xác định “bản lưu sau cùng” bằng cách nào; xử lý hai bản có cùng mốc thời gian hoặc ghi file chưa hoàn tất ra sao?
- Một dạng từ nằm trong nhiều file ngày nhưng có nội dung khác nhau thì bản nào cung cấp nội dung cho thẻ chung?
- Sửa một dạng từ trong app sẽ cập nhật những file nào, và mức trễ đồng bộ chấp nhận được là bao nhiêu?
- Những thao tác xóa/đổi tên từ hoặc file cần được hỗ trợ trực tiếp trong app ở mức nào?

### Q09 — Tự lưu và vận hành Windows

- Tần suất/điểm kích hoạt tự lưu, dấu hiệu báo đã lưu và mức bảo toàn câu trả lời khi mất điện hoặc tiến trình dừng đột ngột là gì?
- Cách cài đặt để biểu tượng khởi động app/CLI trên Windows, xử lý lần mở trùng và lỗi khởi động như thế nào?
- Đóng tab có dừng app hay để tiến trình nền tiếp tục chạy; người dùng thoát hoàn toàn bằng cách nào?

### Q10 — Chi tiết giao diện và accessibility

- Nguồn tham chiếu Sci-Link cụ thể nào dùng để nghiệm thu giao diện?
- Có yêu cầu phóng to chữ không, và nếu có thì đến mức nào?
- Tiêu chí đo tương phản, kiểm tra điều hướng/focus bàn phím và ngôn ngữ giao diện là gì?

### Q11 — Điều kiện đo hiệu năng

- Máy Windows mục tiêu, bộ dữ liệu 100.000 dạng từ, kiểu truy vấn và cách đo giới hạn 1 giây là gì?
- Mốc 2 phút tính từ thao tác nào đến trạng thái nào; app xử lý vượt ngưỡng và hết quota ra sao?
- Thời gian chờ tối đa cho tạo đề và nhận xét viết câu là bao nhiêu?
- Có yêu cầu định lượng cho quy mô lớn hơn 100.000 dạng từ không?

### Q12 — Công thức dashboard và tiêu chí thành công

- Công thức, kỳ thống kê và mẫu số cho từng chỉ số tách riêng là gì, đặc biệt với flashcard tự đánh giá?
- Cách phản ánh thẻ bị đưa về chưa học hoặc lịch sử nguồn lỗi trong thống kê thế nào?
- Theo dõi mục tiêu 6 ngày/tuần trong bao lâu để đánh giá v1 hữu ích? Ngày đạt mục tiêu này có dùng đúng điều kiện streak hay quy tắc khác?

### Q13 — Lưu trữ, bảo vệ dữ liệu và lựa chọn kỹ thuật

- Chốt công nghệ, runtime, mô hình lưu trữ và cách tích hợp CLI sau khi kiểm chứng yêu cầu; không mặc định stack trong đặc tả cũ đã được tái phê duyệt.
- Lịch SRS, lịch sử, bài làm và kết quả được lưu ở đâu để người dùng tự sao lưu đầy đủ?
- Đặc tả cũ gọi SQLite là bản dữ liệu có thể dựng lại nhưng cũng lưu lịch sử học và quiz trong đó; Markdown hiện tại không chứa đủ những dữ liệu này. Cần làm rõ để việc đồng bộ/dựng lại dữ liệu từ vựng không vô tình mất tiến độ và kết quả.
- Xác định giới hạn truy cập file, xử lý dữ liệu đầu vào, cơ chế gọi CLI và quản lý thông tin xác thực phù hợp với app chỉ dùng trên một máy; không thêm luồng tài khoản sản phẩm đã được loại khỏi phạm vi.

### Q14 — Tương thích dữ liệu hiện có và ngày ghi chú

- Xác nhận cách đọc ngược định dạng Markdown cũ; README hiện có mô tả phần ngữ cảnh trong khi v1 không cần lưu câu gốc/nguồn bài đọc mới.
- Các trường ngữ cảnh đã có được bảo toàn/hiển thị như thế nào, và có cần thay đổi định dạng file hay không?
- Ngày lưu mặc định, việc cho chọn ngày khác và quy tắc khi lưu qua nửa đêm chưa được hỏi riêng.
- Tìm kiếm có cần không dấu, dung sai lỗi gõ hoặc hiểu nghĩa tương đương không? Hiện mới chốt tìm bằng một phần nghĩa tiếng Việt và mốc tốc độ.

---

**Kết thúc interview:** Người dùng đã đồng ý giữ các điểm chưa chốt trong **Câu hỏi còn mở**, sau đó gửi `FINALIZE INTERVIEW` để tạo tài liệu này. Bước viết spec cần sử dụng các quyết định đã chốt, giữ nhãn giả định và giải quyết những câu hỏi ảnh hưởng đến phần triển khai tương ứng; tài liệu không tự cấp thêm phạm vi tính năng.
