"""Compare native bitwise ordered compare directly to every original capture."""
from pathlib import Path
import base64
import hashlib
import json
import os
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-fcmp')
subprocess.run(['python3',str(experiment / 'verify_fcmp_dolphin.py')],check=True)
generation = json.loads((output / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
data = base64.b64decode(capture['data'])
inputs,expected = [],[]
for record in generation['records']:
    row = data[record['index'] * 736:(record['index'] + 1) * 736]
    inputs.append(f"{record['a']} {record['b']} {record['initialFpscr'] | record['ni'] * 4} {record['initialCr']}\n")
    expected.append([struct.unpack_from('>I',row,160)[0],struct.unpack_from('>Q',row,704)[0] & 0xffffffff,
        *struct.unpack_from('>2Q',row,192),*struct.unpack_from('>2Q',row,448)])
exe = output / 'fcmp-native-probe'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
result = subprocess.run(['clang++','-std=c++20','-O2','-I',str(experiment),'-I',str(runtime / 'include'),
    str(experiment / 'fcmp_ordered_probe.cpp'),'-o',str(exe)],capture_output=True,text=True,timeout=30)
(output / 'native-build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0,result.stderr
env = {key:value for key,value in os.environ.items() if not key.startswith('SHSM_')}
result = subprocess.run([str(exe)],input=''.join(inputs),env=env,capture_output=True,text=True,timeout=30)
(output / 'native-results.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and not result.stderr
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
actual = [list(map(int,line.split())) for line in result.stdout.splitlines()]
assert len(actual) == len(expected)
differences = [{'index':index,'native':native,'captured':captured}
    for index,(native,captured) in enumerate(zip(actual,expected)) if native != captured]
if differences:
    (output / 'native-discrepancy.json').write_text(json.dumps({'result':'NOT_ADMITTED_FPSCR_DISCREPANCY',
        'verifierSha256':sha(Path(__file__)),'captureSha256':sha(capture_path),
        'adapterSha256':sha(experiment / 'fcmp_ordered_adapter.h'),'cases':1024,
        'differences':differences,'limits':['Do not integrate draft helper until capture/source discrepancy is resolved.']},indent=2) + '\n')
    raise AssertionError(f'Native ordered comparison not admitted: {len(differences)} captured FPSCR discrepancies')
(output / 'native-comparison.json').write_text(json.dumps({'result':'FCMPO_NATIVE1024_ORIGINAL_CR_FPSCR_OPERANDS_LANES_MATCH',
    'verifierSha256':sha(Path(__file__)),'captureSha256':sha(capture_path),
    'adapterSha256':sha(experiment / 'fcmp_ordered_adapter.h'),'probeSha256':sha(experiment / 'fcmp_ordered_probe.cpp'),
    'executableSha256':sha(exe),'cases':1024,'limits':['One exact ordered-compare opcode, enabled exceptions guarded.',
        'Component comparison, not native boot integration/full FPU/physical Wii proof.']},indent=2) + '\n')
print('PASS native ordered compare1024 original CR/FPSCR/both primary-paired lanes match')
