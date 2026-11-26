"""Build an isolated OpenSHSM native executable, without editing or replacing production source."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--phone-fragment', action='store_true')
args = parser.parse_args()
native = Path('outputs/shsm-research/native')
if not native.exists():
    raise SystemExit('Retired native embedding probe: the user removed the old implementation. Use the Wii stock recompilation pipeline; see CONTINUE.md.')
experiment = Path('experiments/wii-static-recomp')
generated = Path('work/private-game/static-recomp/nwii-current')
tools = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
zig = 'C:/OpenSHSM-lab/work/research/zig/zig-x86_64-windows-0.14.1/zig.exe'
sdl = 'C:/OpenSHSM-lab/work/research/sdl/SDL2-2.32.10/x86_64-w64-mingw32'
tag = 'phone-fragment' if args.phone_fragment else 'runtime-probe'
wrapper = experiment / ('runtime_phone.cpp' if args.phone_fragment else 'runtime_probe.cpp')
executable = generated / ('openshsm-runtime-recomp-phone.exe' if args.phone_fragment else 'openshsm-runtime-recomp-probe.exe')
sources = [str(wrapper), str(experiment / 'probe_bridge.cpp'), str(generated / 'selected.cpp')]
sources += [str(native / name) for name in ('Audio.cpp', 'Scene.cpp', 'WiiGeometry.cpp', 'WiiTexture.cpp')]
flags = ['-O2', '-include', 'bit', '-target', 'x86_64-windows-gnu',
           '-I', str(native / 'include'), '-I', str(native / 'vendor'), '-I', sdl + '/include/SDL2',
           '-I', str(tools / 'nWiiRuntime/include')]
private = Path('work/private-game/static-recomp')
native_hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in sorted(native.rglob('*')) if path.suffix in ('.h', '.hpp', '.cpp')}
log = ''
command = [zig, 'c++', '-std=c++20', '-fno-char8_t', *flags, *sources, sdl + '/lib/libSDL2.dll.a', '-lopengl32', '-o', str(executable)]
result = subprocess.run(command, capture_output=True, text=True, timeout=600)
log += result.stdout + result.stderr
(private / (tag + '-build.log')).write_text(log)
assert result.returncode == 0, '\n'.join(line for line in result.stderr.splitlines() if 'error:' in line) or result.stderr[-5000:]
shutil.copyfile('outputs/shsm-research/SDL2.dll', generated / 'SDL2.dll')
records = []
commands = [['--self-test'], ['--experimental-recomp-smoke']]
if args.phone_fragment:
    prepared = Path('work/private-game/fresh Wii r86')
    commands = [['--self-test'], ['--experimental-recomp-phone', '--self-test'],
                ['--experimental-recomp-phone', '--phone-settings-check', str(prepared / 'phone-ui'),
                 str(prepared / 'phone/wii-english.bin')]]
for arguments in commands:
    result = subprocess.run([str(executable), *arguments], capture_output=True, text=True, timeout=90)
    log += result.stdout + result.stderr
    assert result.returncode == 0 and 'PASS' in result.stdout, (arguments, result.stdout, result.stderr)
    records.append({'argument': arguments[0], 'arguments': arguments, 'stdout': result.stdout, 'exitCode': result.returncode})
(private / (tag + '.log')).write_text(log)
report = {'result': 'PASS', 'records': records, 'target': 'x86_64-windows-gnu',
          'executableSha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
          'productionSandboxSha256': hashlib.sha256((native / 'sandbox.cpp').read_bytes()).hexdigest(),
          'generatedSha256': hashlib.sha256((generated / 'selected.cpp').read_bytes()).hexdigest(),
          'wrapperSha256': hashlib.sha256(wrapper.read_bytes()).hexdigest(),
          'bridgeSha256': hashlib.sha256((experiment / 'probe_bridge.cpp').read_bytes()).hexdigest(),
          'nativeSourcesSha256': native_hashes,
          'limits': ['Existing production native source compiled unchanged through a private experimental entrypoint wrapper.',
                     'Original-function call/return tested inside this executable; not live gameplay frame, real Wiimote vibration or a released build.']}
assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest for path, digest in native_hashes.items()), 'Native sources changed during build'
if args.phone_fragment:
    report['limits'] = ['Opt-in callback injection only in private wrapper; production source and default native action remain unchanged.',
                        'Existing PhoneUI input/state/localization test is linked; real render verification is a separate report.',
                        'Only vibrate is recompiled; ringtone/volume, save persistence and hardware rumble remain native/unverified.']
(private / (tag + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print('PASS:isolated native OpenSHSM', tag, 'checks')
