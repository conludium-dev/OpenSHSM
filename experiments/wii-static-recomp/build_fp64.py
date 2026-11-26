"""Apply verified FP64 bit transfers to the existing module without changing code policy."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_branch.py'
output = Path('work/private-game/static-recomp/mass-fp64')
output.mkdir(exist_ok=True)
base = Path('work/private-game/static-recomp/mass-code-write-observer')
(output / 'loader-bat-seed.h').write_bytes((base / 'loader-bat-seed.h').read_bytes())
probe_source = (experiment / 'template_copy_probe.h').read_text()
probe_source = probe_source.replace('experiment_template_copy_probe', 'experiment_fp64_template_copy_probe')
probe_source = probe_source.replace('index * 256', '(index + (ni ? 16 : 0)) * 256')
(output / 'fp64-template-probe.h').write_text(probe_source)
body = builder.read_text().replace('from branch_lowering import lower', 'from fp64_lowering import lower')
body = body.replace("base = Path('work/private-game/static-recomp/mass-l2')", "base = Path('work/private-game/static-recomp/mass-code-write-observer')")
body = body.replace("output = Path('work/private-game/static-recomp/mass-branch')", "output = Path('work/private-game/static-recomp/mass-fp64')")
body = body.replace("str(experiment / 'l2_adapter.h')", "str(experiment / 'fp64_transfer.h')")
body = body.replace("sha(experiment / 'branch_lowering.py')", "sha(experiment / 'fp64_lowering.py')")
body = body.replace("wrapper = base / 'boot-wrapper.cpp'", """wrapper = output / 'boot-wrapper.cpp'
prior = '#include "fp64-template-probe.h"\\n' + (base / 'boot-wrapper.cpp').read_text()
prior = prior.replace('int main(int argc, char** argv) {', 'int main(int argc, char** argv) {\\n    if (argc == 2 && std::string(argv[1]) == "--fp64-template-ni0") { return experiment_fp64_template_copy_probe(false); }\\n    if (argc == 2 && std::string(argv[1]) == "--fp64-template-ni1") { return experiment_fp64_template_copy_probe(true); }')
wrapper.write_text(prior)""")
body = body.replace("policy = base / 'boot-quarantine.tsv'", "policy = Path('work/private-game/static-recomp/mass-ni-guard/boot-quarantine.tsv')")
body = body.replace("str(wrapper), str(experiment / 'processor_adapter.cpp')", "'-I', str(output), str(wrapper), str(experiment / 'processor_adapter.cpp')")
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
path = output / 'lowering.json'
report = json.loads(path.read_text())
report.update({'result': 'FP64_MODULE_COMPILED_CODE_WRITE_POLICY_UNCHANGED',
               'adapterSha256': sha(experiment / 'fp64_transfer.h'), 'baseBuilderSha256': sha(builder),
               'baseProbeSha256': sha(experiment / 'template_copy_probe.h'), 'probeSha256': sha(output / 'fp64-template-probe.h'),
               'seedHeaderSha256': sha(output / 'loader-bat-seed.h')})
path.write_text(json.dumps(report, indent=2) + '\n')
boot_path = output / 'boot.json'
boot = json.loads(boot_path.read_text())
boot['loweringSha256'] = sha(path)
boot['result'] = 'FP64_MODULE_CODE_WRITE_ENDPOINT_UNVERIFIED'
boot_path.write_text(json.dumps(boot, indent=2) + '\n')
