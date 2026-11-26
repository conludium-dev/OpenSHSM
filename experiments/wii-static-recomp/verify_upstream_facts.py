"""Cross-check third-party archive-directory claims against the user's files, without mutation."""
from pathlib import Path
import hashlib
import json
import struct

dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
records = []
for name in ('data.arc', 'igc.arc'):
    path = Path('work/private-game/disc/DATA/files') / name
    with path.open('rb') as stream:
        header = stream.read(16)
        magic, count, first, reserved = struct.unpack('<4I', header)
        assert magic == 0xfa10 and count in (1995, 289) and reserved == 0
        table = stream.read(count * 16)
    assert len(table) == count * 16 and 16 + len(table) <= first
    found = dol.find(table)
    records.append({'archive': name, 'entries': count, 'tableBytes': len(table),
                    'tableInArchive': True, 'identicalTableInDolFileOffset': found if found >= 0 else None,
                    'tableSha256': hashlib.sha256(table).hexdigest()})
report = {'result': 'PASS', 'records': records, 'dolSha256': hashlib.sha256(dol).hexdigest(),
          'sourceClaims': ['Climax docs/formats/SHSM_ARC_FORMAT.md and docs/executables/EXECUTABLES.md',
                           'RenderEclipse FileFormats.md'],
          'limits': ['Byte equality proves duplicate directories, not which directory the original runtime consumes.',
                     'No DOL/archive patching. Required update rules for modified resources need consumer tracing.']}
Path('work/private-game/static-recomp/upstream-archive-directory-check.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(records, indent=2))
