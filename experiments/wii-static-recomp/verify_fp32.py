"""Compare native single transfers to original instructions, including NI1 zero."""
from pathlib import Path
import base64
import hashlib
import json
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-fp32')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation_path = output / 'generation.json'
generation = json.loads(generation_path.read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['records'] == len(generation['records']) == 192 and capture['accurateCache'] == 'True'
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_fp32_dolphin.ps1')
assert generation['generatorSha256'] == sha(experiment / 'build_fp32_dolphin.py')
assert generation['parentGeneratorSha256'] == sha(experiment / 'build_fp64_dolphin.py')
assert generation['helperSha256'] == sha(experiment / 'build_dolphin_probe.py')
assert generation['baseRunnerSha256'] == sha(experiment / 'run_dolphin_probe.ps1')
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert generation['originalSha256'] == sha(original_path)
original, image = original_path.read_bytes(), (output / 'fpr-init.dol').read_bytes()
allowed = {index for patch in generation['patches'] for index in range(patch['offset'],patch['offset'] + 4)}
assert {index for index in range(256,len(original)) if original[index] != image[index]} <= allowed
header = struct.unpack('>64I',original[:256])
data = base64.b64decode(capture['data'])
assert len(data) == 192 * 736
inputs, expected = [], []


def expand(bits):
    sign = (bits >> 31) << 63
    exponent, fraction = (bits >> 23) & 255, bits & 0x7fffff
    if exponent == 255:
        return sign | (2047 << 52) | (fraction << 29)
    if exponent:
        return sign | ((exponent + 896) << 52) | (fraction << 29)
    if not fraction:
        return sign
    leading = fraction.bit_length() - 1
    return sign | ((874 + leading) << 52) | ((fraction - (1 << leading)) << (52 - leading))


def check(row,record):
    reg = record['fd']
    assert row[:16] == b'OSHSM_PPC_DLP001'
    assert struct.unpack_from('>2I',row,16) == (0xc001cafe,record['index'])
    ps0 = struct.unpack_from('>Q',row,192 + reg * 8)[0]
    ps1 = struct.unpack_from('>Q',row,448 + reg * 8)[0]
    fpscr = struct.unpack_from('>Q',row,704)[0] & 0xffffffff
    stored = struct.unpack_from('>I',row,24)[0]
    assert ps0 == ps1 == expand(record['bits']) and stored == record['bits'] and fpscr == record['ni'] * 4
    assert struct.unpack_from('>I',row,712)[0] == record['initialLoadRa']
    assert struct.unpack_from('>I',row,32 + record['storeRa'] * 4)[0] == record['initialStoreRa']
    return [ps0,ps1,fpscr,stored]


mutants = 0
for record in generation['records']:
    assert record['loadRa'] not in (26,27,29) and record['storeRa'] not in (26,27,29)
    for kind in ('load','store'):
        address = record[kind + 'Address']
        section = next(i for i in range(7) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        offset = header[section] + address - header[18 + section]
        assert image[offset:offset + 4] == original[offset:offset + 4]
        assert struct.unpack_from('>I',original,offset)[0] == record[kind + 'Opcode']
    row = data[record['index'] * 736:(record['index'] + 1) * 736]
    expected.append(check(row,record))
    inputs.append(f"{record['bits']} {record['ni'] * 4} {record['loadOpcode']} {record['storeOpcode']}\n")
    for offset in (24,192 + record['fd'] * 8,448 + record['fd'] * 8,708,712):
        bad = bytearray(row)
        bad[offset] ^= 1
        try:
            check(bad,record)
        except AssertionError:
            mutants += 1
        else:
            raise AssertionError('Unchecked FP32 evidence mutation')
assert mutants == 960
exe = output / 'fp32-probe'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
result = subprocess.run(['clang++','-std=c++20','-O2','-I',str(experiment),'-I','work/private-game/static-recomp/mass-ni-guard',
    '-I',str(runtime / 'include'),str(experiment / 'fp32_probe.cpp'),'-o',str(exe)],capture_output=True,text=True,timeout=30)
(output / 'native-build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
result = subprocess.run([str(exe)],input=''.join(inputs),capture_output=True,text=True,timeout=30)
(output / 'native-results.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and not result.stderr
assert [list(map(int,line.split())) for line in result.stdout.splitlines()] == expected
contract = output / 'fp32-contract'
result = subprocess.run(['clang++','-std=c++20','-O2','-I',str(experiment),'-I','work/private-game/static-recomp/mass-ni-guard',
    '-I',str(runtime / 'include'),str(experiment / 'fp32_contract.cpp'),'-o',str(contract)],capture_output=True,text=True,timeout=30)
assert result.returncode == 0, result.stderr
result = subprocess.run([str(contract)],capture_output=True,text=True,timeout=30)
assert result.returncode == 0 and result.stdout == 'FP32_CONTRACT guards=12 roundtrips=786432 zero_RA=2\n', result
(output / 'comparison.json').write_text(json.dumps({'result':'FOUR_ORIGINAL_FP32_TRANSFERS_NI0_NI1_BOTH_LANES_FPSCR_MEMORY_MATCH',
    'cases':192,'mutantsRejected':mutants,'verifierSha256':sha(Path(__file__)),
    'captureSha256':sha(capture_path),'generationSha256':sha(generation_path),
    'adapterSha256':sha(experiment / 'fp32_transfer.h'),'probeSha256':sha(experiment / 'fp32_probe.cpp'),
    'executableSha256':sha(exe),'contractSha256':sha(experiment / 'fp32_contract.cpp'),
    'contractExecutableSha256':sha(contract),'refusalContracts':12,'conversionRoundtripContracts':786432,
    'limits':['Original constructor load/store included; NI0/NI1/4-byte alignment/16 IEEE single encodings.',
        'lfs fills both PS lanes, stores preserve lanes/FPSCR; native helper uses existing BAT/cache frontend.',
        'Stores only exact-single representations verified; arbitrary binary64 truncation/rounding not admitted.',
        'Update forms/unaligned/exceptions/full constructor/retail startup/physical Wii remain unverified.']},indent=2) + '\n')
print('PASS192 original FP32 lfs/stfs/lfsx/stfsx cases/NI0-NI1/both lanes/FPSCR/raw encodings/960 evidence mutations; module integration next')
