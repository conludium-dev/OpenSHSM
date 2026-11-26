"""Validate added original product256 capture against same unobserved whole-SC control."""
from pathlib import Path
import base64
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'dolphin-sysconf-product-oracle-disc'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_sysconf_chain.py')], check=True)
prep = json.loads((output / 'preparation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
control_path = root / 'dolphin-sysconf-long-disc/fpr-init-true-dolphin.json'
control = json.loads(control_path.read_text(encoding='utf-8-sig'))
assert prep['preparerSha256'] == sha(experiment / 'prepare_sysconf_product_oracle.py')
assert capture['scriptSha256'].lower() == sha(experiment / 'run_sysconf_product_oracle.ps1')
assert capture['harnessSha256'].lower() == prep['harnessSha256'] == sha(output / 'DATA/sys/main.dol')
assert capture['harnessSha256'].lower() == control['harnessSha256'].lower()
assert capture['emulatorSha256'].lower() == control['emulatorSha256'].lower()
assert capture['records'] == 16 and capture['accurateCache'] == 'True'
assert sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe')) == capture['emulatorSha256'].lower()
profile = Path('_scratch/tmp/dolphin-sysconf-product-oracle-disc-user')
for name, digest in prep['consoleSourceHashes'].items():
    assert sha(profile / name) == digest
data = base64.b64decode(capture['data'])
reference = base64.b64decode(control['data'])
assert len(data) == len(reference) == 16 * 736
for index in range(5, 16):
    row, old = data[index * 736:(index + 1) * 736], reference[index * 736:(index + 1) * 736]
    for a, b in [(16, 24), (36, 80), (80, 100), (192, 320), (400, 408), (416, 512), (608, 620), (644, 648), (720, 732)]:
        assert row[a:b] == old[a:b]
assert base64.b64decode(capture['confPhysical']) == base64.b64decode(control['confPhysical'])
product = (profile / 'Wii/title/00000001/00000002/data/setting.txt').read_bytes()


def check(payload):
    assert len(payload) == 256 and payload == product


payload = base64.b64decode(capture['productPhysical'])
check(payload)
mutants = 0
for index in (0, 1, 31, 63, 127, 255):
    bad = bytearray(payload)
    bad[index] ^= 1
    try:
        check(bad)
    except AssertionError:
        mutants += 1
    else:
        raise AssertionError(index)
(output / 'verification.json').write_text(json.dumps({'verifierSha256': sha(Path(__file__)),
    'captureSha256': sha(capture_path), 'controlCaptureSha256': sha(control_path),
    'preparationSha256': sha(output / 'preparation.json'), 'productSha256': hashlib.sha256(product).hexdigest(),
    'result': 'ORIGINAL_PRODUCT256_FULL_PHYSICAL_FILE_EQUAL_WHOLE_SC_ENDPOINTS_RETAINED', 'mutants': mutants,
    'limits': ['Original SDK under isolated emulator LAB profile, not physical Wii NAND/retail identity/cycle proof.']}, indent=2) + '\n')
print('PASS original product256/full physical file equality/11 wholeSC endpoints/control unchanged;6mutants;laboratory data only')
