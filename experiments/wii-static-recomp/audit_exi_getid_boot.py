"""Audit GetID boot integration without accepting the unproven return as boot."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'mass-exi-getid-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
boot_path = output / 'boot.json'
boot = json.loads(boot_path.read_text())
assert boot['builderSha256'] == sha(experiment / 'build_exi_getid_boot.py')
assert boot['executableSha256'] == sha(output / 'openshsm-mass-boot')
assert boot['wrapperSha256'] == sha(output / 'boot-wrapper.cpp')
assert boot['baseWrapperSha256'] == sha(private / 'mass-exi-select-boot/boot-wrapper.cpp')
for path, digest in boot['sourceHashes'].items():
    assert sha(Path(path)) == digest
assert boot['nativeExecutionSha256'] == sha(private / 'exi-getid-native/execution.json')
assert boot['nativeProofSha256'] == sha(private / 'exi-getid-native/comparison.json')
policy = private / 'mass-ni-guard/boot-quarantine.tsv'
assert boot['policySha256'] == sha(policy)
body = (private / 'mass-exi-select-boot/boot-wrapper.cpp').read_text()
entry = '    const int result = original_boot_main(argc, argv);'
body = body.replace(entry, '''    nwii::runtime::hw::experiment_register_exi_masks(nwii::runtime::MMIODispatcher::get());
    nwii::runtime::hw::experiment_register_getid_transfer(nwii::runtime::MMIODispatcher::get());
''' + entry)
body = body.replace(entry, entry + '''
    std::cout << "BOOT_GETID_PROFILE phase=" << nwii::runtime::hw::experimentExiTransfer.phase
              << " csr=" << std::hex << nwii::runtime::hw::experimentExiMaskState[0]
              << " pi=" << nwii::runtime::hw::pi_intsr.load() << std::dec << '\\n';''')
assert (output / 'boot-wrapper.cpp').read_text() == '#include "exi_getid_frontend.h"\n' + body
subprocess.run(['python3', str(experiment / 'verify_exi_getid_native.py')], check=True)
assert boot['nativeProofSha256'] == sha(private / 'exi-getid-native/comparison.json')
replay = subprocess.run([str(output / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], capture_output=True, text=True, timeout=30)
assert replay.returncode == boot['returnCode'] == 6
assert replay.stdout == boot['stdout'] and replay.stderr == boot['stderr']
assert 'BOOT_GETID_PROFILE phase=2 csr=1008 pi=0' in replay.stdout
assert replay.stdout.count('BOOT_TRACE address=8020ecd0') == 3
assert replay.stdout.count('BOOT_TRACE address=8020dca0') == 2
assert 'BOOT_TRACE address=80211d10' in replay.stdout
assert 'BOOT_UNPROVEN_RETURN pc=80199f54' in replay.stderr
(output / 'audit.json').write_text(json.dumps({'result': 'GETID_BOOT_SOURCE_EXACT_REPLAY_UNPROVEN_RETURN_RETAINED',
    'bootSha256': sha(boot_path), 'auditorSha256': sha(Path(__file__)), 'nativeProofSha256': boot['nativeProofSha256'],
    'next': 'Investigate generated control-flow exit at80199F54 during OSRegisterVersion/OSReport formatting; no full boot acceptance.'}, indent=2) + '\n')
print('PASS GetID boot source/whole-call proof/exact replay; unproven return80199F54 retained')
