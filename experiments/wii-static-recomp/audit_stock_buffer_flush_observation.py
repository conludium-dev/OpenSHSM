"""Pin bounded observer evidence and the live save-service progression, not full profile success."""
from pathlib import Path
import hashlib
import json
import re
import struct

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-buffer-flush-observe'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, expected in build['dependencies'].items():
    assert sha(Path(path)) == expected
run_path = root / 'window-buffer-flush-observe-headless-windowed-range-source-result.json'
run = json.loads(run_path.read_text())
exe = output / 'OpenSHSMStockBufferFlushObserve'
log = run_path.with_name(run_path.name.replace('-result.json', '.log'))
assert run['terminalReturncode'] == 0 and run['deadlineReached'] and run['seconds'] == 180
assert sha(exe) == run['executableSha256'] == build['executableSha256']
assert sha(log) == run['logSha256']
text = log.read_text()
records = [line for line in text.splitlines() if line.startswith('[Buffer flush snapshot]')]
assert records
counts = {}
for line in records:
    match = re.search(r'phase=(entry|call) valid=([01])', line)
    assert match
    key = '/'.join(match.groups())
    counts[key] = counts.get(key, 0) + 1
    assert counts[key] <= 16
lengths = sorted({int(re.search(r'length=([0-9a-f]+)', line).group(1), 16) for line in records})
assert lengths == [0x400, 0x2000] and all('valid=1' in line for line in records)
open_position = text.index("Open path='/tmp/sys/Store.000' -> fd=7")
seek_position = text.index('[HW IPC] cmd=5 virt=0x93e00080 -> result=0', open_position)
write_position = text.index('[HW IPC] cmd=4 virt=0x93e00080 -> result=cb7a0', seek_position)
close_position = text.index('[HW IPC] cmd=2 virt=0x93e00080 -> result=0', write_position)
rename_position = text.index('[HW IPC] Ioctl fd=3 cmd=0x8', close_position)
assert '[HW IPC] cmd=6 virt=0x93e00080 -> result=fffffffc' in text[rename_position:rename_position + 256]
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
header = struct.unpack('>64I', dol[:256])
anchors = {0x8035AF2C: 0x7C832378, 0x8035AF30: 0x7CC43378, 0x8035AF34: 0x4BEB809D,
    0x80345790: 0x38C1001C, 0x8034579C: 0x39010014, 0x80345910: 0x80C10014}
for address, expected in anchors.items():
    section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
    offset = header[section] + address - header[18 + section]
    assert struct.unpack_from('>I', dol, offset)[0] == expected, hex(address)
(output / 'live-audit.json').write_text(json.dumps({'result': 'BOUNDED_FLUSH_NORMAL_SAVE_WRITE_RENAME_BARRIER',
    'buildSha256': sha(build_path), 'runSha256': sha(run_path), 'logSha256': sha(log), 'dolSha256': sha(dol_path),
    'verifierSha256': sha(Path(__file__)), 'snapshotCounts': counts, 'observedLengths': lengths, 'snapshots': records,
    'sourceOpcodes': {hex(address): hex(opcode) for address, opcode in anchors.items()},
    'writtenBytesReportedByExistingBackend': 0xCB7A0,
    'limits': ['Observed normal1024/8192-byte buffers only; previous enormous source range did not recur, not proved fixed.',
        'Live seek/write/close passed then rename refused; no completed profile or persistence proof.',
        'User reported reaching menu; actual last UI screenshot remains severely noisy.']}, indent=2) + '\n')
print('BOUNDED_FLUSH_NORMAL_SAVE_WRITE_RENAME_BARRIER', counts, 'write bytes', 0xCB7A0)
