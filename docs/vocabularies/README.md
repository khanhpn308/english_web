# Academic Vocabulary Log

Tài liệu ghi chép và lưu trữ từ vựng học thuật, thuật ngữ nghiên cứu khoa học được chuẩn hóa theo từ điển Cambridge.

## Cấu trúc thư mục

- `docs/vocabularies/`: Thư mục lưu trữ nhật ký từ vựng theo ngày với định dạng `DD-MM-YYYY.md`.
- `docs/vocabularies/README.md`: Hướng dẫn cấu trúc, quy tắc chuẩn hóa và hợp đồng định dạng.

## Quy ước định dạng mỗi tệp nhật ký hàng ngày (`DD-MM-YYYY.md`)

1. **Tiêu đề tệp (H1)**: `# DD-MM-YYYY` (theo ngày theo múi giờ `Asia/Bangkok`).
2. **Mục tra cứu nhanh (`## Tra cứu nhanh`)**: Bảng tra cứu đặt ngay dưới tiêu đề H1 và trước các mục chi tiết:
   - Cột: `| Từ/cụm từ | IPA (US) | Nghĩa ngắn | Ví dụ ngắn | Dịch ví dụ |`
   - Cột `Từ/cụm từ` phải là liên kết Markdown trỏ tới tiêu đề chi tiết cấp 2 (`## <Lemma>`) trong cùng tệp (ví dụ: `[anchor](#anchor)`).
   - Mỗi mục từ chi tiết tương ứng đúng một dòng trong bảng tra cứu nhanh.
   - Cột `Ví dụ ngắn` chứa câu ví dụ tiếng Anh tự nhiên.
   - Cột `Dịch ví dụ` chứa bản dịch tiếng Việt chuẩn Cambridge cho ví dụ đó, không để trong dấu ngoặc đơn `( )`.
3. **Mục từ chi tiết (`## <Lemma>`)**:
   - Tên tiêu đề cấp 2 sử dụng dạng bổ đề (lemma) chuẩn theo từ điển Cambridge.
   - Bảng thông số từ vựng: `Từ/cụm từ`, `Từ loại`, `IPA (US)`, `Trọng âm`, `Nguồn` (dẫn link Cambridge Dictionary).
   - **Ý nghĩa**: Giải thích nghĩa súc tích, phân biệt nghĩa phổ thông và nghĩa chuyên ngành/học thuật.
   - **Trong ngữ cảnh**: Trích dẫn câu chứa từ vựng trong bài báo khoa học kèm bản dịch tiếng Việt (hoặc ghi rõ nếu không có ngữ cảnh đi kèm).
   - **Ví dụ**: Câu ví dụ tiếng Anh tự nhiên liên quan đến nghiên cứu học thuật kèm bản dịch tiếng Việt (không để trong dấu ngoặc tròn).
   - **Các dạng liên quan**: Bảng liệt kê các dạng từ phái sinh với các cột `Dạng từ`, `Từ loại`, `IPA (US)`, `Nghĩa`, `Ví dụ ngắn`, `Dịch ví dụ`. Mỗi từ dẫn link Cambridge riêng và xác minh phát âm IPA (US). Cột `Dịch ví dụ` là cột riêng biệt, không để trong dấu ngoặc đơn `( )`.
