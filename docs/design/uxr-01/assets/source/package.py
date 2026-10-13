"""Create the UXR-01 image metadata and owner gallery from the existing PNGs."""
from pathlib import Path
import hashlib
import json
import re
import struct
import zlib

root=Path(__file__).resolve().parents[5]
task=root/'docs/design/uxr-01'
render=(task/'assets/source/render.mjs').read_text(encoding='utf-8')
cases=re.findall(r"\['([^']+)'\s*,\s*'([^']+)'\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*'([^']+)'\]",render)
assert len(cases)==27, f'Expected 27 scenarios; saw {len(cases)}'

state_map={
 'dashboard-first-run':('G1/G9','/','First-run: due 0; unknown streak; no attempts'),
 'dashboard-populated':('G1/G9','/','Populated: due 12; streak 6; independent result types'),
 'lookup-search-detail':('G1/G3','/search → /word-forms/:id','Stored Search and selected Detail; not an AI lookup response'),
 'review':('G1/G5','/review','Revealed word/meaning; four backend-defined rating choices'),
 'quiz':('G1/G6','/quiz/:attemptId','IN_PROGRESS multiple-question attempt; acknowledged draft'),
 'status-consent':('G1/G8','/status#ai-consent','Local ready; AI unknown; incomplete policy; no grant'),
 'status-error':('G1/G8','/status#ai-consent','Unconfirmed revoke UNKNOWN + offline bridge + local ready'),
 'lookup-preview':('G1/G2/G4','/lookup','Synthetic AI preview, UNVERIFIED source; not saved; date/source save section'),
 'edit-conflict':('G1/G4','/word-forms/:id','Bilingual retained edit draft / REVISION_CONFLICT / explicit source reread'),
 'results':('G1/G7','/quiz/:attemptId/result','SUBMITTED objective/self-score separate; advisory AI not requested; SOURCE_BACKED current state NOT_VERIFIED'),
 'navigation-drawer':('G1','Current routes / menu','Mobile open drawer concept; close, groups and consent entry'),
 'quiz-unknown':('G1/G6/G8','/quiz/:attemptId','UNKNOWN autosave; same-intent reconciliation; submit disabled'),
 'review-unknown':('G1/G5/G8','/review','UNKNOWN rating receipt; same-intent check; new ratings disabled'),
}

def png_info(path):
    b=path.read_bytes()
    assert b[:8]==b'\x89PNG\r\n\x1a\n',str(path)
    width,height=struct.unpack('>II',b[16:24])
    pos=8; ended=False
    while pos<len(b):
        n=struct.unpack('>I',b[pos:pos+4])[0]
        tag=b[pos+4:pos+8]; payload=b[pos+8:pos+8+n]
        crc=struct.unpack('>I',b[pos+8+n:pos+12+n])[0]
        assert zlib.crc32(tag+payload)&0xffffffff==crc,f'PNG CRC mismatch: {path}'
        pos+=n+12
        if tag==b'IEND': ended=True;break
    assert ended and pos==len(b),f'Incomplete PNG: {path}'
    return {'width':width,'height':height,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}

images=[]
for direction in ('a','b'):
    for i,(scenario,theme,width,height,name) in enumerate(cases,1):
        group,route,state=state_map[scenario]
        rel=f'assets/{direction}/{name}.png'
        info=png_info(task/rel)
        assert info['width']==int(width) and info['height']==int(height),rel
        images.append({'image_id':f'{direction.upper()}{i:02d}','task_id':'UXR-01','group':group,'route':route,'state':state,'scenario':scenario,'direction':direction.upper(),'viewport_css':f'{width}×{height}','device_scale_factor':1,'theme':theme,'evidence_type':'DESIGN_MOCKUP','data_type':'SYNTHETIC','synthetic_data':True,'version':'v1.2','date':'2026-10-12','path':rel,**info})

baseline=[]
source_root=Path('C:/Users/khanh/projects/vocabularies-smoke/artifacts/uxr00')
for path in sorted((task/'research/uxr00/A3-browser/screenshots').glob('*.png')):
    original=source_root/'A3-browser/screenshots'/path.name
    assert path.read_bytes()==original.read_bytes(),f'Baseline changed: {path}'
    label='SYNTHETIC_RENDERED' if 'SYNTHETIC' in path.name else 'REAL_RENDERED'
    group=path.name.split('-')[0]
    route={'G1':'/','G2':'/lookup','G3':'/word-forms/:id' if 'word-detail' in path.name else '/search','G4':'/word-forms/:id','G5':'/review','G6':'/quiz/new' if 'builder' in path.name else '/quiz/:attemptId','G8':'Consent dialog (initiating route not recorded)' if 'consent-dialog' in path.name else '/status','G9':'/'}[group]
    info=png_info(path)
    baseline.append({'task_id':'UXR-00','group':group,'route':route,'viewport_css':f"{info['width']}×{info['height']}",'direction':'BASELINE','evidence_type':'CURRENT_APP_CAPTURE','fixture_type':label,'synthetic_data':label=='SYNTHETIC_RENDERED','version':'audit-c2417ba6','theme':'as captured','state': 'Status top only; consent not visible' if path.name.startswith('G8-status-consent') else 'See original screenshot inventory','path':str(path.relative_to(task)).replace('\\','/'),**info})
assert len(baseline)==21
for path in (task/'research/uxr00').rglob('*.md'):
    original=source_root/path.relative_to(task/'research/uxr00')
    assert original.read_bytes()==path.read_bytes(),f'Report copy changed: {path}'

