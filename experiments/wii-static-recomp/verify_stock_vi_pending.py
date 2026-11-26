"""Prove linked VI object provenance and existing pending-latch/delivery behavior."""
from pathlib import Path
import hashlib
import json
import os
import re
import shlex
import struct
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = root / 'window-dec-ee-gate/build.json'
build = json.loads(build_path.read_text())
archive = Path(build['archivePath'])
assert sha(archive) == build['archiveSha256']
original_obj = root / 'window-quantization/hw_vi.cpp.o'
member = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), 'hw_vi.cpp.o'])
assert hashlib.sha256(member).hexdigest() == sha(original_obj)
source = root / 'window-quantization/hw_vi.cpp'
flags_path = root / 'window-quantization/build.json'
record = next(item for item in json.loads(flags_path.read_text())['compiled'] if item['object'] == 'hw_vi.cpp.o')
assert sha(source) == record['sourceSha256'] and sha(original_obj) == record['objectSha256']
flags = record['arguments']
cache = Path(tempfile.mkdtemp(prefix='openshsm-vi-pending-', dir='/private/tmp'))
reproduced = cache / 'hw_vi.cpp.o'
command = ['/Library/Developer/CommandLineTools/usr/bin/c++', *flags, '-c', str(source), '-o', str(reproduced)]
compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
assert compiled.returncode == 0, compiled.stderr[-3000:]
def text_bytes(path):
    lines = subprocess.check_output(['/usr/bin/otool', '-s', '__TEXT', '__text', str(path)], text=True).splitlines()
    assert '(__TEXT,__text)' in lines[1]
    return '\n'.join(lines[2:]).encode()
before, after = text_bytes(original_obj), text_bytes(reproduced)
assert before == after, 'Exported VI source does not reproduce current linked executable text'
probe = Path('experiments/wii-static-recomp/stock_vi_pending_probe.cpp').resolve()
obj = cache / 'probe.cpp.o'
probe_flags = json.loads((root / 'window-movie-late/build.json').read_text())['changes']['37']['arguments']
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *probe_flags,
    '-UNDEBUG', '-c', str(probe), '-o', str(obj)], capture_output=True, text=True, timeout=60)
assert compiled.returncode == 0, compiled.stderr[-3000:]
link = list(build['linkCommand'])
main = next(arg for arg in link if Path(arg).name == 'main.cpp.o')
link[link.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
link.insert(1, str(obj))
exe = cache / 'vi-pending-probe'
link[link.index('-o') + 1] = str(exe)
linked = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert linked.returncode == 0, linked.stderr[-3000:]
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
run = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
assert run.returncode == 0 and 'ACTUAL_VI_PENDING_EE0_BUSY_IDLE_NONIDLE_PASS3' in run.stdout, run.stdout + run.stderr
sdk_source = root / 'window-live-phases/output_39.cpp'
words = {int(address, 16): int(word, 16) for address, word in re.findall(
    r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', sdk_source.read_text())}
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
layout = struct.unpack('>64I', dol[:256])
verified = {}
for address in range(0x80228104, 0x80228184, 4):
    section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
    word = struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0]
    assert words[address] == word
    verified[f'{address:08X}'] = f'{word:08X}'
assert words[0x8022810C] == 0xA0652030 and words[0x80228128] == 0xB0052030
assert words[0x80228134] == 0xA0642034 and words[0x80228144] == 0xB0042034
report = {
    'result': 'CURRENT_VI_TEXT_REPRODUCED_PENDING_DEFERRED_DELIVERY_PASS3',
    'buildSha256': sha(build_path), 'archiveSha256': sha(archive), 'sourceSha256': sha(source),
    'linkedMemberSha256': hashlib.sha256(member).hexdigest(), 'textSha256': hashlib.sha256(before).hexdigest(),
    'compileCommand': command, 'flagsSha256': sha(flags_path), 'linkCommand': link,
    'probeSha256': sha(probe), 'executableSha256': sha(exe), 'stdout': run.stdout, 'stderr': run.stderr,
    'verifierSha256': sha(Path(__file__)),
    'sdkSourceSha256': sha(sdk_source), 'originalDolSha256': sha(dol_path), 'verifiedWiiWords': verified,
    'originalBehaviorEvidence': ['Wii DOL80228104..80228180 reads DI high words at CC002030/34/38/3C and conditionally writes values with bit15 cleared.',
        'Original code distinguishes reading/latching pending status from acknowledgement in its handler; no native busy-gate statement inferred from these words.'],
    'limits': ['Current linked archive VI member matches quantization object; same source/recipe executable text reproduced.',
        'Actual VI bit latches/coalesces twice; existing IOS defers EE0 and busy context with idle/nonidle then native dispatches after safe gates.',
        'Synthetic configured dispatch address, not original Wii handler execution, hardware timing or live FPS proof.',
        'No runtime policy/source changes or second queue; original DOL SDK ordering still requires verification.']}
output = root / 'vi-pending-proof'
output.mkdir(exist_ok=True)
(output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['result'])
print(run.stdout)
