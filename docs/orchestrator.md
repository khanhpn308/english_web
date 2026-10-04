# Công cụ điều phối phát triển cục bộ Level 1 và Level 2

## Tra cứu nhanh: trường hợp và lệnh chạy

Chạy tại thư mục gốc repository, với môi trường và CLI đã cài/xác thực:

```bash
source .venv/bin/activate
```

Thay `T018` bằng task cần chạy; thay `RUN_ID` bằng `run_id` trong kết quả status.

| Bạn muốn làm gì? | Lệnh |
|---|---|
| Xem DAG toàn repository, không gọi model hay tạo worktree | `python -m tools.orchestrator schedule --dry-run` |
| Chạy mọi task READY theo DAG, dừng mỗi Pipeline ở audit | `python -m tools.orchestrator schedule --no-integrate` |
| Chạy theo DAG và cho phép tích hợp cục bộ qua Pipeline | `python -m tools.orchestrator schedule --integrate` |
| Xem cấu hình, worktree và luồng dự kiến; chưa chạy model | `python -m tools.orchestrator run T018 --dry-run` |
| Chạy triển khai → audit → sửa lỗi; chưa commit/merge vào main | `python -m tools.orchestrator run T018 --no-integrate` |
| Chạy toàn bộ, cho phép commit và tích hợp vào main sau khi đạt kiểm tra | `python -m tools.orchestrator run T018 --integrate` |
| Xem trạng thái lần chạy mới nhất | `python -m tools.orchestrator status T018` |
| Xem chính xác một lần chạy cũ | `python -m tools.orchestrator status T018 --run-id RUN_ID` |
| Tiếp tục một run đang ở điểm ổn định, chưa tích hợp | `python -m tools.orchestrator resume T018 --run-id RUN_ID --no-integrate` |
| Run đã AUDIT_PASS: tiếp tục để commit, kiểm tra và tích hợp | `python -m tools.orchestrator resume T018 --run-id RUN_ID --integrate` |
| Thử lại sau khi sửa nguyên nhân lỗi, nếu run đủ điều kiện retry | `python -m tools.orchestrator retry T018 --run-id RUN_ID --no-integrate` |
| Lỗi cũ `agy lacks required capability: --print`: sau khi cập nhật bản sửa, tạo lần thử mới | `python -m tools.orchestrator run T021 --no-integrate` |
| Chạy Worker GPT bằng tệp cấu hình riêng đã tạo | `python -m tools.orchestrator run T018 --config orchestrator.gpt.local.yaml --no-integrate` |
| Khóa tích hợp đang bận: chạy lại sau khi task khác tích hợp xong | `python -m tools.orchestrator resume T018 --run-id RUN_ID --integrate` |

- `--no-integrate` vẫn tạo worktree task riêng khi bắt đầu run mới; dry-run không tạo worktree hay gọi model.
- Mặc định Worker dùng **agy / Gemini**. Task GPT cần cấu hình riêng chọn `codex`, model ID thực và reasoning theo Prompt Engineer; bảng task-plan chưa tự đổi model khi chạy.
- `run` tự tiếp tục run ổn định hoặc tạo lần thử mới nếu bằng chứng cho phép. `retry` giữ lại run cũ; lỗi sau khi Worker đã sửa source cần kiểm tra worktree/log, không bảo đảm retry được.
- Prompt Worker và Fix tự kèm skill phù hợp với task, đường dẫn `SKILL.md` và lý do chọn; không cần thêm cờ chạy. Bộ skill đã cài được phát hiện tự động hoặc chọn bằng `skills_root`.
- Mặc định không giới hạn thời gian chạy agent, setup và kiểm tra: `"timeout_seconds": null` (hoặc bỏ trường này). Muốn giới hạn 90 phút cho mỗi lần gọi, đặt `"timeout_seconds": 5400` trong cấu hình.
- Auditor trả JSON sai quy ước được yêu cầu sửa trong tối đa ba lượt của cùng lần gọi; không chạy lại Worker chỉ để sửa báo cáo.
- Chạy thật cần checkout chính sạch. `--integrate` chỉ đưa vào main sau audit và kiểm tra đạt; công cụ không push.
- Scanner đã cấu hình trong `~/.bashrc` được terminal Bash tương tác mới tự nạp. Sau khi vừa sửa `.bashrc`, chạy `source "$HOME/.bashrc"` một lần trong terminal hiện tại; nhập lệnh không kèm dấu backtick.

Chi tiết cấu hình, artifact và phục hồi nằm ở các phần bên dưới.

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
định. Đây là kiểm tra các phụ thuộc trực tiếp của Pipeline; Level 2 ở bên dưới
chỉ dùng metadata để lập lịch trước bước kiểm tra có thẩm quyền này. Cú pháp
lệnh không được hỗ trợ hoặc danh sách tệp được phép sửa dùng thư mục/glob sẽ khiến
quá trình bị chặn, thay vì tự suy diễn phạm vi. Agent lập kế hoạch và kiểm tra đọc
các tài liệu được tham chiếu cùng mã nguồn trong worktree của mình.

