"""Link scoped mutable-data patching and stale-template execution refusal."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_branch.py'
output = Path('work/private-game/static-recomp/mass-template-patch')
output.mkdir(exist_ok=True)
base = Path('work/private-game/static-recomp/mass-fp64')
(output / 'loader-bat-seed.h').write_bytes((base / 'loader-bat-seed.h').read_bytes())
(output / 'fp64-template-probe.h').write_bytes((base / 'fp64-template-probe.h').read_bytes())
probe = (experiment / 'template_copy_probe.h').read_text()
probe = probe.replace('experiment_template_copy_probe', 'experiment_mutable_template_copy_probe')
probe = probe.replace('index * 256', '(index + (ni ? 16 : 0)) * 256')
before = '''        auto word = context.mmu.get_ptr(0x80211c08);
        for (unsigned byte = 0; byte < 4; ++byte) {
            word[byte] = value >> (24 - byte * 8);
        }'''
assert before in probe
probe = probe.replace(before, '        experiment_template_patch(context, 0x80211c08, value, 0x802119a8);')
(output / 'mutable-template-probe.h').write_text('#include "template_patch.h"\n' + probe)
body = builder.read_text().replace('from branch_lowering import lower', 'from template_patch_lowering import lower')
body = body.replace("base = Path('work/private-game/static-recomp/mass-l2')", "base = Path('work/private-game/static-recomp/mass-fp64')")
body = body.replace("output = Path('work/private-game/static-recomp/mass-branch')", "output = Path('work/private-game/static-recomp/mass-template-patch')")
body = body.replace("str(experiment / 'l2_adapter.h')", "str(experiment / 'template_patch.h')")
body = body.replace("sha(experiment / 'branch_lowering.py')", "sha(experiment / 'template_patch_lowering.py')")
body = body.replace("wrapper = base / 'boot-wrapper.cpp'", """wrapper = output / 'boot-wrapper.cpp'
prior = '#include "mutable-template-probe.h"\\n#include "template_stale_probe.h"\\n' + (base / 'boot-wrapper.cpp').read_text()
prior = prior.replace('int main(int argc, char** argv) {', 'int main(int argc, char** argv) {\\n    if (argc == 2 && std::string(argv[1]) == "--mutable-template-ni0") { return experiment_mutable_template_copy_probe(false); }\\n    if (argc == 2 && std::string(argv[1]) == "--mutable-template-ni1") { return experiment_mutable_template_copy_probe(true); }\\n    if (argc == 2 && std::string(argv[1]) == "--template-stale-check") { return experiment_template_stale_probe(); }')
wrapper.write_text(prior)""")
body = body.replace("policy = base / 'boot-quarantine.tsv'", "policy = Path('work/private-game/static-recomp/mass-ni-guard/boot-quarantine.tsv')")
body = body.replace("str(wrapper), str(experiment / 'processor_adapter.cpp')", "'-I', str(output), '-I', str(base), str(wrapper), str(experiment / 'processor_adapter.cpp')")
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
path = output / 'lowering.json'
report = json.loads(path.read_text())
patches = [change for record in report['records'] for change in record['changes'] if change['kind'] == 'patch']
guards = [change for record in report['records'] for change in record['changes'] if change['kind'] == 'execution-guard']
assert len(patches) == 1 and len({change['address'] for change in guards}) == 38
report.update({'result': 'SCOPED_TEMPLATE_PATCH_COMPILED_STALE_CODE_GUARDED',
               'adapterSha256': sha(experiment / 'template_patch.h'), 'baseBuilderSha256': sha(builder),
               'baseProbeSha256': sha(experiment / 'template_copy_probe.h'), 'probeSha256': sha(output / 'mutable-template-probe.h'),
               'fp64ProbeHeaderSha256': sha(output / 'fp64-template-probe.h'),
               'staleProbeSha256': sha(experiment / 'template_stale_probe.h'), 'seedHeaderSha256': sha(output / 'loader-bat-seed.h')})
path.write_text(json.dumps(report, indent=2) + '\n')
boot_path = output / 'boot.json'
boot = json.loads(boot_path.read_text())
boot['loweringSha256'] = sha(path)
boot['result'] = 'TEMPLATE_PATCH_LIVE_ENDPOINT_UNVERIFIED'
boot_path.write_text(json.dumps(boot, indent=2) + '\n')
