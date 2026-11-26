"""Reuse the existing full module builder; NI mode quarantine remains closed."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_branch.py'
output = Path('work/private-game/static-recomp/mass-frsp')
output.mkdir(exist_ok=True)
base = Path('work/private-game/static-recomp/mass-spd')
(output / 'loader-bat-seed.h').write_bytes((base / 'loader-bat-seed.h').read_bytes())
body = builder.read_text().replace('from branch_lowering import lower', 'from frsp_lowering import lower')
body = body.replace("base = Path('work/private-game/static-recomp/mass-l2')", "base = Path('work/private-game/static-recomp/mass-spd')")
body = body.replace("output = Path('work/private-game/static-recomp/mass-branch')", "output = Path('work/private-game/static-recomp/mass-frsp')")
body = body.replace("str(experiment / 'l2_adapter.h')", "str(experiment / 'spd_adapter.h'), '-include', str(experiment / 'frsp_adapter.h')")
body = body.replace("sha(experiment / 'branch_lowering.py')", "sha(experiment / 'frsp_lowering.py')")
body = body.replace("wrapper = base / 'boot-wrapper.cpp'", """wrapper = output / 'boot-wrapper.cpp'
wrapper.write_text((base / 'boot-wrapper.cpp').read_text())""")
body = body.replace("policy = base / 'boot-quarantine.tsv'", "policy = Path('work/private-game/static-recomp/mass-bat/boot-quarantine.tsv')")
body = body.replace("str(wrapper), str(experiment / 'processor_adapter.cpp')", "'-I', str(output), str(wrapper), str(experiment / 'processor_adapter.cpp')")
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
path = output / 'lowering.json'
report = json.loads(path.read_text())
assert report['sites'] == 1407
assert len({change['address'] for record in report['records'] for change in record['changes']}) == 1166
report.update({'result': 'FRSP_MODULE_COMPILED_NI_QUARANTINE_RETAINED', 'adapterSha256': sha(experiment / 'frsp_adapter.h'),
               'conversionSha256': sha(experiment / 'ni_conversion.h'), 'seedHeaderSha256': sha(output / 'loader-bat-seed.h'),
               'baseBuilderSha256': sha(builder)})
path.write_text(json.dumps(report, indent=2) + '\n')
boot_path = output / 'boot.json'
boot = json.loads(boot_path.read_text())
boot['loweringSha256'] = sha(path)
boot['result'] = 'FRSP_MODULE_NI_LIVE_GATE_RETAINED'
boot_path.write_text(json.dumps(boot, indent=2) + '\n')