Prompt Engineer được cung cấp contract mẫu do Python tạo từ task đã cố định.
Agent phải sao chép nguyên văn các trường của mẫu, gồm `objective`, `forbidden_scope`
và `stop_conditions`; diễn giải và kế hoạch triển khai nằm trong prompt Worker.
Theo quyết định T072/ADR-0007, contract mới không có `human_gates` và model không
tạo thêm bước duyệt thủ công trong planning. Agent chỉ bổ sung các tệp cấm cụ thể
vào `forbidden_paths`. Danh sách này không chấp nhận thư mục/glob; các hạn chế rộng
đã nằm trong `forbidden_scope` và mọi sửa đổi ngoài allowlist luôn bị chặn.

Nếu agent đổi trường đã cố định, lỗi `Contract differs from repository-owned task constraints`
liệt kê tên trường bị lệch, không ghi nội dung riêng tư. Lỗi đường dẫn nêu trường
và chỉ số mục không hợp lệ. Đối chiếu artifact task/plan để kiểm tra; không sửa
contract/state đã lưu nhằm ép run `BLOCKED` tiếp tục. Contract mẫu giúp tránh diễn
giải lệch; thiếu bằng chứng kiểm tra vẫn không được gọi là PASS.

Lệnh verification/scanner do repository cấu hình là lựa chọn của chủ repository.
Agent được chạy chúng với phạm vi hiện có, không yêu cầu duyệt lại cho từng task
vì test/scanner có sẵn đọc tệp cục bộ. Agent không được tự mở/sao chép dữ liệu học
hay credentials vào prompt/report, sửa dữ liệu người dùng, tạo fixture thật, gọi
application AI hoặc inference thật trong automated tests. Không bỏ test, thu hẹp
scanner hay giảm threshold. [ADR-0007](adr/0007-owner-verification-authority.md)
ghi rõ quyết định này và ranh giới còn giữ.

Chương trình điều phối chạy các kiểm tra trước audit và sau tích hợp. Mã thoát khác
0, hết thời gian, đầu ra quá lớn, kết quả PASS mâu thuẫn, source/index thay đổi hoặc
tệp bàn giao bị sửa đều chặn việc đưa bản tích hợp vào nhánh đích. Giá trị băm của
source bao gồm HEAD, diff đã stage, nội dung và chế độ của tệp. Báo cáo của Worker
được đối chiếu với Git diff thực tế, bao gồm cả tệp chưa được Git theo dõi và tệp
đã stage. Các tệp sinh tự động phải được tạo bằng generator thuộc task; hạ tầng này
không thay đổi API công khai của ứng dụng, migration cơ sở dữ liệu hay client sinh
tự động.

## Level 2: lập lịch DAG toàn repository (T079)

`scheduler.py` là lớp mỏng phía trên `Pipeline`, dùng thư viện chuẩn và các model
Pydantic sẵn có. `schedule` không nhận Txxx hoặc `--run-id`; các lệnh `run`,
`resume`, `retry`, `status` vẫn dùng như trước. Cấu hình và cờ tích hợp vẫn giống
Level 1, mặc định không tích hợp. Không chọn model theo task ID.

Discovery đọc task cards `tasks/t[0-9]*.md` từ một SHA bất biến của nhánh đích
canonical (`base_branch`, mặc định `main`). `tasks/todo.md` và template không phải
nodes. Như `Pipeline.load`, scheduler xác định checkout chính qua Git common-dir,
nên task card chưa commit trên worktree gọi lệnh không trở thành bằng chứng DONE.
Mỗi node chứa ID, đường dẫn, title, status và dependencies. Định danh dependency chỉ được trích xuất từ các standalone canonical task-ID token trong phần Dependencies (thông qua helper dùng chung `dependency_ids`); các định danh lồng trong prose hoặc trạng thái như `BLOCKED_BY_T080_T081` không tạo cạnh phụ thuộc trong DAG. Cả tầng phân giải metadata scheduler lẫn parser thực thi `task_card()` đều tuân thủ cùng một quy tắc ngữ nghĩa này. Sau khi trích xuất, việc kiểm tra phụ thuộc tiếp tục duy trì cơ chế fail-closed nghiêm ngặt (từ chối missing dependency, self-dependency hoặc cycle). Discovery không gọi `task_card()` vì hàm đó cố ý từ chối dependencies chưa DONE. Ngay trước dispatch, `task_card()` kiểm tra có thẩm quyền; `Pipeline.start()` tiếp tục kiểm tra bản chụp trong worktree, implementation evidence, verification và contract như trước.

| Trạng thái DAG | Quy tắc |
|---|---|
| DONE | Card ở canonical revision có status DONE; không dispatch |
| READY | Card chưa DONE, không có trạng thái BLOCKED/FAILED và mọi dependency DONE |
| BLOCKED | Dependency chưa DONE, card có trạng thái BLOCKED/FAILED, hoặc lần chạy đã dừng mà card canonical chưa DONE |

ID trùng, dependency thiếu, self-dependency hoặc cycle ở bất kỳ node nào (kể cả
DONE) từ chối toàn bộ graph trước khi tạo lock/worktree/process chạy task. Các task
có cùng mức ưu tiên dispatch theo ID tăng dần. JSON report chứa revision, toàn bộ
nodes/edges, topological order, `done`, `ready`, `blocked` cùng lý do dependencies;
sau chạy thật thêm `outcomes` gồm state/run ID/lỗi an toàn. Graph hợp lệ ở dry-run
trả exit0 dù có nodes BLOCKED. Graph không hợp lệ trả exit2 với lỗi; không xuất
READY/BLOCKED counts như thể đã phân giải một DAG hợp lệ. Chạy thật trả exit2 nếu
còn nodes BLOCKED, exit0 nếu canonical cards đều DONE.

