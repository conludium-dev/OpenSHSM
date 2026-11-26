"""Reject malformed diagnostic snapshots before executing original guest code."""
from pathlib import Path
import hashlib
import json
import os
import struct
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'headless-thp-snapshot/replay/invalid-inputs'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
proof_path = output.parent / 'verification.json'
proof = json.loads(proof_path.read_text())
assert proof['result'] == 'COMPLETE_FRAME_REPLAY_LIVE_BYTES_IDENTICAL2'
exe = output.parent / 'headless-constant-fp-replay'
assert sha(exe) == next(row['executableSha256'] for row in proof['variants'] if row['variant'] == 'headless-constant-fp')
snapshot = root / 'headless-sc-pc-decoder-snapshot-retry-decoder-entry.bin'
assert sha(snapshot) == proof['snapshotSha256']
with snapshot.open('rb') as stream:
    prefix = stream.read(800)
assert prefix[:8] == b'SHSMFP01'
cases = {'bad-magic': b'INVALID!', 'truncated-registers': b'SHSMFP01' + b'\0' * 8,
    'invalid-bank-size': prefix[:784] + struct.pack('<Q', 0xFFFFFFFFFFFFFFFF),
    'truncated-bank': prefix}
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
rows = []
for name, data in cases.items():
    path = output / (name + '.bin')
    path.write_bytes(data)
    destination = output / (name + '.yuv')
    assert not destination.exists()
    result = subprocess.run([str(exe), str(path), str(destination)], env=env,
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 13 and not destination.exists(), (name, result.returncode, result.stderr)
    rows.append({'case': name, 'sha256': sha(path), 'returncode': result.returncode, 'error': result.stderr.strip()})
(output / 'verification.json').write_text(json.dumps({'result': 'THP_REPLAY_MALFORMED_INPUT_REFUSAL_PASS4',
    'executableSha256': sha(exe), 'whiteFrameProofSha256': sha(proof_path),
    'verifierSha256': sha(Path(__file__).resolve()), 'cases': rows,
    'limits': ['Magic/truncated registers/oversized bank/truncated RAM rejected before guest decode/output.',
        'Diagnostic snapshot parser only, not game save/import compatibility or hostile complete guest-code validation.']}, indent=2) + '\n')
print('THP_REPLAY_MALFORMED_INPUT_REFUSAL_PASS4')
