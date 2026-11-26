"""Compare both native arithmetic operations with the entire raw original matrix."""
from pathlib import Path
import base64
import hashlib
import json
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-single-arithmetic')
subprocess.run(['python3',str(experiment / 'verify_single_arithmetic_capture.py')],check=True)
generation = json.loads((output / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
data = base64.b64decode(json.loads(capture_path.read_text(encoding='utf-8-sig'))['data'])
inputs,expected = [],[]
for record in generation['records']:
    row = data[record['index'] * 736:(record['index'] + 1) * 736]
    destination = 1 if record['operation'] == 0 else 0
    preserved = 2 if record['operation'] == 0 else 1
    expected.append([struct.unpack_from('>Q',row,position)[0] for position in
        (192 + destination * 8,448 + destination * 8,704,192 + preserved * 8,448 + preserved * 8)])
    expected[-1][2] &= 0xffffffff
    inputs.append(f"{record['a']} {record['b']} {record['initialFpscr'] | record['ni'] * 4} {record['opcode']}\n")
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
exe = output / 'single-native-probe'
result = subprocess.run(['clang++','-std=c++20','-O2','-I',str(experiment),'-I','work/private-game/static-recomp/mass-ni-guard',
    '-I',str(runtime / 'include'),str(experiment / 'single_arithmetic_probe.cpp'),'-o',str(exe)],capture_output=True,text=True,timeout=30)
(output / 'native-build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0,result.stderr
result = subprocess.run([str(exe)],input=''.join(inputs),capture_output=True,text=True,timeout=30)
(output / 'native-results.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and not result.stderr,result.stderr
actual = [list(map(int,line.split())) for line in result.stdout.splitlines()]
assert len(actual) == len(expected)
differences = [{'index':i,'actual':a,'original':b} for i,(a,b) in enumerate(zip(actual,expected)) if a != b]
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'native-comparison.json').write_text(json.dumps({'result':'MATCH' if not differences else 'NOT_ADMITTED',
    'verifierSha256':sha(Path(__file__)),'adapterSha256':sha(experiment / 'single_arithmetic_adapter.h'),
    'captureSha256':sha(capture_path),'executableSha256':sha(exe),'cases':2048,'differences':differences,
    'limits':['Integer bit arithmetic and existing single conversion, no host floating/FENV dependency.',
        'Exact two original opcodes, NI0/NI1/RN0/disabled exceptions; not full FPU or physical Wii proof.']},indent=2) + '\n')
assert not differences,f'{len(differences)} arithmetic mismatches; see private native-comparison.json'
print('PASS native single division/multiplication2048 original result/paired lanes/FPSCR/other operand match')
