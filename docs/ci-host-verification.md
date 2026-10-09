# Host-only CI verification for T089

This workflow is deliberately separate from the AI Worker. The Worker only
edits source code; a GitHub-hosted runner performs deterministic checks and
records its exit codes. A passing CI run does **not** by itself authorize a
merge, certify provider process isolation, or expand the T089 task allowlist.

## Workflow

File: `.github/workflows/t089-host-ci.yml`

- **Fast:** Automatically on a push to
  `feature/t089-r3-final-remediation`. Installs pinned Python/Node
  dependencies, runs the repository's existing fast checks, Mypy and a
  small host/Worker boundary regression smoke suite.
- **Full:** Opt-in only. Performs `npm run check:task:portable`
  (the existing eight-gate host runner) and uploads logs/coverage.
  All three security scanners use the versions in `docs/toolchain.md`;
  Gitleaks and OSV binaries are SHA-256 verified. Scanner/tool/network
  setup failure is a failure, not a PASS.

Both jobs use Python 3.12, Node 22, `npm ci`,
`requirements-dev.lock`, full Git checkout and `QUALITY_BASE_REF=origin/main`.
They run without privileged GitHub write permissions or repository secrets.

## Start the full suite before merge

A `workflow_dispatch` button is only available once the workflow
file exists on the default branch (`main`). While this workflow exists
only on the T089 feature branch, **do not merge just to enable that button**.

Instead, create a *new* qualifying tag pointing at the exact T089 commit
you want to verify:

```bash
cd /home/khanh/projects/english_web-t089-final
git status --short
git pull --ff-only origin feature/t089-r3-final-remediation
git rev-parse HEAD

# Use a unique tag name for each separate full verification request.
git tag ci-full/t089-20261008-r1
git push origin ci-full/t089-20261008-r1
```

The `ci-full/t089-*` tag push starts the **Full portable host gate**
against the tagged commit and does not modify `main`.
If the first tag is already in use, choose a different, unique tag name;
never force-move a tag. For future use after the workflow is merged into
`main`, GitHub Actions > T089 host verification > Run workflow also
supports `suite=full` or `suite=fast`.

## View and interpret results

Open the repository's **Actions** tab, select **T089 host verification**
and the run, then inspect **Fast host checks** or
**Full portable host gate**. Full runs attach a short-lived
`t089-host-verification-...` artifact containing gate logs and
coverage reports (including logs on failure).

The final full check must show `RESULT: PASS` and eight passing gates.
A passing Fast run alone is **not** sufficient for integration.
If no Actions runs appear, check that GitHub Actions is enabled for the
repository, its workflows are permitted by repository policy, and the
tag/branch matches the documented filters. Do not change application
checks or hide failures to make CI green.

## T090 phase-2: immutable PR #5 scope attribution and isolation feasibility (08/10/2026)

This is prospective analysis. It does not change historical T089 run contracts,
artifacts, hashes, or Git commits.

Source identities:
- PR #5: https://github.com/khanhpn308/english_web/pull/5
- PR base SHA: 8fc6d0d4bc9ea0309eb5759b8d48d84c593a1775
- PR head SHA: 39b2dbbc97c3d3806a26a6f3e64dd503d6c1b7a5
- Merge SHA: 835d85a8dafa74657f06597bf8903134bdd721a3
- CI R5: https://github.com/khanhpn308/english_web/actions/runs/37801947447
- T090 phase-1 merge SHA: 943cc2ed28f3621c555b2fe5adcdae10f0858894
- T090 phase-1 CI R4: https://github.com/khanhpn308/english_web/actions/runs/37806152945

The next table records Git blob SHA-1 (not EvidenceBundle SHA-256).
ABSENT means missing from the PR base tree. The original T089 allowlist
excluded every one of these eight paths.

| Exact path | PR base blob | PR head blob | Host ownership / rationale |
|---|---|---|---|
| .github/workflows/t089-host-ci.yml | ABSENT | 1ec59a6f94e9fdab1e3bae4e5e2c3b68d104ef8d | Host-executed CI |
| docs/ci-host-verification.md | ABSENT | 878d2d3a5097d3bfa572c1ff21bc88dc65f94497 | CI procedures and evidence |
| tests/orchestrator/test_recovery.py | ABSENT | 04bfdce32a5f5006a0975a6ccab35bb2b17ea2bb | Recovery/import regression |
| tests/orchestrator/test_runtime.py | ABSENT | f905544d2fa41fd3be937260c45785a7956dcd3e | Provider/process boundary tests |
| tools/orchestrator/__main__.py | 979a652e75113156494c2bca39d8cb910d8e4877 | fb6c2e1166cca39423ae07179fa08f8a016a6b03 | Explicit host verify-candidate CLI |
| tools/orchestrator/recovery.py | ABSENT | 23e634cfbdedbe1276eb1b50d6ccce63f6e80181 | Host-owned recovery provenance |
| tools/orchestrator/runtime.py | 3a9e8b2cb9a6be737fa2a099c4e9d80e0df4bf74 | 7aad2782ddde7899b018aa2f1c35aaac64d06ea0 | CLI/process permission boundary |
| tools/orchestrator/scheduler.py | 6e350dd50f7377fa30da004170537fb236dce305 | 0e36ad47733eaf97e04e57dcb2240e6462ecd59a | Deferred host verification scheduling |

Disposition: owner approval and PR #5 merge are historical facts. No
restaging/transplant is needed to make those already-merged files exist on
main. T090 owns future changes to these exact paths but does not retroactively
validate the T089 source allowlist. Final acceptance of T090 scope remains a
separate independent judgment.

Published AGY guidance describes headless soft-denial of tools that require
approval, accept-edits auto-approval of file edits, and wildcard deny actions
for command(*), mcp(*) and (platform permitting) unsandboxed(*):
- https://www.agy.dev/docs/cli/headless/
- https://www.agy.dev/docs/permissions/
- https://www.agy.dev/docs/cli/modes/

These descriptions do NOT prove effective isolation of the installed provider.
Permissions may vary with CLI version, platform, user settings, and subagent
tools. An OS sandbox that still permits commands does not satisfy code-only.
Codex workspace-write similarly permits commands. A workspace-wide write grant
does not enforce the exact file allowlist.

Required live synthetic attestation: record CLI/version/OS/policy digest,
attempted tool calls, pre-execution denials, absent command-execution sentinel
files, blocked shell/Git/Python/subprocess/indirect MCP/subagent/escalation and
out-of-allowlist writes, and successful allowlisted file editing under the
same policy. Mocks, a model choosing not to issue a command, and exit-code-zero
with headless soft-denial are not equivalent to a negative tool-boundary proof.

If a provider cannot be attested, prefer a host-mediated edit interface:
no executable model tools, typed candidate-bound proposed edits, and a host-only
exact-path/content-digest validator and writer. This is a prospective
implementation option, not yet implemented or security-attested.

Current disposition: T090 IN_PROGRESS; T089 REOPENED_PENDING_T090. The existing
CliProvider WorkerResult block remains required. CI PASS on previous commits
does not constitute live provider command denial or permission to merge new code.
