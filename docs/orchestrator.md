# Công cụ điều phối phát triển cục bộ Level 1

Hạ tầng này thay thế việc chuyển giao thủ công giữa các agent bằng các tệp đã được
kiểm tra tính hợp lệ. Nó hoạt động độc lập với ứng dụng FastAPI/React và không bổ sung
cơ sở dữ liệu hay framework agent. Phần triển khai sử dụng bộ công cụ Python/Pydantic
hiện có. T067–T070 mô tả từng phần triển khai với phạm vi giới hạn; các checkpoint
sản phẩm vẫn thuộc trách nhiệm của những task ban đầu.

## Kiến trúc và các quyết định

`tools/orchestrator/core.py` quản lý các mô hình trạng thái, contract và đầu ra được
kiểm tra nghiêm ngặt, cùng cơ chế lưu JSON theo cách nguyên tử. `runtime.py` quản lý
các tiến trình con, khóa cục bộ, Git và giao thức `AgentProvider` có thể thay thế.
`workflow.py` quản lý việc chuyển trạng thái theo quy tắc xác định và thực thi các
vai trò. `__main__.py` cung cấp giao diện dòng lệnh (CLI). Cách tổ chức namespace
package được giữ nhất quán với repository hiện có; hãy chạy lệnh từ thư mục gốc
của checkout.

Prompt Engineer, tức agent lập kế hoạch và soạn prompt, trả về một `Plan` chứa
contract và prompt cho Worker. Worker, tức agent triển khai, trả về `IMPLEMENTED`
hoặc `BLOCKED`. Auditor, tức agent kiểm tra độc lập, trả về `PASS`, `FAIL` hoặc
`BLOCKED`, kèm một mục bằng chứng cho mỗi tiêu chí nghiệm thu ban đầu. Khi kết quả
là FAIL, Prompt Engineer trả về prompt sửa lỗi và Worker thực hiện lại trong cùng
worktree, mặc định tối đa ba vòng sửa lỗi. Integrator, tức agent đánh giá tích hợp,
trả về `READY` hoặc `BLOCKED` một cách độc lập; Python thực hiện commit, merge vào
bản tích hợp thử, kiểm tra và đưa bản đã đạt kiểm tra vào nhánh đích. Model không
quyết định việc chuyển trạng thái và không trực tiếp merge vào main. Prompt, schema
và kết quả JSON của mọi vai trò đều được lưu lại, không cần sao chép tin nhắn thủ công.

Python ràng buộc định danh task, các task phụ thuộc, SHA gốc, phạm vi tệp chính xác,
tiêu chí, lệnh kiểm tra, mức rủi ro và điều kiện dừng theo thẻ task ban đầu. Thẻ của
các task phụ thuộc phải có trạng thái DONE, hoàn thành các tiêu chí và có mã nguồn
thuộc phạm vi sở hữu; các lệnh kiểm tra của chúng được chạy lại trên bản gốc đã cố
định. Đây là kiểm tra các phụ thuộc trực tiếp, không phải bộ lập lịch DAG. Cú pháp
lệnh không được hỗ trợ hoặc danh sách tệp được phép sửa dùng thư mục/glob sẽ khiến
quá trình bị chặn, thay vì tự suy diễn phạm vi. Agent lập kế hoạch và kiểm tra đọc
các tài liệu được tham chiếu cùng mã nguồn trong worktree của mình.

Chương trình điều phối chạy các kiểm tra trước audit và sau tích hợp. Mã thoát khác
0, hết thời gian, đầu ra quá lớn, kết quả PASS mâu thuẫn, source/index thay đổi hoặc
tệp bàn giao bị sửa đều chặn việc đưa bản tích hợp vào nhánh đích. Giá trị băm của
source bao gồm HEAD, diff đã stage, nội dung và chế độ của tệp. Báo cáo của Worker
được đối chiếu với Git diff thực tế, bao gồm cả tệp chưa được Git theo dõi và tệp
đã stage. Các tệp sinh tự động phải được tạo bằng generator thuộc task; hạ tầng này
không thay đổi API công khai của ứng dụng, migration cơ sở dữ liệu hay client sinh
tự động.

