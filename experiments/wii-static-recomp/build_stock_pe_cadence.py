"""Build an optional bounded observer on the completed-frame runtime; no scheduling change."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline'
public = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
parent_path = root / 'window-completed-frame/build.json'
parent = json.loads(parent_path.read_text())
proof_path = parent_path.parent / 'component-verification.json'
proof = json.loads(proof_path.read_text())
assert proof['buildSha256'] == sha(parent_path)
assert proof['result'] == 'COMPLETED_FRAME_GL172_EVICTION1600_GPU16_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_VERIFIED'
for path, digest in {**parent['dependencies'], **parent['retainedInputs']}.items():
    assert sha(path) == digest
assert sha(parent['archivePath']) == parent['archiveSha256']
record = parent['changes']['gx.cpp']
original = Path(record['sourcePath'])
assert sha(original) == record['sourceSha256']
before = '    if (last_frame_end < 0)'
insertion = '''    static StockPECadenceObservation cadence(std::getenv("NWII_PE_CADENCE_AFTER_MS"));
    bool cadence_sample = false;
    if (cadence.enabled && cadence.samples < 128) {
        const auto now = std::chrono::steady_clock::now();
        const uint64_t host_us = std::chrono::duration_cast<std::chrono::microseconds>(now.time_since_epoch()).count();
        cadence_sample = cadence.inspect(s_carry, execution, host_us,
            [](uint64_t batch, uint64_t id, uint16_t reg, uint32_t val, bool selected, uint64_t host) {
                std::printf("[PECadenceMarker] batch=%llu command=%llu reg=%u value=%u selected=%u hostUs=%llu\\n",
                    (unsigned long long)batch, (unsigned long long)id, unsigned(reg), val,
                    unsigned(selected), (unsigned long long)host);
            });
        if (cadence_sample) {
            std::printf("[PECadenceBatch] batch=%llu hostUs=%llu end=%d copy=%d carry=%llu\\n",
                (unsigned long long)cadence.batch, (unsigned long long)host_us, execution.end,
                execution.last_copy, (unsigned long long)s_carry.size());
        }
    }
'''
after_render = '''            if (cadence_sample) {
                const uint64_t host_us = std::chrono::duration_cast<std::chrono::microseconds>(r1.time_since_epoch()).count();
                std::printf("[PECadenceRendered] batch=%llu hostUs=%llu\\n",
                    (unsigned long long)cadence.batch, (unsigned long long)host_us);
            }
'''
patches = [[before, insertion + before], ['            auto r1 = std::chrono::steady_clock::now();',
    '            auto r1 = std::chrono::steady_clock::now();\n' + after_render]]
text = original.read_text()
for old, new in patches:
    assert text.count(old) == 1
    text = text.replace(old, new, 1)
restored = text
for old, new in reversed(patches):
    assert restored.count(new) == 1
    restored = restored.replace(new, old, 1)
assert restored == original.read_text()
cache = Path(tempfile.mkdtemp(prefix='openshsm-pe-cadence-', dir='/private/tmp'))
source, obj = cache / 'gx.cpp', cache / 'gx.cpp.o'
source.write_text('#include "stock_pe_cadence_observation.h"\n#include <cstdio>\n' + text)
command = list(record['compileCommand'])
command[command.index(str(original))] = str(source)
command[command.index('-o') + 1] = str(obj)
command.insert(1, '-H')
run = subprocess.run(command, capture_output=True, text=True, timeout=120)
(cache / 'compile.log').write_text(run.stdout + run.stderr)
assert run.returncode == 0, run.stderr[-3000:]
assert str(public / 'stock_pe_cadence_observation.h') in run.stderr
archive = cache / 'libnwiiruntime.a'
shutil.copyfile(parent['archivePath'], archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
members = {}
for member, digest in parent['members'].items():
    old = subprocess.check_output(['/usr/bin/ar', '-p', parent['archivePath'], member])
    assert hashlib.sha256(old).hexdigest() == digest
    new = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    assert member == 'gx.cpp.o' or new == old
    members[member] = hashlib.sha256(new).hexdigest()
assert members['gx.cpp.o'] == sha(obj)
link = list(parent['linkCommand'])
link[link.index(parent['archivePath'])] = str(archive)
exe = cache / 'OpenSHSMStockPECadence'
link[link.index('-o') + 1] = str(exe)
run = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert run.returncode == 0, run.stderr[-3000:]
retained = dict(parent['retainedInputs'])
main = parent['changes']['main.cpp']['objectPath']
retained[main] = sha(main)
inputs = [Path(__file__).resolve(), public / 'stock_pe_cadence_observation.h',
    public / 'stock_gx_completed_frame.h', public / 'stock_gx_completion.h', public / 'stock_movie_capture_gate.h', proof_path]
report = {'result': 'PE_CADENCE_OPTIONAL_OBSERVER_BUILT_UNVERIFIED', 'parentBuildSha256': sha(parent_path),
    'archivePath': str(archive), 'archiveSha256': sha(archive), 'members': members,
    'linkCommand': link, 'executablePath': str(exe), 'executableSha256': sha(exe),
    'originalSourcePath': str(original), 'originalSourceSha256': sha(original), 'patches': patches,
    'sourcePath': str(source), 'sourceSha256': sha(source), 'objectPath': str(obj), 'objectSha256': sha(obj),
    'compileCommand': command, 'retainedInputs': retained, 'dependencies': {str(path): sha(path) for path in inputs},
    'limits': ['Optional numeric NWII_PE_CADENCE_AFTER_MS, capped128 batches/512 marker lines; unset/invalid no new clock.',
        'Existing carry read only, command IDs observational; no new queue or scheduling/acknowledgement changes.',
        'Render begin/end bracket, not exact signal time; original guest wait and live observer perturbation unverified.',
        'No runner registration, runtime verification or default promotion yet.']}
path = cache / 'build.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
