"""Audit exact queued-wait integration and the next untouched refusal boundary."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-di86-boot'
output = root / 'mass-di-burst-idle-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
for verifier in ('verify_di_burst_events_dolphin.py', 'verify_di_burst_idle_guard.py'):
    subprocess.run(['python3', str(experiment / verifier)], check=True)
build = json.loads((output / 'build.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_di_burst_idle_boot.py')
assert sha(output / 'openshsm-mass-boot') == build['executableSha256']
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
assert (output / 'di_burst_idle.h').read_bytes() == (experiment / 'di_burst_idle.h').read_bytes()
for path in base.glob('*.h'):
    if path.name != 'si_external_delivery.h':
        assert path.read_bytes() == (output / path.name).read_bytes()
old = (base / 'si_external_delivery.h').read_text()
expected = old.replace('inline bool experiment_fpu_vector_active(CPUContext& context);',
    'inline bool experiment_fpu_vector_active(CPUContext& context);\n}\n#include "di_burst_idle.h"\nnamespace nwii::runtime {').replace(
    'bat_memory_read32(context, (hw::experiment_ipc_snapshot().ppcMessage | 0x80000000u) + 44) != 0x80492658',
    '(bat_memory_read32(context, (hw::experiment_ipc_snapshot().ppcMessage | 0x80000000u) + 44) != 0x80492658 && !experiment_di_burst_wait(context))')
assert (output / 'si_external_delivery.h').read_text() == expected
for name in ('boot-wrapper.cpp', 'mass_boot.cpp', 'di_device.cpp', 'fs_device.cpp', 'es_device.cpp', 'stm_device.cpp'):
    assert (base / name).read_bytes() == (output / name).read_bytes()
previous = json.loads((base / 'build.json').read_text())
assert len(build['records']) == len(previous['records']) == 125
for row, prior in zip(build['records'], previous['records']):
    assert row['file'] == prior['file'] and row['sourceSha256'] == prior['sourceSha256']
    assert sha(Path(row['source'])) == row['sourceSha256']
    assert sha(Path(row['object'])) == row['objectSha256']
    if row['file'] not in ('output_62.cpp', 'output_65.cpp', 'output_67.cpp'):
        assert row['object'] == prior['object']
live = (output / 'live-boot.log').read_text()
disabled = (output / 'disabled-boot.log').read_text()
assert 'BOOT_BOUNDARY pc=80241c30 lr=8024204c msr=30' in live
assert 'reason=IPC reply write caller/value unverified' in live
assert 'BOOT_STM submitted=32 produced=14' in live
assert 'BOOT_SI_DELIVERY entries=34 callbacks=4' in live
assert 'BOOT_BOUNDARY pc=80241c30 lr=80242384 msr=2032' in disabled
assert 'BOOT_STM submitted=30 produced=14' in disabled
assert 'DI86_SOURCE 2' not in live and 'DI86_SOURCE 3' not in live
(output / 'idle-audit.json').write_text(json.dumps({
    'result': 'QUEUED_ES_WAIT_TO_NEXT_ORIGINAL_IRQ_SENDER_PASS',
    'auditSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'),
    'liveLogSha256': sha(output / 'live-boot.log'), 'disabledLogSha256': sha(output / 'disabled-boot.log'),
    'limits': ['All125 PPC sources unchanged; three objects rebuilt with bounded guard,122 retained.',
        'Live native execution passes old idle boundary and stops BEFORE second sender MMIO.',
        'No DI86 reply/callback delivered; multi-request services and SI regression remain pending.']}, indent=2) + '\n')
print('PASS exact queued-ES guard/36 mutants/125 source hashes/122 retained objects/live IRQ sender8024204C-30/disabled baseline; NOT complete burst')
