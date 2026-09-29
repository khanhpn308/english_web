# Contract conformance 002 — T013

**Date:** 29/09/2026 (`Asia/Bangkok`)

**Scope:** Spec/API/UI clarification only; dependency T005 is `DONE` at `bebcc12`.

**Authority:** Owner confirmation in this chat permits the T013 allowlist, including spec/API edits. ADR-0004 supplies v1 policy; ADR-0005 records exact clarifications. `CONSTRAINTS.md` remains the quality bar.

## Baseline and crosswalk

These cases were written before the document changes. A document probe checks the written contract and examples; it does not test the future application.

| ID | Baseline evidence | Required oracle / traceability | Initial result |
|---|---|---|---|
| C013-01 | Spec AC-14 and API `CreateQuizRequest` use 1/1/1 despite ADR-0004's minimum 5. | 2/2/1 succeeds with sufficient sources; 1/1/1 fails `422 VALIDATION_ERROR` before bridge access. AC-14; quiz counts; T035/T036. | FAIL |
| C013-02 | ADR-0004 says HARD “keeps or moves one box up”; API review date is inconsistent with local intervals. | Full transition table and Bangkok midnight fixture. AC-12/19; ReviewEvent; T031/T059. | FAIL |
| C013-03 | Score 0–4 exists without descriptors; null/blank terminal behavior is undefined. | Versioned rubric, each rating mapping, blank objective and missing writing score rules. AC-16/17/19/30; Answer/QuizResult; T059/T048. | FAIL |
| C013-04 | API schema requires source ID/revision but save example omits both; no way to create a new date source. | New-source and existing-source preconditions, backend ID/path, revision and idempotent receipt. AC-04/11; SaveWordFormsRequest/SaveResult; T024. | FAIL |
| C013-05 | AC-28 incorrectly makes an external editor receive HTTP 409. | Hash/watcher external sync; stale API write returns 409. AC-08/28/31; source write protocol; T021–T024/T029. | FAIL |
| C013-06 | IN_PROGRESS question example and public DTOs contain `explanationVi`. | No key/explanation before terminal commit; server-only snapshot; result reveal. AC-15/30; question variants; T034/T035/T048. | FAIL |
| C013-07 | UI result route has no exact read contract; second submission behavior is alternative rather than deterministic. | GET attempt carries terminal result; replay vs new key; revision checks and atomic SRS handoff. AC-18/19/23; QuizAttempt/QuizResult; T047/T048/T051. | FAIL |
| C013-08 | API calls caps “configuration values” without a capabilities oracle. | 1/8/4 MiB, 4096 code points, 100 elements; boundary and max+1 errors. CONSTRAINTS; capabilities/validation; T006/T007/T041. | FAIL |
| C013-09 | Bootstrap/session expiry, exact boundary and second-tab behavior are unspecified in API/UI. | 60s single-use bootstrap; non-sliding 8h session; restart invalidation; durable draft rebootstrap. AC-01/18/23/38–40; session guards; T006/T066. | FAIL |
| C013-10 | Operation retention still an open release setting; deadlines lack exact start/expiry and known/unknown outcome rule. | Lifetime key receipts, immutable policy references; 120/60/30s monotonic deadlines without retry. AC-05/27/35/39; Operation; T014/T007/T016. | FAIL |
| C013-11 | Lookup preview has empty learning fields, consent view omits accepted digest, sample answer assigns a self-score to cloze. | Positive examples must obey their own DTOs; required-field and pre-submit privacy probes. AC-02/33/37; common examples; T017/T019. | FAIL |

Baseline provenance (untracked planning inputs copied into the isolated worktree). The raw API digest is omitted from durable prose after the T063 scanner classified the filename-plus-digest fixture as a generic key; the original baseline remains recoverable from the parent task handoff.

```text
docs/spec.md: 842d951519dafbacda62bc814fe829d82f022681ac7c7318acff29add710ed3d
docs/api-contract.md: [digest omitted from prose; baseline remains recoverable from the parent task handoff]
docs/ui-architecture.md: 8fb9c3ede6bfc265273cffb14618ad70f5fc5c3cef6adc1bbe708d396890fafd
CONSTRAINTS.md: 8d324b1019c682fc6598ebdc4aecbdbc388ab2cff7d6e712a593636954316a25
ADR-0004: 6254e5a512d416938bcfe447c9e6af3c297fa7c5dbd8f6a77b18b227a0545c98
```

## Executable document probes

