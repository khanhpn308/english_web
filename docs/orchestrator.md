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
| Tạo run mới để audit lại candidate đã đóng băng từ FAILED/AUDIT_RUNNING | `python -m tools.orchestrator recover-candidate T089 --run-id SOURCE_RUN_ID --expected-source-digest SHA256 --no-integrate` |
| Nhập candidate đã thẩm định từ ngoài vào run mới có thẩm quyền | `python -m tools.orchestrator import-candidate T089 --run-id SOURCE_RUN_ID --source-worktree PATH --expected-source-digest SHA256 --provenance-manifest PATH --expected-provenance-digest SHA256 --no-integrate` |
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

## T086: parallel read-only review trong một task

Phần này mô tả protocol T086; T087 bên dưới thay đổi thời điểm dispatch trong audit cycle.
Sau Worker/Fix Worker và executable audit checks, Pipeline chạy ba advisory reviewer
song song, rồi mới gọi authoritative Auditor:

```text
Worker -> executable evidence -> correctness-contract-concurrency      ┐
                             -> verification-failure-regression       ├-> bundle -> Auditor
                             -> security-architecture-scope-privacy    ┘
```

Các reviewer dùng chính cấu hình role `auditor`, kể cả provider, model, reasoning
và timeout; không cần thêm provider entry. Đổi auditor model cho run mới tự áp dụng
cho cả ba perspective. Worker/Fix Worker vẫn là writer duy nhất. Reviewer không
được spawn nested agents hoặc quyết định task PASS/FAIL.

`ThreadPoolExecutor` chỉ gọi `AgentProvider.run(..., readonly=True)`; không gọi
`Pipeline.invoke()` concurrently vì method đó thay đổi RunState và authority.
Parent kiểm tra contract/artifact/skills, cố định Git source digest và branch,
đối chiếu source digest của executable evidence, tạo cả ba prompt rồi mới dispatch.
Mỗi call có prefix perspective/cycle và UUID đầy đủ cho prompt/schema/log/response.
Parent ghi `current_agent=parallel_review` một lần trước dispatch; threads không
nhận RunState và không gọi `save()` hoặc `artifact()`.

Parent join/reap tất cả futures, kể cả khi có shard thất bại. Sau join, source,
branch, in-memory state, `state.json`, các file run đã có và skill manifest phải
khớp snapshot. Mutation bị từ chối; source lỗi được giữ lại để điều tra, không tự
rollback. Provider là trusted local CLI: đây là kiểm tra sau thực thi, không phải
OS isolation trước tiến trình độc hại hoặc mutation rồi hoàn nguyên giữa hai lần
kiểm tra. Timeout/output limit/process-tree recovery giữ nguyên từ runtime.

Khi protection checks đạt, chỉ parent đăng ký/băm các file reviewer theo thứ tự
perspective rồi filename. `ReviewBundle` được ghi nguyên tử và đăng ký sau khi
cả ba shard thành công. Kết quả và lỗi được xử lý theo declaration order, không
theo completion order. Host gán finding ID `<perspective>:<ordinal bốn chữ số>`;
reviewer không được cung cấp ID. ID có phạm vi bundle của source/cycle hiện tại.
Bundle parser từ chối perspective thiếu/trùng/sai thứ tự và ID ngoài host order.

Final Auditor nhận task/contract, Worker result, executable evidence và toàn bộ
bundle. `Audit.reviewer_dispositions` mặc định `[]` để đọc historical Audit không
có bundle. Khi có bundle, mỗi finding phải được disposition đúng một lần bằng ID:
`confirmed` nghĩa là unresolved trong frozen source và cấm PASS; `dismissed`
cần rationale/evidence cụ thể, không được rỗng hoặc chỉ whitespace. Python từ
chối missing/unknown/duplicate dispositions và confirmed finding + PASS. Sửa
Audit JSON vẫn tối đa ba lượt trên cùng bundle/source, không lặp lại reviewer hoặc
Worker. Findings confirmed phải đi qua fix cycle hiện có trước audit tiếp theo.

Shard process failure, timeout, output limit, malformed/schema-invalid response,
sai perspective hoặc source/branch/protected-evidence mutation khiến toàn phase
FAILED; không tạo partial bundle và không gọi authoritative Auditor. Fan-out không
retry; diagnostic files được giữ, và được đăng ký khi protection checks đạt.
Level 2 giữ tối đa ba task; T086 có thể tạo tối đa chín advisory calls khi cả ba
task cùng audit. Global resource arbitration thuộc task khác.

Behavioral tests dùng barrier ba bên và event chain, buộc cả ba provider active
trước khi completion theo thứ tự security -> verification -> correctness. Đây là
proof concurrency với logical rounds, không đo tốc độ model/internet. Local CLI
fixtures còn chứng minh exit 7, timeout, oversized output và malformed JSON đi qua
runtime thật. Chưa benchmark T023; không có claim speedup thực tế. Protocol mới
yêu cầu fake/custom providers hỗ trợ `ReviewShard` ngoài các output trước T086.

## T087: concurrent audit preparation

Audit cycle hiện chạy executable verification đồng thời với ba reviewer T086 để
che latency kiểm tra sau thời gian static review, giữ toàn bộ verification và một
parent writer duy nhất:

```text
Worker/Fix Worker -> freeze candidate -> executable verification (commands sequential) ┐
                                     -> correctness-contract-concurrency              │
                                     -> verification-failure-regression               ├-> parent fan-in -> Auditor
                                     -> security-architecture-scope-privacy            ┘
```

Parent kiểm tra contract, authoritative artifacts và skills; freeze Git source digest,
branch, RunState và các file run đã có; chuẩn bị cả ba prompt rồi ghi
`current_agent=concurrent_audit_preparation` đúng một lần trước dispatch. Frozen
`VerificationRequest` chứa cwd, tuple command arrays, timeout, source digest và task ID;
không chứa RunState, Pipeline hay thư mục artifact. Function `collect_verification()`
chỉ chạy commands tuần tự và trả redacted metadata với `command_index` theo declaration
order. Nó không save state, transition, gọi `artifact()` hay đăng ký evidence. Existing
`verify()` tiếp tục dùng tuần tự cho setup/baseline/integration. Existing
`parallel_review()` vẫn hỗ trợ T086 entrypoint với executable evidence đã hoàn tất;
production audit cycle dùng `concurrent_audit()` và shared protected fan-in.

