# Agent Instructions

## Changelog bắt buộc

Mọi thay đổi do agent thực hiện trong workspace phải được ghi vào [docs/changelogs.md](docs/changelogs.md) trước khi kết thúc tác vụ.

Quy định ghi changelog:

- Dùng ngày theo định dạng `dd/mm/yyyy`.
- Dùng múi giờ `Asia/Bangkok`.
- Ghi rõ khu vực hoặc file bị thay đổi.
- Mô tả ngắn gọn nội dung thay đổi và mục đích khi cần.
- Đặt mục mới ở đầu danh sách thay đổi.
- Không xóa hoặc sửa lịch sử cũ, ngoại trừ việc sửa lỗi ghi chép rõ ràng.

## Quy định ghi tài liệu

Khi tạo hoặc cập nhật spec, ADR, API documentation, README, changelog hoặc tài liệu kỹ thuật khác, agent phải sử dụng skill [`agent-skills:documentation-and-adrs`](/mnt/c/Users/khanh/.codex/plugins/cache/agent-skills/agent-skills/0.6.11/skills/documentation-and-adrs/SKILL.md).

Khi áp dụng skill:

- Ghi lại lý do, bối cảnh, ràng buộc, đánh đổi và hệ quả của quyết định khi các thông tin này có ý nghĩa.
- Trước khi tạo ADR mới, kiểm tra convention ADR hiện có trong repository và tiếp tục đúng vị trí, định dạng, cách đánh số đó.
- Không tạo ADR cho thay đổi nhỏ hoặc tài liệu chỉ lặp lại điều hiển nhiên từ code.
- Với quyết định kiến trúc hoặc thay đổi khó đảo ngược, tạo ADR bất biến; nếu quyết định thay đổi, tạo ADR mới để thay thế ADR cũ thay vì xóa lịch sử.
- Tài liệu API công khai phải mô tả input, output, lỗi và ví dụ sử dụng phù hợp.