Scheduler giữ OS lock repository-global `scheduler.lock` để từ chối hai scheduler
sống đồng thời. Pool tối đa ba process dùng spawn; mỗi process gọi Pipeline đồng
bộ, giữ nguyên ba admission slots và khóa task/run/worktree/integration hiện có.
Không dùng threads cho Pipeline vì runtime kế thừa khóa theo process. Future đang
sống và outcomes tránh dispatch lặp trong cùng lần schedule; OS task lock vẫn có
thẩm quyền khi chạy cùng lệnh Level 1 bên ngoài. Contention ở admission/task lock
được hoãn rồi đọc lại canonical graph; task READY khác được phép đi trước node
đang bận. Scheduler có thể chờ slot bên ngoài; Ctrl+C vẫn dùng cơ chế ngắt của CLI.

Sau mỗi completion, scheduler đọc lại canonical SHA và recompute DAG trước khi
dispatch thêm. Metadata được cache chỉ khi SHA không đổi; outcomes vẫn được phân
giải lại. Khi đã hoãn contention, scheduler thăm dò lại cả khi một task khác còn
sống để dùng admission slots vừa được nhả. FAILED/BLOCKED chỉ chặn downstream;
nhánh độc lập tiếp tục. Kết quả
DONE của run hoặc card DONE trong worktree riêng không đủ unlock dependencies.
Không tự gọi thêm recovery cho task đã kết thúc trong lần schedule này; bounded
recovery/Fix và state machine đều thuộc Pipeline. AUDIT_PASS khi tắt tích hợp hoặc
khi integration lock bận được giữ lại; dùng `resume TASK --run-id RUN_ID --integrate`
theo quy tắc Level 1 rồi chạy schedule lại. Scheduler không tự giải quyết overlapping
bookkeeping, merge conflicts hay baseline failures. Khóa tích hợp và snapshot/scope
fences hiện có quyết định promotion; không có push.

T079 không có CPU/RAM budgeting, FAST/FULL gate arbitration, dashboard hoặc daemon.
Resource-aware scheduling thuộc task hạ tầng tiếp theo. Bằng chứng T079 lịch sử: canonical main ngày
04/10/2026 có hai card cho mỗi ID T075/T076; dry-run từ chối `Duplicate task IDs:
T075, T076`. Sửa định danh task cần phạm vi riêng; T079 giữ nguyên các card đó.

T082 đã sửa định danh trong worktree remediation: T075/T076 vẫn là các task
orchestrator; foundation shadcn/ui là T080 và AppShell migration là T081, phụ thuộc
T080. Discovery bằng scheduler hiện có đọc filesystem thấy 82 card/82 ID duy nhất;
graph validation tiếp theo từ chối `Self dependency: T018`, do prose trong phần
Dependencies chứa chính ID của card. T081 cũng giữ prose tự tham chiếu đã có từ
card UI cũ. Không sửa validator hay các lỗi DAG riêng này trong T082.
Lệnh `schedule --dry-run` đọc Git revision trên canonical main, không đọc các sửa
đổi chưa commit trong worktree. Vì T082 chưa commit/tích hợp, lệnh vẫn trả exit2
với duplicate-ID blocker trên main; không có dispatch. Không coi đây là bằng chứng
canonical main đã được sửa. Kết quả cũ ở trên và trong T079 được giữ để kiểm toán.

## Cài đặt và cấu hình

Sử dụng môi trường Python của repository, gồm Python 3.12+ và các dependency phát
triển hiện có, Git, cùng Codex CLI và Antigravity CLI (`agy`) đã được cài đặt và xác thực riêng.
Adapter Gemini CLI độc lập vẫn có sẵn nếu bạn chọn provider `gemini`.
Thông tin xác thực do các CLI đó quản lý; công cụ này không cài CLI hay đọc kho
thông tin xác thực. Chuẩn bị các dependency npm của repository và công cụ quét bảo
mật bên ngoài trước khi chạy thật. Các biến môi trường chỉ định scanner được ghi
trong T063 vẫn được kế thừa bình thường. Các bài kiểm thử không gửi yêu cầu LLM thật.

