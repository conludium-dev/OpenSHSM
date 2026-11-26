"""Instrument original instruction boundaries without altering guest instructions/state."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import struct
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'headless-movie-timing'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base_path = root / 'headless-scheduler-observe/build.json'
base = json.loads(base_path.read_text())
for path, expected in {**base['dependencies'], **base['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected, path
command = list(base['linkCommand'])
archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert sha(archive) == base['archiveSha256']
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
layout = struct.unpack('>64I', dol[:256])
sites = {11: (0x8009C5E0, 0x8009C5E4, 0x8009C624, 0x8009C628,
              0x8009B760, 0x8009B76C), 37: (0x80209D80, 0x8020A044)}
records = json.loads((root / 'window-quantization/build.json').read_text())['compiled']
changed = {}
local_headers = {}
for unit, addresses in sites.items():
    old = next(Path(arg) for arg in command if Path(arg).name == f'output_{unit}.cpp.o')
    original = old.with_suffix('')
    text = original.read_text()
    for name in re.findall(r'^#include "([^"/]+)"', text, re.M):
        header = original.parent / name
        if header.exists():
            shutil.copy2(header, output / name)
            local_headers[str(header)] = sha(header)
    for address in addresses:
        marker = f'loc_{address:08X}: ;\n'
        assert text.count(marker) == 1
        match = re.search(rf'// 0x{address:08X}: ([0-9A-F]{{8}})', text)
        assert match
        section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
        offset = layout[section] + address - layout[18 + section]
        assert struct.unpack_from('>I', dol, offset)[0] == int(match[1], 16)
        text = text.replace(marker, marker + f'    stock_movie_timing::observe(ctx, 0x{address:08X});\n')
    modified = '#include "stock_movie_timing.h"\n' + text
    stripped = modified.replace('#include "stock_movie_timing.h"\n', '', 1)
    for address in addresses:
        stripped = stripped.replace(f'    stock_movie_timing::observe(ctx, 0x{address:08X});\n', '')
    assert stripped == original.read_text()
    source, obj = output / original.name, output / old.name
    source.write_text(modified)
    record = (json.loads((root / 'window-fp-guard/output_37.cpp.record.json').read_text())
              if unit == 37 else next(row for row in records if row['source'] == original.name))
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'], '-I', str(original.parent),
        '-I', str(root / 'window-movie-dma'),
        '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
    (output / f'compile-{unit}.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-3000:]
    command[command.index(str(old))] = str(obj)
    changed[str(unit)] = {'originalPath': str(original), 'originalSha256': sha(original),
        'sourceSha256': sha(source), 'objectSha256': sha(obj), 'sites': list(addresses)}
exe = output / 'OpenSHSMStockMovieTiming'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=180)
(output / 'build.json').write_text(json.dumps({'result': 'MOVIE_TIMING_BUILT_LIVE_UNVERIFIED',
    'baseBuildSha256': sha(base_path), 'dolSha256': sha(dol_path), 'changes': changed,
    'archiveSha256': sha(archive), 'executableSha256': sha(exe), 'linkCommand': command,
    'dependencies': {**local_headers, str(root / 'window-movie-dma/stock_thp_dma_observation.h'):
        sha(root / 'window-movie-dma/stock_thp_dma_observation.h'),
        **{str(path): sha(path) for path in [Path(__file__).resolve(), public / 'stock_movie_timing.h']}},
    'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).suffix == '.o'},
    'limits': ['8 ownDOL instruction boundaries, host timestamps include scheduling/interrupts and observation overhead.',
        'No GPU/presentation timing, no guest writes, no forced FP or queue transitions.',
        '2 guest objects recompiled; runtime archive and other73 guest objects retained.']}, indent=2) + '\n')
print('MOVIE_TIMING_BUILT_LIVE_UNVERIFIED')
