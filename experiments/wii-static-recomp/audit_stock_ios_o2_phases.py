"""Reuse the existing host/VI/movie phase audit on the verified observer-only IOSO2 relink."""
from pathlib import Path
import hashlib
import json

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-ios-o2-phases'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
component_path = output / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['result'] == 'IOS_O2_EXISTING_OBSERVERS_SOURCE_LINK_VERIFIED'
assert component['buildSha256'] == sha(build_path)
assert component['phaseBuildSha256'] == build['phaseBuildSha256']
base = Path('experiments/wii-static-recomp/audit_stock_live_phases.py')
script = base.read_text()
start = script.index('if args.timer_only:\n')
end = script.index('vi_original = Path(vi_build', start)
script = script[:start] + '''vi_build = json.loads((root / 'window-live-phases/build.json').read_text())
vi_source = root / 'window-live-phases/output_39.cpp'
''' + script[end:]
patches = [
    ("output = root / ('window-vi-timer' if args.timer_only else 'window-live-phases')", "output = root / 'window-ios-o2-phases'"),
    ("tag = 'vi-timer' if args.timer_only else 'live-phases'", "tag = 'ios-o2-phases'"),
    ("exe = output / ('OpenSHSMStockVITimer' if args.timer_only else 'OpenSHSMStockLivePhases')", "exe = Path(build['executablePath'])"),
    ("run['windowed'] and run['capture']", "run['windowed'] and not run['capture']")]
for before, after in patches:
    assert script.count(before) == 1
    script = script.replace(before, after, 1)
scope = {'__file__': __file__}
exec(compile(script, str(base), 'exec'), scope)
report_path = output / 'live-audit.json'
report = json.loads(report_path.read_text())
report.update(result='IOS_O2_EXISTING_HOST_VI_MOVIE_PHASES_AUDITED',
    componentSha256=sha(component_path), baseAuditorSha256=sha(base), auditorSha256=sha(Path(__file__)))
report['limits'].extend(['Exact existing main/VI observer objects re-linked with current IOSO2, not new timer/renderer logic.',
    'No new captures/visual/audio/profile/controller acceptance; previous IOSO2 captures checked separately.',
    'FIFO-processing stage wall time includes lock wait/GX parse/upload/draw; no exclusive GPU CPU attribution.',
    'Movie cap and last30s host selection may cover different intervals; late unique packet identity not established by this audit.'])
report_path.write_text(json.dumps(report, indent=2) + '\n')
print('IOS_O2_EXISTING_HOST_VI_MOVIE_PHASES_AUDITED')
