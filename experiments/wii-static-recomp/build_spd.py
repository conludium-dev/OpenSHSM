"""Incremental SPD writer extension; keep old modules and public runtime unchanged."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/mass-spd')
output.mkdir(exist_ok=True)
base = Path('work/private-game/static-recomp/mass-bat')
(output / 'loader-bat-seed.h').write_bytes((base / 'loader-bat-seed.h').read_bytes())
builder = experiment / 'build_branch.py'
body = builder.read_text().replace('from branch_lowering import lower', 'from spd_lowering import lower')
body = body.replace("base = Path('work/private-game/static-recomp/mass-l2')", "base = Path('work/private-game/static-recomp/mass-bat')")
body = body.replace("output = Path('work/private-game/static-recomp/mass-branch')", "output = Path('work/private-game/static-recomp/mass-spd')")
body = body.replace("str(experiment / 'l2_adapter.h')", "str(experiment / 'spd_adapter.h')")
body = body.replace("sha(experiment / 'branch_lowering.py')", "sha(experiment / 'spd_lowering.py')")
body = body.replace("wrapper = base / 'boot-wrapper.cpp'", """wrapper = output / 'boot-wrapper.cpp'
prior = '#include "spd_probe.h"\\n' + (base / 'boot-wrapper.cpp').read_text()
prior = prior.replace('int main(int argc, char** argv) {', 'int main(int argc, char** argv) {\\n    if (argc == 2 && std::string(argv[1]) == "--spd-check") { return experiment_spd_probe(); }')
wrapper.write_text(prior)""")
body = body.replace("str(wrapper), str(experiment / 'processor_adapter.cpp')", "'-I', str(output), str(wrapper), str(experiment / 'processor_adapter.cpp')")
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
path = output / 'lowering.json'
report = json.loads(path.read_text())
assert report['sites'] == 7
report.update({'result': 'SPD_COMPILED_ORIGINAL_COMPARISON_PENDING', 'adapterSha256': sha(experiment / 'spd_adapter.h'),
               'probeSha256': sha(experiment / 'spd_probe.h'), 'seedHeaderSha256': sha(output / 'loader-bat-seed.h'),
               'baseBuilderSha256': sha(builder)})
path.write_text(json.dumps(report, indent=2) + '\n')
boot_path = output / 'boot.json'
boot = json.loads(boot_path.read_text())
boot['loweringSha256'] = sha(path)
boot['result'] = 'SPD_BOOT_ENDPOINT_UNVERIFIED'
boot_path.write_text(json.dumps(boot, indent=2) + '\n')
