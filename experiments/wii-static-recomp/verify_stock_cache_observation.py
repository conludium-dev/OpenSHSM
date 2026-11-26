"""Verify helper state preservation and critical reserve independently of a game launch."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import argparse
import re

parser = argparse.ArgumentParser()
parser.add_argument('--tag', default='helper')
parser.add_argument('--filtered-cache', action='store_true')
parser.add_argument('--expect-filter-defect', action='store_true')
args = parser.parse_args()
assert re.fullmatch(r'[a-z0-9-]{1,32}', args.tag)

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / ('window-cache-filtered' if args.filtered_cache else 'window-cache-observe')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
assert sha(output / 'stock_context_observation.h') == build['headerSha256']
source = Path('experiments/wii-static-recomp/stock_cache_observation_contract.cpp').resolve()
full = json.loads((root / 'window-quantization/build.json').read_text())
arguments = next(row['arguments'] for row in full['compiled'] if row['source'] == 'main_output.cpp')
obj = output / (args.tag + '-contract.cpp.o')
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', '-I', str(output), *arguments,
    '-I', str(source.parent), '-c', str(source), '-o', str(obj)],
    capture_output=True, text=True, timeout=60)
(output / 'helper-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
command = list(build['linkCommand'])
command[command.index(str(root / 'window-quantization/main.cpp.o'))] = str(root / 'window-quantization/contract-entry.cpp.o')
command.insert(1, str(obj))
exe = output / (args.tag + '-contract')
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
capture = output / (args.tag + '-contexts.jsonl')
assert not capture.exists(), 'Preserve existing contract evidence'
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20,
    env=dict(os.environ, NWII_THPDUMP=str(output / args.tag)))
log = output / (args.tag + '.log')
log.write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stdout + result.stderr
rows = [json.loads(line) for line in capture.read_text().splitlines()]
assert len(rows) == (529 if args.expect_filter_defect else 533)
assert sum(row['stage'] == 0 for row in rows) == 512
end = 513 if args.expect_filter_defect else 517
assert {row['stage'] for row in rows[512:end]} == ({8} if args.expect_filter_defect else {4, 5, 6, 7, 8})
assert all(row['hit'] == 1 for row in rows[512:end])
assert len(rows[end:]) == 16 and {row['stage'] for row in rows[end:]} == {2, 3}
assert all(row['ctr'] == 12 and row['lr'] == 0x8009BB9C for row in rows)
report_name = 'filter-defect-component.json' if args.expect_filter_defect else 'helper-component.json'
result_name = 'CACHE_OBSERVER_FILTER_DEFECT_REPRODUCED' if args.expect_filter_defect else 'CACHE_OBSERVER_STATE_BUDGET_CRITICAL_RESERVE_PASS'
(output / report_name).write_text(json.dumps({'result': result_name,
    'events': len(rows), 'buildSha256': sha(build_path), 'sourceSha256': sha(source),
    'objectSha256': sha(obj), 'executableSha256': sha(exe), 'captureSha256': sha(capture),
    'logSha256': sha(log), 'recipeSha256': sha(Path(__file__)),
    'capturePath': str(capture), 'executablePath': str(exe), 'logPath': str(log),
    'limits': ['Own observer only, supplied fixture memory/state; no original IRQ/cache execution.',
        'Selected GPR/FPR/control/count/RAM preservation; not entire device/scheduler state proof.',
        'Normal-stage budget exhaustion cannot consume16reserved criticalzero records; other sampling gaps remain.']}, indent=2) + '\n')
print(result_name, len(rows))
