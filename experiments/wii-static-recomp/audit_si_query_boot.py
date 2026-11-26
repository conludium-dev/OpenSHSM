"""Audit the SI boot integration, retained guards and distinct clock profiles."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'mass-si-query-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_si_vector_native.py')], check=True)
path = output / 'boot.json'
build = json.loads(path.read_text())
assert build['builderSha256'] == sha(experiment / 'build_si_query_boot.py')
assert build['nativeBuildSha256'] == sha(private / 'si-vector-native/build.json')
assert build['nativeProofSha256'] == sha(private / 'si-vector-native/comparison.json')
assert build['baseBootSha256'] == sha(private / 'mass-si-idle-boot/boot.json')
assert build['frontendSha256'] == sha(experiment / 'si_query_frontend.h')
assert build['pollSha256'] == sha(experiment / 'boot_poll.h')
assert build['externalSha256'] == sha(experiment / 'si_external_delivery.h')
assert build['batMemorySha256'] == sha(experiment / 'bat_memory_frontend.h')
for source, digest in build['sourceHashes'].items():
    assert sha(Path(source)) == digest
assert len(build['records']) == 125
native_records = {row['file']: row for row in json.loads((private / 'si-vector-native/build.json').read_text())['records']}
for row in build['records']:
    assert row['sourceSha256'] == sha(Path(row['source'])) and row['objectSha256'] == sha(Path(row['object']))
    if 'transforms' in row:
        assert row['inputSource'] == native_records[row['file']]['source']
        assert row['inputSourceSha256'] == sha(Path(row['inputSource']))
        text = Path(row['inputSource']).read_text()
        for transform in row['transforms']:
            assert transform['before'] in text
            text = text.replace(transform['before'], transform['after'])
        assert text == Path(row['source']).read_text()
    else:
        assert row == native_records[row['file']]
base = private / 'mass-si-idle-boot'
for name in ('mass_boot.cpp', 'loader-bat-seed.h', 'fp64-template-probe.h', 'mutable-template-probe.h', 'hw_vi-clock.inc', 'vi-clock-backend.cpp'):
    assert (base / name).read_bytes() == (output / name).read_bytes()
wrapper = (base / 'boot-wrapper.cpp').read_text().replace('#include "si_idle_frontend.h"', '#include "si_query_frontend.h"')
wrapper = wrapper.replace('    nwii::runtime::hw::experiment_register_si_idle(nwii::runtime::MMIODispatcher::get());',
    '    nwii::runtime::hw::experiment_register_si_query(nwii::runtime::MMIODispatcher::get());\n    nwii::runtime::hw::experimentSiQuery.interruptProfile = true;')
entry = '    const int result = original_boot_main(argc, argv);'
wrapper = wrapper.replace(entry, entry + '\n    std::cout << "BOOT_SI_DELIVERY entries=" << nwii::runtime::siExternalEntries << " callbacks=" << nwii::runtime::hw::experimentSiQuery.callbackCount << "\\n";')
assert wrapper == (output / 'boot-wrapper.cpp').read_text()
exe = output / 'openshsm-mass-boot'
assert sha(exe) == build['executableSha256']
policy = private / 'mass-ni-guard/boot-quarantine.tsv'
assert sha(policy) == build['policySha256']
for mode in ('live', 'scripted'):
    recorded = build['results'][mode]
    assert recorded['returnCode'] == 7
    assert 'BOOT_SI_CONTROL raw=e0010300 written=c0010301' in recorded['stdout']
    assert 'BOOT_SI_DELIVERY entries=0 callbacks=0' in recorded['stdout']
    boundary = re.search(r'^BOOT_BOUNDARY .*$', recorded['stdout'], re.M).group()
    assert boundary == 'BOOT_BOUNDARY pc=8020e344 lr=8020e344 msr=2030 calls=2073 reason=GetID CSR device or fields unverified'
    environment = dict(os.environ)
    environment.pop('SHSM_SI_IDLE_REPLAY', None)
    if mode == 'scripted':
        environment['SHSM_SI_IDLE_REPLAY'] = '1'
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], env=environment,
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 7 and boundary in result.stdout
    if mode == 'scripted':
        assert result.stdout == recorded['stdout'] and result.stderr == recorded['stderr']
    assert 'BOOT_SI_DELIVERY entries=0 callbacks=0' in result.stdout
(output / 'audit.json').write_text(json.dumps({'result': 'SI_QUERY_BOOT2073_SCRIPTED_EXACT_LIVE_BOUNDARY_PASS',
    'buildSha256': sha(path), 'auditorSha256': sha(Path(__file__)),
    'limits': ['Boot submits the original callback-present SI packet; EE remains off and no external IRQ/callback has run before the next EXI refusal.',
        'Exact trace comparison uses the separate scripted clock fixture; live clock confirms the same boundary, not byte-exact timing.',
        'Next EXI profile remains refused; no first frame/menu/controller or complete startup claim.']}, indent=2) + '\n')
print('PASS SI boot2073: status/payload/command accepted, scripted exact replay/live boundary; next EXI guard retained')