Một executor bốn threads dispatch một verification future và ba provider futures.
Reviewer vẫn dùng configured auditor role, read-only, unique names và canonical
perspectives T086, và inspect trực tiếp original frozen task worktree.
Executable verification chạy trong một host-owned temporary Git verification workspace
riêng biệt (`verification_workspace`), materialize từ repository detached tại `base_sha`.
Để tái tạo chính xác cả trạng thái Git index lẫn working tree mà không làm xáo trộn (collapse)
hai tầng nội dung:
1. Host clone repository bằng `--shared --no-checkout` và checkout detached tại `base_sha`.
2. Host trích xuất staged patch qua `git diff --cached --binary base_sha --`, kiểm tra `safe_path`
   cho từng đường dẫn, rồi áp dụng bằng `git apply --binary --index` để tái tạo đúng trạng thái index.
3. Host trích xuất unstaged patch qua `git diff --binary --`, kiểm tra `safe_path`, và áp dụng bằng
   `git apply --binary` lên working tree mà không stage vào index.
4. Host truy vấn các non-ignored untracked files qua `git ls-files --others --exclude-standard -z`,
   sao chép nguyên vẹn nội dung byte và quyền thực thi (`chmod`), giữ nguyên ở trạng thái untracked
   (không gọi `git add`).
5. Trước khi dispatch, host bắt buộc chứng minh:
   `Git(verification_workspace).snapshot(base_sha) == frozen_source_digest`.
   Nếu không tương đương tuyệt đối, host fail closed ngay trước khi dispatch.

Về an toàn toolchain và kiến trúc Private Toolchain Materialization (R3 & R4):
- Độc lập kiểm toán R3 đưa ra kết luận `NEEDS_REMEDIATION`: phát hiện lỗi HIGH do việc giữ lại symlink tệp hệ thống ngoại vi dẫn tới write-through (`sandbox/node_modules/pkg/link.js -> host_toolchain/external.js`), cho phép ghi từ sandbox làm biến đổi tệp trên host, vi phạm bất biến private sandbox filesystem.
- Quyết định kiến trúc R4 — Bất biến an ninh NO WRITABLE EXTERNAL BACKLINKS:
  1. Thư mục đích sandbox `node_modules` và `.venv` là thư mục thật (`is_dir() and not is_symlink()`). Do đó `node_modules/..` phân giải tuyệt đối về chính `verification_workspace`, không thể thoát về authoritative worktree.
  2. Sao chép nội dung bằng tệp thật (copy, không dùng hardlink). Mọi symlink nội bộ bên trong toolchain nguồn được tái tạo thành relative symlink trỏ tương đối bên trong private sandbox toolchain mới.
  3. Chính sách symlink ngoại vi:
     - Mọi external directory symlink: FAIL CLOSED trước dispatch (`OrchestratorError: Unsafe external directory symlink in toolchain`).
     - Mọi external regular-file symlink trong `node_modules` (hoặc tệp không phải interpreter trong `.venv`): FAIL CLOSED trước dispatch (`OrchestratorError: Unsafe external file symlink in toolchain`), ngăn chặn triệt để hành vi write-through ra host.
     - Virtualenv interpreter trong `.venv`: materialize thành bản sao executable độc lập riêng bên trong sandbox (`shutil.copy2`), bảo toàn quyền thực thi `0o755`, bảo toàn `pyvenv.cfg`/site-packages (`import pytest` thành công), và triệt tiêu hoàn toàn backlink ra host.
  4. Post-materialization containment validation: duyệt đệ quy toàn bộ symlink trong thư mục đích sau khi copy, xác nhận mọi symlink đều phân giải về đối tượng tồn tại bên trong chính thư mục đích; bất kỳ symlink nào trỏ ra ngoài hoặc dangling đều fail closed ngay lập tức.
  5. Mọi lỗi đọc, stat, lstat, scandir hoặc resolution trong quá trình validate/copy toolchain đều fail closed (`OrchestratorError`), không có nhánh fail-open.
- Khám phá authoritative roots (`Pipeline.authoritative_roots`): sử dụng định dạng lossless `git worktree list --porcelain -z` tách bằng ký tự NUL (`\0`), bảo toàn chính xác các đường dẫn chứa khoảng trắng đầu/cuối (không dùng `.strip()`), và fail-closed khi Git gặp lỗi hoặc bản ghi malformed.
- Môi trường chạy verification command: loại bỏ hoàn toàn launcher shell script và proxy python. Không thay đổi `runtime.py` hay mutate `os.environ` toàn cục. Host điều khiển qua argv an toàn `/usr/bin/env PATH=... <command...>` (hoặc tương đương platform không shell parsing), ưu tiên `verify_path/.venv/bin` và `verify_path/node_modules/.bin` trước `PATH` thừa kế. Metadata báo cáo giữ nguyên tên command gốc (`python`, `npm`), không báo cáo nhầm `env`.
- Cả `node_modules` và `.venv` đều được loại trừ trong `.git/info/exclude` của verification workspace.
- Trạng thái hiện tại: `R4 IMPLEMENTATION_READY PENDING INDEPENDENT RE-AUDIT`; không tuyên bố `PASS_FOR_INTEGRATION` và không tuyên bố speedup thực tế T023.

Prompt reviewer chỉ chứa frozen task/contract/Worker/skill context và yêu cầu
`STATIC REVIEW ONLY`; không có kết quả audit checks. Nhờ private toolchain materialization,
không gian làm việc và tệp phụ thuộc được phân lập hoàn toàn; các transient artifacts do verification
sinh ra (như `.pytest_cache/transient`, coverage, build artifacts) hoàn toàn nằm trong temporary
workspace và không thể bị reviewer quan sát trong reviewer worktree. Ignored generated output không
thể lọt vào ReviewShard hay ReviewBundle.

