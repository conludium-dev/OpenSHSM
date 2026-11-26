"""Compare the identical isolated decoder on the main thread and a std::thread."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import statistics
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--replay-proof', type=Path, required=True)
args = parser.parse_args()
path = args.replay_proof.resolve()
proof = json.loads(path.read_text())
assert proof['result'] == 'POST_PRESENT_SAME_PACKETS_ISOLATED_CLOCK_EE_ENDPOINTS_EQUAL27'
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
for file, digest in proof['dependencies'].items():
    assert sha(file) == digest
root = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline'
prior_path = root / 'late-packet-replay/verification.json'
prior = json.loads(prior_path.read_text())
original = Path(prior['linkCommand'][1]).with_suffix('')
assert sha(original) == prior['sourceSha256']
before = '''        if (setjmp(ctx.exception_jmp_buf) != 0) {
            std::cerr << "REPLAY_TRAP " << std::hex << ctx.pc << '\\n';
            return 10;
        }
        const auto start = std::chrono::steady_clock::now();
        func_80209D80(ctx);
        const auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now() - start).count();'''
after = '''        int result = 0;
        long long ns = 0, cpu_ns = 0;
        unsigned qos = 0;
        int priority = 0;
        auto decode = [&]() -> int {
            if (setjmp(ctx.exception_jmp_buf) != 0) {
                return 10;
            }
            qos_class_t qos_value = QOS_CLASS_UNSPECIFIED;
            if (pthread_get_qos_class_np(pthread_self(), &qos_value, &priority) != 0) { return 34; }
            qos = unsigned(qos_value);
            timespec cpu_start{}, cpu_end{};
            if (clock_gettime(CLOCK_THREAD_CPUTIME_ID, &cpu_start) != 0) { return 32; }
            const auto start = std::chrono::steady_clock::now();
            func_80209D80(ctx);
            ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
                std::chrono::steady_clock::now() - start).count();
            if (clock_gettime(CLOCK_THREAD_CPUTIME_ID, &cpu_end) != 0) { return 33; }
            cpu_ns = (cpu_end.tv_sec - cpu_start.tv_sec) * 1000000000LL + cpu_end.tv_nsec - cpu_start.tv_nsec;
            return 0;
        };
        if (std::getenv("SHSM_REPLAY_HOST_WORKER")) {
            std::thread worker([&]() { result = decode(); });
            worker.join();
        } else {
            result = decode();
        }
        if (result != 0) { return result; }
        std::cout << "HOST_THREAD_PROFILE wallNs=" << ns << " cpuNs=" << cpu_ns
            << " qos=" << qos << " priority=" << priority << '\\n';'''
text = original.read_text()
assert text.count(before) == 1
text = text.replace(before, after, 1)
assert text.replace(after, before, 1) == original.read_text()
cache = Path(tempfile.mkdtemp(prefix='openshsm-packet-host-thread-', dir='/private/tmp'))
source, obj, exe = cache / 'frame.cpp', cache / 'frame.cpp.o', cache / 'frame'
source.write_text('#include <thread>\n#include <time.h>\n#include <pthread/qos.h>\n' + text)
flags_path = root / 'window-movie-late/build.json'
flags = json.loads(flags_path.read_text())['changes']['37']['arguments']
compile_command = ['/Library/Developer/CommandLineTools/usr/bin/c++', *flags,
    '-c', str(source), '-o', str(obj)]
run = subprocess.run(compile_command, capture_output=True, text=True, timeout=60)
assert run.returncode == 0, run.stderr[-3000:]
command = list(proof['linkCommand'])
command[command.index(prior['linkCommand'][1])] = str(obj)
command[command.index('-o') + 1] = str(exe)
run = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert run.returncode == 0, run.stderr[-3000:]
snapshot = root / 'headless-sc-pc-decoder-snapshot-retry-decoder-entry.bin'
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
env.update(NWII_WALLTB='1', SHSM_REPLAY_EE1='1')
records = []
for iteration in range(3):
    for case in (proof['cases'] if iteration % 2 == 0 else list(reversed(proof['cases']))):
        reference = next(row for row in proof['rows'] if row['label'] == case['label']
            and row['mode'] == 'wall-ee1' and row['iteration'] == 0)
        assert sha(reference['outputPath']) == reference['outputSha256']
        assert sha(str(reference['outputPath']) + '.state') == reference['rawStateSha256']
        for mode in (('main', 'worker') if iteration % 2 == 0 else ('worker', 'main')):
            selected_env = dict(env)
            if mode == 'worker':
                selected_env['SHSM_REPLAY_HOST_WORKER'] = '1'
            raw = cache / f'{case["label"]}-{mode}-{iteration}.yuv'
            run = subprocess.run([str(exe), str(snapshot), str(raw), case['packetPath']],
                env=selected_env, capture_output=True, text=True, timeout=30)
            match = re.search(r'HOST_THREAD_PROFILE wallNs=(\d+) cpuNs=(\d+) qos=(\d+) priority=(-?\d+)', run.stdout)
            assert run.returncode == 0 and match, run.stdout + run.stderr
            assert raw.read_bytes() == Path(reference['outputPath']).read_bytes()
            assert Path(str(raw) + '.state').read_bytes() == Path(str(reference['outputPath']) + '.state').read_bytes()
            log = raw.with_suffix('.log')
            log.write_text(run.stdout + run.stderr)
            records.append({'label': case['label'], 'mode': mode, 'iteration': iteration,
                'wallNs': int(match[1]), 'cpuNs': int(match[2]), 'qos': int(match[3]), 'priority': int(match[4]),
                'outputPath': str(raw), 'outputSha256': sha(raw), 'stateSha256': sha(str(raw) + '.state'),
                'logPath': str(log), 'logSha256': sha(log)})
summary = []
for case in proof['cases']:
    summary.append({'label': case['label'], 'liveHostCpuUs': case['selectedLiveRecord']['hostCpuUs'],
        'modes': {mode: {'medianWallUs': statistics.median(row['wallNs'] / 1000 for row in records
            if row['label'] == case['label'] and row['mode'] == mode),
            'medianCpuUs': statistics.median(row['cpuNs'] / 1000 for row in records
            if row['label'] == case['label'] and row['mode'] == mode),
            'qosValues': sorted({row['qos'] for row in records if row['mode'] == mode})}
            for mode in ('main', 'worker')}})
report = {'result': 'ISOLATED_MAIN_WORKER_SAME_PACKETS_YUV_PPC_EQUAL18',
    'dependencies': {str(file): sha(file) for file in [Path(__file__).resolve(), path, original, flags_path]},
    'fixturePatch': [before, after], 'compileCommand': compile_command, 'linkCommand': command,
    'sourcePath': str(source), 'sourceSha256': sha(source), 'executablePath': str(exe), 'executableSha256': sha(exe),
    'records': records, 'summary': summary,
    'limits': ['Diagnostic fixture only; no live runtime changes or priority/QoS mutation.',
        'setjmp and decode stay on the same executing thread; worker creation/join outside measured decode interval.',
        'QoS query does not identify physical CPU core or prove live scheduling behavior.',
        'Earlier isolated snapshot, not live guest/IRQ/device context; no full-game causality or optimization claim.']}
path = cache / 'verification.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
print(json.dumps(summary, indent=2))
