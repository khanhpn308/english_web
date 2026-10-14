"""Refresh metadata inventory only; image bytes are never modified."""
from pathlib import Path
import hashlib,json,struct
root=Path('docs/design/uxr-02'); manifest=root/'UXR-02-ARTIFACT-MANIFEST.json'; obj=json.loads(manifest.read_text(encoding='utf-8')); entries=obj['artifacts']; known={e['path'] for e in entries}
for entry in entries:
    p=root/entry['path']
    if p.suffix=='.png': assert hashlib.sha256(p.read_bytes()).hexdigest()==entry['sha256']
    else:
        entry['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
        entry['bytes']=p.stat().st_size
for p in sorted(root.rglob('*')):
    if p.is_file() and p.suffix in {'.py','.mjs'} and p.relative_to(root).as_posix() not in known:
        entries.append({'path':p.relative_to(root).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size,'lineage':'RELEASE_VERIFICATION_SOURCE'})
obj['artifacts']=sorted(entries,key=lambda e:e['path']);manifest.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
