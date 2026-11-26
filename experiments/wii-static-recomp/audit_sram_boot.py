"""Audit SRAM boot advance, exact replay and the rebuilt disabled-profile regression."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'mass-sram-boot'
base = private / 'mass-si-query-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_sram_native.py')], check=True)
build_path = output / 'boot.json'
build = json.loads(build_path.read_text())
assert build['builderSha256'] == sha(experiment / 'build_sram_boot.py')
assert build['baseBootSha256'] == sha(base / 'boot.json')
assert build['nativeProofSha256'] == sha(private / 'sram-native/comparison.json')
base_build = json.loads((base / 'boot.json').read_text())
for path, digest in build['sourceHashes'].items():
    assert sha(Path(path)) == digest
for name, digest in build['headerHashes'].items():
    assert sha(experiment / name) == digest
base_records = {row['file']: row for row in base_build['records']}
assert len(build['records']) == 125
for row in build['records']:
    assert row['sourceSha256'] == sha(Path(row['source'])) and row['objectSha256'] == sha(Path(row['object']))
    if row['file'] in ('output_62.cpp', 'output_63.cpp'):
        assert row['inputSource'] == base_records[row['file']]['source']
        assert row['inputSourceSha256'] == sha(Path(row['inputSource']))
        assert Path(row['source']).read_bytes() == Path(row['inputSource']).read_bytes()
    else:
        assert row == base_records[row['file']]
for name in ('loader-bat-seed.h', 'fp64-template-probe.h', 'mutable-template-probe.h', 'hw_vi-clock.inc', 'vi-clock-backend.cpp'):
    assert (output / name).read_bytes() == (base / name).read_bytes()
entry_before = '    nwii::runtime::ProcessorContext context;\n    if (std::getenv("SHSM_SI_IDLE_REPLAY"))'
entry_after = entry_before.replace('\n    if', '\n    nwii::runtime::experiment_sram_attach_memory(context);\n    if')
assert build['entryBefore'] == entry_before and build['entryAfter'] == entry_after
assert (output / 'mass_boot.cpp').read_text() == (base / 'mass_boot.cpp').read_text().replace(entry_before, entry_after)
assert build['entrySha256'] == sha(output / 'mass_boot.cpp')
before = '    const int result = original_boot_main(argc, argv);'
after = '''    if (argc != 4 && argc != 5) { return 2; }
    if (argc == 5 && std::string(argv[4]) != "--no-sram") { return 2; }
    auto& sram = nwii::runtime::hw::experimentExiTransfer;
    std::ifstream settings(argv[3], std::ios::binary);
    if (!settings.read(reinterpret_cast<char*>(sram.sramResponse.data()), sram.sramResponse.size()) || settings.peek() != EOF) { return 4; }
    sram.sramAllowed = argc == 4;
    const int result = original_boot_main(3, argv);
    std::cout << "BOOT_SRAM phase=" << sram.phase << " address=" << std::hex << sram.dmaAddress << " length=" << sram.dmaLength << " control=" << sram.control << std::dec << "\\n";'''
assert build['wrapperBefore'] == before and build['wrapperAfter'] == after
assert (output / 'boot-wrapper.cpp').read_text() == '#include "sram_frontend.h"\n' + (base / 'boot-wrapper.cpp').read_text().replace(before, after)
exe = output / 'openshsm-mass-boot'
settings = private / 'sram-native/settings.bin'
policy = private / 'mass-ni-guard/boot-quarantine.tsv'
assert build['executableSha256'] == sha(exe) and build['settingsSha256'] == sha(settings) and build['policySha256'] == sha(policy)
for mode in ('live', 'scripted', 'disabled'):
    record = build['results'][mode]
    assert record['returnCode'] == 7
    boundary = re.search(r'^BOOT_BOUNDARY .*$', record['stdout'], re.M).group()
    if mode == 'disabled':
        assert boundary == 'BOOT_BOUNDARY pc=8020e344 lr=8020e344 msr=2030 calls=2073 reason=GetID CSR device or fields unverified'
        filtered = ''.join(line for line in record['stdout'].splitlines(True) if not line.startswith('BOOT_SRAM '))
        assert filtered == base_build['results']['scripted']['stdout'] and record['stderr'] == base_build['results']['scripted']['stderr']
    else:
        assert boundary == 'BOOT_BOUNDARY pc=80212ac0 lr=80212d04 msr=32 calls=2117 reason=BAT MMIO/locked-cache/unmapped backing access unavailable'
        assert 'BOOT_SRAM phase=2 address=80492600 length=40 control=2' in record['stdout']
        assert record['stdout'].count('BOOT_TRACE address=80219670\n') == 1
    assert 'BOOT_SI_DELIVERY entries=0 callbacks=0' in record['stdout']
    environment = dict(os.environ)
    environment.pop('SHSM_SI_IDLE_REPLAY', None)
    if mode != 'live':
        environment['SHSM_SI_IDLE_REPLAY'] = '1'
    arguments = [str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy), str(settings)]
    if mode == 'disabled':
        arguments.append('--no-sram')
    result = subprocess.run(arguments, env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 7 and boundary in result.stdout
    if mode != 'live':
        assert result.stdout == record['stdout'] and result.stderr == record['stderr']
invalid = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy), str(settings), '--invalid'], capture_output=True, text=True, timeout=30)
assert invalid.returncode == 2 and 'BOOT_BOUNDARY' not in invalid.stdout
missing = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy), str(settings) + '.missing'], capture_output=True, text=True, timeout=30)
assert missing.returncode == 4 and 'BOOT_BOUNDARY' not in missing.stdout
(output / 'audit.json').write_text(json.dumps({'result': 'SRAM_BOOT2117_SCRIPTED_EXACT_LIVE_BOUNDARY_DISABLED2073_PASS',
    'buildSha256': sha(build_path), 'auditorSha256': sha(Path(__file__)), 'nativeProofSha256': build['nativeProofSha256'],
    'limits': ['Private reference-settings adapter; not a public import/release dependency or physical Wii SRAM emulation.',
        'Next Audio-clock MMIO remains refused; source-inferred first read80212AE8→CD800180 is not an exact-access capture.',
        'Exact replay only for scripted and disabled profiles; live verifies boundary, not timing/frame.']}, indent=2) + '\n')
print('PASS SRAM boot2117 scripted exact/live boundary, disabled2073 exact regression, source125objects/invalid-input gates')
