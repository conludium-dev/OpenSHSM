"""Audit cache-flush syscall boot advance and disabled-profile boundary."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'mass-flush-syscall-boot'
base = private / 'mass-fpu-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'boot.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_flush_syscall_boot.py')
assert build['parentBuilderSha256'] == sha(experiment / 'build_fpu_boot.py')
assert build['baseBootSha256'] == sha(base / 'boot.json')
assert build['nativeBuildSha256'] == sha(private / 'flush-syscall-native/build.json')
assert build['nativeProofSha256'] == sha(private / 'flush-syscall-native/comparison.json')
native = json.loads((private / 'flush-syscall-native/build.json').read_text())
assert build['records'] == native['records'] and len(build['records']) == 125
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
entry = (base / 'mass_boot.cpp').read_text()
assert hashlib.sha256(entry.encode()).hexdigest() == build['entryBeforeSha256']
marker = '    nwii::runtime::experiment_sram_attach_memory(context);'
entry = entry.replace(marker, marker + '\n    context.flushSyscall = !std::getenv("SHSM_FLUSH_DISABLED");')
marker = '        std::cout << "BOOT_REGISTERS";'
entry = entry.replace(marker, '        std::cout << "BOOT_FLUSH entries=" << context.flushEntries << " phase=" << context.flushPhase << " barriers=" << std::hex << context.flushBarriers << std::dec << "\\n";\n' + marker)
assert (output / 'mass_boot.cpp').read_text() == entry and sha(output / 'mass_boot.cpp') == build['entryAfterSha256']
assert (output / 'boot-wrapper.cpp').read_text() == '#include "flush_syscall.h"\n' + (base / 'boot-wrapper.cpp').read_text()
assert build['removedPolicyEntry'] == ''
assert sha(output / 'boot-quarantine.tsv') == build['policySha256'] == build['policyInputSha256'] == sha(base / 'boot-quarantine.tsv')
exe = output / 'openshsm-mass-boot'
assert sha(exe) == build['executableSha256']
checked = {}
for mode in ('live', 'disabled'):
    environment = dict(os.environ)
    for name in ('SHSM_FPU_DISABLED', 'SHSM_FLUSH_DISABLED', 'SHSM_AI_CLOCK_NO_BUS', 'SHSM_SI_IDLE_REPLAY'):
        environment.pop(name, None)
    if mode == 'disabled':
        environment['SHSM_FLUSH_DISABLED'] = '1'
    fresh = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(output / 'boot-quarantine.tsv'),
        str(private / 'sram-native/settings.bin')], env=environment, capture_output=True, text=True, timeout=30)
    assert fresh.returncode == 7 and not fresh.stderr
    for text in (fresh.stdout, build['results'][mode]['stdout']):
        boundary = re.search(r'^BOOT_BOUNDARY .*$', text, re.M).group()
        assert 'BOOT_PC_CLOCK phase=6 writes=6\n' in text
        assert 'BOOT_FPU entries=1 vector=0 resume=800060f4\n' in text
        if mode == 'live':
            assert re.fullmatch(r'BOOT_BOUNDARY pc=80212d38 lr=80212d38 msr=2032 calls=\d+ reason=BAT MMIO/locked-cache/unmapped backing access unavailable', boundary)
            assert 'BOOT_FLUSH entries=1 phase=0 barriers=1\n' in text
            assert text.count('BOOT_TRACE address=8021a120\n') == 1
        else:
            assert re.fullmatch(r'BOOT_BOUNDARY pc=80212ff4 lr=80212d38 msr=2032 calls=\d+ reason=Flush syscall CPU/site/profile unverified', boundary)
            assert 'BOOT_FLUSH entries=0 phase=0 barriers=0\n' in text
            assert 'BOOT_TRACE address=8021a120\n' not in text
    checked[mode] = boundary
(output / 'audit.json').write_text(json.dumps({'result': 'FLUSH_SYSCALL_ORIGINAL_VECTOR_BOOT_ADVANCE_DISABLED_STOP_PASS',
    'buildSha256': sha(output / 'boot.json'), 'auditorSha256': sha(Path(__file__)), 'checks': checked,
    'limits': ['Live call counts vary; no exact live trace/timing proof. Next MMIO refusal retained.',
        'Synchronous model cache writeback/host fence are PC adaptations, not physical bus ordering or original frame/menu/audio proof.']}, indent=2) + '\n')
print('PASS boot original flush syscall/vector/rfi; next MMIO guard retained; disabled profile preserves syscall stop')