Parent reap tất cả futures dù một lane thất bại, rồi đối chiếu original worktree source/branch,
in-memory state, state.json, protected artifacts/prompts và skill manifest. Đồng thời, host kiểm tra
sandbox source integrity sau khi chạy lệnh: candidate source trong verification workspace phải tiếp tục
khớp `frozen_source_digest`; mọi sửa đổi vào tracked source, non-ignored untracked source hay file mode
đều fail closed.
Khi integrity đạt, parent persist/register `audit_checks` trước reviewer diagnostics, theo perspective
rồi filename. Chỉ khi cả ba reviewer hợp lệ và verification không gặp setup failure mới assemble/register
complete ReviewBundle. Temporary verification workspace được dọn dẹp sạch sẽ sau khi lane kết thúc
mà không bao giờ xóa task worktree hay branch. Auditor chạy tuần tự qua `Pipeline.invoke()` sau khi cả hai
loại evidence đã authoritative và concurrent-phase marker đã clear. Không dùng concurrent `invoke()`
hay mutable `verify()`; threads không nhận state authority.

Nonzero exit, timeout và oversized result vẫn là task regression: collector giữ evidence
và dừng tại command lỗi đầu tiên như `verify()` hiện có. Reviewers tiếp tục được reap,
Auditor có thể báo FAIL, và Python từ chối PASS trên failed executable evidence; bounded
correction vẫn tối đa ba attempts trên cùng evidence. Execute infrastructure exception
vẫn `SETUP_FAILED`, giữ partial metadata khi có và ngăn final Auditor sau khi join mọi
reviewer. Reviewer process/schema/perspective failure cũng ngăn bundle/Auditor; diagnostics
được giữ và đăng ký khi integrity đạt. Finding IDs, disposition rules và historical Audit
compatibility giữ nguyên T086.

Behavioral tests dùng barrier bốn bên trong fake executable call và ba provider calls,
Lock đếm tối đa bốn active lanes, Events buộc verification-first hoặc reviewers-first
và reverse reviewer completion. Cả hai ordering đều chứng minh Auditor chờ cả hai lanes;
parent-thread guards bảo vệ invoke/save/artifact/verify, với max active invoke bằng một.
Adversarial probe tests chứng minh: transient file `.pytest_cache/transient` được tạo trong
verification cwd nhưng reviewer không thấy trong reviewer cwd; ReviewShard, ReviewBundle và
Auditor prompt không chứa transient evidence; source finding IDs hoàn toàn ổn định (`:0001`)
ở cả hai thứ tự hoàn tất (verification trước hoặc reviewer trước) và không bị trượt sang `:0002`.
Tests dùng fake commands/providers, không network/inference hoặc arbitrary sleep làm proof.
Đây là bằng chứng overlap và evidence isolation, chưa là real-task/T023 wall-clock benchmark. Vì mỗi task có thêm
một executable lane overlap inference, CPU/I/O có thể cạnh tranh giữa ba task đang audit;
T087 giữ nguyên admission/scheduler concurrency, gate commands/thresholds và max_fix_cycles.
Resource arbitration thuộc task sau. Post-execution integrity checks vẫn không thay thế
OS isolation hoặc phát hiện mutation rồi hoàn nguyên giữa hai snapshot.

## T088: Deterministic Evidence Collection và EvidenceBundle

Status: `DONE`. Authoritative host verification PASS: EvidenceBundle focused 21 passed; concurrent_audit 43 passed; parallel_review 25 passed; scheduler 48 passed; full orchestrator 398 passed; Ruff, Ruff format, Mypy and `git diff --check` PASS.

The independent T088 semantic audit returned `NEEDS_REMEDIATION` with two HIGH findings and one MEDIUM finding:

- HIGH: verification evidence could be rebound to another candidate source.
- HIGH: a successful prefix could claim PASS without executing the complete required declaration.
- MEDIUM: command duration affected semantic equality and used wall-clock subtraction.

R1 addresses these defects within the existing host evidence path. `FrozenEvidenceIdentity` carries `task_id`, `base_sha`, `branch`, `source_digest` and the ordered `required_command_digests`. The parent freezes it before verification dispatch, the detached request validates its argv against it, and the collection retains it. Bundle construction compares freshly collected provenance against this identity and rejects differences. The workflow accessor validates base SHA, branch and the current candidate's source digest, plus task identity.

Each declaration digest is SHA-256 over the UTF-8 compact JSON argv array, with `ensure_ascii=False` and comma/colon separators. Results retain that digest and a display containing only the executable basename and withheld-arguments marker. PASS requires every declared command in exact order. An explicit failed prefix remains valid FAILED evidence through its first failing command. A successful prefix, reordered results, substituted declarations or missing mandatory exit/timeout/oversize/output digest/byte-size metadata fail closed. Setup failures remain failed collection evidence and cannot form a complete bundle.

Every bundle artifact reference carries the same typed frozen identity. For `audit_checks`, validation also checks the artifact's existing `source_digest` and exact execution result prefix against the bundle. Historical `audit_checks` fields and result metadata remain unchanged. The authoritative bundle metadata supplies the declaration association for those historical records; validators do not rewrite them or synthesize missing execution metadata.

Command duration now measures `time.monotonic_ns()` around host execution. Wall-clock start/end strings remain historical metadata and do not determine duration. `semantic_payload()` excludes the entire top-level timing object and every command's `duration_ns`. Artifact hashes still represent the exact referenced bytes.

Focused local regression tests cover these fixes. Host verification, T086/T087 regressions and scheduler/full-suite checks remain pending. R1 introduces no reviewer protocol, provider call, arbitrary command interface or T089 behavior.

