"""Identify default mismatch and test disclosed loader seed on existing DSP."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
subprocess.run(['python3', str(experiment / 'verify_dsp_read_dolphin.py')], check=True)
oracle_path = private / 'dolphin-dsp-read/comparison.json'
oracle = json.loads(oracle_path.read_text())
output = private / 'dsp-read-backend'
output.mkdir(exist_ok=True)
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
exe = output / 'dsp-read-probe'
sources = [experiment / 'dsp_read_backend_probe.cpp', upstream / 'src/hw/hw_dsp.cpp',
           upstream / 'src/hw/mmio_dispatcher.cpp', upstream / 'src/hw/hw_pi.cpp', upstream / 'src/core/event_scheduler.cpp']
build = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-I', str(upstream / 'include'), *map(str, sources), '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'build.log').write_text(build.stdout + build.stderr)
assert build.returncode == 0, build.stderr[-3000:]
native = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
(output / 'native.log').write_text(native.stdout + native.stderr)
assert native.returncode == 0
rows = {line.split()[0]: list(map(int, line.split()[1:])) for line in native.stdout.splitlines() if line.startswith('DSP_')}
assert oracle['readValues'] == [0x0804]
assert rows['DSP_DEFAULT'] == [0x0800, 0x10000]
assert rows['DSP_LOADER_SEED'] == [0x0804, 0x10000]
assert all(row['causeBefore'] == row['causeAfter'] == 0x10000 for row in oracle['observations'])
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = {'result': 'DSP_DEFAULT_MISMATCH_LOADER_SEED_READBACK_PASS', 'originalReadCases': 16,
          'vendorDefault': 0x0800, 'observedLoaderValue': 0x0804, 'nativeSeededValue': rows['DSP_LOADER_SEED'][0],
          'oracleSha256': sha(oracle_path), 'sourceHashes': {str(path): sha(path) for path in sources},
          'executableSha256': sha(exe), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Original DSP read under Dolphin loader state differs from vendor default.',
                     'Writing804 is a native prepared-loader adaptation, not verified original startup or DSP write behavior.',
                     'No DMA, audio, mailbox, interrupt delivery or full boot equivalence.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('DSP vendor default800 differs from original loader804; explicit native seed readback804, PI unchanged')
