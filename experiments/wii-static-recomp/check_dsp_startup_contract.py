"""Build and exercise the existing-backend DSP API; not original PPC execution proof."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'dsp-startup-contract'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert hashlib.sha1(original_path.read_bytes()).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
subprocess.run(['python3', str(experiment / 'verify_audio_trace_dolphin.py')], check=True)
sources = [experiment / 'dsp_startup_contract.cpp', experiment / 'dsp_startup_backend.cpp',
    runtime / 'src/core/loader.cpp', runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/hw/hw_pi.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'dsp-contract'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER',
    '-I', str(experiment), '-I', str(private / 'mass-flush-syscall-boot'), '-I', str(runtime / 'include'), '-I', str(runtime / 'src/hw'),
    '-I', str(runtime.parent / 'nWiiAnalyzer/include'), *map(str, sources), '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
(output / 'contract.log').write_text(result.stdout + result.stderr)
print(result.stdout + result.stderr)
assert result.returncode == 0
assert result.stdout.splitlines() == ['DSP_CONTRACT 0 17 2 0 0', 'DSP_CONTRACT 1 7 0 1 0', 'DSP_CONTRACT 2 17 2 0 1', 'DSP_CONTRACT 3 14 2 1 0']
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'verification.json').write_text(json.dumps({'result': 'DSP_EXISTING_BACKEND_API_DMA_MAIL_NEGATIVES_PASS',
    'runnerSha256': sha(Path(__file__)), 'sourceHashes': {str(path): sha(path) for path in sources},
    'headerHashes': {str(experiment / name): sha(experiment / name) for name in ('dsp_startup_backend.h', 'dsp_startup_frontend.h')},
    'vendorDspSha256': sha(runtime / 'src/hw/hw_dsp.cpp'), 'executableSha256': sha(exe), 'output': result.stdout,
    'originalSha256': sha(original_path), 'referenceSha256': sha(private / 'dolphin-audio-trace/comparison.json'),
    'limits': ['API driver follows the measured command sequence; does not run original compiled __OSInitAudioSystem.',
        'Bounded startup HLE/event compatibility adapter, not a DSP instruction emulator or full audio runtime.',
        'Vendor DMA copies synchronously before queued completion; timing/early visibility are PC adaptations.',
        'Playback MMIO uses an explicit rejecting lab symbol; no audio playback or full runtime verification.']}, indent=2) + '\n')
