"""Reuse whole-module build, preserving quarantine until reader verification completes."""
from pathlib import Path
import hashlib
import json

builder = Path('experiments/wii-static-recomp/build_branch.py')
body = builder.read_text().replace('from branch_lowering import lower', 'from timebase_lowering import lower')
body = body.replace("base = Path('work/private-game/static-recomp/mass-l2')", "base = Path('work/private-game/static-recomp/mass-carry')")
body = body.replace("output = Path('work/private-game/static-recomp/mass-branch')", "output = Path('work/private-game/static-recomp/mass-timebase')")
body = body.replace("str(experiment / 'l2_adapter.h')", "str(experiment / 'timebase_adapter.h')")
body = body.replace("sha(experiment / 'branch_lowering.py')", "sha(experiment / 'timebase_lowering.py')")
body = body.replace("wrapper = base / 'boot-wrapper.cpp'", """wrapper = output / 'boot-wrapper.cpp'
prior_wrapper = Path('work/private-game/static-recomp/mass-poll/boot-wrapper.cpp').read_text()
assert '#include "boot_poll.h"' in prior_wrapper
prior_wrapper = prior_wrapper.replace('#include "boot_poll.h"', '#include "timebase_adapter.h"\\n#include "timebase_probe.h"')
prior_wrapper = prior_wrapper.replace('#define ProcessorContext L2Context', '#define ProcessorContext ClockContext')
prior_wrapper = prior_wrapper.replace('int main(int argc, char** argv) {', 'int main(int argc, char** argv) {\\n    if (argc == 2 && std::string(argv[1]) == "--clock-check") { return experiment_clock_probe(); }')
wrapper.write_text(prior_wrapper)""")
body = body.replace("policy = base / 'boot-quarantine.tsv'", "policy = Path('work/private-game/static-recomp/mass-l2/boot-quarantine.tsv')")
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-timebase/lowering.json')
report = json.loads(path.read_text())
report['adapterSha256'] = hashlib.sha256(Path('experiments/wii-static-recomp/timebase_adapter.h').read_bytes()).hexdigest()
report['baseBuilderSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
boot_path = path.parent / 'boot.json'
boot = json.loads(boot_path.read_text())
boot['loweringSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
boot['result'] = 'TIMEBASE_QUARANTINE_RETAINED'
boot_path.write_text(json.dumps(boot, indent=2) + '\n')
