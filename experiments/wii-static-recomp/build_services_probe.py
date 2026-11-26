"""Build a scoped patched analyzer copy; leave pinned upstream and first milestone intact."""
from pathlib import Path
import difflib
import hashlib
import json
import re
import struct
import subprocess

root = Path('.').resolve()
experiment = root / 'experiments/wii-static-recomp'
tools = root / '_scratch/tmp/wii-static-recomp-tools'
upstream = tools / 'NWiiRecomp'
private = root / 'work/private-game/static-recomp'
output = private / 'phone-services'
output.mkdir(exist_ok=True)
dol = root / 'work/private-game/disc/DATA/sys/main.dol'
dol_bytes = dol.read_bytes()
assert hashlib.sha1(dol_bytes).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
dol_header = struct.unpack('>64I', dol_bytes[:256])


def original_word(address):
    index = next(index for index in range(18) if dol_header[18 + index] <= address < dol_header[18 + index] + dol_header[36 + index])
    return struct.unpack_from('>I', dol_bytes, dol_header[index] + address - dol_header[18 + index])[0]


source_path = upstream / 'nWiiAnalyzer/src/analyzer.cpp'
original = source_path.read_text()
assert hashlib.sha256(source_path.read_bytes()).hexdigest() == '2d283a2765281086f24036fa50fadf33138411b0d47cf3263be8031b8c000fcc'
patched = original


def replace_once(old, new):
    global patched
    assert patched.count(old) == 1, old
    patched = patched.replace(old, new)


replace_once('#include "analyzer/analyzer.h"', '#include "analyzer/analyzer.h"\n#include "analyzer_profile.h"')
replace_once('(inst.value() & 0x3FF) == 528', 'inst.extended_opcode() == 528')
replace_once('uint32_t spr = (inst.value() >> 11) & 0x3FF;',
             'uint32_t spr = ((inst.value() >> 16) & 31) | (((inst.value() >> 11) & 31) << 5);')
replace_once('while (true) {\n      uint32_t ptr = read_data32(scan_addr);',
             'while (true) {\n      uint32_t limit = experimentJumpTableLimit(table_base);\n'
             '      if (limit && scan_addr >= table_base + limit * 4) { break; }\n'
             '      uint32_t ptr = read_data32(scan_addr);')
replace_once('if (known_functions.find(ptr) != known_functions.end()) {',
             'if (!experimentJumpTableLimit(table_base) && known_functions.find(ptr) != known_functions.end()) {')
replace_once('if (visited_blocks.count(current_pc))',
             'if (!experimentFunctionContains(func_start, current_pc)) { break; }\n        if (visited_blocks.count(current_pc))')
patched_path = output / 'analyzer-profile.cpp'
patched_path.write_text(patched)
(output / 'analyzer-profile.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True), patched.splitlines(True),
                                                                         fromfile='pinned/analyzer.cpp', tofile='experimental/analyzer-profile.cpp')))
dtk_bounds = {}
for path in (private / 'dtk-output/asm').glob('*.s'):
    for start, size in re.findall(r'# \.text:0x[0-9A-Fa-f]+ \| 0x([0-9A-Fa-f]+) \| size: 0x([0-9A-Fa-f]+)', path.read_text()):
        dtk_bounds[int(start, 16)] = int(start, 16) + int(size, 16)
entries = [0x800c770c, 0x800c7720, 0x800ed314, 0x800ed3c8, 0x800f3d94, 0x800f3e30, 0x800f3e60, 0x800f3ec0]
bound_word = original_word(0x800ed3f4)
assert bound_word == 0x2800001e, 'Original switch bound is not the verified cmplwi r0,30'
table_entries = (bound_word & 0xffff) + 1
assert all(0x800ed3c8 <= original_word(0x803f0608 + index * 4) < dtk_bounds[0x800ed3c8] for index in range(table_entries))
profile = ''.join(f'F {entry:x} {dtk_bounds[entry]:x}\n' for entry in entries) + f'T 803f0608 {table_entries:x}\n'
profile_path = output / 'analyzer-profile.tsv'
profile_path.write_text(profile)
sources = [experiment / 'nwii_services_driver.cpp', patched_path]
sources += [upstream / path for path in ('nWiiAnalyzer/src/signature_scanner.cpp', 'nWiiAnalyzer/src/dolphin_sigdb.cpp',
            'nWiiRecomp/src/recompiler.cpp', 'nWiiRecomp/src/symbols.cpp', 'nWiiRuntime/src/core/loader.cpp')]
includes = [experiment] + [upstream / directory / 'include' for directory in ('nWiiAnalyzer', 'nWiiRecomp', 'nWiiRuntime')]
exe = output / 'nwii-services-probe'
command = ['clang++', '-std=c++20', '-O2', *[flag for path in includes for flag in ('-I', str(path))],
           *[str(path) for path in sources], '-o', str(exe)]
result = subprocess.run(command, capture_output=True, text=True, timeout=180)
(output / 'build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-4000:]
result = subprocess.run([str(exe), str(dol), str(output), str(profile_path)], capture_output=True, text=True, timeout=180)
(output / 'analysis.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-4000:]
assert source_path.read_text() == original
analysis_stdout = result.stdout
host = output / 'services-host'
result = subprocess.run(['clang++', '-std=c++20', '-O2', '-include', 'bit',
                         '-I', str(upstream / 'nWiiRuntime/include'), '-I', str(upstream / 'nWiiAnalyzer/include'),
                         str(experiment / 'services_host.cpp'), str(output / 'selected.cpp'),
                         str(upstream / 'nWiiRuntime/src/core/loader.cpp'), '-o', str(host)],
                         capture_output=True, text=True, timeout=180)
(output / 'host-build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-4000:]
report = {'result': 'PASS', 'scope': 'Analyzer/profile generation only; execution verification is separate.',
          'upstreamAnalyzerSha256': hashlib.sha256(source_path.read_bytes()).hexdigest(),
          'patchedAnalyzerSha256': hashlib.sha256(patched_path.read_bytes()).hexdigest(),
          'profileSha256': hashlib.sha256(profile_path.read_bytes()).hexdigest(),
          'driverSha256': hashlib.sha256((experiment / 'nwii_services_driver.cpp').read_bytes()).hexdigest(),
          'generatedSha256': hashlib.sha256((output / 'selected.cpp').read_bytes()).hexdigest(),
          'nativeHostSha256': hashlib.sha256(host.read_bytes()).hexdigest(),
          'hostSourceSha256': hashlib.sha256((experiment / 'services_host.cpp').read_bytes()).hexdigest(),
          'profileHeaderSha256': hashlib.sha256((experiment / 'analyzer_profile.h').read_bytes()).hexdigest(),
          'buildScriptSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'limits': ['Profile function bounds obtained from existing own-DOL dtk split; explicit table31-entry limit from original cmplwi/table evidence.',
                     'Scoped switch-table target inclusion overrides pointer-scanned known-function classification; unprofiled tables keep upstream policy.',
                     'No claims of general-game analyzer correctness, audio-service behavior, full phone or unchanged generated bodies across patched backend.']}
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')
print(analysis_stdout[-2500:])