T088 thiết lập tầng bằng chứng xác định (deterministic host evidence) do host / control plane sở hữu, tách biệt hoàn toàn việc thu thập, kiểm tra, chuẩn hóa và đóng gói bằng chứng cơ học khỏi vòng lặp suy luận của AI:

```text
HOST / DETERMINISTIC CONTROL PLANE
        |
        +-- candidate provenance (HEAD, staged index, unstaged WT, untracked)
        +-- Git / changed-path evidence & allowlist scope verdict
        +-- executable verification evidence (exit codes, digests, failure metadata)
        +-- artifact integrity references (safe relative paths, SHA-256, byte sizes)
        +-- monotonic timing (diagnostics only)
        |
        v
VERSIONED EvidenceBundle (schema_version = 1)
        |
        v
AI semantic/adversarial reasoning (T089+)
```

### Nguyên tắc kiến trúc và ranh giới thẩm quyền
- **Nguyên tắc cốt lõi:** Nếu tính đúng đắn có thể xác định từ exit code, trạng thái Git/filesystem, mã băm (hashes), schema validation, deterministic parsing hoặc predefined tests, AI **tuyệt đối không tham gia** vào execution hoặc decision loop đó.
- **Host-only execution:** Toàn bộ quá trình thu thập evidence thực thi hoàn toàn trong logic tiến trình host Python (`tools/orchestrator/evidence.py`). Subsystem này:
  - Không import hay gọi `AgentProvider`, `CliProvider`, hoặc `Pipeline.invoke()`;
  - Không chọn model, không hỏi AI lệnh nào cần chạy;
  - Không cho phép AI sinh lệnh shell tùy ý; mọi lệnh thực thi đều thuộc quyền quản lý của task card/contract;
  - Không để AI suy diễn PASS/FAIL cơ học.

### Cấu trúc schema EvidenceBundle (versioned)
`EvidenceBundle` được mô hình hóa chặt chẽ qua Pydantic (`extra="forbid"`, `schema_version: Version = 1`), bao gồm các cấu trúc con:
1. `CandidateProvenance`: Liên kết chặt chẽ với candidate đã đóng băng:
   - `base_sha`, `branch`, `head_sha`, `source_digest` (khớp chính xác `Git.snapshot(base_sha)`);
   - Phân biệt rõ rệt 3 tầng trạng thái Git:
     - Tầng staged / index: `staged_paths`, `staged_diff_digest` (`git diff --cached --binary base_sha --`);
     - Tầng unstaged working tree: `unstaged_paths`, `unstaged_diff_digest` (`git diff --binary --`);
     - Tầng non-ignored untracked files: `untracked_paths`, `untracked_digest` (băm nội dung và mode của untracked files).
2. `ScopeEvidence`: Tính toán cơ học tính tuân thủ allowlist:
   - `allowed_paths`, `actual_changed_paths`, `unexpected_changed_paths`, `verdict` (`PASS` | `FAIL`);
   - Áp dụng `safe_path()`; chuẩn hóa và từ chối duplicate paths;
   - Thay đổi ngoài allowlist lập tức fail closed (`BLOCKED_FOR_SCOPE_EXTENSION`). Bundle hoàn chỉnh không thể biểu diễn candidate ngoài phạm vi là hợp lệ.
3. `VerificationEvidence`: Kế thừa ngữ nghĩa `VerificationCollection` hiện có mà không tạo runner thứ hai:
   - Bảo toàn thứ tự khai báo qua `FrozenEvidenceIdentity.required_command_digests`, `command_index` và `declaration_digest`; PASS cần toàn bộ manifest, FAILED cho phép prefix kết thúc bằng lỗi rõ ràng;
   - Lưu trữ metadata có giới hạn: `command`, `exit_code`, `timed_out`, `oversized`, bytes và SHA-256 digest của stdout/stderr, `failure_classification`;
   - Tuyệt đối không nhúng stdout/stderr không giới hạn;
   - Lỗi kiểm tra thông thường (exit code != 0) là bằng chứng thực thi hợp lệ (`passed=False`, `failed=True`);
   - Lỗi hạ tầng / thiết lập (`setup_error`) lập tức fail closed, không bao giờ bị báo cáo nhầm thành PASS.
4. `EvidenceArtifactRef`: Tham chiếu tệp bằng chứng dung lượng lớn trong thư mục run artifacts:
   - Ghi nhận `name`, `path` (đường dẫn tương đối an toàn), `digest` (SHA-256), `byte_size`, `classification`, `summary` và `identity` khớp frozen verification identity;
   - Ngăn chặn triệt để đường dẫn tuyệt đối, path traversal (`..`), và symlink escape;
   - Hàm `validate_artifact_ref` kiểm tra tính tồn tại, tệp thông thường (regular file), nằm gọn trong thư mục artifacts, đúng kích thước byte và đúng mã băm SHA-256. Mọi hành vi sửa đổi (tampering) đều bị phát hiện và fail closed.
5. `TimingEvidence`: Ghi nhận thời gian đo lường bằng đồng hồ đơn điệu (`time.monotonic_ns()`). Thời gian thuần túy mang tính chẩn đoán (diagnostic), không quyết định kết quả PASS/FAIL. Phương thức `bundle.semantic_payload()` loại bỏ toàn bộ top-level `timing` và `verification.commands[*].duration_ns`. Artifact digests vẫn phản ánh bytes chính xác của artifact.

### Tính xác định và toàn vẹn
- **Canonical Ordering:** Các danh sách không có thứ tự hợp đồng (changed_paths, staged_paths, unstaged_paths, untracked_paths, allowed_paths, unexpected_changed_paths, artifacts) đều được sắp xếp canonical deterministically (`sorted()`). Thứ tự hoàn tất của luồng (thread completion order) hoặc thứ tự duyệt filesystem không thể làm thay đổi payload ngữ nghĩa.
- **Fail-Closed Completeness:** `EvidenceBundle` yêu cầu đầy đủ các bằng chứng cần thiết (`is_complete: Literal[True] = True`). Mọi sai lệch về `base_sha`, `branch`, `source_digest`, sự xuất hiện của unexpected path, thiếu bằng chứng kiểm tra, lỗi setup hoặc artifact digest mismatch đều khiến việc hoàn thành bundle thất bại ngay lập tức.
- **Parent-Only Authority:** Chỉ tiến trình Pipeline cha mới có quyền persist và đăng ký `EvidenceBundle` vào `RunState.artifacts`. Worker threads và reviewer threads không có quyền hạn tạo hoặc ghi đè artifact này.

