"""Verify retained link/source closure, helper derivation and actual bounded run."""
from pathlib import Path
import hashlib
import json
import re

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'headless-psq-scale'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, expected in {**build['dependencies'], **build['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
parent_path = root / 'headless-constant-fp/build.json'
parent = json.loads(parent_path.read_text())
assert sha(parent_path) == build['baseBuildSha256']
command = list(parent['linkCommand'])
old = next(Path(arg) for arg in command if Path(arg).name == 'output_37.cpp.o')
command[command.index(str(old))] = str(output / 'output_37.cpp.o')
exe = output / 'OpenSHSMStockPSQScale'
command[command.index('-o') + 1] = str(exe)
assert command == build['linkCommand'] and sha(exe) == build['executableSha256']
archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert sha(archive) == build['archiveSha256'] == parent['archiveSha256']
source = output / 'output_37.cpp'
assert sha(source) == build['sourceSha256']
restored = source.read_text().replace('#include "psq_scale.h"\n', '', 1)
for name in ('psq_load', 'psq_store'):
    restored = restored.replace(f'stock_{name}(ctx, ', f'ctx.{name}(')
assert restored == old.with_suffix('').read_text()
cpu = (root / 'window-quantization/include/runtime/cpu_context.h').read_text()
body = cpu[cpu.index('  void psq_load('):cpu.index('  inline void ps_add(')]
body = body.replace('  void psq_load(', '  inline void stock_psq_load(CPUContext& ctx, ')
body = body.replace('  void psq_store(', '  inline void stock_psq_store(CPUContext& ctx, ')
for member in ('gqr', 'mmu', 'fpr', 'ps1'):
    body = re.sub(rf'\b{member}\b', 'ctx.' + member, body)
body = body.replace('std::ldexp(1.0f, -signed_scale)', 'std::bit_cast<float>(uint32_t(127 - signed_scale) << 23)')
body = body.replace('std::ldexp(1.0f, signed_scale)', 'std::bit_cast<float>(uint32_t(127 + signed_scale) << 23)')
assert (output / 'psq_scale.h').read_text() == '#pragma once\n#include "runtime/cpu_context.h"\n#include <bit>\nnamespace nwii::runtime {\n' + body + '\n}\n'
component = output / 'component-verification.json'
assert json.loads(component.read_text())['result'] == 'PSQ_SCALE_DIFFERENTIAL_PASS49152'
frame_path = root / 'headless-thp-snapshot/psq-hm1ply-frame15/verification.json'
frame = json.loads(frame_path.read_text())
assert frame['result'] == 'COLORED_COMPLETE_FRAME_NATIVE_BYTES_IDENTICAL10'
assert frame['executables']['headless-psq-scale']['buildSha256'] == sha(build_path)
run_path = root / 'headless-sc-pc-headless-psq-scale-first-result.json'
run = json.loads(run_path.read_text())
assert run['result'] == 'BOUNDED_STOCK_RUN_COMPLETE' and run['executableSha256'] == sha(exe)
assert run['experimentalExecutable'] == str(exe) and not run['windowed']
log = root / 'headless-sc-pc-headless-psq-scale-first.log'
assert sha(log) == run['logSha256']
capture = root / 'headless-sc-pc-psq-scale-first-movie-timing.jsonl'
rows = [json.loads(line) for line in capture.read_text().splitlines()] if capture.exists() else []
assert all(row['serial'] == i for i, row in enumerate(rows))
(output / 'live-audit.json').write_text(json.dumps({'result': 'PSQ_SCALE_SOURCE_LINK_RUN_AUDITED',
    'buildSha256': sha(build_path), 'componentSha256': sha(component), 'frameProofSha256': sha(frame_path),
    'runSha256': sha(run_path), 'logSha256': sha(log), 'captureSha256': sha(capture) if rows else None,
    'records': len(rows), 'auditorSha256': sha(Path(__file__).resolve()),
    'limits': ['Only168PSQ calls changed, helper body recomputed, runtime/all74other guests retained; no ABI/guard change.',
        '49152native differential/fullsame-frame benchmark; speedup includes helper inlining/layout, not isolated ldexp cost.',
        'Live headless records not GPU/flicker/FPS/original Wii lifecycle proof.']}, indent=2) + '\n')
print('PSQ_SCALE_SOURCE_LINK_RUN_AUDITED', len(rows))
