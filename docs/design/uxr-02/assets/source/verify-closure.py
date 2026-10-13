"""Read-only UXR-02 release artifact/Markdown validation."""
from pathlib import Path
import hashlib, json, re, struct

repo=Path.cwd(); root=repo/'docs/design/uxr-02'; issues=[]
manifest=json.loads((root/'UXR-02-ARTIFACT-MANIFEST.json').read_text(encoding='utf-8'))
for entry in manifest['artifacts']:
    p=root/entry['path']
    if not p.is_file(): issues.append('Missing '+entry['path']); continue
    raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=entry['sha256']: issues.append('Hash mismatch '+entry['path'])
    if 'width' in entry and struct.unpack('>II',raw[16:24])!=(entry['width'],entry['height']): issues.append('Dimension mismatch '+entry['path'])
for p in list(root.rglob('*.md'))+[repo/'tasks/uxr-02-design-foundation-appshell-specification.md']:
    s=p.read_text(encoding='utf-8-sig')
    for target in re.findall(r'\]\(([^)]+)\)',s):
        if re.match(r'^(https?:|#|app:|plugin:)',target): continue
        target=target.split('#')[0]
        if not (p.parent/target).exists(): issues.append(f'Broken Markdown link {p.relative_to(repo)} -> {target}')
for p in root.rglob('*.html'):
    for target in re.findall(r'(?:src|href)="([^"#]+)"',p.read_text(encoding='utf-8-sig')):
        if target.startswith(('http:','https:','data:','/')): continue
        if not (p.parent/target).exists(): issues.append(f'Broken HTML link {p.relative_to(repo)} -> {target}')
print(json.dumps({'manifest_entries':len(manifest['artifacts']),'png_count':sum('width' in x for x in manifest['artifacts']),'issues':issues},indent=2))
raise SystemExit(bool(issues))