### Tính tương thích ngược và phạm vi hoãn lại
- Artifact lịch sử `audit_checks` giữ nguyên format và metadata kết quả. Các trường identity, declaration digest và monotonic duration mới nằm trong EvidenceBundle, không thêm vào historical artifact.
- T088 bổ sung artifact `evidence_bundle` song song bên cạnh `audit_checks`.

## T089: Evidence-Aware Semantic Reviewer Protocol và Safe Host-Owned Probes

Status: `DONE`. Authoritative host verification PASS: probes test suite 44 passed; core/evidence/workflow probe suite 27 passed; concurrent_audit 43 passed; parallel_review 25 passed; scheduler 48 passed; full orchestrator 447 passed; Ruff, Ruff format, Mypy and `git diff --check` PASS.

T089 hoàn thiện trust boundary giữa deterministic control plane (host) và AI semantic reviewers/auditor:
```text
                   frozen candidate
                         |
              +----------+----------+
              |                     |
              v                     v
     HOST verification        semantic reviewers
              |                     |
              |                findings and/or
              |                 ProbeRequest
              |                     |
              +----------+----------+
                         |
                         v
                  parent deterministic join
                         |
                         v
                   EvidenceBundle
                         |
             validate ProbeRequest(s)
                         |
                         v
                    ProbeCatalog
               (host-owned registry)
                         |
                         v
                  deterministic probe
                         |
                         v
                    ProbeEvidence
                         |
             optional bounded reviewer resume
                         |
                         v
                    ReviewBundle
                         |
                         v
                 authoritative Auditor
                         |
                         v
                   host final gate
```

### Nguyên tắc kiến trúc cốt lõi
1. **AI yêu cầu quan sát có kiểu, host định đoạt cách thực thi:**
   - AI có thể trả về `ReviewShard` chứa các phát hiện (`findings`) và tùy chọn một `probe_request: ProbeRequest | None`.
   - AI tuyệt đối không thể gửi `command`, `argv`, `shell`, `executable`, `script`, `powershell`, `bash`, hay biến môi trường.
   - Bất kỳ trường nào trong `FORBIDDEN_PROBE_OVERRIDE_KEYS` xuất hiện ở root model hoặc trong parameters dictionary đều khiến schema validation thất bại ngay lập tức (`extra="forbid"`).
2. **Host-Owned ProbeCatalog:**
   - Chỉ code repository phía host mới có quyền đăng ký hoặc quản lý `ProbeDefinition` trong `ProbeCatalog`.
   - Model output không thể đăng ký thêm probe mới hay biến đổi logic của probe hiện có.
   - Catalog ban đầu bao gồm 2 probe an toàn:
     - `source_inspection`: tìm kiếm literal theo dòng thuần Python (không qua shell), giới hạn file 1 MiB, tối đa 50 dòng kết quả, kiểm tra path traversal và cấm các đường dẫn transient/ignored (`.git`, `node_modules`, `.venv`, `.pytest_cache`, v.v.).
     - `git_diff_check`: thực thi lệnh cố định `["git", "diff", "--check"]`, không nhận tham số (`_validate_git_diff_check_params` cấm tham số).
3. **Exact Candidate Binding & Stale Detection:**
   - `ProbeRequest` và `ProbeEvidence` bắt buộc phải bind chính xác vào candidate identity (`task_id`, `base_sha`, `branch`, `source_digest`).
   - Nếu source code thay đổi sau khi reviewer gửi request nhưng trước khi host thực thi, host lập tức fail closed (`STALE_PROBE_REQUEST`). Không bao giờ thực thi một probe trên source đã stale.
4. **Preserve T087 Concurrency:**
   - Initial reviewer fan-out diễn ra song song với luồng xác minh thực thi (`collect_verification`), bảo toàn tối ưu thời gian chạy của T087.
   - Initial reviewers nhận `ReviewerContext` với `verification_status="PENDING"` và bị cấm đưa ra kết luận PASS/FAIL về kiểm tra thực thi.
   - Sau khi các luồng join và `EvidenceBundle` được hoàn tất, nếu có reviewer yêu cầu probe hợp lệ, host thực thi probe và cho phép tối đa 1 lượt resume reviewer.
5. **Bounded 1-Round Probe:**
   - Mỗi reviewer perspective chỉ được thực hiện tối đa 1 vòng probe request.
   - Reviewer resume nhận `ReviewerContext` với `round_index=2` và structured `ProbeEvidence`.
   - Nếu reviewer cố tình yêu cầu probe lần 2 ở vòng resume, host lập tức fail closed với `OrchestratorError("Reviewer exceeded probe round limit: second probe request forbidden")`.
6. **Deterministic Ordering:**
   - Nếu nhiều reviewer cùng yêu cầu probe, việc thực thi probe và resume reviewer diễn ra xác định theo thứ tự canonical declaration của `ReviewPerspective` (`CORRECTNESS` -> `VERIFICATION` -> `SECURITY`).
7. **Parent-Only Authority & Final Gate:**
   - Reviewer threads và probe executors không có quyền ghi state hay đăng ký authoritative artifacts. Chỉ parent process mới đăng ký `ProbeEvidence` và `ReviewBundle`.
   - Final Auditor nhận `EvidenceBundle.semantic_payload()` hoàn chỉnh, candidate identity, `ReviewBundle`, và toàn bộ `ProbeEvidence`.
   - Auditor PASS không thể override lỗi kiểm tra cơ học (`verification_failed and audit.status == "PASS"` lập tức raise `OrchestratorError`).

