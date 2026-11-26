"""Translate every discovered DOL function with the existing scoped backend, without a game build or publication."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('.').resolve()
experiment = root / 'experiments/wii-static-recomp'
upstream = root / '_scratch/tmp/wii-static-recomp-tools/NWiiRecomp'
private = root / 'work/private-game/static-recomp'
services = private / 'phone-services'
output = private / 'mass-current'
output.mkdir(exist_ok=True)
dol = root / 'work/private-game/disc/DATA/sys/main.dol'
assert hashlib.sha1(dol.read_bytes()).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
checked = json.loads((services / 'build.json').read_text())
assert checked['upstreamAnalyzerSha256'] == hashlib.sha256((upstream / 'nWiiAnalyzer/src/analyzer.cpp').read_bytes()).hexdigest()
assert checked['patchedAnalyzerSha256'] == hashlib.sha256((services / 'analyzer-profile.cpp').read_bytes()).hexdigest()
assert checked['profileSha256'] == hashlib.sha256((services / 'analyzer-profile.tsv').read_bytes()).hexdigest()
sources = [experiment / 'nwii_mass_driver.cpp', services / 'analyzer-profile.cpp']
sources += [upstream / name for name in ('nWiiAnalyzer/src/signature_scanner.cpp', 'nWiiAnalyzer/src/dolphin_sigdb.cpp',
            'nWiiRecomp/src/recompiler.cpp', 'nWiiRecomp/src/symbols.cpp', 'nWiiRuntime/src/core/loader.cpp')]
includes = [experiment] + [upstream / directory / 'include' for directory in ('nWiiAnalyzer', 'nWiiRecomp', 'nWiiRuntime')]
exe = output / 'nwii-mass-probe'
command = ['clang++', '-std=c++20', '-O2', *[flag for path in includes for flag in ('-I', str(path))],
           *[str(path) for path in sources], '-o', str(exe)]
print('Building mass generator', flush=True)
result = subprocess.run(command, capture_output=True, text=True, timeout=180)
(output / 'generator-build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-4000:]
print('Translating all discovered functions', flush=True)
result = subprocess.run([str(exe), str(dol), str(output), str(services / 'analyzer-profile.tsv')],
                         capture_output=True, text=True, timeout=600)
(output / 'generation.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-4000:]
files = (output / 'generated-files.txt').read_text().splitlines()
assert files and all((output / name).is_file() for name in files)
report = {'result': 'PASS', 'scope': 'Mass generation only; compilation/boot/behavior are separate gates.',
          'dolSha256': hashlib.sha256(dol.read_bytes()).hexdigest(), 'entry': '0x80006310',
          'candidateFunctions': len((output / 'functions.tsv').read_text().splitlines()),
          'generatedFiles': len(files), 'generatedBytes': sum((output / name).stat().st_size for name in files),
          'generatedSha256': {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in files},
          'driverSha256': hashlib.sha256((experiment / 'nwii_mass_driver.cpp').read_bytes()).hexdigest(),
          'backendSourcesSha256': {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources[1:]},
          'rejectedAutomaticHle': (output / 'rejected-automatic-hle.tsv').read_text().splitlines(),
          'limits': ['Heuristic function candidates may overlap/include data or omit code; generation count is not decomp progress.',
                     'Only existing eight-function/table profile is behaviorally tested. Broader switch/tail/floating-point semantics remain unverified.',
                     'Automatic HLE labels are cleared before generation to avoid substituting unverified SHSM functions.',
                     'Upstream emitter may include explicit unimplemented traps, approximations, stubs and interpreter requests; these are not accepted original behavior.',
                     'No CMake auto-downloads, original assets export, native production modifications or release changes.']}
(output / 'generation.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS:generation only', report['candidateFunctions'], 'candidates,', len(files), 'files,', report['generatedBytes'], 'bytes', flush=True)
