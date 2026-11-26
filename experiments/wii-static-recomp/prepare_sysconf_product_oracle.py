"""Clone only the validated laboratory disc/profile for an additional product-buffer capture."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp')
source = root / 'dolphin-sysconf-long-disc'
output = root / 'dolphin-sysconf-product-oracle-disc'
profile_source = Path('_scratch/tmp/dolphin-sysconf-long-disc-user')
profile = Path('_scratch/tmp/dolphin-sysconf-product-oracle-disc-user')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', 'experiments/wii-static-recomp/verify_sysconf_chain.py'], check=True)
output.mkdir(exist_ok=True)
if not (output / 'DATA').exists():
    subprocess.run(['cp', '-cR', str(source / 'DATA'), str(output / 'DATA')], check=True)
assert sha(output / 'DATA/sys/main.dol') == sha(source / 'DATA/sys/main.dol')
if not profile.exists():
    subprocess.run(['cp', '-cR', str(profile_source), str(profile)], check=True)
configs = ['Wii/shared2/sys/SYSCONF', 'Wii/title/00000001/00000002/data/setting.txt']
for name in configs:
    assert sha(profile / name) == sha(profile_source / name)
(output / 'preparation.json').write_text(json.dumps({'preparerSha256': sha(Path(__file__)),
    'controlPreparationSha256': sha(source / 'preparation.json'), 'controlCaptureSha256': sha(source / 'fpr-init-true-dolphin.json'),
    'harnessSha256': sha(output / 'DATA/sys/main.dol'),
    'consoleSourceHashes': {name: sha(profile_source / name) for name in configs},
    'limits': ['Same original SDK harness and cloned isolated emulator LAB console data; not a physical Wii NAND dump.']}, indent=2) + '\n')
print('PASS same DOL/private independent COW disc and laboratory profile staged; originals unchanged')