## T089-R2: Agent Liveness Watchdog và Bounded Final-Auditor Context

Hạ tầng remediation giải quyết sự cố Auditor bị stall/treo trong T089 và thu gọn context prompt của final Auditor:

### 1. Host-Owned Silence/Stall Watchdog (Khắc phục treo tiến trình AI)
- **Tách biệt với timeout tổng**: `timeout_seconds` tiếp tục quản lý thời gian thực thi tối đa (nếu được cấu hình). Nếu `timeout_seconds = None`, không có deadline wall-clock tổng.
- **Cấu hình theo Role**:
  - `stall_timeout_seconds: StrictInt | None = None`: thời gian im lặng (không có output bytes trên stdout/stderr) trước khi vào cửa sổ xác nhận nghi vấn. Mặc định `None` để tương thích ngược hoàn toàn với các cấu hình/chạy cũ.
  - `stall_confirm_seconds: StrictInt = 30`: thời gian trong cửa sổ xác nhận nghi ngờ stall. Nếu tiến trình phát sinh output mới trong thời gian này, nghi vấn bị hủy bỏ.
  - `max_stall_retries: StrictInt = 1`: số lượt retry tối đa riêng biệt dành cho lỗi stall (mặc định cho phép tối đa 1 lần retry sau lần thử ban đầu).
- **Quan sát tiến trình khách quan (Observable Progress)**:
  - Host giám sát dung lượng file descriptor (`fstat(fd).st_size`) của stdout và stderr của subprocess.
  - Bất kỳ byte tăng trưởng nào đều reset đồng hồ im lặng. Không dùng AI model hay heuristics cảm tính để xác định liveness.
- **Xử lý tiến trình có kiểm soát (Process-Tree Termination)**:
  - Khi stall được xác nhận, host gọi `_terminate_process_tree` thu dọn toàn bộ process group / process tree trên Linux/POSIX (`killpg`) và Windows (`taskkill /F /T`), không để sót tiến trình con mồ côi (orphan CLI/subprocess).
  - Trả về `ProcessResult` với `stalled=True` và ghi nhận rõ ràng trong metadata (`normal exit`, `timed_out`, `oversized`, `stalled`).
- **Định danh lần thử bất biến (Attempt Artifact Identity - R2B-001)**:
  - Mỗi lần gọi provider (kể cả retry do validation hay do stall) đều nhận định danh duy nhất và bất biến:
    - `invocation_base = f"{state.fix_cycle:02d}-{role_name}-{uuid4().hex[:8]}"`
    - `attempt_name = f"{invocation_base}-a{attempt_index:02d}"` (ví dụ: `-a01`, `-a02`, v.v.).
  - Mọi artifact phát sinh trong lần thử đều dùng đường dẫn bất biến theo `attempt_name`:
    - Prompt: `<attempt_name>.prompt.md`
    - Schema: `<attempt_name>.schema.json`
    - Response: `<attempt_name>.response.json`
    - Log: `<attempt_name>.log.json`
    - Auditor context (dành riêng cho auditor): `<attempt_name>.auditor-context.json`
    - Phản hồi bị từ chối (nếu có): `<attempt_name>.rejected.json`
  - Không bao giờ ghi đè lên artifact của lần thử trước đã được đóng dấu (`sealed`).
  - Sau khi mỗi attempt kết thúc: host kiểm tra toàn vẹn candidate source và protected artifacts của các attempt trước không bị suy chuyển, đóng dấu (`seal`) artifacts của attempt đó vào `state.artifact_digests` và danh sách bảo vệ, rồi mới tiến hành attempt tiếp theo.
- **Ngân sách retry độc lập (Orthogonal Retry Budget - R2B-002)**:
  - Duy trì hai bộ đếm độc lập:
    - Ngân sách retry thẩm tra cấu trúc/schema lịch sử: `validation_retries <= 2` (bảo toàn hành vi lịch sử tối đa 3 lượt thử validation).
    - Ngân sách retry stall: `stall_retries <= role.max_stall_retries` (mặc định 1, hỗ trợ cấu hình từ 0 đến 10).
  - Lỗi stall được xác nhận **không** tiêu tốn ngân sách retry validation lịch sử.
  - Phân loại stall hoàn toàn bằng kiểu (Typed Stall Classification - R2C-F01):
    - `is_stall = isinstance(error, AgentStallError)`.
    - Tuyệt đối không fallback theo chuỗi con, regex hoặc phân tích văn bản ngoại lệ (exception prose); văn bản từ model hoặc thông báo lỗi không thể tạo bằng chứng cơ học về stall.
  - Đóng dấu toàn bộ artifact của attempt (Sealing Attempt Artifacts - R2C-F02):
    - Sử dụng hàm đơn nhất `seal_attempt_artifacts` cho cả 3 trường hợp: retryable failed attempt, terminal confirmed stall, và successful attempt.
    - Kiểm tra tập suffix cố định `KNOWN_ATTEMPT_ARTIFACT_SUFFIXES`: `.prompt.md`, `.auditor-context.json`, `.schema.json`, `.response.json`, `.log.json`, `.rejected.json`.
    - Đối với mỗi tệp thông thường, không phải symlink (regular non-symlink file), tính SHA-256 digest, đăng ký vào `state.artifact_digests` và thêm vào `protected` tracking. Không quét/glob tệp tùy ý.
    - Tuyệt đối không ghi đè hoặc làm biến đổi artifact đã đóng dấu trước đó.
  - Khi cạn kiệt ngân sách retry stall (terminal confirmed stall):
    - Host xác nhận candidate source và protected artifacts không đổi.
    - Đóng dấu (`seal`) toàn bộ attempt artifacts hiện có (`.prompt.md`, `.auditor-context.json`, `.schema.json`, `.log.json`, `.response.json` nếu có) vào `state.artifact_digests`.
    - Host bắt buộc gán `current_agent = None` và lưu `state.json` trước khi nâng lỗi `AgentStallError`.
    - Pipeline chuyển sang trạng thái: `state = FAILED`, `blocked_from = <active stage>`, `current_agent = None`.

