"""Link a diagnostic observer while retaining identical write/FP/service policies."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_branch.py'
output = Path('work/private-game/static-recomp/mass-code-write-observer')
output.mkdir(exist_ok=True)
base = Path('work/private-game/static-recomp/mass-ni-guard')
(output / 'loader-bat-seed.h').write_bytes((base / 'loader-bat-seed.h').read_bytes())
body = builder.read_text().replace('from branch_lowering import lower', 'from code_write_lowering import lower')
body = body.replace("base = Path('work/private-game/static-recomp/mass-l2')", "base = Path('work/private-game/static-recomp/mass-ni-guard')")
body = body.replace("output = Path('work/private-game/static-recomp/mass-branch')", "output = Path('work/private-game/static-recomp/mass-code-write-observer')")
body = body.replace("str(experiment / 'l2_adapter.h')", "str(experiment / 'code_write_observer.h')")
body = body.replace("sha(experiment / 'branch_lowering.py')", "sha(experiment / 'code_write_lowering.py')")
body = body.replace("wrapper = base / 'boot-wrapper.cpp'", """wrapper = output / 'boot-wrapper.cpp'
wrapper.write_text((base / 'boot-wrapper.cpp').read_text())""")
body = body.replace("str(wrapper), str(experiment / 'processor_adapter.cpp')", "'-I', str(output), str(wrapper), str(experiment / 'processor_adapter.cpp')")
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
path = output / 'lowering.json'
report = json.loads(path.read_text())
assert report['sites'] == 1
report.update({'result': 'CODE_WRITE_OBSERVER_COMPILED_POLICY_UNCHANGED',
               'adapterSha256': sha(experiment / 'code_write_observer.h'), 'baseBuilderSha256': sha(builder),
               'seedHeaderSha256': sha(output / 'loader-bat-seed.h')})
path.write_text(json.dumps(report, indent=2) + '\n')
boot_path = output / 'boot.json'
boot = json.loads(boot_path.read_text())
boot['loweringSha256'] = sha(path)
boot['result'] = 'EXACT_WRITE_DIAGNOSTIC_COMPLETE_ENDPOINT_UNVERIFIED'
boot_path.write_text(json.dumps(boot, indent=2) + '\n')
