"""Privately correct original SC sites in the affected unit, retaining all original operations."""
from pathlib import Path
import hashlib
import json
import subprocess
from stock_sc_pc_patch import adapt

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
base_path = root / 'headless-cache-irq-observe/build.json'
base = json.loads(base_path.read_text())
for path, expected in base['dependencies'].items():
    assert sha(Path(path)) == expected
for path, expected in base['retainedLinkInputs'].items():
    assert sha(Path(path)) == expected
command = list(base['linkCommand'])
old_obj = next(Path(arg) for arg in command if Path(arg).name == 'output_38.cpp.o')
original = old_obj.with_suffix('')
assert sha(original) == base['sourceSha256'] and sha(old_obj) == base['objectSha256']
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
text, sites = adapt(original.read_text(), dol_path.read_bytes())
output = root / 'headless-sc-pc'
output.mkdir(exist_ok=True)
source, obj = output / 'output_38.cpp', output / 'output_38.cpp.o'
source.write_text(text)
arguments = json.loads((root / 'window-fp-guard/output_38.cpp.record.json').read_text())['arguments']
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
command[command.index(str(old_obj))] = str(obj)
exe = output / 'OpenSHSMStockSCPC'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=60)
(output / 'build.json').write_text(json.dumps({'result': 'SC_PC_SYNCHRONIZED_UNIT_BUILT_BOOT_UNVERIFIED',
    'baseBuildSha256': sha(base_path), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
    'originalSourceSha256': sha(original), 'sites': [hex(site) for site in sites],
    'executableSha256': sha(exe), 'linkCommand': command,
    'dependencies': {str(p): sha(p) for p in [Path(__file__).resolve(), public / 'stock_sc_pc_patch.py']},
    'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file()
        and Path(arg).suffix in ('.o', '.a') and arg != str(obj)},
    'limits': ['All SC sites in affected output38 synchronized; other translation units require separate integration/verification.',
        'Existing syscall/callback/cache/register semantics retained; no CTR/length clamp or bypass.',
        'Controlled cache-SC callback proof exists, not whole hardware SC/boot/video performance acceptance.']}, indent=2) + '\n')
print('SC_PC_SYNCHRONIZED_UNIT_BUILT_BOOT_UNVERIFIED', len(sites))