## Cài đặt và cấu hình

Sử dụng môi trường Python của repository, gồm Python 3.12+ và các dependency phát
triển hiện có, Git, cùng Codex CLI và Gemini CLI đã được cài đặt và xác thực riêng.
Thông tin xác thực do các CLI đó quản lý; công cụ này không cài CLI hay đọc kho
thông tin xác thực. Chuẩn bị các dependency npm của repository và công cụ quét bảo
mật bên ngoài trước khi chạy thật. Các biến môi trường chỉ định scanner được ghi
trong T063 vẫn được kế thừa bình thường. Các bài kiểm thử không gửi yêu cầu LLM thật.

Các phiên bản đã kiểm tra tại máy: Codex **0.159.2** trước khi tạm dừng và **0.159.3**
ở lần kiểm tra cuối; Gemini CLI **0.59.0**. Những cờ cần thiết vẫn được hỗ trợ.
Đây là bằng chứng kiểm tra, không phải cam kết tương thích với các phiên bản khác.
Mỗi lần gọi đều kiểm tra `--version`/`--help` của CLI đã cài và `exec --help` của
Codex; nếu thiếu khả năng cần thiết, công cụ báo lỗi rõ ràng. Codex sử dụng
`-a never exec --ephemeral --sandbox`, `--output-schema`, `--output-last-message`,
cờ `--model` tùy chọn và cấu hình mức suy luận; prompt được truyền qua stdin.
Gemini sử dụng `--prompt`, `--output-format json`, `--approval-mode plan` khi kiểm
tra hoặc `auto_edit` khi triển khai, cùng cờ `--model` tùy chọn; ngữ cảnh được truyền
qua stdin. Công cụ hỗ trợ cấu trúc JSON bao ngoài của Gemini và phản hồi JSON nằm
trong khối Markdown có định dạng chính xác. Phiên bản này không có cờ điều chỉnh
mức suy luận: hãy đặt `reasoning: null`.

`orchestrator.yaml` chủ ý sử dụng **cú pháp JSON, là một tập con của YAML 1.2**, được
đọc bằng thư viện chuẩn. Công cụ không chấp nhận cú pháp YAML tùy ý. Cách này tránh
bổ sung dependency khi chạy. Cấu hình `provider`, `executable`, `model` và `reasoning`
cho từng vai trò; `model: null` kế thừa cấu hình của CLI đã cài, không tự đặt tên
model. Chọn rõ model có sẵn khi chạy thật để có thể tái hiện cấu hình. Mặc định,
Worker dùng Gemini; lập kế hoạch, audit và tích hợp dùng Codex. Có thể thay provider
qua giao thức có kiểu dữ liệu mà không phải viết lại máy trạng thái.

Cấu hình còn quản lý `base_branch` (mặc định là main cục bộ), `max_fix_cycles` (0–10),
`timeout_seconds`, các lệnh kiểm tra bắt buộc dưới dạng mảng đối số,
`setup_commands`, thư mục gốc của run/worktree và `integrate`. Bước chuẩn bị mặc định
chạy `npm ci` riêng trong mỗi worktree task và bản tích hợp thử sau merge; công cụ
Python/phát triển được kế thừa từ môi trường gọi lệnh. Bước chuẩn bị của Level 1 chỉ
chấp nhận lệnh cài đặt chuẩn này của repository. Lỗi dependency hoặc chuẩn bị môi
trường khiến quá trình dừng với bằng chứng rõ ràng; không gọi trình cài đặt chưa
được kiểm tra.

Thư mục run phải nằm trong repository và được Git bỏ qua; worktree phải nằm bên
ngoài repository. Đường dẫn tương đối được tính từ checkout chính, không phải
worktree của nơi gọi lệnh. Thư mục worktree mặc định là `../english_web-worktrees`;
không có đường dẫn riêng của máy được ghi cứng. Gate mặc định gồm `check:task`,
Ruff và Mypy. Lỗi có sẵn trên baseline sẽ chặn lần chạy thật cho đến khi được sửa
trong phạm vi đã cho phép; lỗi đó không bao giờ được gọi là PASS. Tích hợp mặc định
tắt, vì việc cài hạ tầng không đồng nghĩa với cho phép các lần merge sau này.

