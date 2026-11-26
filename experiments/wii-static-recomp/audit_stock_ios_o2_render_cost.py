"""Use already-emitted GUI-owned parse/render counters; do not mislabel lock wait or GL driver time as CPU."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-ios-o2-phases'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
audit_path = output / 'live-audit.json'
audit = json.loads(audit_path.read_text())
assert audit['result'] == 'IOS_O2_EXISTING_HOST_VI_MOVIE_PHASES_AUDITED'
run_path = root / 'headless-sc-pc-headless-windowed-ios-o2-phases-result.json'
run = json.loads(run_path.read_text())
assert sha(run_path) == audit['runSha256']
log = root / 'headless-sc-pc-headless-windowed-ios-o2-phases.log'
assert sha(log) == run['logSha256']
gx_source = root / 'headless-tev-banks/gx.cpp'
gx_obj = root / 'headless-tev-banks/gx.cpp.o'
archive = root / 'window-ios-o2/libnwiiruntime.a'
member = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), 'gx.cpp.o'])
assert hashlib.sha256(member).hexdigest() == sha(gx_obj)
source = gx_source.read_text()
assert 'g_renderer->Render(frame);' in source
assert 'g_stat_render_us +=' in source and 'g_stat_parse_us += decode_us;' in source
text = log.read_text()
rows = [{'labelSeconds': int(seconds), 'frames': int(frames), 'draws': int(draws),
    'parseMs': int(parse), 'renderMs': int(render)} for seconds, frames, draws, parse, render in re.findall(
    r'^\[STAT\] (\d+)s frames=(\d+) draws=(\d+) parse_ms=(\d+) render_ms=(\d+) ', text, re.M)]
assert rows and all(a['frames'] <= b['frames'] for a, b in zip(rows, rows[1:]))
total_parse = sum(row['parseMs'] for row in rows)
total_render = sum(row['renderMs'] for row in rows)
summary = {'validReportingEpochs': len(rows), 'sumParseMs': total_parse, 'sumRendererMs': total_render,
    'rendererToParseWallRatio': total_render / total_parse if total_parse else None,
    'hostLast30Seconds': audit['selectedLast30Seconds'], 'lastEpochs': rows[-6:]}
(output / 'render-cost-audit.json').write_text(json.dumps({
    'result': 'EXISTING_GUI_PARSE_RENDER_WALL_COUNTERS_AUDITED',
    'phaseAuditSha256': sha(audit_path), 'runSha256': sha(run_path), 'logSha256': sha(log),
    'gxSourceSha256': sha(gx_source), 'gxObjectSha256': sha(gx_obj), 'archiveSha256': sha(archive),
    'auditorSha256': sha(Path(__file__)), 'summary': summary, 'reportingEpochs': rows,
    'excludedStatRows': text.count('[STAT] ') - len(rows),
    'limits': ['Existing counters reset after each GUI reporting epoch, integer-ms rounding; labels are nominal5s not exact timestamps.',
        'Parse counter includes vertex DecodeDraw but excludes initial FIFO mutex wait.',
        'Renderer counter brackets g_renderer->Render: includes texture/shader/GL calls/driver waits, not pure CPU or GPU time.',
        'Host GX stage includes locking/parse/render and surrounding overhead; no direct exact interval subtraction against5s epochs.',
        'No rendering changes/FIFO loss claim/controlled speedup/visual/audio/profile/controller/hardware acceptance.']}, indent=2) + '\n')
print('EXISTING_GUI_PARSE_RENDER_WALL_COUNTERS_AUDITED')
print(json.dumps(summary, indent=2))
