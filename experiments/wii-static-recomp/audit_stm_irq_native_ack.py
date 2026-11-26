"""Audit current original ACK CPU return, exact three seams and unsupported-state guards."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess

root = Path('work/private-game/static-recomp')
output = root / 'stm-irq-native-ack'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'attempt.json').read_text())
assert build['builderSha256'] == sha(Path('experiments/wii-static-recomp/build_stm_irq_native_attempt.py'))
assert build['baseBuildSha256'] == sha(root / 'mass-flush-packet-boot/build.json')
assert build['contextEvidenceSha256'] == sha(root / 'mass-ipc-irq-context-observer/irq-context.json')
assert build['returnCode'] == 7
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
prior = json.loads((root / 'mass-flush-packet-boot/build.json').read_text())
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
layout = struct.unpack('>64I', dol[:256])
assert len(build['records']) == len(prior['records']) == 125
for row, old in zip(build['records'], prior['records']):
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    if row['file'] != 'output_67.cpp':
        assert row == old
    else:
        source = Path(old['source']).read_text()
        for before, after in build['transforms']:
            assert source.count(before) == 1
            address, opcode = [int(value, 16) for value in before.splitlines()[0].strip().removeprefix('// 0x').split(': ')]
            section = next(i for i in range(7) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
            assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == opcode
            source = source.replace(before, after)
        assert source == Path(row['source']).read_text()
exe = output / 'stm-irq-attempt'
assert build['executableSha256'] == sha(exe)
expected = [0x807f0000, 0xa032, 0x807f0000, 0xa032, 0x80540000, 0x805335e0, 0x8052e720, 0xc0680000,
    0x30, 0x135e0020, 0, 0x10000, 0x40f8, 1, 0, 0x80492658, 27]
fresh = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
assert fresh.returncode == 7 and not fresh.stderr
for log in (fresh.stdout, (output / 'native.log').read_text()):
    lines = log.splitlines()
    assert len(lines) == 2
    assert 'pc=807f0000 lr=807f0000 msr=a032' in lines[0]
    assert 'entries=1 reason=Original ACK returned; reply producer not activated' in lines[0]
    assert list(map(int, lines[1].split()[1:])) == expected
guards = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', 'guards'], capture_output=True, text=True, timeout=30)
assert guards.returncode == 0 and guards.stdout == 'IPC_ACK_GUARDS 10\n' and not guards.stderr
(output / 'audit.json').write_text(json.dumps({'result': 'CURRENT_ORIGINAL_CPU_IPC_ACK_RETURNS_RFI_10_GUARDS_PASS',
    'auditorSha256': sha(Path(__file__)), 'attemptSha256': sha(output / 'attempt.json'), 'guards': 10,
    'freshAckState': expected, 'limits': ['Prepared original ACK producer, exact helper accesses through existing shared hardware storage.',
        'Return sentinel replaces original fixture wait PC; three MMIO instruction seams only,124objects retained.',
        'IRQ flag projection updated at native clear in this bounded probe, not original cycle timing.',
        'No native reply/OPEN/wait-node wakeup/SI-regression/general boot or full-game completion claim.']}, indent=2) + '\n')
print('PASS current125-object original IPC ACK/vector/IRQ27/rfi return;10state-preserving guards;3DOL-checked seams')
