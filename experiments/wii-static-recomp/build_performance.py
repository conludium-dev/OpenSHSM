"""Reuse the full module builder; keep live policy until native comparison passes."""
from pathlib import Path
import hashlib
import json

builder = Path('experiments/wii-static-recomp/build_branch.py')
body = builder.read_text().replace('from branch_lowering import lower', 'from performance_lowering import lower')
body = body.replace("base = Path('work/private-game/static-recomp/mass-l2')", "base = Path('work/private-game/static-recomp/mass-timebase')")
body = body.replace("output = Path('work/private-game/static-recomp/mass-branch')", "output = Path('work/private-game/static-recomp/mass-performance')")
body = body.replace("str(experiment / 'l2_adapter.h')", "str(experiment / 'performance_adapter.h')")
body = body.replace("sha(experiment / 'branch_lowering.py')", "sha(experiment / 'performance_lowering.py')")
body = body.replace("wrapper = base / 'boot-wrapper.cpp'", """wrapper = output / 'boot-wrapper.cpp'
prior = (base / 'boot-wrapper.cpp').read_text()
prior = prior.replace('#include "timebase_probe.h"', '#include "timebase_probe.h"\\n#include "performance_probe.h"')
prior = prior.replace('#define ProcessorContext ClockContext', '#define ProcessorContext PerformanceContext')
prior = prior.replace('int main(int argc, char** argv) {', 'int main(int argc, char** argv) {\\n    if (argc == 2 && std::string(argv[1]) == "--performance-check") { return experiment_performance_probe(); }')
wrapper.write_text(prior)""")
body = body.replace("policy = base / 'boot-quarantine.tsv'", "policy = Path('work/private-game/static-recomp/mass-timebase-active/boot-quarantine.tsv')")
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-performance')
path = output / 'lowering.json'
report = json.loads(path.read_text())
assert report['sites'] == 6
report.update({'result': 'PERFORMANCE_RESET_COMPILED_QUARANTINE_RETAINED',
               'adapterSha256': hashlib.sha256(Path('experiments/wii-static-recomp/performance_adapter.h').read_bytes()).hexdigest(),
               'probeSha256': hashlib.sha256(Path('experiments/wii-static-recomp/performance_probe.h').read_bytes()).hexdigest(),
               'baseBuilderSha256': hashlib.sha256(builder.read_bytes()).hexdigest()})
path.write_text(json.dumps(report, indent=2) + '\n')
boot_path = output / 'boot.json'
boot = json.loads(boot_path.read_text())
boot['loweringSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
boot['result'] = 'PERFORMANCE_RESET_QUARANTINE_RETAINED'
boot_path.write_text(json.dumps(boot, indent=2) + '\n')
