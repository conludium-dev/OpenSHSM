"""Reuse owned movie/SDK/audio/coherence gates for the main-only scheduling variant."""
from pathlib import Path
import json

base = Path('experiments/wii-static-recomp/audit_stock_texture_late.py')
script = base.read_text().replace('window-texture-late', 'window-post-present')
script = script.replace('texture-late', 'post-present-live')
script = script.replace('window-dispatch-select/build.json', 'window-pe-cadence/build.json')
script = script.replace('TEXTURE_LATE_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_EQUAL',
    'POST_PRESENT_GPU22_MAIN_DELTA_RETAINED_PARENT_COMPONENTS_VERIFIED')
scope = {'__file__': __file__}
exec(compile(script, str(base), 'exec'), scope)
path = scope['path']
report = json.loads(path.read_text())
report.update(result='POST_PRESENT_LIVE_MOVIE_SDK_AUDIO_COHERENCE_AUDITED',
    baseAuditorSha256=scope['sha'](base))
report['limits'].append('Main-only post-swap drain changes live scheduling; archived CPU/texture/VI probes inherited unchanged, not full-game equivalence.')
report['limits'].append('Diagnostic timestamps perturb execution; no controlled performance percent or visual promotion from numerical audit.')
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'])
print(json.dumps({key: report[key] for key in ['captures', 'pairedCaptures', 'changedPairs', 'decodedMixedPairs', 'movieEvidenceMissing']}, indent=2))
