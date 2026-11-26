"""Execute original IPC store in an isolated fixture; prove ordinary boot remains guarded."""
from pathlib import Path
import hashlib
import json
import subprocess
from ipc_reset_lowering import lower

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base, output = private / 'mass-pi-mask', private / 'mass-ipc-reset-fixture'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_ipc_reset_backend.py')], check=True)
metadata = json.loads((base / 'lowering.json').read_text())
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['sites'] == 1 and lowering['baseLoweringSha256'] == sha(base / 'lowering.json')
for key, name in [('scriptSha256', 'build_ipc_reset_fixture.py'), ('lowererSha256', 'ipc_reset_lowering.py'), ('baseBuilderSha256', 'build_branch.py')]:
    assert lowering[key] == sha(experiment / name)
for name, digest in lowering['helperSha256'].items():
    assert digest == sha(experiment / name)
for name, digest in lowering['privateHeaderSha256'].items():
    assert digest == sha(output / name) == sha(base / name)
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
assert lowering['vendorIpcSha256'] == sha(upstream / 'src/hw/hw_ipc.cpp')
for name, digest in metadata['vendorSourceSha256'].items():
    assert digest == sha(upstream / name)
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert len(metadata['records']) == len(lowering['records']) == 125
for old, record in zip(metadata['records'], lowering['records']):
    source = Path(old['directory']) / old['file']
    assert sha(source) == old['sourceSha256'] and old['file'] == record['file']
    expected, changes = lower(source.read_text(), original)
    target = Path(record['directory']) / record['file']
    assert target.read_text() == expected and changes == record['changes']
    assert sha(target) == record['sourceSha256'] and sha(Path(str(target) + '.o')) == record['objectSha256']
boot = json.loads((output / 'boot.json').read_text())
exe, policy = output / 'openshsm-mass-boot', private / 'mass-ni-guard/boot-quarantine.tsv'
assert boot['executableSha256'] == sha(exe) and boot['wrapperSha256'] == sha(output / 'boot-wrapper.cpp')
assert boot['loweringSha256'] == sha(output / 'lowering.json') and boot['policySha256'] == sha(policy)
main = 'int main(int argc, char** argv) {'
new_main = main + '\n    if (argc == 2 && std::string(argv[1]) == "--ipc-reset-isolated") { return experiment_ipc_reset_instruction_probe(); }'
assert (output / 'boot-wrapper.cpp').read_text() == '#include "ipc_reset_instruction_probe.h"\n' + (base / 'boot-wrapper.cpp').read_text().replace(main, new_main)
oracle_path = private / 'dolphin-ipc-reset/comparison.json'
oracle = json.loads(oracle_path.read_text())
selected = [row for row in oracle['observations'] if row['requestedMask'] == 0x40000000]
native = subprocess.run([str(exe), '--ipc-reset-isolated'], capture_output=True, text=True, timeout=30)
assert native.returncode == 0, (native.returncode, native.stdout, native.stderr)
(output / 'native-instruction.log').write_text(native.stdout + native.stderr)
rows = [list(map(int, line.split()[1:])) for line in native.stdout.splitlines() if line.startswith('IPC_INSTRUCTION_CASE ')]
assert len(rows) == len(selected) == 8
for native_row, row in zip(rows, selected):
    index, control, message, fpscr, cause = native_row
    assert index == selected.index(row) and control == row['controlAfter'] and message == row['armMessageAfter']
    assert fpscr == row['fpscr'] and cause == row['causeAfter'] == 0x10000
stale = subprocess.run([str(exe), '--template-stale-check'], capture_output=True, text=True, timeout=30)
assert stale.returncode == 0 and stale.stdout == 'TEMPLATE_STALE_GUARDS 38\n'
prefix = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(private / 'mass-l2/boot-quarantine.tsv')], capture_output=True, text=True, timeout=30)
assert prefix.returncode == 7 and prefix.stdout == json.loads((private / 'mass-timebase/boot.json').read_text())['stdout']
live = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], capture_output=True, text=True, timeout=30)
assert live.returncode == 7 and live.stdout == boot['stdout'] == json.loads((base / 'boot.json').read_text())['stdout']
(output / 'live-replay.log').write_text(live.stdout + live.stderr)
report = {'result': 'ORIGINAL_IPC_STORE8_ISOLATED_CASES_MATCH_ORDINARY_BOOT_REFUSAL_UNCHANGED',
          'originalInstructionCases': 8, 'compiledStaleEntryRefusals': 38,
          'oracleSha256': sha(oracle_path), 'loweringSha256': sha(output / 'lowering.json'), 'bootSha256': sha(output / 'boot.json'),
          'backendProofSha256': sha(private / 'ipc-reset-backend/comparison.json'), 'verifierSha256': sha(Path(__file__)),
          'limits': ['One original PPC store executed via validated frontend/cache/BAT context and same vendor register storage.',
                     'Synthetic native fixture exits after store; not full original enclosing function/OS execution.',
                     'Live fixture flag false delegates unchanged refused writer; no IPC reset activation.',
                     'IOS queues/events/GPIO/device reset/nonquiescent semantics/full original boot remain unverified.']}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS originalIPCstore8isolatedcases/38staleentries/pretime; ordinarybootIPCrefusalunchanged')
