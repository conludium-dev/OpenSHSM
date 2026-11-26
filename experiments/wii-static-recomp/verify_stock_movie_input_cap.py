"""Stress aggregate capture cap without modifying the existing built helper or component evidence."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = root / 'window-movie-input/build.json'
build = json.loads(build_path.read_text())
header = public / 'stock_movie_input.h'
assert sha(header) == build['dependencies'][str(header)]
original = public / 'stock_movie_input_probe.cpp'
source = original.read_text()
before = '    for (unsigned i = 0; i < 130; ++i) {'
after = '    if (registers != ctx.gpr || mem1 != ctx.mmu.mem1 || mem2 != ctx.mmu.mem2) {'
assert source.count(before) == source.count(after) == 1
source = source.replace(before, '    write(ctx.gpr[25], 1024 * 1024);\n' + before, 1)
source = source.replace(after, '    write(ctx.gpr[25], 4);\n' + after, 1)
temporary = Path(tempfile.mkdtemp(prefix='openshsm-movie-cap-', dir='/private/tmp'))
fixture, exe = temporary / 'cap.cpp', temporary / 'cap'
fixture.write_text(source)
flags = build['changes']['37']['arguments']
sdk = flags[flags.index('-isysroot') + 1]
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', '-isysroot', sdk,
    '-std=c++20', '-O2', '-I', str(public), str(fixture), '-o', str(exe)],
    capture_output=True, text=True, timeout=60)
assert compiled.returncode == 0, compiled.stderr[-2500:]
prefix = temporary / 'timing'
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
env['NWII_MOVIE_TIMING'] = str(prefix)
run = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
assert run.returncode == 0, run.stderr
metadata = Path(str(prefix) + '.inputs.jsonl')
data = Path(str(prefix) + '.inputs.bin')
rows = [json.loads(line) for line in metadata.read_text().splitlines()]
assert len(rows) == 16 and data.stat().st_size == 16 * 1024 * 1024
for index, row in enumerate(rows):
    assert row['index'] == index and row['offset'] == index * 1024 * 1024 and row['bytes'] == 1024 * 1024
assert sum(row['bytes'] for row in rows) == data.stat().st_size
(root / 'movie-packet-metadata/aggregate-cap-verification.json').write_text(json.dumps({
    'result': 'MOVIE_INPUT_AGGREGATE_16MIB_CAP_PASS', 'buildSha256': sha(build_path),
    'headerSha256': sha(header), 'originalProbeSha256': sha(original), 'fixtureSha256': sha(fixture),
    'executablePath': str(exe), 'executableSha256': sha(exe), 'verifierSha256': sha(Path(__file__)),
    'metadataSha256': sha(metadata), 'dataSha256': sha(data), 'attempts': 130, 'records': len(rows),
    'bytes': data.stat().st_size, 'terminalReturncode': run.returncode,
    'limits': ['Synthetic1MiB payload repeated130times;16records exhaust totalcap before128recordcap.',
        'Existing production helper unchanged; same metadata/refusal/bank invariance fixture.',
        'Not real-game throughput/audio/visual/controller/hardware acceptance.']}, indent=2) + '\n')
print('MOVIE_INPUT_AGGREGATE_16MIB_CAP_PASS', len(rows), data.stat().st_size)