## Cách sử dụng

```bash
python -m tools.orchestrator run T018 --dry-run
python -m tools.orchestrator run T018 --no-integrate
python -m tools.orchestrator status T018
python -m tools.orchestrator resume T018 --run-id <recorded-run-id>
# Cho phép tích hợp task này vào nhánh cục bộ khi checkout đích đã sẵn sàng:
python -m tools.orchestrator resume T018 --integrate
```

Dùng `--config <path>` để chọn tệp cấu hình khác. Status/resume chọn lần chạy mới
nhất đã lưu, trừ khi có `--run-id`. Mã thoát 0 nghĩa là thao tác yêu cầu đã thành
công, kể cả khi đang ở AUDIT_PASS chờ tích hợp; không nhất thiết là DONE. Mã thoát
2 nghĩa là từ chối thực hiện, BLOCKED hoặc FAILED. Ctrl+C trước khi pipeline tiếp
nhận tác vụ trả về 130; ngắt trong một giai đoạn sẽ ghi BLOCKED và trả về 2.

Dry run đọc bằng chứng từ task, phụ thuộc, cấu hình và Git, rồi in bản gốc, branch,
worktree, phân công vai trò, các kiểm tra và luồng dự kiến. Nó không tạo tệp kết quả
hay worktree, không gọi LLM và không thay đổi trạng thái Git. Nhánh gốc cục bộ được
cấu hình phải chứa commit hạ tầng này cùng các công cụ cần thiết; gọi từ checkout
khác không tự đưa source vào worktree task mới. Hãy tích hợp hạ tầng đã review theo
quy trình của repository trước khi chạy task thật trên nhánh gốc đó.

Chạy thật yêu cầu checkout chính sạch và thư mục runtime được Git bỏ qua. Nếu task
đã có worktree, kể cả branch task được tạo thủ công, công cụ sẽ từ chối; hãy kiểm
tra hoặc tiếp tục lần chạy hiện có thay vì ghi đè. Worktree đã hoàn thành nhưng còn
được giữ lại phải được kiểm tra và chủ động xóa thủ công trước khi bắt đầu lần chạy
mới của cùng task. Orchestrator không có lệnh dọn dẹp mang tính phá hủy.

Với 1–3 task độc lập, khởi động các tiến trình CLI riêng. Mỗi task nhận một branch
`agent/Txxx-<run-id>` duy nhất, worktree bên ngoài và thư mục run riêng. Các khóa
hệ điều hành dùng chung toàn repository tại `.agent-runs/.locks` cho phép tối đa
ba tiến trình hoạt động, mỗi task một tiến trình, và chỉ một lần tích hợp tại một
thời điểm. Những khóa này vẫn dùng chung khi cấu hình thư mục run khác nhau.
Lần chạy thứ tư hoặc tiến trình cạnh tranh cho cùng task sẽ bị từ chối an toàn.

Nếu khóa tích hợp đang bận, task giữ trạng thái AUDIT_PASS; chạy
`resume --integrate` khi khóa đã được giải phóng. Nếu lỗi khóa xảy ra sau khi tích
hợp đã bắt đầu, trạng thái chuyển sang BLOCKED để giữ nguyên kết quả chưa xác định,
thay vì báo đang chờ. Không có daemon chạy nền để tự thử lại. Các task độc lập có
thể tiếp tục thực thi trong khi một lần tích hợp khác đang chạy, tùy giới hạn
CPU/bộ nhớ của máy; hạn chế chạy nhiều gate nặng cùng lúc.

## Tệp kết quả và trạng thái

Mỗi thư mục `.agent-runs/Txxx/<UTC-time>-<random-id>/` chứa `state.json`, các báo cáo
task/plan/contract/worker/audit/fix bất biến được đánh số theo vòng, prompt cho Worker,
prompt/schema đầu ra/phản hồi của từng vai trò, log tiến trình dạng JSON, bằng chứng
kiểm thử, đánh giá/báo cáo tích hợp và `final_report.md`. Các vòng trước và bằng chứng
thất bại được giữ lại. Mỗi tệp JSON có tính quyết định được ràng buộc với giá trị băm
đã lưu; prompt Worker/fix khi tiếp tục phải trùng với Plan/Fix đã lưu.

