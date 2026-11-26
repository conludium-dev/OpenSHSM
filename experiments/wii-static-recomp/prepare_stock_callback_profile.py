"""Compile counters around the actual callback body, restoring it mechanically; no full live build yet."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'callback-profile-component'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
original = root / 'headless-scheduler-observe/ios.cpp'
original_obj = original.with_suffix('.cpp.o')
provenance = json.loads((original.parent / 'build.json').read_text())
assert sha(original) == provenance['sourceSha256'] and sha(original_obj) == provenance['objectSha256']
archive = root / 'window-adma-deadline/libnwiiruntime.a'
member = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), 'ios.cpp.o'])
assert hashlib.sha256(member).hexdigest() == sha(original_obj)
text = original.read_text()
patches = [('bool process_pending_callbacks(CPUContext &ctx) {',
    'static bool stock_profile_pending_impl(CPUContext &ctx) {'),
    ('      restore_count++;', '      restore_count++;\n      stock_callback_profile::restored();')]
for before, after in patches:
    assert text.count(before) == 1
    text = text.replace(before, after, 1)
wrapper = '''
bool process_pending_callbacks(CPUContext& ctx) {
    const auto ticket = stock_callback_profile::enter(ctx);
    const bool result = stock_profile_pending_impl(ctx);
    return stock_callback_profile::leave(ticket, result);
}

extern "C" void stock_callback_profile_snapshot(uint64_t* values) {
    stock_callback_profile::snapshot(values);
}
'''
position = text.rfind('\n} ')
assert position > text.index('static bool stock_profile_pending_impl') and text[position:].strip() == '}'
text = '#include "stock_callback_profile.h"\n' + text[:position] + wrapper + text[position:]
source, obj = output / 'ios.cpp', output / 'ios.cpp.o'
source.write_text(text)
restored = text.replace('#include "stock_callback_profile.h"\n', '', 1).replace(wrapper, '', 1)
for before, after in reversed(patches):
    restored = restored.replace(after, before, 1)
assert restored == original.read_text()
record = next(row for row in json.loads((root / 'window-quantization/build.json').read_text())['compiled'] if row['source'] == 'ios.cpp')
flags = record['arguments']
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *flags,
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=90)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2500:]
temporary = Path(tempfile.mkdtemp(prefix='openshsm-callback-profile-', dir='/private/tmp'))
exe = temporary / 'probe'
sdk = flags[flags.index('-isysroot') + 1]
probe = public / 'stock_callback_profile_probe.cpp'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', '-isysroot', sdk,
    '-std=c++20', '-O2', '-I', str(public), str(probe), '-o', str(exe)],
    capture_output=True, text=True, timeout=60)
assert result.returncode == 0, result.stderr[-2500:]
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
runs = []
for active, marker in [(False, 'CALLBACK_PROFILE_DISABLED_PASS'), (True, 'CALLBACK_PROFILE_RETURN_EE_CALLBACK_NONLOCAL_COUNTS_PASS')]:
    selected_env = dict(env)
    if active:
        selected_env['NWII_MOVIE_TIMING'] = 'component-only'
    run = subprocess.run([str(exe)], env=selected_env, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0 and marker in run.stdout, run.stdout + run.stderr
    runs.append({'enabled': active, 'terminalReturncode': run.returncode, 'stdout': run.stdout})
(output / 'verification.json').write_text(json.dumps({
    'result': 'ACTUAL_CALLBACK_BODY_RESTORED_COMPILED_COUNTER_COMPONENT_PASS',
    'originalSourceSha256': sha(original), 'originalObjectSha256': sha(original_obj), 'archiveSha256': sha(archive),
    'sourceSha256': sha(source), 'objectSha256': sha(obj), 'arguments': flags, 'patches': patches, 'wrapper': wrapper,
    'helperSha256': sha(public / 'stock_callback_profile.h'), 'probeSha256': sha(probe),
    'executablePath': str(exe), 'executableSha256': sha(exe), 'scriptSha256': sha(Path(__file__)), 'runs': runs,
    'counterOrder': ['calls', 'ordinaryReturns', 'trueReturns', 'ee0Entries', 'inCallbackEntries',
        'sampledEntries', 'sampledOrdinaryReturns', 'sampleCpuNs', 'sampleClockFailures', 'successfulContextRestores'],
    'limits': ['Actual original callback body restored byte-for-byte after reversing wrapper/include/counter additions.',
        'Original compiler arguments retained; no O2 switch/setjmp/longjmp/IRQ/context/callback semantics change.',
        'Synthetic counter component tests bool passthrough/disabled/EE/callback flags/sampled longjmp skipped ordinary return.',
        'Only one in1024 calls timed; sampled CPU includes clock/observer overhead and excludes nonlocal-return samples.',
        'Single CPU-host-thread counters/snapshot only; no concurrent GUI access/physical Wii/full runtime execution proof.',
        'Full archive/executable/movie-boundary integration and real IRQ/replay/live tests pending.']}, indent=2) + '\n')
print('ACTUAL_CALLBACK_BODY_RESTORED_COMPILED_COUNTER_COMPONENT_PASS')
