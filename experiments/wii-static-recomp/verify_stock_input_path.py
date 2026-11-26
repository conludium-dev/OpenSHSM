"""Audit the actual input provider/guest boundary and verify the existing host provider without OS input."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base = root / 'window-legacy-context'
output = root / 'input-path-diagnosis'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = base / 'build.json'
build = json.loads(build_path.read_text())
assert sha(base / 'OpenSHSMStockLegacyContext') == build['executableSha256']
command = list(build['linkCommand'])
archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
full = root / 'window-quantization'
members = {}
for name in ['input_manager.cpp', 'mouse_keyboard_source.cpp', 'gamepad_source.cpp', 'pad.cpp', 'usb_device.cpp']:
    obj = full / (name + '.o')
    data = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), name + '.o'])
    assert data == obj.read_bytes(), name
    source = full / name
    members[name] = {'sourceSha256': sha(source), 'objectSha256': hashlib.sha256(data).hexdigest()}
generated = [Path(arg).with_suffix('') for arg in command if re.fullmatch(r'output_\d+\.cpp\.o', Path(arg).name)
    or Path(arg).name in ['fixed.cpp.o', 'main_output.cpp.o']]
assert len(generated) == 76
references = []
for path in generated:
    for symbol in ['WPADInit', 'WPADRead', 'WPADProbe', 'KPADInit', 'KPADRead']:
        if re.search(r'\b' + symbol + r'\b', path.read_text()):
            references.append({'path': str(path), 'symbol': symbol})
assert not references, references
game_exe = base / 'OpenSHSMStockLegacyContext'
symbols = subprocess.check_output(['/usr/bin/nm', '-g', str(game_exe)], text=True)
pad_symbols = [line for line in symbols.splitlines() if re.search(r'\b[ Tt] _(?:WPAD|KPAD)\w*$', line)]
assert not pad_symbols, pad_symbols
usb = (full / 'usb_device.cpp').read_text()
assert 'InputManager' not in usb and 'get_wiimote_state' not in usb
assert 'return IPC_NO_REPLY' in usb
run_path = root / 'window-legacy-context-headless-windowed-legacy180-result.json'
run = json.loads(run_path.read_text())
log_path = root / 'window-legacy-context-headless-windowed-legacy180.log'
assert sha(log_path) == run['logSha256']
log = log_path.read_text()
assert 'Input mode 6 (keyboard-mouse)' in log and 'Total sources: 2' in log
assert "path='/dev/usb/oh1/57e/305'" in log and '[USB] HCI command opcode' in log
source = Path('experiments/wii-static-recomp/stock_host_input_probe.cpp').resolve()
full_build = json.loads((full / 'build.json').read_text())
arguments = next(row['arguments'] for row in full_build['compiled'] if row['source'] == 'main_output.cpp')
obj = output / 'probe.cpp.o'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments, '-c', str(source), '-o', str(obj)],
    capture_output=True, text=True, timeout=60)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
command[command.index(str(full / 'main.cpp.o'))] = str(full / 'contract-entry.cpp.o')
command.insert(1, str(obj))
exe = output / 'host-input-probe'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
(output / 'probe.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stdout + result.stderr
(output / 'diagnosis.json').write_text(json.dumps({'result': 'HOST_PROVIDER_GUEST_INPUT_BRIDGE_MISSING',
    'baseBuildSha256': sha(build_path), 'linkedMembers': members,
    'generatedSources': {str(path): sha(path) for path in generated}, 'guestHleReferences': references,
    'gameExecutableSha256': sha(game_exe), 'gamePadSymbols': pad_symbols,
    'runSha256': sha(run_path), 'logSha256': sha(log_path), 'probeSourceSha256': sha(source),
    'probeExeSha256': sha(exe), 'probeLogSha256': sha(output / 'probe.log'), 'recipeSha256': sha(Path(__file__)),
    'limits': ['Actual linked keyboard provider supplies host state; no button/IR/motion/physical controller acceptance.',
        'No named WPAD/KPAD HLE references in generated guest/dispatcher; original PPC Bluetooth route is observed.',
        'USB stub has no host input consumer/ACL report delivery; full guest warning condition not yet traced.',
        'Existing pad.cpp buffer formats are not verified against own Wii SDK and must not be blindly bound.',
        'No new game launch/OS focus or synthetic input/forced readiness/production changes.']}, indent=2) + '\n')
print('HOST_PROVIDER_GUEST_INPUT_BRIDGE_MISSING')
print(result.stdout)
