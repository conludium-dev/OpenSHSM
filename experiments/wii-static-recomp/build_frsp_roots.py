"""Generate omitted original-code roots with the existing analyzer/backend in isolation."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'frsp-roots'
output.mkdir(exist_ok=True)
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
services = private / 'phone-services'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
roots = [0x801015cc, 0x801123dc, 0x803d1470]
driver = (experiment / 'nwii_mass_driver.cpp').read_text()
driver = driver.replace('analyzer.analyze();', 'analyzer.analyze({0x801015cc, 0x801123dc, 0x803d1470});')
driver = driver.replace('for (auto& [entry, function] : functions) {', '''for (auto item = functions.begin(); item != functions.end();) {
        if (item->first != 0x801015cc && item->first != 0x801123dc && item->first != 0x803d1470) {
            item = functions.erase(item);
        } else {
            ++item;
        }
    }
    for (auto& [entry, function] : functions) {''')
source = output / 'root-driver.cpp'
source.write_text(driver)
sources = [source, services / 'analyzer-profile.cpp']
sources += [upstream / name for name in ('nWiiAnalyzer/src/signature_scanner.cpp', 'nWiiAnalyzer/src/dolphin_sigdb.cpp',
            'nWiiRecomp/src/recompiler.cpp', 'nWiiRecomp/src/symbols.cpp', 'nWiiRuntime/src/core/loader.cpp')]
includes = [experiment] + [upstream / name / 'include' for name in ('nWiiAnalyzer', 'nWiiRecomp', 'nWiiRuntime')]
exe = output / 'root-generator'
result = subprocess.run(['clang++', '-std=c++20', '-O2', *[flag for path in includes for flag in ('-I', str(path))],
                         *map(str, sources), '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'generator-build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
dol = Path('work/private-game/disc/DATA/sys/main.dol')
assert hashlib.sha1(dol.read_bytes()).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
result = subprocess.run([str(exe), str(dol), str(output), str(services / 'analyzer-profile.tsv')],
                        capture_output=True, text=True, timeout=180)
(output / 'generation.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
rows = (output / 'functions.tsv').read_text().splitlines()
assert {int(row.split('\t')[0], 16) for row in rows} == set(roots)
files = (output / 'generated-files.txt').read_text().splitlines()
report = {'result': 'EXPLICIT_ROOTS_GENERATED_NOT_BEHAVIOR_VERIFIED', 'roots': [hex(value) for value in roots],
          'functions': rows, 'generatedSha256': {name: sha(output / name) for name in files},
          'originalSha256': sha(dol), 'baseDriverSha256': sha(experiment / 'nwii_mass_driver.cpp'),
          'driverSha256': sha(source), 'scriptSha256': sha(Path(__file__)),
          'analyzerSha256': sha(services / 'analyzer-profile.cpp'), 'profileSha256': sha(services / 'analyzer-profile.tsv'),
          'limits': ['Explicit roots from original prologue/control-flow evidence; whole-program reachability not proven.',
                     'Only missing-root functions emitted, existing module and dispatch untouched.',
                     'Compilation, ABI/behavior comparison and runtime integration are separate requirements.']}
(output / 'generation.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], rows, files, flush=True)