Run from the T013 worktree using the existing T001/T058 interpreter. This standard-library script reads JSON examples and contract statements. It creates no files and makes no network calls.

```text
/home/khanh/projects/vocabularies/.venv/bin/python -c 'from pathlib import Path; p=Path("docs/reviews/contract-conformance-002.md").read_text(); exec(p.split("```python\n",1)[1].split("\n```\n",1)[0])'
```

```python
import json
import re
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

api = Path("docs/api-contract.md").read_text()
spec = Path("docs/spec.md").read_text()
ui = Path("docs/ui-architecture.md").read_text()
adr_path = Path("docs/adr/0005-contract-clarifications.md")
adr = adr_path.read_text() if adr_path.exists() else ""
samples = {}
invalid_json = []
for block in re.findall(r"```json\n(.*?)\n```", api, re.S):
    try:
        value = json.loads(block)
    except json.JSONDecodeError:
        invalid_json.append(block)
        continue
    if isinstance(value, dict):
        samples.update(value)

failures = []


def check(case, predicate):
    passed = bool(predicate)
    print(f"{case}: {'PASS' if passed else 'FAIL'}")
    if not passed:
        failures.append(case)


counts = samples.get("CreateQuizRequest", {}).get("counts", {})
check(
    "C013-01",
    counts == {"mcq": 2, "cloze": 2, "writing": 1}
    and "1/1/1" in spec
    and "422 VALIDATION_ERROR" in adr
    and '"counts":{"mcq":1,"cloze":1,"writing":1}' in api
    and '"reason":"total_below_minimum"' in api,
)
srs_rows = [
    tuple(map(int, row))
    for row in re.findall(r"^\| (\d) \| (\d) \| (\d) \| (\d) \| (\d) \|$", adr, re.M)
]
due_rows = re.findall(r"^\| ([1-5]) \| (\d+) \| (\d{4}-\d{2}-\d{2}) \| `([^`]+)` \|$", adr, re.M)
bangkok = ZoneInfo("Asia/Bangkok")
review_date = datetime.fromisoformat("2026-09-29T10:20:30Z").astimezone(bangkok).date()
due_valid = len(due_rows) == 5
for box, days, local_date, due_utc in due_rows:
    expected_date = review_date + timedelta(days=int(days))
    expected_utc = datetime.combine(expected_date, time(), bangkok).astimezone(UTC)
    due_valid = due_valid and int(days) == [1, 3, 7, 14, 30][int(box) - 1]
    due_valid = due_valid and local_date == expected_date.isoformat()
    due_valid = due_valid and due_utc == expected_utc.isoformat().replace("+00:00", "Z")
check(
    "C013-02",
    "HARD = max(1, currentBox)" in adr
    and srs_rows
    == [
        (0, 1, 1, 1, 2),
        (1, 1, 1, 2, 3),
        (2, 1, 2, 3, 4),
        (3, 1, 3, 4, 5),
        (4, 1, 4, 5, 5),
        (5, 1, 5, 5, 5),
    ]
    and due_valid
    and samples.get("ReviewEvent", {}).get("nextDueAt") == "2026-09-29T17:00:00Z",
)
rubric_rows = re.findall(r"^\| ([0-4]) \| ([^|\n]+) \| (AGAIN|HARD|GOOD|EASY) \|$", adr, re.M)
check(
    "C013-03",
    [(int(score), rating) for score, _, rating in rubric_rows]
    == [(0, "AGAIN"), (1, "AGAIN"), (2, "HARD"), (3, "GOOD"), (4, "EASY")]
    and "writing-rubric-v1" in api
    and "BLANK" in adr
    and "selfScore=null" in adr
    and "422 VALIDATION_ERROR" in adr,
)
check(
    "C013-04",
    "If-None-Match: *" in api
    and "If-Match" in api
    and "sourceId" not in samples.get("SaveWordFormsRequest", {})
    and samples.get("SaveResult", {}).get("sourceId")
    and "sourceId" in ui
    and "C013-04" in adr,
)
ac28 = next((line for line in spec.splitlines() if "| `AC-28` |" in line), "")
check(
    "C013-05",
    "API" in ac28
    and "hash/watcher" in ac28
    and "editor nhận `409" not in ac28
    and "C013-05" in adr,
)
questions = samples.get("QuizAttempt", {}).get("questions", [])
question_counts = {
    kind.lower(): sum(q["type"] == kind for q in questions) for kind in ("MCQ", "CLOZE", "WRITING")
}
check(
    "C013-06",
    len(questions) == 5
    and question_counts == counts
    and all(
        not ({"explanationVi", "correctOptionId", "acceptedAnswers"} & q.keys()) for q in questions
    )
    and "C013-06" in adr
    and samples.get("QuizAttempt", {}).get("result", "missing") is None,
)
terminal = samples.get("QuizResult", {})
results = terminal.get("questionResults", [])
by_question = {q["id"]: q for q in questions}
result_ids_match = {r["questionId"] for r in results} == set(by_question)
rating_order = {rating: index for index, rating in enumerate(("AGAIN", "HARD", "GOOD", "EASY"))}
grouped_ratings = {}
for result in results:
    form_id = by_question[result["questionId"]]["wordFormId"]
    old = grouped_ratings.get(form_id, "EASY")
    grouped_ratings[form_id] = min(old, result["rating"], key=rating_order.__getitem__)
handoffs = terminal.get("reviewHandoffs", [])
handoffs_match = (
    len(handoffs) == len(grouped_ratings)
    and {h["wordFormId"]: h["rating"] for h in handoffs} == grouped_ratings
)
objective_valid = all(
    terminal.get("objectiveScores", {}).get(kind)
    == {"total": 2, "attempted": 2, "correct": 1, "accuracy": 0.5}
    for kind in ("mcq", "cloze")
)
check(
    "C013-07",
    "result: QuizResult | null" in api
    and "GET /api/v1/quiz-attempts/{attemptId}" in ui
    and "409 ALREADY_SUBMITTED" in adr
    and "submissionRevision" in adr
    and terminal.get("status") == "SUBMITTED"
    and terminal.get("submissionRevision") == 5
    and result_ids_match
    and handoffs_match
    and objective_valid,
)
limits = samples.get("Capabilities", {}).get("limits", {})
check(
    "C013-08",
    limits
    == {
        "requestJsonBytes": 1048576,
        "sourceMarkdownBytes": 8388608,
        "bridgeResponseBytes": 4194304,
        "contentCodePoints": 4096,
        "collectionItems": 100,
        "quizTotalMin": 5,
        "quizTotalMax": 30,
        "quizPerTypeMax": 20,
        "pageSizeMax": 100,
        "termCodePoints": 80,
    }
    and "502 BRIDGE_INVALID_RESPONSE" in adr,
)
session = samples.get("Capabilities", {}).get("session", {})
check(
    "C013-09",
    session
    == {
        "bootstrapTokenTtlSeconds": 60,
        "browserSessionTtlSeconds": 28800,
        "expiresOnBackendRestart": True,
        "slidingExpiration": False,
    }
    and "C013-09" in adr
    and "8 giờ" in ui,
)
check(
    "C013-10",
    "lifetime of the local database" in api
    and "elapsed >= budget" in adr
    and samples.get("Capabilities", {}).get("operationDeadlinesSeconds")
    == {"lookup": 120, "quizGeneration": 60, "writingFeedback": 30},
)
check(
    "C013-11",
    not invalid_json
    and samples.get("AnswerDraftRequest", {}).get("selfScore", "missing") is None
    and 'acceptedPolicyDigest":null' in api
    and bool(samples.get("LookupResult", {}).get("forms", [{}])[0].get("meaningsVi")),
)
if failures:
    raise SystemExit(f"Nonconforming document cases: {', '.join(failures)}")
```

## Walkthroughs and verification evidence

Manual document walkthroughs, checked against spec/API/UI and ADR-0005:

| Scenario | Deterministic expected sequence | Document result / runtime owner |
|---|---|---|
| Clean install + new date | Sources for 2026-09-29 absent → explicit save with If-None-Match:* → backend source ID, `29-09-2026.md`, revision1, three NEW cards → same-key replay identical201/no extra card → same content on another date reuses cards. Source appearance during create →409 with existing bytes preserved. | Conforms C013-04 / AC-04/11; T024 runtime pending |
| External editor | Read revision1/E1/H1 → editor writes H2 → hash/watcher validates revision2/E2 → stale API revision1 rejected409 before replacement → explicit re-read/reconfirm →revision3. Before watcher completion, hash recheck still rejects; invalid edit suspends the source without deleting history. | Conforms C013-05 / AC-08/28/31; T021–T024/T029 runtime pending |
| Quiz config + terminal result | 1/1/1 rejected422/zero bridge; 2/2/1 with A/B/C creates five public questions/no explanation → save answers, aggregate revision5 → local atomic submission201/result/SRS once → same-key replay201; new key409 ALREADY_SUBMITTED → GET attempt contains stored result. Writing null rejects422; inactive source skips SRS but preserves result. | Conforms C013-01/03/06/07 / AC-14–19/23/30; T035/T047/T048/T051/T059 runtime pending |
| Revoke/restart/session | Persist revoke revision2 → pending pre-admission AI denied → restart invalidates old cookie → fresh bootstrap exchange → acknowledged answers/result and REVOKED consent read back → direct new AI request denied/no preflight; old grant receipt cannot change state. At token60s/session8h, exchange/request denies401. Earlier admitted output may complete per disclosure. | Conforms C013-09/10 / AC-18/23/38–40; T006/T014–16/T066 runtime pending |

### Negative probe reproducibility

The following probes corrupt the contract example in memory only, then require the checker to reject it. Each inner run exits1 for the named nonconformance; the wrapper exits0 when that rejection is confirmed. This is a checker test, not a call to the future quiz API.

```text
/home/khanh/projects/vocabularies/.venv/bin/python -c 'from pathlib import Path; p=Path("docs/reviews/contract-conformance-002.md").read_text(); exec(p.split("```python\n",2)[2].split("\n```\n",1)[0])'
```

```python
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

report = Path("docs/reviews/contract-conformance-002.md").read_text()
script = report.split("```python\n", 1)[1].split("\n```\n", 1)[0]
original = Path("docs/api-contract.md").read_text()
script = script.replace('api = Path("docs/api-contract.md").read_text()', "api = injected_api", 1)
mutations = [
    (
        "positive quiz changed to 1/1/1",
        "C013-01",
        original.replace(
            '"mcq": 2, "cloze": 2, "writing": 1', '"mcq": 1, "cloze": 1, "writing": 1', 1
        ),
    ),
    (
        "pre-submit explanation disclosure",
        "C013-06",
        original.replace(
            '"id": "question_a", "type": "MCQ"',
            '"id": "question_a", "type": "MCQ", "explanationVi": "synthetic leak"',
            1,
        ),
    ),
]
for label, expected, mutated in mutations:
    assert mutated != original
    with redirect_stdout(StringIO()):
        try:
            exec(script, {"injected_api": mutated})
        except SystemExit as error:
            assert expected in str(error), str(error)
        else:
            raise AssertionError(f"Negative probe incorrectly passed: {label}")
    print(f"{label}: expected document rejection at {expected} confirmed")
```

### Recorded commands and outcomes

Environment: isolated managed worktree `/home/khanh/.codex/worktrees/task-t013-contract-conformance/vocabularies`, branch `feature/task-t013-contract-conformance`, Linux, existing T001/T058 Python3.12.3 interpreter from the shared checkout. Baseline HEAD `bebcc12`; a concurrent T053 worker owns the shared checkout's manifest/tooling changes. Only standard-library document probes run here.

| Command/check | Exit / result |
|---|---|
| Executable document probe command above, before contract edits | 1; C013-01–11 all FAIL. Initial command extraction had a syntax error; delimiter corrected before this valid RED run. |
| Same probe after edits (strengthened with full transition/date, JSON/snapshot/result/grouped-rating consistency) | 0; C013-01–11 all PASS |
| Negative probes above | Wrapper0; both inner runs rejected as expected, at C013-01 and C013-06 |
| `git diff --check` | 0; repeat staged check required before commit because spec/API/UI were originally untracked |
| Task-card `rg` command below | 0; required oracle markers present |
| `gitleaks detect --redact --no-banner` | 127; executable unavailable, PENDING T063; not a passing secret scan |
| Post-T063 Gitleaks 8.30.1 recheck | Initial RED: five generic-key false positives. After non-semantic placeholder/prose edits, directory, staged diff and current-HEAD history (8 commits) each report 0 findings; no allowlist/suppression. |
| `git diff --cached --check` | First run exited2 on inherited Markdown hard-break spaces in newly tracked planning files; scoped metadata now uses blank-line paragraphs. Final run exits0, no whitespace errors. |
| Staged scope/link/provenance/redacted-pattern script below | Exit0: exactly 8 task files; application/config diff empty; 96 local links resolve; CONSTRAINTS/ADR-0004 hashes unchanged; 0 credential-pattern candidates in staged diff and local Git history. |

```text
rg -n 'HARD|AC-14|sourceId|session|explanationVi|rubric|SUBMITTED' docs/spec.md docs/api-contract.md docs/adr/0005-contract-clarifications.md
```

Local-link/provenance/scope and supplemental redacted credential-pattern verification use the third script below, after staging only the eight task files. Context links may resolve in the shared planning checkout because unrelated planning files were originally untracked and are intentionally not committed by T013. The pattern scan was supplemental evidence for the original baseline; the post-T063 Gitleaks recheck above is the authoritative secret-scan result. The supplemental script inspects staged diff and local Git history in memory and prints no matched credential text.

```text
/home/khanh/projects/vocabularies/.venv/bin/python -c 'from pathlib import Path; p=Path("docs/reviews/contract-conformance-002.md").read_text(); exec(p.split("```python\n",3)[3].split("\n```\n",1)[0])'
```

```python
import hashlib
import re
import subprocess
from pathlib import Path

root = Path.cwd()
shared = Path("/home/khanh/projects/vocabularies")
scope = {
    "docs/spec.md",
    "docs/api-contract.md",
    "docs/ui-architecture.md",
    "docs/adr/0005-contract-clarifications.md",
    "docs/reviews/contract-conformance-002.md",
    "tasks/t013-contract-conformance.md",
    "tasks/todo.md",
    "docs/changelogs.md",
}
staged_names = set(
    subprocess.check_output(["git", "diff", "--cached", "--name-only"], text=True).splitlines()
)
assert staged_names == scope, staged_names ^ scope
assert not subprocess.check_output(
    [
        "git",
        "diff",
        "HEAD",
        "--",
        "backend",
        "frontend",
        "package.json",
        "package-lock.json",
        "requirements.lock",
        "requirements-dev.lock",
        "pyproject.toml",
        "vite.config.ts",
        "tsconfig.json",
        "eslint.config.js",
    ],
    text=True,
)
checked = 0
for name in sorted(scope):
    path = root / name
    for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
        target = target.split("#", 1)[0]
        if not target or "://" in target or target.startswith("mailto:"):
            continue
        local = (path.parent / target).resolve()
        if not local.exists():
            assert (shared / local.relative_to(root)).exists(), (name, target)
        checked += 1
authority_hashes = {
    "CONSTRAINTS.md": "8d324b1019c682fc6598ebdc4aecbdbc388ab2cff7d6e712a593636954316a25",
    "docs/adr/0004-v1-product-policy-and-operational-baseline.md": "6254e5a512d416938bcfe447c9e6af3c297fa7c5dbd8f6a77b18b227a0545c98",
}
for name, digest in authority_hashes.items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name
pattern = re.compile(
    r"sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,}|gh[pousr]_[0-9A-Za-z]{20,}"
    r"|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
)
for label, command in (
    ("staged diff", ["git", "diff", "--cached", "--no-ext-diff"]),
    ("local Git history", ["git", "log", "--all", "-p", "--no-ext-diff"]),
):
    candidates = len(pattern.findall(subprocess.check_output(command, text=True)))
    print(f"{label}: {candidates} credential-pattern candidates (contents redacted)")
    assert candidates == 0, "Review credential candidates without printing their values"
print(
    f"Scope: 8 task files; application/config unchanged; {checked} local links resolve; 2 authority hashes unchanged"
)
```

Frontend/backend lint/type/test/build and changed-code coverage are not required for a document-only task with unchanged application/config files. No source/test suppression or quality-bar edit is present. `npm run check:task`, generated-contract and security/architecture aggregate gates are SETUP_PENDING at this branch's baseline (T053/T017/T062/T063); no runtime gate is counted as passed.

## Handoff

All eleven ambiguity groups have a normative ADR decision, spec/API/UI mapping and document oracle. The documentation skill shaped the ADR's authority, alternatives, consequences and separate verification ownership; TDD supplied the RED→GREEN probes; incremental implementation kept each document slice verifiable; API/UI skills aligned receipt, source precondition and terminal-read/disclosure semantics.

Files changed: the five T013 allowlisted documents plus its card, `tasks/todo.md` and `docs/changelogs.md`. Spec/API/UI/card were untracked planning inputs before this task, so the atomic commit introduces their full snapshots; the provenance section above records the baseline without retaining a scanner-sensitive API digest fixture. Intentionally untouched: application/config/locks, CONSTRAINTS, ADR-0001–0004, historical review/security/observability/runbooks, real vocabulary data/credentials and concurrent T053 work. Read-only context copies remain untracked in this worktree.

Next: T006 is dependency-ready after T013; finish T053/T063 quality tooling in the ordered wave before downstream integration gates. Generated DTO/runtime source/SRS/quiz/session tests, Windows/browser/bridge profile/entitlement, semantic content, accessibility and performance remain with their existing task owners. No inference ran.
