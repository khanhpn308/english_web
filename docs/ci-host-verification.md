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
