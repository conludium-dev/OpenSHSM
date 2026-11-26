"""Verify the actual bounded save-write/rename sequence and retain its precise limits."""
from pathlib import Path
import hashlib
import json
import re

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-fs-rename'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, expected in build['dependencies'].items():
    assert sha(Path(path)) == expected
run_path = root / 'window-fs-rename-headless-windowed-profile-commit-result.json'
run = json.loads(run_path.read_text())
log = run_path.with_name(run_path.name.replace('-result.json', '.log'))
assert run['terminalReturncode'] == 0 and run['deadlineReached'] and run['seconds'] == 180
assert sha(output / 'OpenSHSMStockFSRename') == run['executableSha256'] == build['executableSha256']
assert sha(log) == run['logSha256']
text = log.read_text()
start = text.index("Open path='/tmp/sys/Store.000' -> fd=7")
rename_line = '[FS rename] /tmp/sys/Store.000 -> /title/00010000/52355745/data/Store.000 nodes=1'
end = text.index(rename_line, start)
sequence = text[start:end]
writes = [int(value, 16) for value in re.findall(r'\[HW IPC\] cmd=4 virt=0x93e00080 -> result=([0-9a-f]+)', sequence)]
assert writes and sum(writes) == 833440
assert sequence.count('[HW IPC] cmd=2') >= 2
assert '[HW IPC] cmd=6 virt=0x93e00080 -> result=0' in text[end:end + 256]
assert '[DI] Read:' in text[end:]
capture = root / 'window-fs-rename-profile-commit-efb_9000.png'
assert capture.is_file()
(output / 'live-audit.json').write_text(json.dumps({'result': 'LIVE_SESSION_PROFILE_WRITE_RENAME_PROGRESS',
    'buildSha256': sha(build_path), 'runSha256': sha(run_path), 'logSha256': sha(log),
    'captureSha256': sha(capture), 'verifierSha256': sha(Path(__file__)), 'writeSizes': writes,
    'writtenBytes': sum(writes), 'rename': rename_line,
    'userObservation': 'After profile confirmation proceeds further.',
    'visualObservation': 'Last inspected image changes to darker subsequent content; severe grain persists, exact scene unidentified.',
    'limits': ['Actual original-generated save services progress in native runtime; no original hardware matching oracle.',
        'Session-only virtual NAND; no persistence across restart, completed story/gameplay or corrected renderer proof.']}, indent=2) + '\n')
print('LIVE_SESSION_PROFILE_WRITE_RENAME_PROGRESS', len(writes), 'writes', sum(writes), 'bytes')
