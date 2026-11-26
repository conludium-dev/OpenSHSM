"""Audit first-use exception boot advance and the disabled-profile stop."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'mass-fpu-boot'
base = private / 'mass-ai-clock-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'boot.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_fpu_boot.py')
assert build['baseBootSha256'] == sha(base / 'boot.json')
assert build['nativeBuildSha256'] == sha(private / 'fpu-first-use-native/build.json')
assert build['nativeProofSha256'] == sha(private / 'fpu-first-use-native/comparison.json')
native = json.loads((private / 'fpu-first-use-native/build.json').read_text())
assert build['records'] == native['records'] and len(build['records']) == 125
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for path, digest in build['sourceHashes'].items():
    assert sha(Path(path)) == digest
for name, digest in build['headerHashes'].items():
    assert sha(experiment / name) == digest
entry_before = (base / 'mass_boot.cpp').read_text()
assert hashlib.sha256(entry_before.encode()).hexdigest() == build['entryBeforeSha256']
entry_after = entry_before.replace('    nwii::runtime::experiment_sram_attach_memory(context);',
    '    nwii::runtime::experiment_sram_attach_memory(context);\n    context.fpuFirstUse = !std::getenv("SHSM_FPU_DISABLED");')
entry_after = entry_after.replace('        std::cout << "BOOT_REGISTERS";',
    '        std::cout << "BOOT_FPU entries=" << context.fpuEntries << " vector=" << context.exceptionVector << " resume=" << std::hex << context.fpuResume << std::dec << "\\n";\n        std::cout << "BOOT_REGISTERS";')
assert (output / 'mass_boot.cpp').read_text() == entry_after
assert sha(output / 'mass_boot.cpp') == build['entryAfterSha256']
wrapper = '#include "fpu_first_use.h"\n' + (base / 'boot-wrapper.cpp').read_text()
wrapper = wrapper.replace('    if (context.gpr[1] >= 16 && context.mmu.get_ptr(context.gpr[1] - 16)) {',
    '    if ((context.msr & 0x10) && context.gpr[1] >= 16 && context.mmu.get_ptr(context.gpr[1] - 16)) {')
assert (output / 'boot-wrapper.cpp').read_text() == wrapper
assert build['policyInputSha256'] == sha(base / 'boot-quarantine.tsv')
assert build['policySha256'] == sha(output / 'boot-quarantine.tsv')
assert build['removedPolicyEntry'] == '80211BA0\t//_unhandled\n'
assert (output / 'boot-quarantine.tsv').read_text() == (base / 'boot-quarantine.tsv').read_text().replace(build['removedPolicyEntry'], '')
exe = output / 'openshsm-mass-boot'
assert sha(exe) == build['executableSha256']
checked = {}
for mode in ('live', 'disabled'):
    environment = dict(os.environ)
    for name in ('SHSM_FPU_DISABLED', 'SHSM_AI_CLOCK_NO_BUS', 'SHSM_SI_IDLE_REPLAY'):
        environment.pop(name, None)
    if mode == 'disabled':
        environment['SHSM_FPU_DISABLED'] = '1'
    fresh = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(output / 'boot-quarantine.tsv'),
        str(private / 'sram-native/settings.bin')], env=environment, capture_output=True, text=True, timeout=30)
    assert fresh.returncode == 7 and not fresh.stderr
    for text in (fresh.stdout, build['results'][mode]['stdout']):
        boundary = re.search(r'^BOOT_BOUNDARY .*$', text, re.M).group()
        assert 'BOOT_PC_CLOCK phase=6 writes=6\n' in text
        if mode == 'live':
            assert re.fullmatch(r'BOOT_BOUNDARY pc=80212ff4 lr=80212d38 msr=2032 calls=\d+ reason=System-call service unavailable', boundary)
            assert 'BOOT_FPU entries=1 vector=0 resume=800060f4\n' in text
            assert text.count('BOOT_TRACE address=80213dc0\n') == 1
            assert text.count('BOOT_TRACE address=802135c0\n') == 1
        else:
            assert re.fullmatch(r'BOOT_BOUNDARY pc=80005f34 lr=80212d18 msr=32 calls=\d+ reason=FPU first-use CPU/instruction profile unverified', boundary)
            assert 'BOOT_FPU entries=0 vector=0 resume=0\n' in text
            assert 'BOOT_TRACE address=80213dc0\n' not in text
    checked[mode] = boundary
(output / 'audit.json').write_text(json.dumps({'result': 'FPU_ORIGINAL_HANDLER_RETRY_BOOT_ADVANCE_DISABLED_STOP_PASS',
    'buildSha256': sha(output / 'boot.json'), 'auditorSha256': sha(Path(__file__)), 'checks': checked,
    'limits': ['Live timer changes call count; no exact live trace or physical timing claim.',
        'First-use empty context/owner0 only; next system-call guard remains, no original frame/menu/audio acceptance.']}, indent=2) + '\n')
print('PASS boot original FPU handler/retry; reaches next Wii syscall guard; disabled profile retains old stop')
