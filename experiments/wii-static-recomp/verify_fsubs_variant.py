"""Check the actual register-variant original instruction against the unchanged arithmetic helper."""
from pathlib import Path
import base64
import hashlib
import json
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-fsubs-variant')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert generation['generatorSha256'] == sha(experiment / 'build_fsubs_variant_dolphin.py')
assert generation['parentGeneratorSha256'] == sha(experiment / 'build_fp_initializer_dolphin.py')
assert generation['helperSha256'] == sha(experiment / 'build_dolphin_probe.py')
assert generation['wrapperSha256'] == capture['scriptSha256'].lower() == sha(experiment / 'run_fsubs_variant_dolphin.ps1')
assert generation['harnessSha256'] == capture['harnessSha256'].lower() == sha(output / 'fpr-init.dol')
assert generation['baseRunnerSha256'] == sha(experiment / 'run_dolphin_probe.ps1')
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert generation['originalSha256'] == hashlib.sha256(original).hexdigest()
image = (output / 'fpr-init.dol').read_bytes()
offset = generation['patchOffset']
assert image[256:offset] == original[256:offset] and image[offset + 4:len(original)] == original[offset + 4:]
assert image[offset - 4:offset] == bytes.fromhex('ec401828') and image[offset:offset + 4] == bytes.fromhex('4e800020')
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
assert capture['records'] == 128 and capture['accurateCache'] == 'True'
data = base64.b64decode(capture['data'])
assert len(data) == 128 * 736


def check(row,record):
    value = record['value']
    single = struct.unpack('>I',struct.pack('>f',float(value)))[0]
    double = struct.unpack('>Q',struct.pack('>d',struct.unpack('>f',struct.pack('>I',single))[0]))[0]
    fpscr = ((record['initialFpscr'] | record['ni'] * 4) & ~0x1f000) | ((2 if not value else 8 if value < 0 else 4) << 12)
    actual = [struct.unpack_from('>Q',row,position)[0] for position in (208,464,704,192,216,448,472)]
    actual[2] &= 0xffffffff
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I',row,16) == (0xc001cafe,record['index'])
    assert actual == [double,double,fpscr,0x4330000000000000 | ((value & 0xffffffff) ^ 0x80000000),
        0x4330000080000000,0x4008000000000000,0x4008000000000000]
    assert struct.unpack_from('>I',row,36)[0] == 0x8053ffe0
    return actual


inputs,expected,mutants = [],[],0
for record in generation['records']:
    row = data[record['index'] * 736:(record['index'] + 1) * 736]
    expected.append(check(row,record))
    inputs.append(f"{record['value']} {record['initialFpscr'] | record['ni'] * 4}\n")
    for position in (208,464,708,192,216,448,472,36):
        bad = bytearray(row)
        bad[position] ^= 1
        try:
            check(bad,record)
        except AssertionError:
            mutants += 1
        else:
            raise AssertionError('Unchecked variant evidence')
assert mutants == 1024
exe = output / 'variant-probe'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
result = subprocess.run(['clang++','-std=c++20','-O2','-I',str(experiment),'-I','work/private-game/static-recomp/mass-ni-guard',
    '-I',str(runtime / 'include'),str(experiment / 'fsubs_variant_probe.cpp'),'-o',str(exe)],capture_output=True,text=True,timeout=30)
assert result.returncode == 0,result.stderr
result = subprocess.run([str(exe)],input=''.join(inputs),capture_output=True,text=True,timeout=30)
(output / 'native-results.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and not result.stderr
assert [list(map(int,line.split())) for line in result.stdout.splitlines()] == expected
(output / 'comparison.json').write_text(json.dumps({'result':'ORIGINAL_PREFIX16_REG_VARIANT_FSUBS128_NATIVE_MATCH',
    'verifierSha256':sha(Path(__file__)),'captureSha256':sha(capture_path),
    'helperSha256':sha(experiment / 'fsubs_integer_bias.h'),'probeSha256':sha(experiment / 'fsubs_variant_probe.cpp'),
    'executableSha256':sha(exe),'cases':128,'mutants':1024,
    'limits':['Original first16 instructions; destinationF2/leftF0/rightF3/NI0-NI1/two status controls.',
        'Only fsubs result/lanes/status/operand preservation matched; not full prefix CPU/whole constructor or later division-multiplication proof.',
        'Other register variant opcodes remain unverified until separately tested.']},indent=2) + '\n')
print('PASS original prefix16/fsubs F2-F0-F3/native128/lanes-status-operands/1024 mutations')
