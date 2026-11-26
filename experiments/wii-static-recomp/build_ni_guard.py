"""Compile NI guards across the existing full module, retaining live quarantine."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_branch.py'
output = Path('work/private-game/static-recomp/mass-ni-guard')
output.mkdir(exist_ok=True)
base = Path('work/private-game/static-recomp/mass-frsp')
(output / 'loader-bat-seed.h').write_bytes((base / 'loader-bat-seed.h').read_bytes())
body = builder.read_text().replace('from branch_lowering import lower', 'from ni_guard_lowering import lower')
body = body.replace("base = Path('work/private-game/static-recomp/mass-l2')", "base = Path('work/private-game/static-recomp/mass-frsp')")
body = body.replace("output = Path('work/private-game/static-recomp/mass-branch')", "output = Path('work/private-game/static-recomp/mass-ni-guard')")
body = body.replace("str(experiment / 'l2_adapter.h')", "str(experiment / 'spd_adapter.h'), '-include', str(experiment / 'ni_guard.h')")
body = body.replace("sha(experiment / 'branch_lowering.py')", "sha(experiment / 'ni_guard_lowering.py')")
body = body.replace("wrapper = base / 'boot-wrapper.cpp'", """wrapper = output / 'boot-wrapper.cpp'
prior = '#include "ni_set_probe.h"\\n' + (base / 'boot-wrapper.cpp').read_text()
prior = prior.replace('int main(int argc, char** argv) {', 'int main(int argc, char** argv) {\\n    if (argc == 2 && std::string(argv[1]) == "--ni-set-check") { return experiment_ni_set_probe(); }')
wrapper.write_text(prior)""")
body = body.replace("policy = base / 'boot-quarantine.tsv'", "policy = Path('work/private-game/static-recomp/mass-bat/boot-quarantine.tsv')")
body = body.replace("str(wrapper), str(experiment / 'processor_adapter.cpp')", "'-I', str(output), str(wrapper), str(experiment / 'processor_adapter.cpp')")
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
path = output / 'lowering.json'
report = json.loads(path.read_text())
setters = [change for record in report['records'] for change in record['changes'] if change['kind'] == 'setter']
assert setters and {change['address'] for change in setters} == {'0x80210830'}
report.update({'result': 'NI_GUARD_MODULE_COMPILED_QUARANTINE_RETAINED',
               'adapterSha256': sha(experiment / 'ni_guard.h'), 'frspAdapterSha256': sha(experiment / 'frsp_adapter.h'),
               'probeSha256': sha(experiment / 'ni_set_probe.h'), 'seedHeaderSha256': sha(output / 'loader-bat-seed.h'),
               'baseBuilderSha256': sha(builder), 'setterSites': len(setters)})
path.write_text(json.dumps(report, indent=2) + '\n')
boot_path = output / 'boot.json'
boot = json.loads(boot_path.read_text())
boot['loweringSha256'] = sha(path)
boot['result'] = 'NI_GUARD_COMPILED_MODE_ACTIVATION_PENDING'
boot_path.write_text(json.dumps(boot, indent=2) + '\n')
