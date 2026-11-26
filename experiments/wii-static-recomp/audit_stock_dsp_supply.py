"""Pin producer/pull observation to the actually retained object and bounded live execution."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-dsp-supply'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, expected in {**build['dependencies'], **build['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
source = output / 'hw_dsp.cpp'
original = root / 'window-quantization/hw_dsp.cpp'
assert sha(source) == build['sourceSha256'] and sha(original) == build['baseSourceSha256']
restored = source.read_text().replace('#include "stock_dsp_supply.h"\n', '', 1)
for before, after in reversed(build['patches']):
    assert restored.count(after) == 1
    restored = restored.replace(after, before)
assert restored == original.read_text()
parent_path = root / 'window-debug-overlay/build.json'
parent = json.loads(parent_path.read_text())
assert sha(parent_path) == build['parentBuildSha256']
command = list(parent['linkCommand'])
old_archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert sha(old_archive) == parent['archiveSha256']
archive = output / 'libnwiiruntime.a'
exe = output / 'OpenSHSMStockDSPSupply'
command[command.index(str(old_archive))] = str(archive)
command[command.index('-o') + 1] = str(exe)
assert command == build['linkCommand'] and sha(archive) == build['archiveSha256'] and sha(exe) == build['executableSha256']
members = [name for name in subprocess.run(['/usr/bin/ar', 't', str(archive)],
    capture_output=True, check=True, text=True).stdout.splitlines() if name.endswith('.o')]
assert set(members) == set(build['retainedArchiveMembers']) and len(members) == len(set(members))
for member in members:
    actual = hashlib.sha256(subprocess.run(['/usr/bin/ar', 'p', str(archive), member], capture_output=True, check=True).stdout).hexdigest()
    assert actual == build['derivedArchiveMembers'][member]
    if member != 'hw_dsp.cpp.o':
        assert actual == build['retainedArchiveMembers'][member]
component_path = output / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['result'] == 'DSP_SUPPLY_PCM_SCHEDULE_NONMUTATION_PASS' and component['buildSha256'] == sha(build_path)
run_path = root / 'headless-sc-pc-headless-windowed-dsp-supply-live-result.json'
run = json.loads(run_path.read_text())
assert run['dspSupply'] and run['debugOverlay'] and run['windowed'] and not run['capture']
assert run['terminalReturncode'] == 0 and run['deadlineReached'] and run['executableSha256'] == sha(exe)
log = root / 'headless-sc-pc-headless-windowed-dsp-supply-live.log'
assert sha(log) == run['logSha256']
text = log.read_text(errors='replace')
names = ['elapsedMs', 'events', 'producedFrames', 'cappedFrames', 'blockFrames', 'periodTicks',
    'maxLateTicks', 'missedPeriods', 'maxGapUs', 'pulls', 'requestedFrames', 'suppliedFrames', 'short', 'maxRingFrames']
pattern = r'\[DSPSupply\] ' + ' '.join(name + r'=(\d+)' for name in names)
rows = [dict(zip(names, map(int, match.groups()))) for match in re.finditer(pattern, text)]
assert len(rows) > 2
cumulative = ['elapsedMs', 'events', 'producedFrames', 'cappedFrames', 'maxLateTicks', 'missedPeriods',
    'maxGapUs', 'pulls', 'requestedFrames', 'suppliedFrames', 'short', 'maxRingFrames']
for previous, current in zip(rows, rows[1:]):
    assert all(current[name] >= previous[name] for name in cumulative)
    assert current['suppliedFrames'] <= current['producedFrames']
    assert current['producedFrames'] - current['suppliedFrames'] <= current['maxRingFrames']
    assert current['short'] <= current['pulls']
active = [row for row in rows if row['events']]
assert active and all(row['blockFrames'] == 96 and row['periodTicks'] == 303750 for row in active)
assert all(row['producedFrames'] == row['events'] * 96 and row['cappedFrames'] == 0 for row in active)
last = active[-1]
header = root / 'window-quantization/include/runtime/cpu_context.h'
header_text = header.read_text()
assert 'static const bool wall = std::getenv("NWII_WALLTB") != nullptr;' in header_text and 'return inst_count;' in header_text
first = active[0]
duration = (last['elapsedMs'] - first['elapsedMs']) / 1000
summary = {'last': last, 'rows': len(rows), 'clockMode': 'DEFAULT_INSTRUCTION_COUNT',
    'fixedBlockVirtualFramesPerSecond': 96 * 60750000 / 303750,
    'observedProducedFramesPerWallSecond': (last['producedFrames'] - first['producedFrames']) / duration,
    'requestedOutputFramesPerSecond': 32000}
(output / 'live-audit.json').write_text(json.dumps({'result': 'DSP_SUPPLY_SOURCE_ARCHIVE_COMPONENT_LIVE_AUDITED',
    'buildSha256': sha(build_path), 'componentSha256': sha(component_path), 'runSha256': sha(run_path),
    'logSha256': sha(log), 'clockHeaderSha256': sha(header), 'auditorSha256': sha(Path(__file__).resolve()),
    'rows': rows, 'summary': summary,
    'limits': ['Observer changes only DSP object; original payload/ring/event scheduling/75guests/main retained.',
        'Totals under original mutex, source count/PCM/deadline/coalescing/stop comparison; native fixtures, not physical Wii.',
        'Fixed virtual period/rate and observed wall shortage proven; hardware-correct rate/latching/clock/audio output not implemented.',
        'No capture or human listening, no FPS/purple/controller/story acceptance; observation adds host overhead.']}, indent=2) + '\n')
print('DSP_SUPPLY_SOURCE_ARCHIVE_COMPONENT_LIVE_AUDITED')
print(json.dumps(summary, indent=2))
