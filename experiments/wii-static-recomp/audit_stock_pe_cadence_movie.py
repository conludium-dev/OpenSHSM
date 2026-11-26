"""Retain owned movie/SDK/audio/coherence acceptance while observing PE cadence."""
from pathlib import Path
import json

base = Path('experiments/wii-static-recomp/audit_stock_texture_late.py')
script = base.read_text().replace('window-texture-late', 'window-pe-cadence')
script = script.replace('texture-late', 'pe-cadence-live')
script = script.replace('window-dispatch-select/build.json', 'window-completed-frame/build.json')
script = script.replace('TEXTURE_LATE_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_EQUAL',
    'PE_CADENCE_GPU16_SETTINGS3_RETAINED_PARENT_COMPONENTS_VERIFIED')
scope = {'__file__': __file__}
exec(compile(script, str(base), 'exec'), scope)
path = scope['path']
report = json.loads(path.read_text())
report.update(result='PE_CADENCE_LIVE_OWNED_MOVIE_SDK_AUDIO_COHERENCE_AUDITED',
    baseAuditorSha256=scope['sha'](base))
report['limits'].append('Observational GX member only; original native component proof inherited for unchanged CPU/texture/VI/main, not rerun in this variant.')
report['limits'].append('Diagnostic timestamps perturb execution; no controlled performance gain or visual promotion from numerical audit.')
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'])
print(json.dumps({key: report[key] for key in ['captures', 'pairedCaptures', 'changedPairs', 'decodedMixedPairs', 'movieEvidenceMissing']}, indent=2))
