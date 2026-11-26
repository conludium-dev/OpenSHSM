"""Reduce measured diagnostic overhead in a private copy of the verified runtime."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
from stock_observer_env_patch import idct, ios

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'headless-observer-env-cache'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base_path = root / 'headless-tev-banks/build.json'
base = json.loads(base_path.read_text())
for path, expected in base['dependencies'].items():
    assert sha(Path(path)) == expected
for path, expected in base['retainedLinkInputs'].items():
    assert sha(Path(path)) == expected
command = list(base['linkCommand'])
old_guest = next(Path(arg) for arg in command if Path(arg).name == 'output_37.cpp.o')
original_guest = old_guest.with_suffix('')
guest_record = json.loads((root / 'window-fp-guard/output_37.cpp.record.json').read_text())
assert sha(original_guest) == guest_record['sourceSha256'] and sha(old_guest) == guest_record['objectSha256']
source, obj = output / 'output_37.cpp', output / 'output_37.cpp.o'
source.write_text(idct(original_guest.read_text()))
compiler = '/Library/Developer/CommandLineTools/usr/bin/c++'
def run(cmd, log, cwd=None):
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=180)
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-3000:]
    return result.stdout

run([compiler, *guest_record['arguments'], '-c', str(source), '-o', str(obj)], output / 'guest-compile.log')
command[command.index(str(old_guest))] = str(obj)
original_ios = root / 'headless-cache-irq-observe/ios.cpp'
ios_source, ios_obj = output / 'ios.cpp', output / 'ios.cpp.o'
ios_source.write_text(ios(original_ios.read_text()))
record = next(row for row in json.loads((root / 'window-quantization/build.json').read_text())['compiled'] if row['source'] == 'ios.cpp')
run([compiler, *record['arguments'], '-c', str(ios_source), '-o', str(ios_obj)], output / 'ios-compile.log')
old_archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert sha(old_archive) == base['archiveSha256']
assert subprocess.check_output(['/usr/bin/ar', '-p', str(old_archive), 'ios.cpp.o']) == (root / 'headless-cache-irq-observe/ios.cpp.o').read_bytes()
archive = output / 'libnwiiruntime.a'
shutil.copy2(old_archive, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(ios_obj)], check=True, capture_output=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
retained = {}
for member in subprocess.check_output(['/usr/bin/ar', '-t', str(old_archive)], text=True).splitlines():
    if member.startswith('__') or member == 'ios.cpp.o':
        continue
    data = subprocess.check_output(['/usr/bin/ar', '-p', str(old_archive), member])
    assert data == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    retained[member] = hashlib.sha256(data).hexdigest()
command[command.index(str(old_archive))] = str(archive)
exe = output / 'OpenSHSMStockObserverEnvCache'
command[command.index('-o') + 1] = str(exe)
run(command, output / 'link.log', root / 'export/build')
probe_cmd = list(command)
probe_cmd[probe_cmd.index(str(root / 'headless-tev-banks/main.cpp.o'))] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
proof = root / 'sc-emitter-research/native-execution'
proof_manifest = json.loads((proof / 'comparison.json').read_text())
assert sha(proof / 'corrected.cpp.o') == proof_manifest['records']['corrected']['objectSha256']
probe_cmd[1:1] = [str(proof / 'corrected.cpp.o'), str(proof / 'probe.cpp.o')]
probe = output / 'sc-resume-probe'
probe_cmd[probe_cmd.index('-o') + 1] = str(probe)
run(probe_cmd, output / 'probe-link.log', root / 'export/build')
stdout = run([str(probe)], output / 'probe.log')
assert 'SYNCHRONIZED_SC_PC_RETURN_PASS' in stdout
(output / 'build.json').write_text(json.dumps({'result': 'OBSERVER_ENV_CACHE_BUILT_SC_RESUME_PASS_GAME_UNVERIFIED',
    'baseBuildSha256': sha(base_path), 'originalGuestSha256': sha(original_guest), 'guestSourceSha256': sha(source), 'guestObjectSha256': sha(obj),
    'originalIOSSourceSha256': sha(original_ios), 'iosSourceSha256': sha(ios_source), 'iosObjectSha256': sha(ios_obj),
    'archiveSha256': sha(archive), 'executableSha256': sha(exe), 'linkCommand': command,
    'retainedRuntimeMembers': retained, 'probeSha256': sha(probe), 'probeLogSha256': sha(output / 'probe.log'),
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), public / 'stock_observer_env_patch.py']},
    'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).suffix == '.o' and arg != str(obj)},
    'limits': ['Only two per-process diagnostic flags latched at first use; runtime changes to these environment flags no longer supported.',
        'All original guest operations/FPU/HID2 checks/interrupt/callback/state/GX/FS semantics retained.',
        'Existing controlled SC resume regression passes, not original hardware/video/FPS acceptance.']}, indent=2) + '\n')
print('OBSERVER_ENV_CACHE_BUILT_SC_RESUME_PASS_GAME_UNVERIFIED')