### 2. Bounded Final-Auditor Context (AuditorContextV1)
- **Ràng buộc ngữ cảnh chuẩn tắc (Authoritative Auditor Context Binding - R2B-003)**:
  - Trước mỗi lần dispatch final Auditor, host lưu trữ tệp ngữ cảnh bất biến:
    `<attempt_name>.auditor-context.json` chứa chính xác các byte của `serialize_auditor_context(context)`.
  - Đăng ký SHA-256 của tệp này vào `state.artifact_digests` và protected artifact tracking.
  - Nếu retry chỉ thay đổi prompt hướng dẫn mà ngữ cảnh không đổi, digest của context giữ nguyên nhưng prompt artifact phân biệt rõ ràng giữa các attempt.
- **Thay thế prompt dư thừa bằng một cấu trúc dữ liệu chuẩn hóa**:
  - `AuditorContextV1` mang đầy đủ thông tin ngữ nghĩa cần thiết:
    - `schema_version`: 1
    - `candidate_identity`: `task_id`, `base_sha`, `branch`, `source_digest`
    - `contract`: `title`, `objective`, `allowed_paths`, `forbidden_paths`, `acceptance_criteria` (giữ nguyên thứ tự khai báo), `risk_level`, `stop_conditions`
    - `worker_summary`: `status`, `changed_files`, `known_issues` (loại bỏ `commands_run` vì quyền thực thi thuộc về EvidenceBundle)
    - `evidence_bundle`: `EvidenceBundle.semantic_payload()` chính xác 1 lần
    - `review_bundle`: `ReviewBundle` đầy đủ chính xác 1 lần
    - `probe_evidence`: danh sách kết quả probe của cycle hiện tại
    - `artifact_digests`: bản đồ hash của các artifact phục vụ ràng buộc tính toàn vẹn
- **Loại bỏ hoàn toàn thông tin dư thừa khỏi model prompt**:
  - Không nhúng `TaskCard.context_text` hoặc bản sao thứ hai của `TaskCard`.
  - Không nhúng raw `Plan` hay `worker_prompt`.
  - Không nhúng `WorkerResult.commands_run` hay stdout/stderr kiểm tra thô.
  - Không nhúng lặp lại `ReviewBundle` lần thứ hai ở cuối prompt.
- **Giới hạn kích thước nghiêm ngặt (Context Size Guard)**:
  - Giới hạn vận hành: `canonical AuditorContext JSON <= 64 KiB` (UTF-8 bytes).
  - Tuần tự hóa tất định (deterministic serialization: sorted keys, compact separators `(",")`, `(":")`, ensure_ascii=False).
  - Nếu payload bắt buộc vượt quá 64 KiB, host **FAIL CLOSED** ngay lập tức trước khi gọi provider, tiêu tốn **0 lượt gọi model (0 attempts consumed)**.
  - Cung cấp chẩn đoán chi tiết dung lượng từng thành phần (`auditor_context_component_sizes`) mà không để lộ nội dung thô bí mật.

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

### Recover a frozen failed audit candidate

T089 recovery remediation adds a host-only construction command. It accepts only
historical `FAILED` runs with `blocked_from == AUDIT_RUNNING` and
`current_agent is None`. The historical run remains failed. Its `state.json`, run
artifacts, Git index/history and candidate-authoritative source must remain unchanged.
Ignored transient toolchains/caches are outside the candidate digest and are not
copied into recovery authority. `Git.snapshot` does not cover ignored/transient files.

```bash
python -m tools.orchestrator recover-candidate T089 \
  --run-id SOURCE_RUN_ID \
  --expected-source-digest SHA256 \
  --no-integrate
```

After success, run the exact Bash command in the CLI's `recovery_handoff.next_step`.
It executes from the trusted control-plane worktree, NOT from the recovered candidate
worktree. The handoff distinguishes `control_plane_cwd` and `candidate_worktree`, while
also preserving `cwd` (pointing to control plane), `branch`, `task_id`, `run_id` and
fixed resume `argv`, preserving the integration flag and any custom config path as an
absolute path. The equivalent manual sequence is below. Replace placeholders using the
recovery output.

```bash
cd -- "/absolute/control/plane/from/recovery_handoff/control_plane_cwd"
python -m tools.orchestrator resume T089 --run-id NEW_RUN_ID --no-integrate
```

The orchestrator implementation executes from the trusted host control plane
(incorporating R2/R3 liveness watchdog, stall retry, bounded AuditorContextV1, and
recovery compatibility logic). The recovered candidate worktree remains strictly candidate
data at the historical frozen digest and does NOT gain R2/R3 infrastructure source files.
The recovery-tool CLI refuses recovered-run resume if invoked from the candidate worktree
or using candidate Python modules, printing the exact handoff command without invoking
Reviewer/Auditor. The normal Pipeline operates on `state.worktree_path` for candidate
Git/source operations and reviewer/auditor working directories.

Both source arguments are required. `SHA256` must be the independently approved
frozen candidate digest, using the existing `Git.snapshot(source.base_sha)` format.
The host calculates and compares the actual digest. There is no caller-supplied
worktree path, patch, shell command or provider call. `--config`, `--integrate` and
`--no-integrate` select the normal configuration and later integration policy.
Configuration must match the source run structurally except for `integrate` and host-owned
Role liveness fields (`stall_timeout_seconds`, `stall_confirm_seconds`, `max_stall_retries`)
via `recovery_config_compatible()`. Changes to provider, executable, model, reasoning,
worker_access, allow_process, base_branch, paths, setup_commands, verification commands,
global timeout_seconds, max_fix_cycles, or skills_root are strictly rejected. The recovered
`RunState` persists the new recovery configuration so subsequent normal `resume()` calls
succeed under unmodified configuration equality. Recovery itself performs neither review nor
integration.

