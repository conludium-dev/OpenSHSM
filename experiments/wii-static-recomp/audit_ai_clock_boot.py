"""Check the scoped clock boot profile, disabled regression and missing-bus failure."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'mass-ai-clock-boot'
base = private / 'mass-sram-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'boot.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_ai_clock_boot.py')
assert build['baseBootSha256'] == sha(base / 'boot.json')
native_proof_path = private / 'ai-clock-native/comparison.json'
assert build['nativeProofSha256'] == sha(native_proof_path), 'Native live proof changed; rebuild boot against the current proof first'
assert json.loads(native_proof_path.read_text())['result'] == 'COMPILED_AI_CLOCK16_ORIGINAL_COMMANDS_ABI_WAITS_PC_STUB_PROFILE_MATCH'
assert build['profileSha256'] == sha(experiment / 'ai_clock_profile.h')
for path, digest in build['sourceHashes'].items():
    assert sha(Path(path)) == digest
base_build = json.loads((base / 'boot.json').read_text())
base_records = {row['file']: row for row in base_build['records']}
assert len(build['records']) == 125
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256']
    assert sha(Path(row['object'])) == row['objectSha256']
    if row['file'] == 'output_63.cpp':
        assert row['inputSourceSha256'] == base_records[row['file']]['sourceSha256']
        assert row['after'] == row['before'].replace('experiment_si_query_read32(', 'experiment_ai_clock_read32(').replace('experiment_si_query_write32(', 'experiment_ai_clock_write32(')
        original = Path(row['inputSource']).read_text()
        assert original.count(row['before']) == 1
        assert Path(row['source']).read_text() == original.replace(row['before'], row['after'])
    else:
        assert row == base_records[row['file']]
policy_input = Path(build['policyInput'])
policy = output / 'boot-quarantine.tsv'
assert sha(policy_input) == build['policyInputSha256']
assert sha(policy) == build['policySha256']
assert build['removedPolicyEntry'] == '8021C020\tUNVERIFIED_PROCESSOR_REGISTER_268\n'
assert policy.read_text() == policy_input.read_text().replace(build['removedPolicyEntry'], '')
assert sha(base / 'mass_boot.cpp') == build['entryBeforeSha256']
assert sha(output / 'mass_boot.cpp') == build['entryAfterSha256']
marker = '    context.pc = executable.entry_point;'
seed = '    if (nwii::runtime::hw::experimentPcClock.enabled && !std::getenv("SHSM_AI_CLOCK_NO_BUS")) {\n        context.mmu.write32(0xf8, 243000000);\n    }\n'
assert (output / 'mass_boot.cpp').read_text() == (base / 'mass_boot.cpp').read_text().replace(marker, seed + marker)
exe = output / 'openshsm-mass-boot'
settings = private / 'sram-native/settings.bin'
assert sha(exe) == build['executableSha256'] and sha(settings) == build['settingsSha256']
checked = {}
for mode in ('live', 'disabled', 'missing-bus'):
    environment = dict(os.environ)
    environment.pop('SHSM_SI_IDLE_REPLAY', None)
    environment.pop('SHSM_AI_CLOCK_NO_BUS', None)
    args = [str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy), str(settings)]
    if mode == 'disabled':
        environment['SHSM_SI_IDLE_REPLAY'] = '1'
        args.append('--no-clock')
    if mode == 'missing-bus':
        environment['SHSM_AI_CLOCK_NO_BUS'] = '1'
    fresh = subprocess.run(args, env=environment, capture_output=True, text=True, timeout=30)
    assert fresh.returncode == 7 and not fresh.stderr
    for text in (fresh.stdout, build['results'][mode]['stdout']):
        boundary = re.search(r'^BOOT_BOUNDARY .*$', text, re.M).group()
        assert 'BOOT_SRAM phase=2 address=80492600 length=40 control=2\n' in text
        if mode == 'live':
            assert re.fullmatch(r'BOOT_BOUNDARY pc=80005f34 lr=80212d18 msr=32 calls=\d+ reason=FP64 opcode/FP availability/exception profile unavailable', boundary)
            assert 'BOOT_PC_CLOCK phase=6 writes=6\n' in text
            assert text.count('BOOT_TRACE address=802129e0\n') == 1
        elif mode == 'missing-bus':
            assert boundary == 'BOOT_BOUNDARY pc=8021c020 lr=80212b20 msr=32 calls=20001 reason=Function-call budget exceeded'
            assert 'BOOT_PC_CLOCK phase=2 writes=2\n' in text
        else:
            filtered = ''.join(line for line in text.splitlines(True) if not line.startswith('BOOT_PC_CLOCK '))
            filtered = filtered.replace('PC clock profile caller/mapping unverified', 'BAT MMIO/locked-cache/unmapped backing access unavailable')
            assert filtered == base_build['results']['scripted']['stdout']
    checked[mode] = {'returnCode': fresh.returncode, 'boundary': boundary}
(output / 'audit.json').write_text(json.dumps({'result': 'PC_CLOCK_BOOT_ADVANCE_DISABLED_REPLAY_MISSING_BUS_REFUSAL_PASS',
    'buildSha256': sha(output / 'boot.json'), 'auditorSha256': sha(Path(__file__)), 'checks': checked,
    'limits': ['Prepared loader bus frequency and Dolphin zero/no-op register profile are PC adaptations.',
        'No exact live timing/trace, physical PLL, audible audio or first frame/menu proof.']}, indent=2) + '\n')
print('PASS clock boot returns past six writes; disabled exact replay; missing bus retains timed-loop budget refusal')
