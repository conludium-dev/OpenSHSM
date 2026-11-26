"""Integrate only the oracle-verified format table repair into guarded boot."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
proof = json.loads((private / 'format-parse/comparison.json').read_text())
assert proof['result'] == 'COMPLETE_PARSE_FORMAT126_CASES_PPC_NATIVE_PASS'
build = json.loads((private / 'format-parse/build.json').read_text())
assert proof['buildSha256'] == sha(private / 'format-parse/build.json')
assert build['objectSha256'] == sha(private / 'format-parse/output_50.cpp.o')
builder = experiment / 'build_exi_getid_boot.py'
body = builder.read_text().replace("output = private / 'mass-exi-getid-boot'", "output = private / 'mass-format-boot'")
before = "*[row['object'] for row in execution['records']]"
assert body.count(before) == 1
body = body.replace(before, "*[str(private / 'format-parse/output_50.cpp.o') if row['file'] == 'output_50.cpp' else row['object'] for row in execution['records']]")
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = private / 'mass-format-boot/boot.json'
report = json.loads(path.read_text())
report['baseBuilderSha256'] = sha(builder)
report['formatBuildSha256'] = sha(private / 'format-parse/build.json')
report['formatProofSha256'] = sha(private / 'format-parse/comparison.json')
report['formatObjectSha256'] = build['objectSha256']
report['limits'] = ['Original format table repair only; actual next guest boundary/return remains unproven, not a successful game boot.']
path.write_text(json.dumps(report, indent=2) + '\n')