Các phiên bản đã kiểm tra tại máy: Codex **0.159.2** trước khi tạm dừng và **0.159.3**
ở lần kiểm tra cuối; Gemini CLI **0.59.0**; Antigravity CLI **1.2.14**. Những cờ cần thiết vẫn được hỗ trợ.
Đây là bằng chứng kiểm tra, không phải cam kết tương thích với các phiên bản khác.
Mỗi lần gọi đều kiểm tra `--version`/`--help` của CLI đã cài và `exec --help` của
Codex; đọc help từ cả stdout và stderr vì agy1.2.14 in help ra stderr dù exit0.
Probe lỗi/timeout/quá giới hạn không được gọi agent. Chỉ kiểm tra cờ thực sự dùng;
agy stdin headless không yêu cầu hoặc truyền `--print`. Nếu thiếu khả năng cần thiết,
công cụ báo lỗi rõ ràng. Codex sử dụng
`-a never exec --ephemeral --sandbox`, `--output-schema`, `--output-last-message`,
cờ `--model` tùy chọn và cấu hình mức suy luận; prompt được truyền qua stdin.
Gemini sử dụng `--prompt`, `--output-format json`, `--approval-mode plan` khi kiểm
tra hoặc `yolo` khi triển khai, cùng cờ `--model` tùy chọn; ngữ cảnh được truyền
qua stdin. Adapter kiểm tra và truyền `--skip-trust` cho phiên trong worktree được
giao: không sửa trusted-folders hay credentials toàn máy. Worker dùng `yolo` theo
yêu cầu chạy tự động, nên các tool không chờ duyệt tương tác. Công cụ hỗ trợ cấu trúc JSON bao ngoài của Gemini và phản hồi JSON nằm
trong khối Markdown có định dạng chính xác. Phiên bản này không có cờ điều chỉnh
mức suy luận: hãy đặt `reasoning: null`.

`orchestrator.yaml` chủ ý sử dụng **cú pháp JSON, là một tập con của YAML 1.2**, được
đọc bằng thư viện chuẩn. Công cụ không chấp nhận cú pháp YAML tùy ý. Cách này tránh
bổ sung dependency khi chạy. Cấu hình `provider`, `executable`, `model` và `reasoning`
cho từng vai trò; `model: null` kế thừa cấu hình của CLI đã cài, không tự đặt tên
model. Chọn rõ model có sẵn khi chạy thật để có thể tái hiện cấu hình. Mặc định,
Worker dùng `agy` với `gemini-3.8-flash-high`, có trong danh sách `agy models`;
lập kế hoạch, audit và tích hợp dùng Codex. Gemini CLI (`gemini`) không tự sử dụng
model/tài khoản đang chạy qua `agy`. Có thể thay provider
qua giao thức có kiểu dữ liệu mà không phải viết lại máy trạng thái.

### Tích hợp agent-skills và yêu cầu dùng skill

Công cụ dùng bộ [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills).
Skill là workflow phải đọc và áp dụng khi liên quan, không chỉ là tên để liệt kê.
Theo hướng dẫn upstream, có thể cài native vào CLI nếu máy chưa có:

```bash
# Antigravity
agy plugin install https://github.com/addyosmani/agent-skills.git
agy plugin list

# Codex
codex plugin marketplace add addyosmani/agent-skills
codex plugin add agent-skills@agent-skills

# Gemini CLI độc lập
gemini skills install https://github.com/addyosmani/agent-skills.git --path skills
```

