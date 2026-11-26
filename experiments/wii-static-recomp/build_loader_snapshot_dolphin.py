"""Capture emulator-provided Wii low-memory values before any original OSInit call."""
from pathlib import Path
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_si_query_dolphin.py'
source = parent.read_text()
exec(compile(source[:source.index('for index in range(16):')].replace('dolphin-si-query', 'dolphin-loader-snapshot'), str(parent), 'exec'), globals())
addresses = list(range(0x3100, 0x3164, 4)) + [0x28, 0x2c, 0x30, 0x34, 0xf0, 0xf8, 0xfc]
for index in range(16):
    data[index * stride:index * stride + 16] = b'OSHSM_PPC_DLP001'
    struct.pack_into('>I', data, index * stride + 20, index)
    pointer(code, 30, 0xc0680000 + index * stride)
    pointer(code, 11, 0xc0000000)
    for slot, address in enumerate(addresses):
        code.extend([dform(32, 0, 11, address), dform(36, 0, 30, 24 + slot * 4)])
    pointer(code, 0, 0xc001cafe)
    code.append(dform(36, 0, 30, 16))
    records.append({'index': index, 'addresses': addresses})
halt = base + len(code) * 4
code.append(branch(halt, halt))
patches = []
exec(compile(source[source.index('while len(code) % 8:'):source.index('sha = lambda path:')], str(parent), 'exec'), globals())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'generation.json').write_text(json.dumps({
    'originalSha256': sha(original_path), 'harnessSha256': sha(output / 'fpr-init.dol'),
    'generatorSha256': sha(Path(__file__)), 'parentSha256': sha(parent), 'helperSha256': sha(helpers),
    'wrapperSha256': sha(experiment / 'run_loader_snapshot_dolphin.ps1'),
    'baseRunnerSha256': sha(experiment / 'run_dolphin_probe.ps1'), 'records': records, 'patches': [],
    'limits': ['Direct owned-DOL emulator boot, entry replaced with read-only low-memory snapshot.',
        'Not retail disc apploader, original OSInit execution or physical Wii evidence.'],
}, indent=2) + '\n')
print('Generated16read-only initial Wii loader snapshots; no low-memory seeds or original-code patches')
