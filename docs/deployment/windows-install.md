# T056 — Windows install and recovery (CODE_ONLY)

This records **source implementation only**. No Windows artifact, installer, browser
bootstrap, offline launch, upgrade or uninstall has been independently verified.

## Build inputs

- Windows 11 x64 with Python 3.12, Tk/Tcl and a dedicated, clean build environment.
- Pin the packager to **PyInstaller 6.16.0** in an isolated packaging environment.
- Install the application's Python runtime dependencies using the repository's
  approved lockfile procedure. `tzdata` must be available to the Windows build:
  this is **currently an unresolved platform lockfile remediation** (T040
  follow-up). Do not modify `requirements.lock` manually or use a Linux
  requirements workaround as a substitute for a regenerated Windows lock.
- Node/npm from the pinned project toolchain; source tree checked out at an
  intended clean commit, with no user data or real credentials included.
- Inno Setup 6 compiler (`ISCC.exe`) is a separate, manually installed tool;
  no installer compilation or download runs from the build helper.

## Source build recipe (not executed in this checkpoint)

From the root of the clean Windows checkout:

```powershell
npm ci
npm run build
python -m pip install -r requirements.lock
python -m pip install "pyinstaller==6.16.0" tzdata
python packaging/build_windows.py --build
python packaging/build_windows.py --verify
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "packaging\installer.iss"
```

**Note:** The above is an operator recipe, *not* evidence of successful lockfile
installation. The application already demonstrated a missing `tzdata` blocker on
Windows. Resolve the Windows-specific Python lockfile via the approved dependency
workflow before issuing a release artifact. For the final build, use an isolated
venv containing only runtime and packaging dependencies, never the development
environment containing pytest, ruff, mypy or real learning databases.

`build_windows.py --build` requires Windows Python 3.12, the exact PyInstaller
version and Tk availability. It refuses to overwrite an existing dist directory.
PyInstaller onedir contains Tcl/Tk, bundled IANA timezones, Alembic migration
scripts and the Vite production assets; it excludes uvloop and test tooling.
The package manifest contains the Git source revision, pinned build-tool version
and lexically sorted SHA-256 file inventory. `--verify` independently recomputes
the inventory and rejects missing, changed, symlinked or known secret/dev/data
artifacts. This gives reproducible **manifest rules**; bit-for-bit PE binary
reproducibility across Windows builders remains unverified.

Installer inputs:

- `packaging/dist/VocabularyApp/`: signed-off verified binary tree
- `packaging/installer.iss`: per-user Inno Setup installer
- Installer output: `packaging/dist/installer/`

The installer creates a Start Menu shortcut and optional desktop shortcut
to `VocabularyApp.exe`. Launcher owns loopback socket/bootstrap; there is no
second HTTP server, Electron runtime, remote login or launch-time inference.
Do not sign the release without a real trusted signing key. No signing
certificate has been created, inferred, or requested here.

## Persistence and upgrade invariants

Installation directory: `%LOCALAPPDATA%\Programs\VocabularyApp`.

The installer does not own or delete:

- `%LOCALAPPDATA%\VocabularyApp` (current-user configuration and DPAPI key);
- `%USERPROFILE%\Documents\VocabularyApp` (default SQLite/data root);
- user-selected Markdown roots and any alternate native-configured data root.

No `[UninstallDelete]` action is present. An upgrade must reuse the same
stable `AppId`; never put a study database, user Markdown or protected key in
the PyInstaller tree. Close the launcher before updating executable files.

Before updating, obtain a consistent **offline** independent backup of both
roots. For integrity/migration recovery, follow
[staging restore](../runbooks/first-run-and-restore.md) and verify the new
candidate first; never overwrite the original database.

## Deferred evidence

The following remain **PENDING**, not PASS: fresh Windows x64 packaging build,
PyInstaller/Tcl/Tk bundled dialog exercise, ZIP/file manifest reproducibility,
Inno compiler result, cold offline launch and authenticated loopback bootstrap,
real update/uninstall data retention, Windows-native security and accessibility
checks, negative secret scan, dependency SBOM and signing/distribution approval.
