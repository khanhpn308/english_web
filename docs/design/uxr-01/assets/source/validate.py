"""Bounded validation of the design review packet, not application acceptance."""
from pathlib import Path
import json
import re
import subprocess

root=Path(__file__).resolve().parents[5]
task=root/'docs/design/uxr-01'
required=['UXR-01-EVIDENCE-LEDGER.md','UXR-01-DIRECTION-COMPARISON.md','UXR-01-DESIGN-DECISION.md','UXR-01-HANDOFF.md','UXR-01-VISUAL-GALLERY.md','UXR-01-IMPECCABLE-EVIDENCE.md']
for name in required: assert (task/name).is_file(),name
manifest=json.loads((task/'assets/image-manifest.json').read_text(encoding='utf-8'))
links=[];missing=[]
for name in required+['CHANGELOG.md','research/SESSION-RESULT.md']:
    p=task/name
    text=p.read_text(encoding='utf-8')
    # Inspect actual Markdown destinations, not backtick provenance paths.
    for target in re.findall(r'\]\(([^\s)]+)\)',text):
        if target.startswith(('https://','http://','app://')):continue
        target=target.split('#',1)[0]
        if not target:continue
        actual=(p.parent/target).resolve()
        links.append((name,target))
        if not actual.is_file():missing.append((name,target))
assert not missing,missing
for x in manifest['original_images']+manifest['baseline_copies']+manifest['derived_contact_sheets']:
    assert (task/x['path']).is_file(),x['path']
checks=json.loads((task/'research/static-render-checks.json').read_text(encoding='utf-8'))
assert len(checks)==50
assert all(not x['errors'] and x['pageWidth']==x['width'] for x in checks)
assert all(x['largestButtonHeight']<=90 for x in checks)
status=subprocess.run(['git','status','--porcelain=v1','--untracked-files=all'],cwd=root,text=True,capture_output=True,check=True).stdout
changed=[line[3:].strip('"') for line in status.splitlines()]
assert all(p.startswith('docs/design/uxr-01/') for p in changed),changed
files=[p for p in task.rglob('*') if p.is_file()]
record=f'''# UXR-01 package verification

Task UXR-01, visual version v1.2, owner visual approval PENDING.

- Required packet documents present: {len(required)}. (The user-required gallery and Impeccable evidence are included.)
- Original task PNGs: A 27 + B 27. Baseline capture copies: 21. Derived contact sheets: {len(manifest['derived_contact_sheets'])}.
- `python docs/design/uxr-01/assets/source/package.py`: every PNG signature, exact frame dimension, chunk CRC and complete IEND validated; SHA256 recorded. Archived reports/captures compare byte-identically to UXR-00 originals. No current-app image was synthesized.
- `python docs/design/uxr-01/assets/source/validate.py`: {len(links)} local Markdown destinations in the integrated packet resolve to real files; all manifest paths exist; only task-folder changes in dedicated worktree. External links are citations, not a claim of a new HTTP status check for each page. Original archived report wording and relative context are preserved rather than rewritten.
- `node docs/design/uxr-01/assets/source/confirm.mjs`: 50 standalone light-state renders with zero recorded script errors, zero page-level horizontal overflow, zero visible buttons taller than 90px.
- Original PNGs, desktop A/B contact sheet and representative mobile, drawer, dark, result, conflict and UNKNOWN states were opened with image viewing tools. This is visual review, not actual application testing.
- No frontend/backend/generated DTO/components.json/lockfile/task-todo/constraints/schema/ADR/shared changelog mutation appears in the task worktree.
- Gitleaks gate: attempted, exit 1, `SETUP_FAILED: gitleaks is unavailable`. No security PASS; commit and push not attempted. Manual task asset review does not replace the missing pinned scanner.
- Git whitespace: `git diff --check` concerns tracked diffs only; task files are new/untracked at this checkpoint. It is not represented as staged-diff validation or a commit result.

No full test/CI/WCAG PASS is claimed. The static checks do not establish production focus, screen reader, browser zoom, API behavior, source safety, persistence or AI policy correctness.
'''
(task/'research/PACKAGE-VERIFICATION.md').write_text(record,encoding='utf-8')
print(json.dumps({'required_documents':len(required),'original_images':54,'baseline_images':21,'local_links':len(links),'missing_local_links':0,'files_before_verification_record':len(files),'only_task_folder_changes':True}))
