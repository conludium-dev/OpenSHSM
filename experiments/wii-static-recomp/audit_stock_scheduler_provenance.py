"""Pin the actual current scheduler object and compile flags before any optimization proposal."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = root / 'window-movie-late/build.json'
build = json.loads(build_path.read_text())
archive = next(Path(arg) for arg in build['linkCommand'] if Path(arg).name == 'libnwiiruntime.a')
assert sha(archive) == build['retainedInputs'][str(archive)]
source = root / 'window-adma-deadline/event_scheduler.cpp'
header = root / 'window-adma-deadline/include/runtime/event_scheduler.h'
obj = root / 'window-adma-deadline/event_scheduler.cpp.o'
prior_path = source.parent / 'build.json'
prior = json.loads(prior_path.read_text())
data = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), 'event_scheduler.cpp.o'])
assert hashlib.sha256(data).hexdigest() == sha(obj)
assert sha(source) == prior['schedulerSourceSha256']
assert sha(obj) == prior['schedulerObjectSha256']
assert sha(header) == prior['dependencies'][str(header)]
record_path = root / 'window-quantization/build.json'
record = next(row for row in json.loads(record_path.read_text())['compiled'] if row['source'] == 'event_scheduler.cpp')
flags = ['-I', str(source.parent / 'include'), *record['arguments']]
assert not any(flag.startswith('-O') for flag in flags)
text = source.read_text()
assert 'if (now < m_now) return;' in text and 'if (m_firing) return;' in text
assert 'cb(ctx, late);' in text and 'm_firing = false;' in text
ios = root / 'headless-scheduler-observe/ios.cpp'
ios_text = ios.read_text()
assert 'EventScheduler::get().advance(ctx, ctx.read_timebase());' in ios_text
output = root / 'late-packet-replay'
output.mkdir(exist_ok=True)
(output / 'scheduler-provenance.json').write_text(json.dumps({
    'result': 'CURRENT_ARCHIVE_SCHEDULER_OBJECT_DEFAULT_O0_PINNED', 'buildSha256': sha(build_path),
    'archivePath': str(archive), 'archiveSha256': sha(archive), 'sourcePath': str(source),
    'sourceSha256': sha(source), 'headerSha256': sha(header), 'objectPath': str(obj), 'objectSha256': sha(obj),
    'compileFlags': flags, 'priorBuildSha256': sha(prior_path), 'compileRecordSha256': sha(record_path),
    'iosSourceSha256': sha(ios), 'auditorSha256': sha(Path(__file__)),
    'limits': ['Archive member equals exact ADMA-deadline object/source/header pinned by manifest; historical compile not independently reproduced.',
        'Initial exported scheduler object mismatch refused; current adapter preserves additive schedule_at API, not obsolete export.',
        'Scheduler host adaptation, not recovered Wii scheduler implementation.',
        'No optimization yet or exclusive CPU-cost claim; earlier O0 IOS counter timings cannot be reused as current IOSO2 costs.',
        'Candidate must preserve event ordering/cancellation/late recurring/reentrancy/callback semantics plus frame/IRQ regressions and live acceptance.']}, indent=2) + '\n')
print('CURRENT_ARCHIVE_SCHEDULER_OBJECT_DEFAULT_O0_PINNED', sha(obj))
