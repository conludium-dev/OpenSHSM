"""Record bounded execution of the hidden native GPU fixture."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline/headless-tev-banks').resolve()
manifest = root / 'pixel-build.json'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base = json.loads(manifest.read_text())
for path, expected in base['dependencies'].items():
    assert sha(Path(path)) == expected
exe = root / 'pixel-probe'
assert sha(exe) == base['executableSha256']
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
log = root / 'pixel-verification.log'
log.write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
assert 'TEV_BANK_NATIVE_GPU_PIXEL_PASS 4' in result.stdout
(root / 'pixel-verification.json').write_text(json.dumps({'result': 'TEV_BANK_NATIVE_GPU_PIXEL_PASS4',
    'pixelBuildSha256': sha(manifest), 'executableSha256': sha(exe), 'logSha256': sha(log),
    'verifierSha256': sha(Path(__file__).resolve()), 'stdout': result.stdout,
    'limits': ['Hidden native macOS GL context, actual generated one-stage shader plus corrected extracted uniform decoding.',
        'Four synthetic RGB/alpha pixel cases, both retained banks and both write orders.',
        'Direct fixture uniform upload/draw, not full existing renderer or original SHSM frame/video/Wii hardware.']}, indent=2) + '\n')
print(result.stdout, end='')