Các cách cài được mô tả ở [agy setup](https://github.com/addyosmani/agent-skills/blob/main/docs/antigravity-setup.md),
[Codex setup](https://github.com/addyosmani/agent-skills/blob/main/docs/codex-setup.md)
và [Gemini setup](https://github.com/addyosmani/agent-skills/blob/main/docs/gemini-cli-setup.md).
Orchestrator không tự tải/cài/nâng cấp plugin hay sửa cấu hình CLI toàn máy.
Trên máy đã kiểm tra, pack agy0.6.11 có ở `~/.gemini/config/plugins/agent-skills/skills`;
không cần cài lại.

Mặc định tìm skill theo thứ tự: workspace `.agents/skills`, `.gemini/skills`, pack
agy nêu trên, rồi các thư mục skill người dùng Gemini/Agents/Codex và cache plugin
Codex. Muốn chọn rõ một pack hoặc thư mục skills, thêm vào cấu hình JSON:

```json
"skills_root": "~/.gemini/config/plugins/agent-skills/skills"
```

Hoặc đặt `AGENT_SKILLS_ROOT` trỏ tới pack. `skills_root` có ưu tiên hơn biến môi
trường; đường dẫn tương đối được tính từ checkout chính. Khi đã cấu hình rõ một
root, không âm thầm dùng pack khác nếu root đó thiếu skill.

| Tính chất task | Skill yêu cầu thêm ngoài workflow chung |
|---|---|
| Logic/behavior | `incremental-implementation`, `test-driven-development` |
| React/UI | `frontend-ui-engineering` |
| API/typed interface | `api-and-interface-design` |
| Input, filesystem, persistence, consent/security | `security-and-hardening` |
| Race, atomicity, durable state, crash recovery, migration | `doubt-driven-development` |
| Migration sở hữu trong task | `deprecation-and-migration` |
| Browser/a11y harness | `browser-testing-with-devtools` |
| CI, performance, observability hoặc semantics CLI/provider | Skill chuyên môn tương ứng |
| Fix sau audit | Thêm `debugging-and-error-recovery` |
| Auditor/Integrator review | `code-review-and-quality` và các skill review liên quan |

Mọi task giữ `git-workflow-and-versioning` cho diff/branch an toàn và
`documentation-and-adrs` cho bookkeeping bắt buộc. Task chỉ sửa tài liệu không bị
buộc làm TDD. Chọn theo file task sở hữu, title/goal và acceptance criteria; không
chọn theo số Txxx hoặc boilerplate references tới API/UI/security trong mọi card.

Run mới lưu `00-skills.json` gồm task digest, danh sách theo phase, lý do chọn,
đường dẫn thật và SHA256 của từng `SKILL.md`. Prompt Engineer được cung cấp policy;
Python bảo đảm khối `REQUIRED AGENT SKILLS` có trong Plan/Worker và Fix handoff đã
lưu, kể cả khi model quên thêm. Worker đọc file và áp dụng workflow; Auditor xem
bằng chứng trong code/tests và các trường JSON hiện có. Một lời khai "đã dùng skill"
không chứng minh skill thực sự được áp dụng. Không thêm field JSON ngoài schema.

Headless dùng đường dẫn file trực tiếp, không phụ thuộc slash commands bị tắt ở
agy; không nạp toàn bộ pack hay meta-router. Chỉ đọc supporting references khi cần.
Skill không được mở rộng allowlist, tiêu chí, threshold, Git quyền hạn hoặc yêu cầu
sản phẩm; Worker vẫn không được commit/merge và không dừng để chờ review khác model
chỉ vì skill gợi ý. Task-owned tests/tools và chỉ dẫn chủ repo có ưu tiên.

Skill bắt buộc thiếu/không đọc được hoặc entrypoint thay đổi giữa run là
`SETUP_FAILED`; phải sửa setup, không giả vờ đã sử dụng. Manifest pin entrypoint,
không pin toàn bộ supporting references. Không sửa manifest/prompt/hash bằng tay.
Config và run cũ vẫn đọc được; run đã planning trước tính năng này giữ nguyên
handoff lịch sử, không bị tự viết lại. Run FAILED cũ không được mở lại.

### Quyền Worker GPT và Gemini qua agy

Worker Antigravity mặc định trong `orchestrator.yaml`:

```json
"worker": {
  "provider": "agy",
  "executable": "agy",
  "model": "gemini-3.8-flash-high",
  "reasoning": "high",
  "worker_access": "workspace-write",
  "allow_process": true
}
```

`allow_process: true` truyền `--dangerously-skip-permissions` cho Worker: tự duyệt
các yêu cầu tool/process trong phiên, tương ứng nhu cầu Allow Processes khi chạy
tự động. Cờ này duyệt cả các tool khác, không chỉ terminal. Công cụ không ghi
`/config`, settings hay credentials toàn máy. `agy` chạy ở `accept-edits`; các
vai trò chỉ đọc chạy `plan` và không nhận cờ bỏ duyệt. CLI vẫn tự quản lý đăng nhập
và quyền sử dụng model; orchestrator không có fallback provider tự động.

Adapter truyền prompt qua stdin pipe với `--input-format text --output-format json`,
`--json-schema <file>`, `--mode` và `--disable-slash-commands`. Trong agy1.2.14,
stdin pipe tự kích hoạt headless; không ghép `--print` không có giá trị trước cờ
khác vì CLI sẽ lấy nhầm cờ làm prompt. Đã kiểm tra cách truyền stdin bằng `/help`,
changelog xác nhận lệnh này không tạo agent turn/tiêu quota. Adapter đọc response
JSON hoặc structured_output, từ chối error/denied_actions và kiểm tra schema.
`--model` và `--effort` được kiểm tra qua help, reasoning hỗ trợ low/medium/high.
Timeout Python tiếp tục giới hạn toàn bộ tiến trình và các tiến trình con.

Để chuyển rõ sang Worker GPT/Codex với full access, thay riêng mục `worker`:

```json
"worker": {
  "provider": "codex",
  "executable": "codex",
  "model": null,
  "reasoning": "high",
  "worker_access": "full-access",
  "allow_process": false
}
```

`model: null` dùng model Codex đã cấu hình; có thể nhập tên model thực tế của bạn.
`worker_access: full-access` truyền `--sandbox danger-full-access`, vẫn dùng
`-a never` để không chờ hỏi duyệt. Mặc định cũ workspace-write vẫn được hỗ trợ.
Chỉ Worker được cấu hình quyền nâng cao; Prompt Engineer/Auditor/Integrator bị từ
chối nếu cấu hình full-access hoặc allow_process. Những quyền này không giới hạn
OS vào worktree: chỉ chạy agent cục bộ bạn tin cậy. Contract, kiểm tra scope,
source/evidence, audit và khóa tích hợp vẫn được thực thi.

Đổi provider/quyền áp dụng cho run mới. Resume một run đang tiến triển yêu cầu
cấu hình khớp cấu hình đã lưu. Với lỗi route Gemini CLI exit1 cũ, `run`/`retry`
có thể tạo run mới sau khi Worker đã được chuyển rõ sang agy và xác minh toàn bộ
run sở hữu worktree đều failed, không có stdout, không timeout, log còn hash,
source/history/artifacts nguyên vẹn và chưa triển khai/tích hợp. Đây là khởi tạo
lại từ main, không tiếp tục Worker outcome chưa biết hoặc sửa JSON cũ. Crash cùng
provider hoặc worktree có thay đổi vẫn cần kiểm tra và giữ nguyên công việc.

Riêng lỗi cũ `agy lacks required capability: --print` do kiểm tra help sai kênh,
`run`/`retry` được tạo lần thử mới khi worktree vẫn sạch tại base, task/plan/contract
còn nguyên vẹn, prompt/schema khớp và chưa có log/response/result Worker. Giữ nguyên
run cũ và chạy lại baseline/planning; không sửa state FAILED hoặc replay outcome
không xác định. Lỗi thực thi khác không được coi là lỗi pre-dispatch này.

Cấu hình còn quản lý `base_branch` (mặc định là main cục bộ), `max_fix_cycles` (0–10),
`timeout_seconds` (mặc định `null`), các lệnh kiểm tra bắt buộc dưới dạng mảng đối số,
`setup_commands`, thư mục gốc của run/worktree và `integrate`. Bước chuẩn bị mặc định
chạy `npm ci` riêng trong mỗi worktree task và bản tích hợp thử sau merge; công cụ
Python/phát triển được kế thừa từ môi trường gọi lệnh. Bước chuẩn bị của Level 1 chỉ
chấp nhận lệnh cài đặt chuẩn này của repository. Lỗi dependency hoặc chuẩn bị môi
trường khiến quá trình dừng với bằng chứng rõ ràng; không gọi trình cài đặt chưa
được kiểm tra.

Thư mục run phải nằm trong repository và được Git bỏ qua; worktree phải nằm bên
ngoài repository. Đường dẫn tương đối được tính từ checkout chính, không phải
worktree của nơi gọi lệnh. Thư mục worktree mặc định là `../english_web-worktrees`;
không có đường dẫn riêng của máy được ghi cứng. Gate mặc định gồm
`npm run check:task:portable`, Ruff và Mypy.

Portable baseline giữ fast checks, frontend coverage, Python suite, changed/total
coverage, security (secrets/code/dependencies) và architecture gate. Script
`npm run check:task:portable` ủy quyền cho mode `portable-task` trong
`.agent/scripts/run-gates.sh`. Runner thực thi theo đồ thị phụ thuộc hai pha:
Phase A chạy song song 7 gate độc lập (`check:fast:active`, `test:frontend:coverage`,
`test:python:portable`, `security:secrets`, `security:code`, `security:deps`,
`architecture:check`), sau đó đồng bộ chờ tất cả tiến trình con hoàn tất và thu
dọn exit status. Phase B chỉ chạy `coverage:check` sau khi cả hai producer
(frontend và Python coverage) cùng toàn bộ Phase A thành công. Nếu bất kỳ gate nào
trong Phase A thất bại, runner dừng fail-closed, hiển thị log và không thực thi Phase B.
Lệnh Python `python -m pytest --ignore=backend/tests/windows -n 10` chỉ loại thư mục
native-Windows với 10 worker xdist đã được repository phê duyệt. Không đổi
cấu hình pytest toàn cục hay threshold.

`check:task`, `check:task:active` và `check:full` giữ nguyên Python suite đầy đủ,
gồm native-Windows tests fail-closed trên Linux/WSL. Portable baseline chỉ phục vụ
admission và verification portable; task yêu cầu Windows vẫn cần genuine
native-Windows acceptance evidence. Lỗi có sẵn trên baseline sẽ chặn lần chạy thật
cho đến khi được sửa trong phạm vi đã cho phép; lỗi đó không bao giờ được gọi là
PASS. Tích hợp mặc định tắt, vì việc cài hạ tầng không đồng nghĩa với cho phép các
lần merge sau này.

T081 tách `Verification commands` khỏi `Snapshot results` lịch sử. Revalidation
của dependency này chỉ thêm bốn lệnh: AppShell focused tests, TypeScript,
frontend architecture và diff integrity. Snapshot giữ nguyên kết quả lịch sử,
kể cả coverage với `QUALITY_BASE_REF`, E2E/A11y và native-Windows inherited
failure; không đưa toàn bộ snapshot vào `card.dependency_verification`.
Pipeline vẫn chạy dependency checks cộng với baseline cấu hình, nên coverage và
security được kiểm tra ở repository baseline mà không cần lặp lại trong T081.

## Cách sử dụng

```bash
python -m tools.orchestrator run T018 --dry-run
python -m tools.orchestrator run T018 --no-integrate
python -m tools.orchestrator status T018
python -m tools.orchestrator resume T018 --run-id <recorded-run-id>
# Cho phép tích hợp task này vào nhánh cục bộ khi checkout đích đã sẵn sàng:
python -m tools.orchestrator resume T018 --integrate
# Tạo lần chạy mới sau lỗi đã được sửa, nếu lần cũ dừng trước Worker:
python -m tools.orchestrator retry T059 --no-integrate
# Chọn chính xác lần thất bại có worktree cần đối chiếu:
python -m tools.orchestrator retry T059 --run-id <recorded-run-id> --no-integrate
```

### Thời gian chạy: mặc định chờ đến khi hoàn thành

Trong `orchestrator.yaml` (dùng cú pháp JSON), mặc định là:

```json
"timeout_seconds": null
```

Bỏ hẳn trường này cũng có cùng kết quả. Agent của cả bốn vai trò, bước `npm ci`
và các lệnh verification không bị orchestrator dừng chỉ vì chạy lâu. Muốn tự đặt
thời hạn, thay bằng số nguyên từ 1 đến 86400; ví dụ `"timeout_seconds": 5400` là
90 phút cho **mỗi lần gọi/lệnh**, không phải tổng thời gian task. `0`, số âm,
chuỗi hoặc boolean đều không hợp lệ; dùng `null` để tắt timeout.

Không giới hạn thời gian đồng nghĩa tiến trình bị treo có thể chờ mãi; dùng Ctrl+C
khi cần dừng. Giới hạn output, xử lý exit khác 0, số vòng Fix và khóa tài nguyên
vẫn áp dụng. Các thao tác quản trị ngắn như Git (60 giây), kiểm tra CLI help/version
(30 giây) và dọn cây tiến trình vẫn có giới hạn riêng. Deadline của AI trong ứng
dụng không thay đổi. CLI/provider có thể tự kết thúc do lỗi hoặc giới hạn riêng;
agy mặc định `--print-timeout` là 0 (không giới hạn).

Run lưu một bản cấu hình tại thời điểm bắt đầu. Đổi tệp cấu hình chỉ áp dụng cho
run mới; không thay timeout của run đang chạy, không mở lại run FAILED và không
sửa bằng chứng cũ. Run cũ có timeout số nguyên vẫn đọc được và giữ thời hạn đó;
resume tại điểm ổn định yêu cầu cấu hình khớp bản đã lưu.

Dùng `--config <path>` để chọn tệp cấu hình khác. Status/resume chọn lần chạy mới
nhất đã lưu, trừ khi có `--run-id`. Mã thoát 0 nghĩa là thao tác yêu cầu đã thành
công, kể cả khi đang ở AUDIT_PASS chờ tích hợp; không nhất thiết là DONE. Mã thoát
2 nghĩa là từ chối thực hiện, BLOCKED hoặc FAILED. Ctrl+C trước khi pipeline tiếp
nhận tác vụ trả về 130; ngắt trong một giai đoạn sẽ ghi FAILED và trả về 2.

Dry run đọc bằng chứng từ task, phụ thuộc, cấu hình và Git, rồi in bản gốc, branch,
worktree, phân công vai trò, các kiểm tra và luồng dự kiến. Nó không tạo tệp kết quả
hay worktree, không gọi LLM và không thay đổi trạng thái Git. Nhánh gốc cục bộ được
cấu hình phải chứa commit hạ tầng này cùng các công cụ cần thiết; gọi từ checkout
khác không tự đưa source vào worktree task mới. Hãy tích hợp hạ tầng đã review theo
quy trình của repository trước khi chạy task thật trên nhánh gốc đó.

Chạy thật yêu cầu checkout chính sạch và thư mục runtime được Git bỏ qua. Nếu task
đã có worktree, kể cả branch task được tạo thủ công, công cụ sẽ từ chối; hãy kiểm
tra hoặc tiếp tục lần chạy hiện có thay vì ghi đè. Lỗi trùng worktree được từ chối
trước khi tạo run mới, tránh bản ghi BLOCKED rỗng che mất lần có worktree thật.
Worktree đã hoàn thành nhưng còn
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
hợp đã bắt đầu, trạng thái chuyển sang FAILED để giữ nguyên kết quả chưa xác định,
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
của nó. T073 bỏ trạng thái BLOCKED khỏi luồng mới. Lỗi thực tế không phục hồi
được kết thúc bằng FAILED (exit khác0), không được gọi là DONE. BLOCKED chỉ còn
được đọc để tương thích bằng chứng lịch sử; chuyển trạng thái không hợp lệ vẫn bị từ chối. Contract không được
nới lỏng tiêu chí hay kiểm tra, mở rộng đường dẫn hoặc tự đưa ra lựa chọn sản phẩm
mới. Lỗi capability/phạm vi, kiểm tra thất bại hoặc tích hợp không an toàn vẫn chặn
quá trình; không có danh sách human gate do model tạo để phủ quyết planning.

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
kết quả chưa xác định: resume ghi FAILED thay vì thực hiện lại thao tác thay đổi.
Hãy kiểm tra báo cáo cuối/lỗi, tệp kết quả từng vòng, Git index/lịch sử, worktree
của bản tích hợp thử và các tiến trình CLI còn sống trước khi phục hồi thủ công.
Không thể tự xóa BLOCKED hay chỉnh state để giả vờ đã kiểm tra. Bằng chứng trước
đó không bị âm thầm ghi đè.

T073 tự thử tối đa ba lần cho một lần gọi agent thất bại hoặc output/planning
không hợp lệ, chỉ khi source/history, state và các handoff vẫn bất biến. Mỗi lần
có tên artifact riêng; log thất bại/Plan bị từ chối được băm, không ghi đè. Không
đổi provider/model hoặc gọi lại một Worker đã sửa source rồi crash. Worker/Auditor
báo BLOCKED được đưa vào vòng Fix hiện có (mặc định tối đa ba vòng); tiêu chí,
phạm vi, test và audit vẫn phải đạt trước tích hợp. Lỗi thật hết số lần thử trả
FAILED cùng báo cáo cuối. Số lần gọi agent có thể tăng; giới hạn áp dụng cho từng
lần gọi, tách khỏi số vòng sửa code. Không retry application AI.

### Quy ước báo cáo Auditor và sửa JSON

`findings` chỉ chứa lỗi còn tồn tại cần xử lý. Bằng chứng đạt, kết quả lệnh và giới
hạn kiểm tra được ghi vào `acceptance_criteria[].evidence`. Mỗi tiêu chí ban đầu
phải xuất hiện đúng một lần, nguyên văn. Báo cáo PASS cần mọi tiêu chí PASS và
`findings`, `scope_violations`, `required_fixes` đều là danh sách rỗng.

Nếu báo cáo mâu thuẫn (ví dụ PASS nhưng ghi kết quả test đạt vào `findings`),
Python lưu JSON bị từ chối thành `NN-auditor-ID.rejected.json`, băm artifact và
gửi lại lỗi kiểm tra cùng báo cáo để Auditor sửa. Tổng cộng tối đa ba lượt trả
báo cáo trong một lần gọi, dùng cùng source/contract/bằng chứng; không tăng
`fix_cycle` hay gọi thêm Worker. Báo cáo FAIL hợp lệ vẫn vào vòng sửa code thông
thường. Python không tự xóa findings hoặc đổi trạng thái thành PASS.

Lệnh kiểm tra thất bại không thể được báo PASS. Source, lịch sử Git, state,
handoff hoặc báo cáo đã lưu bị sửa sẽ khiến quá trình dừng; JSON vẫn không hợp
lệ sau ba lượt thì run kết thúc FAILED và giữ bằng chứng. Thay đổi này áp dụng
khi gọi Auditor, không tự phục hồi hay viết lại run lịch sử đã FAILED sau khi
Worker triển khai (như lỗi `Contradictory audit PASS` cũ).

- `run`: bắt đầu task mới; nếu có run ổn định thì tự tiếp tục. Nếu lần cũ thất bại
  trước triển khai đủ bằng chứng, tự tạo run/worktree mới để thử lại.
- `resume`: tiếp tục chính run ở điểm ổn định. Không sửa state kết thúc cũ.
- `retry`: yêu cầu rõ lần thử mới; giữ nguyên run/worktree/branch và log trước đó.

Retry nhận FAILED mới hoặc BLOCKED lịch sử đã được chứng minh dừng trước Worker,
worktree sạch, HEAD đúng SHA gốc, task và các artifact đã băm không đổi. Khóa task/
run vẫn từ chối agent sống; mọi worktree giữ lại phải có chủ sở hữu được quản lý.
Có một ngoại lệ hẹp cho Gemini CLI0.59.0 exit55: lỗi untrusted-workspace diễn ra
trước inference/tool dispatch. Phải có log Worker providerGemini, exit55 không
timeout/oversized, không stdout, đúng cwd; chưa có Worker result/audit/integration,
contract đã băm và toàn bộ source phải khớp baseline sạch. Log mới được niêm phong;
log phiên bản cũ chưa được băm được đọc theo metadata lịch sử cùng các điều kiện
nguồn/contract trên. Không suy đoán mọi mã lỗi Worker là an toàn để gọi lại.

Lỗi planning do human_gates của phiên bản cũ vẫn retry được nếu bằng chứng đạt.
Lần mới chạy lại baseline và tạo Plan mới, không phát lại prompt cũ bị chặn.

Không truyền `--run-id` thì retry chọn run có worktree thật mới nhất và bỏ qua bản
ghi trùng rỗng từ phiên bản cũ. Status/resume vẫn chọn bản ghi mới nhất: cần chỉ định
ID thật khi bản ghi rỗng còn tồn tại. State mới có `retry_of`, artifact `retry_origin`
ghi SHA/state digest và các worktree giữ lại; `blocked_from` ghi giai đoạn thất bại.
State cũ chưa có hai trường này vẫn đọc được; retry chỉ nhận lỗi baseline/setup
hoặc contract/planning đã biết nếu các bằng chứng khác đầy đủ. Plan/Contract cũ có
`human_gates` được kiểm tra và chuyển trong bộ nhớ; file/digest gốc giữ nguyên.
Contract mới không xuất trường này và model trả nó trong output mới sẽ lỗi schema.
Dùng controller đã cập nhật
để đọc state mới; controller cũ kiểm tra schema nghiêm ngặt có thể từ chối trường mới.

Retry không sửa lỗi môi trường, không bỏ baseline và không hứa chạy lại mọi lỗi.
Nếu Worker đã triển khai hoặc có kết quả chưa rõ (ngoài exit55 đã kiểm chứng),
source/history thay đổi, bằng chứng bị sửa hoặc
merge chưa rõ kết quả, nó từ chối và giữ nguyên công việc để review. Khôi phục thủ
công trong các trường hợp này cần quyết định có căn cứ, không sửa state để ép chạy.
Run/worktree cũ được giữ để kiểm toán nên dung lượng tăng qua mỗi retry; chỉ dọn
thủ công sau khi đã kiểm tra và lưu bằng chứng. Retry không có chế độ dry-run.

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
bảo mật trước agent cục bộ độc hại**, đặc biệt với Gemini Worker `yolo`. Chỉ chạy agent
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

Level 1 chạy đồng bộ trong từng task, dùng JSON để lưu trạng thái, ba admission
slots và tích hợp tuần tự. T079 bổ sung pool process và lập lịch DAG phía trên
Pipeline, giữ nguyên contract của các vai trò. Không có cơ sở dữ liệu scheduler,
dashboard, khóa phân tán hay resume chạy nền. Resource-aware scheduling và cơ chế
cô lập mạnh hơn thuộc giai đoạn hạ tầng sau.