State ghi cấu hình ban đầu, bản gốc đã cố định, metadata worktree, agent hiện tại,
số vòng sửa lỗi, thời gian, tên tệp kết quả, giá trị băm source/contract và lỗi gần
nhất. Ghi state sử dụng tệp tạm riêng, fsync tệp, thay thế nguyên tử và fsync thư mục
trên POSIX; quá trình đọc JSON được kiểm tra nghiêm ngặt và giới hạn kích thước.
Khóa riêng của từng run ngăn việc resume đồng thời và dùng chung một phần state.
Các tệp runtime được Git bỏ qua và không bao giờ được commit.

Các chuyển trạng thái thông thường:

```text
PENDING -> READY -> PLANNING -> PROMPT_READY -> WORKER_RUNNING
-> IMPLEMENTED -> AUDIT_RUNNING -> AUDIT_PASS -> INTEGRATION_RUNNING
-> MERGED -> VERIFYING -> DONE

AUDIT_RUNNING -> AUDIT_FAIL -> FIX_PROMPT_READY -> FIX_RUNNING
-> IMPLEMENTED -> AUDIT_RUNNING
```

`MERGED` chỉ bản tích hợp thử được cô lập, chưa phải đã đưa vào nhánh đích. Chỉ bản
đã kiểm tra thành công mới được đưa vào nhánh đích bằng merge ff-only với đúng SHA
của nó. Giai đoạn không an toàn sẽ chuyển sang BLOCKED; chuyển trạng thái không hợp
lệ bị từ chối. DONE, BLOCKED và FAILED là trạng thái kết thúc. Contract không được
nới lỏng tiêu chí hay kiểm tra, mở rộng đường dẫn hoặc tự đưa ra lựa chọn sản phẩm
mới. Nếu model báo cần quyết định của con người, quá trình bị chặn.

## Tích hợp và phục hồi

Branch task chưa được commit trong suốt quá trình triển khai/audit. Khi tích hợp
được cho phép, Python stage đúng các tệp đã audit, kiểm tra phạm vi và khoảng trắng
của phần đã stage, commit, tạo bản tích hợp thử riêng từ nhánh đích cục bộ hiện tại,
merge no-ff, kiểm tra cây mã nguồn sau merge và đưa đúng SHA bất biến đã được kiểm
tra vào nhánh đích.

Nhánh đích phải đang được checkout và sạch. Công cụ hỗ trợ nhánh đích tiến thêm các
thay đổi không trùng với thay đổi của task. Nếu thay đổi chồng lấn, lịch sử phân kỳ,
có xung đột hoặc nhánh đích/bản tích hợp thử bị thay đổi, quá trình dừng và giữ lại
mọi công việc. Không có fetch, pull, reset, stash, force push hay tự giải quyết xung
đột. Worker giữ quy ước của repository về cập nhật thẻ task, todo và changelog cho
task của mình, nên thay đổi bookkeeping đồng thời có thể cần con người review khi
tích hợp. Không đánh dấu checkpoint hoàn thành chỉ vì một task riêng lẻ đã pass.

Các điểm dừng ổn định (READY, PROMPT_READY, IMPLEMENTED, AUDIT_FAIL,
FIX_PROMPT_READY, AUDIT_PASS) có thể tiếp tục sau khi kiểm tra cấu hình ban đầu,
bản chụp task, định danh worktree và bằng chứng đã cố định. Chỉ được thay đổi tùy
chọn bật/tắt tích hợp. Khi agent đang chạy, commit/merge hoặc kiểm tra bị ngắt,
kết quả chưa xác định: resume ghi BLOCKED thay vì thực hiện lại thao tác thay đổi.
Hãy kiểm tra báo cáo cuối/lỗi, tệp kết quả từng vòng, Git index/lịch sử, worktree
của bản tích hợp thử và các tiến trình CLI còn sống trước khi phục hồi thủ công.
Không thể tự xóa BLOCKED hay chỉnh state để giả vờ đã kiểm tra. Bằng chứng trước
đó không bị âm thầm ghi đè.

