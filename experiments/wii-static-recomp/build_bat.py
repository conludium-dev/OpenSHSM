"""Build the complete module on the same MMU/cache with observed loader BAT inputs."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/mass-bat')
output.mkdir(exist_ok=True)
subprocess.run(['python3', str(experiment / 'verify_bat_seed.py')], check=True)
seed_path = Path('work/private-game/static-recomp/dolphin-bat-seed/seed.json')
seed = json.loads(seed_path.read_text())
seed_header = output / 'loader-bat-seed.h'
text = '#pragma once\n#include "bat_memory_frontend.h"\nnamespace nwii::runtime {\nstruct SeededBatContext : BatContext {\n    SeededBatContext() {\n'
text += f'        hid4 = 0x{seed["hid4"]:08x};\n'
for bank in ('ibat', 'dbat'):
    text += '        ' + bank + ' = {' + ', '.join(f'BatPair{{0x{upper:08x}, 0x{lower:08x}}}' for upper, lower in seed[bank]) + '};\n'
text += '    }\n};\n}\n'
seed_header.write_text(text)
builder = experiment / 'build_branch.py'
body = builder.read_text().replace('from branch_lowering import lower', 'from bat_lowering import lower')
body = body.replace("base = Path('work/private-game/static-recomp/mass-l2')", "base = Path('work/private-game/static-recomp/mass-performance')")
body = body.replace("output = Path('work/private-game/static-recomp/mass-branch')", "output = Path('work/private-game/static-recomp/mass-bat')")
body = body.replace("str(experiment / 'l2_adapter.h')", "str(experiment / 'bat_memory_frontend.h')")
body = body.replace("sha(experiment / 'branch_lowering.py')", "sha(experiment / 'bat_lowering.py')")
body = body.replace("wrapper = base / 'boot-wrapper.cpp'", """wrapper = output / 'boot-wrapper.cpp'
prior = (base / 'boot-wrapper.cpp').read_text()
prior = '#include "loader-bat-seed.h"\\n' + prior
prior = '#include "bat_hid4_probe.h"\\n' + prior
prior = prior.replace('#define ProcessorContext PerformanceContext', '#define ProcessorContext SeededBatContext')
prior = prior.replace('int main(int argc, char** argv) {', 'int main(int argc, char** argv) {\\n    if (argc == 2 && std::string(argv[1]) == "--bat-hid4-check") { return experiment_bat_hid4_probe(); }')
prior = prior.replace('const uint32_t physical = virtualAddress & 0x3fffffffu;', 'const uint32_t physical = bat_memory_range(context, virtualAddress, 1).physical;')
prior = prior.replace('memory_cached(context, virtualAddress)', 'bat_memory_cached(context, bat_memory_range(context, virtualAddress, 1))')
wrapper.write_text(prior)""")
body = body.replace("policy = base / 'boot-quarantine.tsv'", "policy = Path('work/private-game/static-recomp/mass-performance/boot-quarantine.tsv')")
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
path = output / 'lowering.json'
report = json.loads(path.read_text())
report.update({'result': 'FULL_BAT_MODULE_COMPILED_EXECUTION_UNVERIFIED', 'seedProofSha256': sha(seed_path),
               'seedHeaderSha256': sha(seed_header), 'baseBuilderSha256': sha(builder),
               'contextSha256': sha(experiment / 'bat_context.h'), 'frontendSha256': sha(experiment / 'bat_memory_frontend.h'),
               'resolverSha256': sha(experiment / 'bat_translation.h'),
               'probeSha256': sha(experiment / 'bat_hid4_probe.h'),
               'rotateLowererSha256': sha(experiment / 'rotate_record_lowering.py'),
               'rotateRecordSites': sum(change['kind'] == 'rotate-record' for record in report['records'] for change in record['changes']),
               'memoryRoutingLines': sum(change['sites'] for record in report['records'] for change in record['changes'] if change['kind'] == 'memory'),
               'registerSites': sum(change['kind'] == 'register' for record in report['records'] for change in record['changes'])})
path.write_text(json.dumps(report, indent=2) + '\n')
boot_path = output / 'boot.json'
boot = json.loads(boot_path.read_text())
boot['loweringSha256'] = sha(path)
boot['result'] = 'BAT_ROUTED_LIVE_ENDPOINT_UNVERIFIED_HID4_QUARANTINE_RETAINED'
boot_path.write_text(json.dumps(boot, indent=2) + '\n')
print('BAT full module:', report['memoryRoutingLines'], 'memory lines;', report['registerSites'], 'original register sites; HID4 gate retained')