The host checks recorded task/run/repository identity, registered worktree ownership,
branch, historical base HEAD, task snapshot, contract, plan, every sealed artifact,
and a successfully parsed `WorkerResult` with status `IMPLEMENTED`. Actual candidate
changes must independently pass the frozen Contract, `Pipeline.scope()`, expected
source digest and changelog rule. Worker changed-file claims are advisory and may
predate owner/host remediation. A mismatched claim does not reject valid host evidence;
a claim naming out-of-scope paths never authorizes actual source changes there.
Optional skills must still validate against their recorded references and hashes.
Source state, artifact bytes,
index bytes, branch and candidate digest are checked again during construction.

A new run uses `<worktree_root>/<task>-<new_run_id>` and
`agent/<task>-<new_run_id>`, starting at the historical `base_sha` even when main has
advanced. Shared T087 materialization applies the cached binary diff, applies the
unstaged binary diff, and copies only non-ignored untracked candidate files with
permissions. Exact snapshot equality is required before and after fresh configured
setup commands. Source node_modules, virtual environments, caches and ignored
outputs are not copied. This costs a fresh setup but prevents inherited toolchain
state from becoming new verification evidence.

Only validated `task_card`, `plan`, `contract`, `worker` and optional `skills` are
carried as raw bytes. Historical audit checks, evidence/review bundles, audit and
rejected audit reports, probes and integration artifacts remain in the source run.
Fresh setup evidence and a hash-registered `recovery_origin` artifact record the new
authority. Origin schema version 1 binds task ID, source run/state digest/base/branch/
source digest, recovery run/branch/worktree/source digest, `worker_claim_matches`,
`worker_changed_files_digest`, `recovered_changed_files_digest`, source/recovery
fix cycles, immutable `source_config_digest`, `recovery_config_digest`, and boolean
`liveness_config_upgraded`. Config digests hash UTF-8 JSON of the typed configuration
with sorted keys and compact separators `(',', ':')`. Each file-list digest hashes UTF-8 JSON
of the sorted list with default ASCII escaping and compact separators `(',', ':')`. Historical
Worker bytes remain unchanged. Recovery preserves `fix_cycle=source.fix_cycle` and
`max_fix_cycles=source.max_fix_cycles`, so it cannot replenish the bounded fix budget.
No State enum or mandatory RunState field changes are required.

Construction stays `PENDING` until validation and setup succeed. Success returns
`IMPLEMENTED` with no current agent, blocked stage, last error or inherited audit
authority. Normal `resume` then performs fresh verification, review and audit through
the existing path. Rejected eligibility creates no new run. A construction error
retains a `FAILED` new run and any partial worktree for inspection; interruption
leaves non-resumable construction evidence rather than successful recovery authority.
Recovery does not repair the historical run or replay its Worker.

### Import an externally salvaged candidate (`import-candidate`)

`import-candidate` provides a host-only control-plane command to import an externally salvaged candidate into a fresh authoritative run. It accepts a historical lineage run in `FAILED` state (including lineages failing from `FIX_RUNNING` and retaining `current_agent="worker"`). The historical run remains byte-identical and sealed.

```bash
python -m tools.orchestrator import-candidate TASK \
  --run-id HISTORICAL_RUN_ID \
  --source-worktree PATH \
  --expected-source-digest SHA256 \
  --provenance-manifest PATH \
  --expected-provenance-digest SHA256 \
  [--config PATH] \
  [--integrate | --no-integrate]
```

#### Locked Architecture and Host Gates

The control plane enforces:
1. **Host candidate validation**: The external worktree must be a real Git worktree belonging to the same repository, with HEAD at historical `base_sha`, and `Git.snapshot(base_sha)` exactly matching `expected_source_digest`. Symlinks in worktree or ancestry are rejected.
2. **Host semantic evidence validation**: Untrusted provenance JSON is decoded via strict parser (rejecting duplicate keys, trailing data, NaN/Infinity, invalid UTF-8). All 9 required v1 artifacts (`source-manifest.txt`, `scout-A/B/C.packet.json`, `adjudication-packet[.compact].json`, `heavy-judge.prompt.txt`, `heavy-judge.schema.json`, `heavy-judge.response.json`) must be present, match digest and size bounds (max 256 KiB single, 2 MiB combined).
3. **Complete semantic coverage**: Exact set equality is required: `actual_changed_paths == source_manifest == union(Scout A/B/C reviewed_files)`. No changed file may bypass semantic review. Partial salvages (such as 6 of 9 paths) fail closed.
4. **Zero-findings v1 policy**: Scout findings must be empty, Adjudication finding count must be 0 with empty findings, and Heavy Judge decision must be `PASS` with zero confirmed findings, dismissed findings, or evidence requests.
5. **Copied evidence independence**: Accepted artifacts are copied into the new run directory under flat sealed filenames (`00-imported-*`). The authoritative run never depends on external `/tmp` files.
6. **Mechanical reverification**: Materializes into a managed worktree, executes setup, and deterministically reverifies contract and config verification commands.
7. **Atomic publication**: Only when BOTH mechanical and semantic gates pass is `AUDIT_PASS` granted with `audited_digest` and `verified_digest` bound to the candidate digest. Exactly zero AI calls occur during import.
8. **Continuation via trusted control plane**: `resume --no-integrate` leaves the run at `AUDIT_PASS` with 0 AI calls. `resume --integrate` invokes Integrator and merges without re-running ReviewShard or Audit. CLI rejects resume execution from the candidate worktree, enforcing trusted control plane execution.

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

Level 1 giữ state transition đồng bộ với T087 concurrent verification và T086 advisory review, dùng JSON, ba admission
slots và tích hợp tuần tự. T079 bổ sung pool process và lập lịch DAG phía trên
Pipeline, giữ nguyên contract của các vai trò. Không có cơ sở dữ liệu scheduler,
dashboard, khóa phân tán hay resume chạy nền. Resource-aware scheduling và cơ chế
cô lập mạnh hơn thuộc giai đoạn hạ tầng sau.
