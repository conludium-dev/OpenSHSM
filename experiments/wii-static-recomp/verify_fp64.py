"""Compare native bit transfers with original DOL double-transfer observations."""
from pathlib import Path
import base64
import hashlib
import json
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-fp64')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['records'] == len(generation['records']) == 320 and capture['accurateCache'] == 'True'
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_fp64_dolphin.ps1')
assert generation['generatorSha256'] == sha(experiment / 'build_fp64_dolphin.py')
assert generation['helperSha256'] == sha(experiment / 'build_dolphin_probe.py')
assert generation['baseRunnerSha256'] == sha(experiment / 'run_dolphin_probe.ps1')
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert generation['originalSha256'] == sha(original_path)
original, image = original_path.read_bytes(), (output / 'fpr-init.dol').read_bytes()
allowed = {index for patch in generation['patches'] for index in range(patch['offset'], patch['offset'] + 4)}
assert {index for index in range(256, len(original)) if original[index] != image[index]} <= allowed
header = struct.unpack('>64I', original[:256])
data = base64.b64decode(capture['data'])
assert len(data) == 320 * 736
inputs, expected, observations = [], [], []
for record in generation['records']:
    for kind in ('load', 'store'):
        address = record[kind + 'Address']
        section = next(index for index in range(7) if header[18 + index] <= address < header[18 + index] + header[36 + index])
        offset = header[section] + address - header[18 + section]
        assert image[offset:offset + 4] == original[offset:offset + 4]
        assert struct.unpack_from('>I', original, offset)[0] == record[kind + 'Opcode']
    index, fd = record['index'], record['fd']
    row = data[index * 736:(index + 1) * 736]
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>II', row, 16) == (0xc001cafe, index)
    ps0 = struct.unpack_from('>Q', row, 192 + fd * 8)[0]
    ps1 = struct.unpack_from('>Q', row, 448 + fd * 8)[0]
    fpscr = struct.unpack_from('>Q', row, 704)[0] & 0xffffffff
    stored = struct.unpack_from('>Q', row, 24)[0]
    load_ra = struct.unpack_from('>I', row, 712)[0]
    store_ra = struct.unpack_from('>I', row, 32 + record['storeRa'] * 4)[0]
    assert ps0 == stored == record['bits'] and ps1 == record['ps1'] and fpscr == record['ni'] * 4
    assert load_ra == (record['inputAddress'] if record['loadOpcode'] >> 26 == 51 else record['initialLoadRa'])
    assert store_ra == (record['destination'] if record['storeOpcode'] >> 26 == 55 else record['initialStoreRa'])
    load_delta = (load_ra - record['inputAddress']) & 0xffffffff
    store_delta = (store_ra - record['destination']) & 0xffffffff
    inputs.append(f"{record['bits']} {record['ps1']} {fpscr} {record['loadOpcode']} {record['storeOpcode']} {record['inputAddress'] & 7}\n")
    expected.append([ps0, ps1, fpscr, stored, load_delta, store_delta])
    observations.append({'index': index, 'ps0': ps0, 'ps1': ps1, 'fpscr': fpscr, 'stored': stored,
                         'loadRaDelta': load_delta, 'storeRaDelta': store_delta})
exe = output / 'fp64-probe'
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
build = subprocess.run(['clang++', '-std=c++20', '-O2', '-I', str(experiment),
                        '-I', 'work/private-game/static-recomp/mass-ni-guard', '-I', str(upstream / 'nWiiRuntime/include'),
                        str(experiment / 'fp64_probe.cpp'), '-o', str(exe)], capture_output=True, text=True, timeout=30)
(output / 'native-build.log').write_text(build.stdout + build.stderr)
assert build.returncode == 0, build.stderr
result = subprocess.run([str(exe)], input=''.join(inputs), capture_output=True, text=True, timeout=30)
(output / 'native-results.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
assert [list(map(int, row.split())) for row in result.stdout.splitlines()] == expected
contract = output / 'fp64-contract'
build = subprocess.run(['clang++', '-std=c++20', '-O2', '-I', str(experiment),
                        '-I', 'work/private-game/static-recomp/mass-ni-guard', '-I', str(upstream / 'nWiiRuntime/include'),
                        str(experiment / 'fp64_contract.cpp'), '-o', str(contract)], capture_output=True, text=True, timeout=30)
assert build.returncode == 0, build.stderr
contract_result = subprocess.run([str(contract)], capture_output=True, text=True, timeout=30)
assert contract_result.returncode == 0 and contract_result.stdout == 'FP64_CONTRACT guards=9 zero_RA=3\n', contract_result
report = {'result': 'SIX_ORIGINAL_FP64_FORMS_NI0_NI1_PS0_PS1_STATUS_MEMORY_UPDATE_MATCH', 'cases': 320,
          'captureSha256': sha(capture_path), 'generationSha256': sha(output / 'generation.json'),
          'adapterSha256': sha(experiment / 'fp64_transfer.h'), 'probeSha256': sha(experiment / 'fp64_probe.cpp'),
          'contractSha256': sha(experiment / 'fp64_contract.cpp'), 'refusalRollbackCases': 9, 'zeroRaContracts': 3,
          'verifierSha256': sha(Path(__file__)), 'observations': observations,
          'limits': ['Original six forms, NI0/NI1,4/8-byte alignment,16IEEE patterns including signaling/quiet NaN payloads.',
                     'Native helper uses raw64 BAT/cache access; FPSCR/PS1 retained, update RA after successful transfer.',
                     'Indexed-update forms absent from DOL and unsupported; exceptions/unaligned/unmapped/code writes refuse.',
                     'Whole enclosing-function/live boot integration and physical Wii behavior require separate checks.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS320original FP64cases/sixforms/NI0-NI1/4-8alignment/rawNaNs/PS0-PS1-FPSCR-memory-RA; runtime integration pending')
