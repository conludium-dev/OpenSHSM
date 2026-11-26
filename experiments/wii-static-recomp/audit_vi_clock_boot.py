"""Audit the measured VI clock extension and exact next SI store refusal."""
from pathlib import Path
import hashlib
import json
import subprocess
import struct

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'mass-vi-clock-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'audit_uart_boot.py')], check=True)
subprocess.run(['python3', str(experiment / 'verify_vi_clock_dolphin.py')], check=True)
boot_path = output / 'boot.json'
boot = json.loads(boot_path.read_text())
base = json.loads((private / 'mass-uart-boot/boot.json').read_text())
assert boot['builderSha256'] == sha(experiment / 'build_vi_clock_boot.py')
assert boot['executableSha256'] == sha(output / 'openshsm-mass-boot')
assert boot['wrapperSha256'] == sha(output / 'boot-wrapper.cpp')
assert boot['canonicalEntrySha256'] == base['canonicalEntrySha256']
assert (output / 'mass_boot.cpp').read_bytes() == (private / 'mass-uart-boot/mass_boot.cpp').read_bytes()
assert boot['entrySourceSha256'] == sha(output / 'mass_boot.cpp')
assert boot['generatedDispatcherSourceSha256'] == sha(private / 'mass-current/main_output.cpp')
assert boot['functionCallBudget'] == 20000
for key in ('nativeExecutionSha256', 'nativeProofSha256', 'uartProofSha256', 'backendSha256', 'policySha256', 'baseWrapperSha256', 'baseBuilderSha256'):
    assert boot[key] == base[key]
for path, digest in boot['sourceHashes'].items():
    assert sha(Path(path)) == digest
expected_wrapper = (private / 'mass-uart-boot/boot-wrapper.cpp').read_text().replace(
    '    nwii::runtime::hw::experimentExiTransfer.uartAllowed = true;\n',
    '    nwii::runtime::hw::experimentExiTransfer.uartAllowed = true;\n    nwii::runtime::hw::register_vi(nwii::runtime::MMIODispatcher::get());\n')
assert (output / 'boot-wrapper.cpp').read_text() == expected_wrapper
vi = boot['viClock']
assert vi['baseBuilderSha256'] == sha(experiment / 'build_uart_boot.py')
assert vi['originalProofSha256'] == sha(private / 'dolphin-vi-clock/comparison.json')
vendor = Path(vi['vendorSource'])
assert vi['vendorSha256'] == sha(vendor)
assert vi['generatedSha256'] == sha(output / 'hw_vi-clock.inc')
assert vendor.read_text().count(vi['before']) == 1
assert (output / 'hw_vi-clock.inc').read_text() == vendor.read_text().replace(vi['before'], vi['after'])
assert vi['backendSha256'] == sha(output / 'vi-clock-backend.cpp')
observer = boot['observer']
assert observer['headerSha256'] == sha(experiment / 'vi_clock_frontend.h')
assert observer['inputSha256'] == sha(Path(observer['inputSource']))
expected_source = Path(observer['inputSource']).read_text()
for change in vi['sourceTransforms']:
    assert expected_source.count(change['before']) == change['sites']
    expected_source = expected_source.replace(change['before'], change['after'])
assert expected_source.count(observer['before']) == observer['sites'] == 2
expected_source = expected_source.replace(observer['before'], observer['after'])
assert (output / 'output_63.cpp').read_text() == expected_source
assert observer['sourceSha256'] == sha(output / 'output_63.cpp')
assert observer['objectSha256'] == sha(output / 'output_63.cpp.o')
execution = json.loads((private / 'exi-getid-native/execution.json').read_text())
assert len(execution['records']) == 125
for row in execution['records']:
    assert sha(Path(row['source'])) == row['sourceSha256']
    assert sha(Path(row['object'])) == row['objectSha256']
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
layout = struct.unpack('>64I', dol[:256])
address = 0x8020feec
section = next(i for i in range(7) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == 0x93e46430
policy = private / 'mass-ni-guard/boot-quarantine.tsv'
replay = subprocess.run([str(output / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], capture_output=True, text=True, timeout=30)
assert replay.returncode == boot['returnCode'] == 7
assert replay.stdout == boot['stdout'] and replay.stderr == boot['stderr']
boundary = 'BOOT_BOUNDARY pc=8020fed0 lr=8020fed0 msr=2030 calls=1944 reason=BAT MMIO/locked-cache/unmapped backing access unavailable; memory instruction=8020feec address=cd006430 length=4 write value=1ec0200 physical=d006430 wimg=5 slot=1'
assert boundary in replay.stdout
original = json.loads((private / 'dolphin-vi-clock/comparison.json').read_text())['values'][0]
assert original['rate'] == 0 and original['tableAddress'] == 0x8042b718
assert replay.stdout.count('VI_CLOCK_PROVEN_READ instruction=80210620 address=cc00206c value=1') == 1
assert replay.stdout.count('VI_SAMPLING_ARGS x=' + str(original['x']) + ' y=' + str(original['y'])) == 1
assert original['x'] << 16 | original['y'] << 8 == 0x1ec0200
assert 'BOOT_TRACE address=8020feb0' in replay.stdout
assert 'BOOT_GETID_PROFILE phase=6 csr=1008 pi=0' in replay.stdout
(output / 'audit.json').write_text(json.dumps({'result': 'VI_CLOCK_BOOT1944_EXACT_REPLAY_SI_STORE_REFUSED',
    'bootSha256': sha(boot_path), 'auditorSha256': sha(Path(__file__)), 'originalProofSha256': vi['originalProofSha256'],
    'next': {'instruction': '0x8020feec', 'address': '0xcd006430', 'width': 4, 'operation': 'write', 'value': '0x01ec0200'},
    'limits': boot['limits']}, indent=2) + '\n')
print('PASS existing VI clock callback extension; original NTSC0 sampling arguments;125objects/exact1944-call replay; SI store refused')