derived=[]
for path in sorted((task/'assets/contact-sheets').glob('*.png')):
    derived.append({'task_id':'UXR-01','evidence_type':'DESIGN_MOCKUP','direction':'A/B' if path.stem.startswith('ab') else path.stem[0].upper(),'group':'G1–G9 representative','route_state':'Matched direction preview montage; see original image rows','theme':'mixed labelled originals','synthetic_data':True,'version':'v1.2','path':str(path.relative_to(task)).replace('\\','/'),**png_info(path)})

manifest={'task_id':'UXR-01','version':'v1.2','status':'OWNER_VISUAL_APPROVAL_PENDING','original_images':images,'baseline_copies':baseline,'derived_contact_sheets':derived}
(task/'assets/image-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

gallery='''# UXR-01 visual gallery — v1.2

**OWNER_VISUAL_APPROVAL_PENDING.** 27 original full-resolution PNGs for A and 27 for B. This includes 24 minimum matched frames (six scenarios × two directions × desktop/mobile) plus 30 responsive/theme/conflict/uncertainty/source-backed extras. All task originals are **DESIGN_MOCKUP / SYNTHETIC**, 100% intended zoom, device scale 1, rendered in installed Chrome from standalone local HTML. They are not production React screenshots, real study records, provider output, or proof of persistence.

Open an individual filename below for its original PNG. The desktop/mobile/fold names denote exact image and CSS viewport dimensions, not a downsampled export. A visible viewport may continue below its fold; full resolution does not mean a full-page screenshot.

Compare [A/B six-scenario board](assets/contact-sheets/ab-comparison.png), [A contact sheet](assets/contact-sheets/a-gallery.png), [B contact sheet](assets/contact-sheets/b-gallery.png), [scores and nine-group analysis](UXR-01-DIRECTION-COMPARISON.md), or [pending owner decisions](UXR-01-DESIGN-DECISION.md). Contact sheets aid comparison and never replace the individual originals. [Image manifest](assets/image-manifest.json) provides exact dimensions, bytes and SHA256.

'''
for direction,name in [('A','Calm Academic Workspace'),('B','Compact Study Console')]:
    gallery+=f'## Direction {direction} v1.2\n\n{name}. All rows: UXR-01, DESIGN_MOCKUP, synthetic data YES, version v1.2, 12/10/2026.\n\n'
    gallery+=f'![Direction {direction} overview](assets/contact-sheets/{direction.lower()}-gallery.png)\n\n'
    gallery+='| Image ID / Task | Group | Route / state | Direction | Viewport CSS / PNG | Theme | Evidence / synthetic | Version | Full-resolution original |\n|---|---|---|---|---|---|---|---|---|\n'
    for x in images:
        if x['direction']!=direction:continue
        gallery+=f"| {x['image_id']} / UXR-01 | {x['group']} | `{x['route']}` — {x['state']} | {direction} | {x['viewport_css']} | {x['theme']} | DESIGN_MOCKUP / YES | v1.2 | [{Path(x['path']).name}]({x['path']}) |\n"
    gallery+='\n'
gallery+='''## Baseline current-app images — UXR-00

The accessible [original baseline inventory and issues](research/uxr00/A3-browser/REPORT.md) explain the actual captured route/state, fixture category and source. The local originals were copied byte-for-byte; manifest hashes verify the copies. They are **CURRENT_APP_CAPTURE**, never proposed A/B visuals. No current G7 or populated G9 capture exists. Narrow legacy G8 Status filenames do not prove consent-section reachability.

'''
gallery+='| Task / group | Route / state | Direction / version / theme | Evidence / synthetic | CSS / PNG viewport | Full-resolution baseline |\n|---|---|---|---|---|---|\n'
for x in baseline:
    gallery+=f"| UXR-00 / {x['group']} | `{x['route']}` — {x['state']} | BASELINE / audit-c2417ba6 / as captured | CURRENT_APP_CAPTURE / {x['fixture_type']} / {'YES' if x['synthetic_data'] else 'NO (isolated local state)'} | {x['width']}×{x['height']} | [{Path(x['path']).name}]({x['path']}) |\n"
gallery+='''
## Contact-sheet metadata

Contact sheets are derived comparison assets, not additional original scenario captures. All are task UXR-01, group G1–G9 representative, direction as labelled, mixed route/state originals, DESIGN_MOCKUP / SYNTHETIC YES / v1.2. Their exact exported dimensions and hashes are in the manifest. They include only the task mockup images.

| Derived image | Direction | Purpose | Direct PNG |
|---|---|---|---|
| CS-A | A | Representative desktop/responsive/theme/state gallery | [A gallery](assets/contact-sheets/a-gallery.png) |
| CS-B | B | Equivalent representative gallery | [B gallery](assets/contact-sheets/b-gallery.png) |
| CS-AB | A/B | Equivalent six desktop scenarios side by side | [A/B comparison](assets/contact-sheets/ab-comparison.png) |

## Render provenance and caveats

The final standalone sources are [A HTML](assets/source/direction-a.html), [B HTML](assets/source/direction-b.html) and the [renderer](assets/source/render.mjs). They reuse no production page and make no HTTP/API/provider call. The appearance illustrates how canonical and proposed official components could be composed; it is not an installed Radix component demonstration. Static anchors/actions do not prove app navigation, autosave, consent, rating, or focus behavior.

G3/G4/G7 are source-backed concepts; the ledger distinguishes partial current captures from missing states. Error/UNKNOWN/offline and long Vietnamese data are meaningful proposed states; their actual application transitions remain NOT_VERIFIED.

Reviewing these screenshots does not automatically approve them. Choose a **named direction and version** and complete the owner decision sheet. UXR-01 remains pending; UXR-02 is not started.
'''
(task/'UXR-01-VISUAL-GALLERY.md').write_text(gallery,encoding='utf-8')
print(json.dumps({'A':27,'B':27,'baseline':21,'contact_sheets':len(derived),'all_png_crc_valid':True}))
