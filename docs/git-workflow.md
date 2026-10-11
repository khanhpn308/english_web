# Git workflow

T045 implements local Git hygiene under [AGENTS.md](../AGENTS.md), [CONSTRAINTS.md](../CONSTRAINTS.md) and the [task plan](task-plan.md). The existing [toolchain guide](toolchain.md) owns dependency installation and scanner versions. T045 adds no dependencies, changes no thresholds and does not configure a remote.

## Branches and worktrees

Use one short-lived branch per task. The default repository convention is `feature/task-<id>-<slug>`. Preserve an explicitly assigned name, including T045's `feature/t045-git-hygiene`; do not rename an existing branch to match an example.

Parallel Agents use separate Git worktrees, task write allowlists and temporary data. Inspect existing branches/worktrees before creating anything. Start a new worktree from the latest owner-authorized `origin/main`, after an authorized fetch. A stale remote-tracking ref is not evidence of the latest remote state. For example, only when worktree creation and fetching are authorized:

```sh
git worktree list
git branch --list feature/task-t046-metrics
git fetch origin main
git worktree add -b feature/task-t046-metrics ../vocabularies-t046 origin/main
```

Choose a fresh path and branch. Never overwrite, force-checkout or remove another Agent's worktree. A branch or path collision requires a different unused name or explicit coordination with its owner.

The Host serializes integration when tasks touch the same file. Resolve each conflict against both task contracts and preserve both implementations and changelog histories. Keep generated artifacts with their designated generator/owner. Do not resolve conflicts by discarding a side or resetting another worktree.

## Commits

Use atomic Conventional Commits with a task scope and a reason, for example `chore(T045): guard staged commits against unsafe files`. Supported types include `feat`, `fix`, `test`, `docs`, `chore` and `refactor`.

Before an authorized commit, inspect the staged paths and diff locally. Stage only the task's approved files and required bookkeeping. Never stage the whole worktree automatically. Include the task's changelog with its implementation; keep Host merge commits and integration-status-only metadata changes separate from implementation commits.

Never commit credentials, real environment files, learning databases/journals, browser profiles or authentication state, dependency directories, build output, or unreviewed screenshots/archives. Use synthetic or reviewed public fixtures. `.env.example` may contain placeholders only. Record intentionally untouched files in the handoff.

## Text and executable files

[.gitattributes](../.gitattributes) normalizes text to LF, explicitly including shell, Python, JavaScript/TypeScript/TSX, Markdown, YAML and cross-platform PowerShell. Windows `.bat`/`.cmd` files check out with CRLF. Declared binary formats do not receive text normalization.

The attributes apply to future staging/checkouts. Do not run `git add --renormalize` as part of T045 or rewrite historical file contents. Executability is a Git file mode, not a text attribute. The Host must make `.githooks/pre-commit` executable and preserve mode `100755` when it stages the source. On Windows, after explicitly staging that file, `git update-index --chmod=+x .githooks/pre-commit` records the executable mode. These steps were not performed by the coding Worker.

## Local hook activation

Activation is explicit and requires Git, a POSIX shell such as Git Bash on Windows, Python 3.12+, Node.js >=20.19.0 and npm >=10.0.0. Install locked dependencies using the toolchain guide before committing, activate the Python development venv so `python` resolves correctly, and provide pinned Gitleaks 8.30.1 on PATH or via an absolute `GITLEAKS_BIN` path. The hook never installs missing tools.

First inspect and record any existing `core.hooksPath`. On POSIX systems, the Host can make the file executable. The following commands document activation; the Worker does not run them:

```sh
git config --show-origin --get-all core.hooksPath
chmod +x .githooks/pre-commit
git config --local core.hooksPath .githooks
```

An absent configuration value returns nonzero from the inspection command. Do not treat that as a check result. Repository-local configuration is shared by linked worktrees unless `extensions.worktreeConfig` has already been enabled. Coordinate activation with the Host and other worktree owners. If that extension is already enabled, use `git config --worktree core.hooksPath .githooks` to configure only the intended worktree. Do not change global configuration or enable the extension automatically.

## What the hook does

1. Requires Git, Python and npm, and rejects staged whitespace errors with `git diff --cached --check`.
2. Reads staged filenames using NUL separators, rejects files matching ignore rules even if force-added, and blocks known credential, database/journal and browser-profile/auth-state paths.
3. Copies the index into an owned temporary directory with `git checkout-index --all --prefix=...`. It reuses installed `node_modules` through a POSIX directory link or a Windows junction. Unstaged changes and untracked source cannot hide an invalid staged version. Symlinks, submodules and unresolved index entries fail closed; the current repository has regular tracked files.
4. Runs the existing `npm run check:fast:active` in that staged snapshot. As defined in `package.json`, it runs `format:check`, `lint`, `typecheck` and `floor:check`. The existing quality baseline and thresholds remain unchanged, including `QUALITY_BASE_REF` when explicitly provided.
5. Runs the existing `npm run security:secrets` in the actual worktree. Its T063 wrapper scans working/untracked files, the index and history reachable from the current HEAD with redaction. Before an initial commit without HEAD, the hook additionally runs that same scanner on the staged snapshot because the wrapper otherwise scans only working files.
6. Rejects an index change detected during checks and removes its owned temporary snapshot. It never stages, stashes, resets or cleans developer files.

