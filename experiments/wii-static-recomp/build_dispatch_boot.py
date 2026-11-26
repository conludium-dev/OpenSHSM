"""Use the existing generated dispatcher instead of one direct entry call."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'mass-dispatch-boot'
output.mkdir(exist_ok=True)
canonical = experiment / 'mass_boot.cpp'
entry = canonical.read_text()
assert entry.count('        func_80006310(context);') == 1
entry = entry.replace('        func_80006310(context);', '        run_game(context);')
entry = 'extern "C" void run_game(nwii::runtime::CPUContext&);\n' + entry
(output / 'mass_boot.cpp').write_text(entry)
builder = experiment / 'build_exi_getid_boot.py'
body = builder.read_text().replace("output = private / 'mass-exi-getid-boot'", "output = private / 'mass-dispatch-boot'")
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
path = output / 'boot.json'
report = json.loads(path.read_text())
report['result'] = 'EXISTING_MODULE_DISPATCH_BOOT_NEXT_GUARD_RETAINED'
report['baseBuilderSha256'] = sha(builder)
report['canonicalEntrySha256'] = sha(canonical)
report['entrySourceSha256'] = sha(output / 'mass_boot.cpp')
report['generatedDispatcherSourceSha256'] = sha(private / 'mass-current/main_output.cpp')
report['limits'] = ['Existing125-object module dispatcher; no parse-table repair object linked.',
                    'Interpreter/callback/MMIO guards stay active; no idle-EE/pending delivery/full boot acceptance.']
path.write_text(json.dumps(report, indent=2) + '\n')
