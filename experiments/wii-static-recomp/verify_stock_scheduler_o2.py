"""Compare actual scheduler contracts, nonlocal callbacks, SDK/SC resumes and exact late frame endpoints."""
from pathlib import Path
import hashlib
import json
import os
import re
import struct
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-scheduler-o2'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
parent_path = root / 'window-movie-late/build.json'
parent = json.loads(parent_path.read_text())
assert sha(parent_path) == build['parentBuildSha256']
assert Path(build['sourcePath']).read_bytes() == Path(build['originalSourcePath']).read_bytes()
assert sha(Path(build['sourcePath'])) == build['sourceSha256']
assert sha(Path(build['objectPath'])) == build['objectSha256']
assert build['arguments'] == build['originalArguments'] + ['-O2']
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
archive = Path(build['archivePath'])
assert sha(archive) == build['archiveSha256']
old_archive = next(Path(arg) for arg in parent['linkCommand'] if Path(arg).name == 'libnwiiruntime.a')
for member, digest in build['members'].items():
    data = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    assert hashlib.sha256(data).hexdigest() == digest
    if member != 'event_scheduler.cpp.o':
        assert data == subprocess.check_output(['/usr/bin/ar', '-p', str(old_archive), member])
expected = list(parent['linkCommand'])
expected[expected.index(str(old_archive))] = str(archive)
expected[expected.index('-o') + 1] = build['executablePath']
assert expected == build['linkCommand']
temporary = Path(tempfile.mkdtemp(prefix='openshsm-scheduler-tests-', dir='/private/tmp'))
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
flags = parent['changes']['37']['arguments']
records = []
for name, source, marker in [
    ('scheduler', public / 'stock_scheduler_contract_probe.cpp', 'SCHEDULER_ORDER_CANCEL_LATE_REENTRANT_EXCEPTION_RESET_PASS'),
    ('callback', public / 'stock_callback_runtime_probe.cpp', 'ACTUAL_CALLBACK_QUEUE_NONLOCAL_ENDPOINT_PASS4'),
    ('sdk', public / 'stock_sdk_enable_resume_probe.cpp', 'RESUME '),
    ('sc', public / 'stock_sc_resume_probe.cpp', 'SYNCHRONIZED_SC_PC_RETURN_PASS')]:
    obj = temporary / f'{name}.cpp.o'
    compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++',
        '-I', str(root / 'window-adma-deadline/include'), *flags, '-c', str(source), '-o', str(obj)],
        capture_output=True, text=True, timeout=60)
    assert compiled.returncode == 0, compiled.stderr[-2500:]
    endpoints = []
    for variant, configuration in [('baseline', parent), ('candidate', build)]:
        command = list(configuration['linkCommand'])
        main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
        command[command.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
        command.insert(1, str(obj))
        if name == 'sc':
            proof_path = root / 'sc-emitter-research/native-execution/comparison.json'
            proof = json.loads(proof_path.read_text())
            corrected = proof_path.parent / 'corrected.cpp.o'
            assert sha(corrected) == proof['records']['corrected']['objectSha256']
            command.insert(1, str(corrected))
        exe = temporary / f'{name}-{variant}'
        command[command.index('-o') + 1] = str(exe)
        linked = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
        assert linked.returncode == 0, linked.stderr[-2500:]
        endpoint = temporary / f'{name}-{variant}.bin'
        run = subprocess.run([str(exe), *([str(endpoint)] if name == 'callback' else [])],
            env=env, capture_output=True, text=True, timeout=30)
        log = temporary / f'{name}-{variant}.log'
        log.write_text(run.stdout + run.stderr)
        assert run.returncode == 0 and marker in run.stdout, run.stdout + run.stderr
        if name == 'sdk':
            assert sum(line.startswith('RESUME ') for line in run.stdout.splitlines()) == 7
        compared = endpoint.read_bytes() if name == 'callback' else run.stdout.encode()
        endpoints.append(compared)
        records.append({'probe': name, 'variant': variant, 'sourceSha256': sha(source), 'objectSha256': sha(obj),
            'executablePath': str(exe), 'executableSha256': sha(exe), 'logPath': str(log), 'logSha256': sha(log),
            'endpointSha256': hashlib.sha256(compared).hexdigest()})
    assert endpoints[0] == endpoints[1]

prior_path = root / 'late-packet-replay/verification.json'
prior = json.loads(prior_path.read_text())
assert prior['result'] == 'LATE_EXACT_PACKETS_CURRENT_OBJECTS_CLOCK_EE_ENDPOINTS_EQUAL18'
assert prior['buildSha256'] == sha(parent_path)
command = list(prior['linkCommand'])
assert sha(Path(command[1])) == prior['objectSha256']
command[command.index(str(old_archive))] = str(archive)
exe = temporary / 'frame'
command[command.index('-o') + 1] = str(exe)
linked = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert linked.returncode == 0, linked.stderr[-2500:]
snapshot = root / 'headless-sc-pc-decoder-snapshot-retry-decoder-entry.bin'
assert sha(snapshot) == prior['snapshotSha256']
frames = []
for iteration in range(3):
    for case in (prior['cases'] if iteration % 2 == 0 else list(reversed(prior['cases']))):
        packet = Path(case['packetPath'])
        assert sha(packet) == case['selectedLiveRecord']['capture']['packetSha256']
        for mode in ('instruction-ee0', 'wall-ee0', 'wall-ee1'):
            reference = next(row for row in prior['rows'] if row['movie'] == case['movie'] and row['mode'] == mode and row['iteration'] == 0)
            reference_raw = Path(reference['outputPath'])
            assert sha(reference_raw) == reference['outputSha256']
            raw = temporary / f'{case["movie"]}-{mode}-{iteration}.yuv'
            selected = dict(env)
            if mode.startswith('wall'):
                selected['NWII_WALLTB'] = '1'
            if mode.endswith('ee1'):
                selected['SHSM_REPLAY_EE1'] = '1'
            run = subprocess.run([str(exe), str(snapshot), str(raw), str(packet)], env=selected,
                capture_output=True, text=True, timeout=30)
            log = raw.with_suffix('.log')
            log.write_text(run.stdout + run.stderr)
            assert run.returncode == 0 and raw.read_bytes() == reference_raw.read_bytes(), run.stderr[-2500:]
            state_path = Path(str(raw) + '.state')
            assert sha(Path(str(reference_raw) + '.state')) == reference['rawStateSha256']
            assert state_path.read_bytes() == Path(str(reference_raw) + '.state').read_bytes()
            match = re.search(r'COMPLETE_FRAME_REPLAY_RETURN0 ns=(\d+)', run.stdout)
            assert match
            frames.append({'movie': case['movie'], 'mode': mode, 'iteration': iteration, 'decoderNs': int(match[1]),
                'outputPath': str(raw), 'outputSha256': sha(raw), 'stateSha256': sha(state_path), 'logSha256': sha(log)})
report = {'result': 'SCHEDULER_O2_CONTRACT_CALLBACK4_SDK7_SC3_LATE18_EQUAL',
    'buildSha256': sha(build_path), 'verifierSha256': sha(Path(__file__)), 'priorLateReplaySha256': sha(prior_path),
    'records': records, 'frameExecutablePath': str(exe), 'frameExecutableSha256': sha(exe), 'frames': frames,
    'limits': ['Same current scheduler source/O2only, only one archive member; no changes to event/callback semantics.',
        'Actual native scheduler equal stdout/state assertions for due/id ordering, cancellation100, backward time, recurring late/zero/self-cancel, recursive advance, exception-latched/reset behavior.',
        'Exception-latched behavior preserved, not endorsed/fixed; no native longjmp from inside an EventScheduler std::function callback tested.',
        'Actual IOS callback4 nonlocal endpoints and SDK7/emitted SC3 resume paths equal; not full hardware interrupt vector proof.',
        '18 late packets/modes full reference YUV/raw selected PPC state exact; isolated context/no live pending IRQ producers.',
        'Live visual/audio/profile/controller acceptance and promotion pending; large test evidence temporary/private.']}
(output / 'component-verification.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['result'])
