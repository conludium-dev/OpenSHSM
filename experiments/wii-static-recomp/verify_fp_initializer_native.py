"""Run the whole generated original function on this same125-object boot module."""
from pathlib import Path
import base64
import hashlib
import json
import os
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'mass-fp-initializer-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3',str(experiment / 'verify_fp_initializer_dolphin.py')],check=True)
build = json.loads((output / 'build.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_fp_initializer_boot.py')
assert build['executableSha256'] == sha(output / 'openshsm-mass-boot')
assert (output / 'fsubs_integer_bias.h').read_bytes() == (experiment / 'fsubs_integer_bias.h').read_bytes()
assert (output / 'fp_initializer_probe.h').read_bytes() == (experiment / 'fp_initializer_probe.h').read_bytes()
for path,digest in {**build['sourceHashes'],**build['headerHashes']}.items():
    assert sha(Path(path)) == digest
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
generation = json.loads((root / 'dolphin-fp-initializer/generation.json').read_text())
capture_path = root / 'dolphin-fp-initializer/fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
data = base64.b64decode(capture['data'])
inputs, expected = [], []
for record in generation['records']:
    index = record['index']
    row = data[index * 736:(index + 1) * 736]
    inputs.append(f"{index} {record['value']} {record['ni']} {record['initialFpscr']}\n")
    expected.append([index,*struct.unpack_from('>2I',row,24),
        struct.unpack_from('>Q',row,192)[0],struct.unpack_from('>Q',row,448)[0],
        struct.unpack_from('>Q',row,704)[0] & 0xffffffff,
        struct.unpack_from('>Q',row,200)[0],struct.unpack_from('>Q',row,456)[0]])
env = {key:value for key,value in os.environ.items() if not key.startswith('SHSM_')}
result = subprocess.run([str(output / 'openshsm-mass-boot'),'--fp-initializer-probe'],input=''.join(inputs),
    env=env,capture_output=True,text=True,timeout=30)
(output / 'initializer-probe.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and not result.stderr, result.stdout + result.stderr
actual = [list(map(int,line.split()[1:])) for line in result.stdout.splitlines() if line.startswith('FP_INITIALIZER_PROBE ')]
assert actual == expected
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
contract = output / 'fsubs-bias-contract'
contract_source = output / 'fsubs-bias-contract.cpp'
contract_source.write_bytes((experiment / 'fsubs_integer_bias_contract.cpp').read_bytes())
compiled = subprocess.run(['clang++','-std=c++20','-O2','-I',str(output),'-I',str(experiment),
    '-I',str(runtime / 'include'),str(contract_source),'-o',str(contract)],
    capture_output=True,text=True,timeout=30)
assert compiled.returncode == 0,compiled.stderr
checked = subprocess.run([str(contract)],env=env,capture_output=True,text=True,timeout=30)
assert checked.returncode == 0 and checked.stdout == 'Fsubs_BIAS_CONTRACT guards=16\n' and not checked.stderr,checked
(output / 'initializer-native-comparison.json').write_text(json.dumps({
    'result':'SAME125_OBJECTS_WHOLE_ORIGINAL_INITIALIZER128_DOL_TO_NATIVE_ORACLE_MATCH',
    'verifierSha256':sha(Path(__file__)),'buildSha256':sha(output / 'build.json'),
    'captureSha256':sha(capture_path),'probeLogSha256':sha(output / 'initializer-probe.log'),
    'cases':128,'guardContracts':16,'contractSha256':sha(experiment / 'fsubs_integer_bias_contract.cpp'),
    'contractExecutableSha256':sha(contract),'limits':['Whole14-instruction recompiled function on the actual boot module, not substituted callback/result.',
        'Rounded global/saved integer/both output lanes/untouched F1 lanes/FPSCR/stack/return-to-native match.',
        'Measured signed-int bias family only; not general fsubs/physical Wii or full runtime.']},indent=2) + '\n')
print('PASS SAME125 whole original initializer128/native execution-return/rounded global-saved int/both lanes/FPSCR/stack/originalDolphin match')
