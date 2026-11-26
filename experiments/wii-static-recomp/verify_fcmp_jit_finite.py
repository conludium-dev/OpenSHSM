"""Verify the JIT finite/infinity domain without copying the interpreter FPCC bug."""
from pathlib import Path
import ast
import base64
import hashlib
import json
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-fcmp-jit-fprf')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture_path = output / 'fpr-init-false-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert generation['generatorSha256'] == sha(experiment / 'build_fcmp_jit_fprf.py')
assert generation['wrapperSha256'] == capture['scriptSha256'].lower() == sha(experiment / 'run_fcmp_jit_fprf.ps1')
assert generation['helperSha256'] == sha(experiment / 'build_dolphin_probe.py')
assert generation['baseRunnerSha256'] == sha(experiment / 'run_dolphin_probe.ps1')
assert generation['harnessSha256'] == capture['harnessSha256'].lower() == sha(output / 'fpr-init.dol')
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert generation['originalSha256'] == hashlib.sha256(original).hexdigest()
image = (output / 'fpr-init.dol').read_bytes()
offset = generation['patchOffset']
assert image[256:offset] == original[256:offset] and image[offset + 4:len(original)] == original[offset + 4:]
assert image[offset - 4:offset] == bytes.fromhex('fc010040')
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
assert capture['accurateCache'] == 'False' and capture['records'] == 1024
namespace = {}
for node in ast.parse((experiment / 'verify_fcmp_dolphin.py').read_text()).body:
    if isinstance(node,ast.FunctionDef) and node.name == 'expected':
        exec(compile(ast.Module(body=[node],type_ignores=[]),'expected','exec'),namespace)
data = base64.b64decode(capture['data'])
assert len(data) == 1024 * 736
inputs,expected = [],[]
for record in generation['records']:
    row = data[record['index'] * 736:(record['index'] + 1) * 736]
    cr = namespace['expected'](record)[0]
    status = record['initialFpscr'] | record['ni'] * 4
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I',row,16) == (0xc001cafe,record['index'])
    assert struct.unpack_from('>I',row,160)[0] == cr
    assert struct.unpack_from('>Q',row,24)[0] & 0xffffffff == status
    assert struct.unpack_from('>2Q',row,192) == (record['b'],record['a'])
    assert struct.unpack_from('>2Q',row,448) == (0x4008000000000000,0x4008000000000000)
    post = struct.unpack_from('>Q',row,712)[0] & 0xffffffff
    assert post == struct.unpack_from('>Q',row,704)[0] & 0xffffffff
    assert post == (status & ~0xf000) | ((cr >> 28) << 12)
    if any((value & 0x7fffffffffffffff) > 0x7ff0000000000000 for value in (record['a'],record['b'])):
        continue
    inputs.append(f"{record['a']} {record['b']} {status} {record['initialCr']}\n")
    expected.append([cr,post,*struct.unpack_from('>2Q',row,192),*struct.unpack_from('>2Q',row,448)])
assert len(inputs) == 576
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
probe = output / 'finite-probe.cpp'
probe.write_text((experiment / 'fcmp_ordered_probe.cpp').read_text().replace('fcmp_ordered_adapter.h','fcmp_finite_adapter.h').replace('experiment_fcmp_ordered','experiment_fcmp_finite'))
exe = output / 'finite-probe'
for source,target in [(probe,exe),(experiment / 'fcmp_finite_contract.cpp',output / 'finite-contract')]:
    result = subprocess.run(['clang++','-std=c++20','-O2','-I',str(experiment),'-I',str(runtime / 'include'),str(source),'-o',str(target)],capture_output=True,text=True,timeout=30)
    assert result.returncode == 0,result.stderr
result = subprocess.run([str(exe)],input=''.join(inputs),capture_output=True,text=True,timeout=30)
(output / 'finite-native.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and not result.stderr
assert [list(map(int,line.split())) for line in result.stdout.splitlines()] == expected
contract = subprocess.run([str(output / 'finite-contract')],capture_output=True,text=True,timeout=30)
assert contract.returncode == 0 and contract.stdout == 'FCMP_FINITE_CONTRACT guards=17\n',contract
(output / 'finite-comparison.json').write_text(json.dumps({'result':'ORIGINAL_JIT_FCMPO576_FINITE_INFINITY_NATIVE_CR_FPCC_LANES_MATCH',
    'verifierSha256':sha(Path(__file__)),'captureSha256':sha(capture_path),'executableSha256':sha(exe),
    'adapterSha256':sha(experiment / 'fcmp_finite_adapter.h'),'cases':576,'guards':17,
    'limits':['JIT CPUCore1/FPRF=True/AccurateCache=False; only finite and infinity operands admitted.',
        'NaN invalid exceptions in JIT remain unverified;448 NaN cases not admitted by helper.',
        'Interpreter FPCC mask bug retained as separate evidence, not copied into native runtime.',
        'No physical Wii/full FPU/whole caller or boot integration proof.']},indent=2) + '\n')
print('PASS original JIT finite-infinity576/native CR-FPSCR/lanes/17 atomic guards; NaN refused')