Tiến trình CLI được tạo kế thừa khóa POSIX: việc kết thúc tiến trình Python cha
không giải phóng khóa tích hợp/run nếu tiến trình CLI con trực tiếp vẫn còn sống.
Hết thời gian hoặc Ctrl+C sẽ kết thúc nhóm tiến trình con; giám sát đầu ra giới
hạn mỗi luồng ở 4 MiB, nhưng có thể vượt tạm thời giữa các lần kiểm tra định kỳ.
Windows native dùng khóa theo vùng byte và taskkill khi hết thời gian; việc tiến
trình mồ côi kế thừa khóa sau khi tiến trình cha bị dừng đột ngột chưa được kiểm chứng.

Linux/WSL là môi trường đã kiểm thử. Tích hợp tự động trên Windows native trả về
ENVIRONMENT_BLOCKED cho đến khi cơ chế phục hồi cây tiến trình được kiểm chứng
độc lập; lập kế hoạch/triển khai có thể chạy với các giới hạn khóa native đã mô tả.

Kết quả tiến trình lưu argv, cwd, thời gian, stdout/stderr, mã thoát và trạng thái
hết thời gian trong bộ nhớ. Log được lưu chủ ý bỏ nội dung thô/đối số, chỉ giữ độ
dài, giá trị băm, provider/model và metadata mã thoát để tránh ghi thông tin xác
thực hoặc nội dung học tập. Prompt và phản hồi agent đã được kiểm tra là những
tệp bàn giao riêng cần thiết: dùng ngữ cảnh task tổng hợp, không đưa thông tin xác
thực hay dữ liệu từ vựng thật vào. Thông báo INFO/STATE/AGENT/GIT/TEST/ERROR hỗ trợ
chẩn đoán tại máy; không ghi toàn bộ biến môi trường vào log.

Chế độ phê duyệt của CLI và kiểm tra phạm vi sau khi thực thi **không tạo ranh giới
bảo mật trước agent cục bộ độc hại**, đặc biệt với Gemini `auto_edit`. Chỉ chạy agent
cục bộ đáng tin cậy. Chúng có cùng quyền filesystem/Git với người dùng; tiến trình
độc hại có thể sửa metadata Git hoặc phớt lờ hướng dẫn trước khi các kiểm tra phát
hiện. Cô lập mạnh hơn ở cấp hệ điều hành và phục hồi sau khi tiến trình cha trên
Windows native bị dừng đột ngột thuộc các giai đoạn hạ tầng sau.

## Kiểm tra và giới hạn

```bash
python -m pytest tests/orchestrator -q
python -m ruff format --check tools/orchestrator tests/orchestrator
python -m ruff check tools/orchestrator tests/orchestrator
python -m mypy tools/orchestrator tests/orchestrator
npm run check:task
```

Các bài kiểm thử dùng chương trình provider giả và repository Git tạm thật để
kiểm tra luồng PASS, FAIL/fix/PASS, giới hạn, khóa tiến trình, ba lần chạy độc lập
đồng thời, từ chối worktree không an toàn, bằng chứng lỗi thời/mâu thuẫn và sự cố
tiến trình; không gọi dịch vụ trả phí. Xác thực provider thật và chất lượng model
vẫn cần được kiểm chứng khi vận hành, không phải bằng chứng từ các bài kiểm thử.
Runtime của ứng dụng không phụ thuộc vào package điều phối hay các CLI.

Level 1 chạy trên máy cục bộ, đồng bộ trong từng task, dùng JSON để lưu trạng thái,
giới hạn ba tiến trình phối hợp và tích hợp tuần tự theo cách thận trọng. Không có
cơ sở dữ liệu, dashboard, khóa phân tán, bộ lập lịch, worker pool, tự lập lịch DAG
hay resume chạy nền. Giao diện state/provider/Git cho phép bổ sung bộ lập lịch
Level 2 và cơ chế cô lập mạnh hơn mà không thay contract của các vai trò. Những
tính năng này được chủ ý để lại cho giai đoạn sau.
