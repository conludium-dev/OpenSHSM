"""Reuse current phase/render audits with exact texture-only build and explicit temporary captures."""
from pathlib import Path
import hashlib
import json

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-texture-o2'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
component_path = output / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['result'] == 'TEXTURE_O2_REAL_GL_PIXELS172_EVICTION1600_EQUAL'
assert component['buildSha256'] == sha(build_path)
parent_path = root / 'window-ios-o2-phases/build.json'
assert build['parentBuildSha256'] == sha(parent_path)
run_path = root / 'headless-sc-pc-headless-windowed-texture-o2-live-result.json'
run = json.loads(run_path.read_text())
prefix = Path(run['capturePrefix'])
assert run['temporaryCapture'] and run['capture']
assert prefix.parent.parent == Path('/private/tmp')
assert prefix.parent.name.startswith('openshsm-captures-')
assert prefix.name == 'headless-sc-pc-texture-o2-live-efb'

base = Path('experiments/wii-static-recomp/audit_stock_live_phases.py')
script = base.read_text()
start = script.index('if args.timer_only:\n')
end = script.index('vi_original = Path(vi_build', start)
script = script[:start] + '''vi_build = json.loads((root / 'window-live-phases/build.json').read_text())
vi_source = root / 'window-live-phases/output_39.cpp'
''' + script[end:]
patches = [
    ("output = root / ('window-vi-timer' if args.timer_only else 'window-live-phases')", "output = root / 'window-texture-o2'"),
    ("tag = 'vi-timer' if args.timer_only else 'live-phases'", "tag = 'texture-o2-live'"),
    ("exe = output / ('OpenSHSMStockVITimer' if args.timer_only else 'OpenSHSMStockLivePhases')", "exe = Path(build['executablePath'])"),
    ("root.glob(f'headless-sc-pc-{tag}-efb_debug_*.bmp')", "Path(run['capturePrefix']).parent.glob(Path(run['capturePrefix']).name + '_debug_*.bmp')")]
for before, after in patches:
    assert script.count(before) == 1
    script = script.replace(before, after, 1)
exec(compile(script, str(base), 'exec'), {'__file__': __file__})
report_path = output / 'live-audit.json'
report = json.loads(report_path.read_text())
assert report['captures']
report.update(result='TEXTURE_O2_EXISTING_HOST_VI_MOVIE_PHASES_AUDITED',
    componentSha256=sha(component_path), baseAuditorSha256=sha(base), auditorSha256=sha(Path(__file__)),
    capturePrefix=str(prefix))
report['limits'].append('Temporary captures retain original RGBA; display PNGs preserve exact RGB. Human visual/audio acceptance separate.')
report_path.write_text(json.dumps(report, indent=2) + '\n')

render_base = Path('experiments/wii-static-recomp/audit_stock_ios_o2_render_cost.py')
render = render_base.read_text()
for before, after in [
    ("output = root / 'window-ios-o2-phases'", "output = root / 'window-texture-o2'"),
    ("'IOS_O2_EXISTING_HOST_VI_MOVIE_PHASES_AUDITED'", "'TEXTURE_O2_EXISTING_HOST_VI_MOVIE_PHASES_AUDITED'"),
    ("headless-sc-pc-headless-windowed-ios-o2-phases", "headless-sc-pc-headless-windowed-texture-o2-live"),
    ("archive = root / 'window-ios-o2/libnwiiruntime.a'", "archive = Path(json.loads((output / 'build.json').read_text())['archivePath'])")]:
    assert before in render
    render = render.replace(before, after)
assert render.count("'labelSeconds': int(seconds)") == 1
render = render.replace("'labelSeconds': int(seconds)", "'labelRaw': seconds")
assert render.count(r"(\d+)s frames=") == 1
render = render.replace(r"(\d+)s frames=", r"([0-9a-f]+)s frames=")
exec(compile(render, str(render_base), 'exec'), {'__file__': __file__})
audio_base = Path('experiments/wii-static-recomp/audit_stock_bounds_visual.py')
audio = audio_base.read_text()
audio_start = audio.index("fields = ['wallUs'")
audio_end = audio.index("timing = root /", audio_start)
scope = {'text': (root / 'headless-sc-pc-headless-windowed-texture-o2-live.log').read_text()}
exec('import re\n' + audio[audio_start:audio_end], scope)
report = json.loads(report_path.read_text())
report.update(lastCallback=scope['callback'][-1], lastAdma=scope['adma'][-1],
    excludedCallbackRows=scope['text'].count('[AudioCallback] ') - len(scope['callback']),
    excludedAdmaRows=scope['text'].count('[ADMAAccounting] ') - len(scope['adma']),
    audioAuditorSha256=sha(audio_base))
prior = json.loads((root / 'window-ios-o2-phases/live-audit.json').read_text())
report['previousPhaseComparison'] = {
    'priorAuditSha256': sha(root / 'window-ios-o2-phases/live-audit.json'),
    'prior': prior['selectedLast30Seconds'], 'candidate': report['selectedLast30Seconds'],
    'limits': 'Separate live sessions, different video/IRQ/context histories; not controlled exact-frame FPS gain.'}
report_path.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'lastCallback': report['lastCallback'], 'lastAdma': report['lastAdma']}, indent=2))
print('TEXTURE_O2_LIVE_PHASE_RENDER_CAPTURE_AUDITED')
