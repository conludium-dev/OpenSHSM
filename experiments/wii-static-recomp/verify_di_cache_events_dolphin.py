"""Check filtered original dcbi execution and unchanged snapshots/endpoints."""
from pathlib import Path
import base64
import json
import struct

parent = Path('experiments/wii-static-recomp/verify_di_burst_events_dolphin.py')
body = parent.read_text().split("for key in ('data'", 1)[0]
body = body.replace('dolphin-di-burst-events', 'dolphin-di-cache-events').replace(
    'build_di_burst_events_dolphin.py', 'build_di_cache_events_dolphin.py').replace(
    'run_di_burst_events_disc_dolphin.ps1', 'run_di_cache_events_disc_dolphin.ps1').replace(
    'prepare_di_burst_events_disc.py', 'prepare_di_cache_events_disc.py')
body = body.replace("exec(compile(body, str(parent), 'exec'), globals())", "body = body.replace(\"len(generation['patches']) == 9\", \"len(generation['patches']) == 3\")\nexec(compile(body, str(parent), 'exec'), globals())")
exec(compile(body, str(parent), 'exec'), globals())
assert generation['cacheParentGeneratorSha256'] == sha(experiment / 'build_di_burst_events_dolphin.py')
for patch in generation['patches']:
    assert words_at(patch['filterBranch'] - 16, 4) == [0x7d8802a6, 0x3d608024, 0x616b1d88, 0x7c0c5840]
    branch_word = words_at(patch['filterBranch'], 1)[0]
    assert branch_word >> 16 == 0x4082
    offset = branch_word & 0xfffc
    assert patch['filterBranch'] + offset == patch['restore']
for key in ('data', 'confPhysical', 'productPhysical', 'inquiryPhysical'):
    assert base64.b64decode(capture[key]) == base64.b64decode(control[key])
raw = base64.b64decode(capture['events'])
assert len(raw) == 0x50040 and raw[:16] == b'OSHSM_SC_EVENTS1'
assert struct.unpack_from('>2I', raw, 16) == (6, 0)
events = [raw[64 + i * 1280:64 + (i + 1) * 1280] for i in range(6)]


def check(rows):
    for index, row in enumerate(rows):
        part, step = index // 3, index % 3
        assert struct.unpack_from('>2I', row) == (10 + step, (0x80212fa0, 0x80212fbc, 0x80212fc0)[step])
        assert struct.unpack_from('>2I', row, 12) == (0x80241d88, 0x30)
        assert struct.unpack_from('>3I', row, 24) == (0x135e2560 + part * 32, 32 if step == 0 else 1, 0x935e0080 + part * 96)
    assert rows[1][8:] == rows[2][8:] and rows[4][8:] == rows[5][8:]


check(events)
mutants = 0
for index in range(6):
    for offset in (0, 4, 12, 16, 24, 28, 32):
        changed = list(events)
        row = bytearray(changed[index])
        row[offset] ^= 1
        changed[index] = row
        try:
            check(changed)
        except AssertionError:
            mutants += 1
assert mutants == 42
for index in (2, 5):
    for offset in range(8, 1280):
        changed = list(events)
        row = bytearray(changed[index])
        row[offset] ^= 1
        changed[index] = row
        try:
            check(changed)
        except AssertionError:
            mutants += 1
assert mutants == 2586
(output / 'cache-comparison.json').write_text(json.dumps({'result': 'ORIGINAL_INPUT_DCBI_ENTRY_OPERATION_AFTER_UNCHANGED_PASS',
    'verifierSha256': sha(Path(__file__)), 'generationSha256': sha(generation_path),
    'captureSha256': sha(capture_path), 'controlCaptureSha256': sha(control_path),
    'mutantsRejected': mutants, 'limits': generation['limits'] + [
        'All16 control records/full files equal; both original physical input dcbi calls survive with observed state unchanged.',
        'Snapshot equivalence is not a proof of all hidden CPU/cache state or physical Wii behavior; scoped Dolphin LAB adapter only.']}, indent=2) + '\n')
print('PASS six original input-cache events/three filtered replays/all256 stride/all16 endpoints;2586 mutations rejected')