`npm run check:fast` already combines `check:fast:active` with `security:secrets`. The hook splits those existing commands so quality checks see staged source and the secret scan retains its real worktree/index/history scopes. It does not run `check:fast` again, duplicate the floor guard, or reimplement secret detection. Except for the necessary no-HEAD snapshot scan, it runs each gate once.

Any required failure returns nonzero. Missing tooling and snapshot/Git setup errors return nonzero as well; no skipped check reports success. The hook discards raw command output because whitespace and formatter/linter diagnostics can contain source or credentials. It reports the failed guard or npm command without displaying matched contents. The existing scanner may write its redacted, ignored `htmlcov/security/gitleaks.json` report. Diagnose the named command locally only when verification is authorized and output can be handled privately.

The fast gate does not run unit/integration suites, Python Mypy/Ruff lint, coverage, browser checks or a build. Task-specific checks and CI remain required evidence when the owner authorizes verification. Text scanning cannot classify arbitrary private learning content or read secrets in screenshots/archives. Manual staged scope and asset review remains required. Do not edit or stage files concurrently with a commit attempt.

## Disabling or overriding a local hook

If necessary and explicitly authorized, remove only the T045 configuration value or restore the previously recorded value. If the previous repository-local value was absent and the current value is exactly `.githooks`, the removal command is:

```sh
git config --local --unset-all core.hooksPath
```

For a worktree-specific activation, use `--worktree` instead. Reinspect `core.hooksPath` afterwards because inherited configuration may still apply. Do not delete other hooks or edit global settings.

Git's explicit `--no-verify` override and disabled hooks bypass local guards. Any owner-authorized emergency use must record the reason, approving owner, commit and outstanding checks. It is a review failure and an unverified handoff, never accepted verification or release evidence. The hook has no environment-variable or automatic bypass.

## Remotes and release hygiene

Push, PR creation, merging, tagging and publishing require explicit authorization. Never force-push protected integration branches such as `main`, move published release tags, or rewrite history to conceal previous work. A local pre-commit hook cannot enforce remote force-push protection. Required remote branch/ruleset protection is separate repository policy managed by the owner; T045 does not configure it.

Exclude secrets and private data from commits, CI reports and release artifacts. If a credential enters history, stop distribution, rotate it, and have the owner coordinate incident recovery. Do not silently purge history or publish another artifact.

Release tags must identify the exact accepted integration commit and follow the owner-approved repository release plan. [T056](../tasks/t056-windows-package.md) owns packaging and [T057](../tasks/t057-release-verification.md) owns release acceptance. The current task plan does not prescribe a tag format or approve a release version. Obtain the approved tag/version before tagging; do not infer release acceptance from the manifests' `0.1.0` or create a tagging scheme in T045.

## Coding First and evidence

The owner policy completes implementation of all 90 tasks before project-wide testing, audit and remediation. `CODING_DONE` records source implementation completion. `FINAL_VERIFICATION_DEFERRED` records outstanding executable checks and release evidence. They can coexist; neither means PASS, TESTED or RELEASE_ACCEPTED.

Use the [PR template](../.github/pull_request_template.md) to record `IMPLEMENTED`, `IMPLEMENTED_UNVERIFIED`, `TESTED`, `MERGED` and `RELEASE_ACCEPTED` separately. Each actual check needs its command, environment, exit code and evidence for the relevant commit. A merged implementation retains its unresolved verification. Historical dependency evidence does not verify a new candidate.

T045 is `IMPLEMENTED_UNVERIFIED` on `feature/t045-git-hygiene`. T012's card records coding integration with final CI/release acceptance deferred; T063 records historical scanner evidence. This Worker inspected source only and ran no hook, tests, lint, typecheck, build, security scan, CI or audit. The task card and todo remain unchanged.

The Host's next actions are to record executable mode, inspect/stage only the five allowed files, and integrate only with authorization while preserving the unverified status. Hook activation is optional explicit setup. After the owner authorizes final verification, exercise staged whitespace/private-file rejection, missing-tool failures, clean/partial staging, no-HEAD secret handling, filenames with whitespace, Linux/Git Bash and Windows junction cleanup. Run the task's documented checks and applicable gates then; do not label these deferred checks PASS.
