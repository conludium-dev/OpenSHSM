"""Prove actual linked FIFO/PE member identities and parse-time acknowledgement."""
from pathlib import Path
import hashlib
import json
import os
import re
import struct
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = root / 'window-texture-late/build.json'
build = json.loads(build_path.read_text())
archive = Path(build['archivePath'])
assert sha(archive) == build['archiveSha256']
identities = []
for name, directory in [('fifo_parser.cpp', 'headless-tev-banks'), ('hw_pe.cpp', 'window-quantization')]:
    source = root / directory / name
    obj = source.with_suffix('.cpp.o')
    member = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), name + '.o'])
    assert hashlib.sha256(member).hexdigest() == sha(obj), name
    identities.append({'sourcePath': str(source), 'sourceSha256': sha(source),
        'objectPath': str(obj), 'linkedMemberSha256': sha(obj)})
probe = Path('experiments/wii-static-recomp/stock_pe_parse_ack_probe.cpp').resolve()
cache = Path(tempfile.mkdtemp(prefix='openshsm-pe-parse-proof-', dir='/private/tmp'))
def text_bytes(path):
    lines = subprocess.check_output(['/usr/bin/otool', '-s', '__TEXT', '__text', str(path)], text=True).splitlines()
    assert '(__TEXT,__text)' in lines[1]
    return '\n'.join(lines[2:]).encode()
for identity in identities:
    source = Path(identity['sourcePath'])
    if source.name == 'fifo_parser.cpp':
        recipe_path = root / 'headless-tev-banks/build.json'
        recipe = next(row for row in json.loads(recipe_path.read_text())['compiled'] if row['member'] == source.name + '.o')
    else:
        recipe_path = root / 'window-quantization/build.json'
        recipe = next(row for row in json.loads(recipe_path.read_text())['compiled'] if row['object'] == source.name + '.o')
    assert sha(source) == recipe['sourceSha256'] and identity['linkedMemberSha256'] == recipe['objectSha256']
    reproduced = cache / (source.name + '.o')
    reproduction = ['/Library/Developer/CommandLineTools/usr/bin/c++', *recipe['arguments'], '-c', str(source), '-o', str(reproduced)]
    compiled = subprocess.run(reproduction, capture_output=True, text=True, timeout=90)
    assert compiled.returncode == 0, compiled.stderr[-3000:]
    original_text = text_bytes(Path(identity['objectPath']))
    assert original_text == text_bytes(reproduced)
    identity.update(recipeSha256=sha(recipe_path), reproductionCommand=reproduction,
        executableTextSha256=hashlib.sha256(original_text).hexdigest())
guest_source = root / 'window-quantization/output_40.cpp'
guest_words = {int(address, 16): int(word, 16) for address, word in re.findall(
    r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', guest_source.read_text())}
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
layout = struct.unpack('>64I', dol[:256])
wii_words = {}
for address in list(range(0x8023A690, 0x8023A75C, 4)) + list(range(0x8023A9FC, 0x8023AA40, 4)):
    section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
    word = struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0]
    assert guest_words[address] == word
    wii_words[f'{address:08X}'] = f'{word:08X}'
assert guest_words[0x8023A6B8] == 0x3C804500 and guest_words[0x8023A6BC] == 0x38040002
assert guest_words[0x8023A708] == 0x9BEDC860 and guest_words[0x8023AA1C] == 0x986DC860
flags = json.loads((root / 'window-movie-late/build.json').read_text())['changes']['37']['arguments']
obj = cache / 'probe.cpp.o'
command = ['/Library/Developer/CommandLineTools/usr/bin/c++', *flags, '-UNDEBUG', '-c', str(probe), '-o', str(obj)]
compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
assert compiled.returncode == 0, compiled.stderr[-3000:]
link = list(build['linkCommand'])
main = next(arg for arg in link if Path(arg).name == 'main.cpp.o')
link[link.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
link.insert(1, str(obj))
exe = cache / 'parse-ack-probe'
link[link.index('-o') + 1] = str(exe)
linked = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert linked.returncode == 0, linked.stderr[-3000:]
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
run = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
assert run.returncode == 0 and 'ACTUAL_PE_FINISH_TOKEN_SIGNAL_DURING_PARSE_BEFORE_RENDER_PASS5' in run.stdout, run.stdout + run.stderr
output = root / 'pe-parse-ack-proof'
output.mkdir(exist_ok=True)
(output / 'verification.json').write_text(json.dumps({
    'result': 'CURRENT_PE_FINISH_TOKEN_PARSE_BEFORE_RENDER_PASS5', 'buildSha256': sha(build_path),
    'identities': identities, 'compileCommand': command, 'linkCommand': link,
    'probeSha256': sha(probe), 'verifierSha256': sha(Path(__file__)),
    'executablePath': str(exe), 'executableSha256': sha(exe), 'stdout': run.stdout, 'stderr': run.stderr,
    'originalDolSha256': sha(dol_path), 'wiiWords': wii_words, 'guestSourceSha256': sha(guest_source),
    'originalEvidence': ['Wii8023A690 path writes FIFO BP45000002, clears r13-C860, loops/testing that byte with call8021B4E0.',
        'Wii8023AA1C path writes same completion byte; DrawDone naming is inferred from command/wait pattern, not recovered source symbols.'],
    'limits': ['Actual currently linked parser/PE members, no renderer called: finish and interrupt token set pending/PI during Parse.',
        'Ordinary/noninterrupt token/truncated BP distinguish negative cases; current native adapter, not original physical Wii ordering oracle.',
        'Current parser/PE source recipes reproduce executable text; own DOL words verify guest completion command/wait flag path.',
        'No physical Wii beam/GPU timing or full original interrupt-handler execution proof.',
        'No runtime policy change, no causal proof for specific bad corner or new frame/performance improvement.']}, indent=2) + '\n')
print('CURRENT_PE_FINISH_TOKEN_PARSE_BEFORE_RENDER_PASS5')
print(run.stdout)
