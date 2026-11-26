"""Validate progress and isolate the remaining XER carry gap without accepting the OS prefix."""
from pathlib import Path
import base64
import hashlib
import json
import re
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
verifier = experiment / 'verify_poll.py'
prefix = verifier.read_text().split("comparator = experiment / 'verify_dcache.py'", 1)[0]
exec(compile(prefix, str(verifier), 'exec'), globals())
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
exe = native / 'poll-contract'
result = subprocess.run(['clang++', '-std=c++20', '-O0', '-include', 'bit', '-I', str(upstream / 'nWiiRuntime/include'),
                         str(experiment / 'poll_contract.cpp'), str(experiment / 'processor_adapter.cpp'), '-o', str(exe)],
                        capture_output=True, text=True, timeout=30)
assert result.returncode == 0, result.stderr
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
assert result.returncode == 0 and 'BOOT_POLL_CONTRACT cleanState 14refusals PASS' in result.stdout
normalized = Path('work/private-game/static-recomp/dolphin-poll-normalized-probe')
captures = {}
for folder, builder, runner in [(output, 'build_poll_probe.py', 'run_poll_probe.ps1'),
                                (normalized, 'build_poll_normalized_probe.py', 'run_poll_normalized_probe.ps1')]:
    generation = json.loads((folder / 'generation.json').read_text())
    capture = json.loads((folder / 'boot-true-dolphin.json').read_text(encoding='utf-8-sig'))
    assert generation['generatorSha256'] == sha(experiment / builder)
    assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / runner)
    assert generation['baseRunnerSha256'] == sha(experiment / 'run_dolphin_probe.ps1')
    assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(folder / 'boot.dol')
    assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
    original_path = Path('work/private-game/disc/DATA/sys/main.dol')
    assert generation['originalSha256'] == sha(original_path)
    original = original_path.read_bytes()
    assert hashlib.sha1(original).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
    header = struct.unpack('>64I', original[:256])
    section = next(i for i in range(18) if header[18 + i] <= 0x8021c000 < header[18 + i] + header[36 + i])
    offset = header[section] + 0x8021c000 - header[18 + section]
    image = (folder / 'boot.dol').read_bytes()
    assert {i for i in range(256, len(original)) if image[i] != original[i]} <= set(range(offset, offset + 4))
    data = base64.b64decode(capture['data'])
    assert len(data) == 800 and data[:16] == b'OSHSM_PPC_DLP001'
    assert struct.unpack_from('>II', data, 16) == (0xc001cafe, 0)
    assert capture['accurateCache'] == 'True' and capture['records'] == 1
    captures[folder.name] = data
generation = json.loads((normalized / 'generation.json').read_text())
assert generation['baseMeasurementSha256'] == sha(output / 'boot.dol')
assert generation['baseGenerationSha256'] == sha(output / 'generation.json')
assert generation['normalizedInputs'] == [{'address': '0x80000034', 'value': 0}, {'address': '0x800000f4', 'value': 0}]
stdout = boot['stdout']
assert 'BOOT_BOUNDARY pc=8021c000 lr=8021c054 msr=2030' in stdout and 'UNVERIFIED_PROCESSOR_REGISTER_269' in stdout
registers = list(map(int, re.search(r'BOOT_REGISTERS((?: \d+){32})', stdout)[1].split()))
raw = captures[output.name]
raw_diff = [index for index, (a, b) in enumerate(zip(registers, struct.unpack_from('>32I', raw, 32))) if a != b]
assert raw_diff == [5, 6]
data = captures[normalized.name]
assert list(struct.unpack_from('>32I', data, 32)) == registers
cr, lr, ctr, xer, hid2, hid0, msr = struct.unpack_from('>7I', data, 160)
state = [list(map(int, line.split()[1:])) for line in stdout.splitlines() if line.startswith('FP_STATE ')][-1]
assert state[0] == 0x8021c000
assert cr == sum(value << ((7 - index) * 4) for index, value in enumerate(state[2:10]))
assert (lr, ctr, hid2, hid0, msr) == (0x8021c054, state[74], 0xa0000000, 0xc000, 0x2030)
assert list(struct.unpack_from('>32Q', data, 192)) == state[10:42]
assert list(struct.unpack_from('>32Q', data, 448)) == state[42:74]
assert (struct.unpack_from('>Q', data, 704)[0] & 0xffffffff) == state[1]
stack = [list(map(int, line.split()[2:])) for line in stdout.splitlines() if line.startswith('CPU_STACK ')][-1]
assert data[736:] == bytes(stack)
assert struct.unpack_from('>I', data, 24)[0] == 0x80000000
assert state[75] == 0 and xer == 0x20000000, 'Known gap changed; investigate instead of widening acceptance'
report = {'result': 'XER_CA_GAP_CONFIRMED_OS_PREFIX_NOT_ACCEPTED', 'guardedPollChecks': 26830, 'contractRefusals': 14,
          'rawFixtureGprDifferences': raw_diff, 'normalizedCpuDifference': {'register': 'XER', 'native': '0x00000000', 'dolphin': '0x20000000'},
          'endpointAccepted': False, 'bootSha256': sha(native / 'boot.json'), 'verifierSha256': sha(Path(__file__)),
          'pollVerifierSha256': sha(verifier), 'contractSourceSha256': sha(experiment / 'poll_contract.cpp'), 'contractExeSha256': sha(exe),
          'capturesSha256': {name: sha(Path('work/private-game/static-recomp') / name / 'boot-true-dolphin.json') for name in captures},
          'limits': ['Guarded pre-service no-delivery does not implement device ticking/event registration/interrupt delivery/resume.',
                     'Low-memory normalization is a disclosed controlled fixture, not physical Wii boot evidence.',
                     'Original OS-prefix remains unaccepted until arithmetic carry mismatch is fixed and verified.',
                     'Full initialized data/BSS memory, timebase/OS/IOS/GX/menu/game remain unverified.'],
          'next': 'Trace original carry-producing instructions and correct generic PPC arithmetic lowering, then rerun strict endpoint comparison.'}
(normalized / 'gap-comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('EVIDENCE:26830guarded polls/14refusals; low-memory mismatch isolated; XER.CA gap remains; OS prefix NOT accepted')
