"""Check the future existing-backend latch/phase helper; it is not a second runtime or integrated fix."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('.').resolve()
public = root / 'experiments/wii-static-recomp'
output = root / 'work/private-game/static-recomp/stock-adma-sdk/cursor'
output.mkdir(parents=True, exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
header = public / 'stock_adma_cursor.h'
source = public / 'stock_adma_cursor_probe.cpp'
exe = output / 'cursor-probe'
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20', '-O2',
    '-isysroot', '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk',
    '-I', str(public), str(source), '-o', str(exe)], capture_output=True, text=True, timeout=60)
assert compiled.returncode == 0, compiled.stderr
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=10)
log = output / 'probe.log'
log.write_text(result.stdout + result.stderr)
assert result.returncode == 0 and 'ADMA_CURSOR_PHASE_PASS chunks=32793 periods=20000' in result.stdout, result.stdout + result.stderr
(output / 'verification.json').write_text(json.dumps({'result': 'ADMA_CURSOR_PHASE_PASS32793_CHUNKS20000_PERIODS',
    'headerSha256': sha(header), 'sourceSha256': sha(source), 'executableSha256': sha(exe),
    'logSha256': sha(log), 'verifierSha256': sha(Path(__file__).resolve()),
    'limits': ['Inferred latch/chunk/count behavior follows Dolphin reference; ownWii SDK register protocol verified separately.',
        'No duplicate programmed-register state: caller supplies existing register values; helper only tracks latched cursor.',
        'Rational TB periods for32/48k atGC/Wii nominal clocks, rate changes applied at event boundary/reset fraction.',
        'Not integrated into actual backend, no IRQ startup/host conversion/real clock/audio/game acceptance.']}, indent=2) + '\n')
print(result.stdout.strip())
