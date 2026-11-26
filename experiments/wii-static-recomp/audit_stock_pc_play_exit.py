"""Attribute an owned logged exit without treating the stale dispatch PC as an instruction PC."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct

parser = argparse.ArgumentParser()
parser.add_argument('--artifacts', type=Path, required=True)
args = parser.parse_args()
project = Path(__file__).resolve().parents[2]
root = project / 'work/private-game/static-recomp/stock-baseline'
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
artifacts = args.artifacts.resolve()
assert artifacts.parent == Path('/private/tmp') and artifacts.name.startswith('openshsm-pc-play-')
run_path = artifacts / 'result.json'
run = json.loads(run_path.read_text())
assert run['result'] == 'USER_PLAY_EXITED' and not run['deadlineEnabled']
build_path = Path(run['buildPath'])
assert sha(build_path) == run['buildSha256']
build = json.loads(build_path.read_text())
assert sha(build['executablePath']) == run['executableSha256'] == build['executableSha256']
tail_path = artifacts / 'runtime-tail.log'
tail = tail_path.read_text(errors='replace')
assert tail_path.stat().st_size == run['logTailBytes'] <= 256 * 1024
assert (artifacts / 'runtime-prefix.log').stat().st_size == run['logPrefixBytes'] <= 8 * 1024 * 1024
fatal = re.findall(r'UNIMPLEMENTED Opcode 4 \(ps_\*\) XO (\d+) XO_10 (\d+) at 0x([0-9a-f]+)', tail)
assert fatal == [('26', '26', '80071110')] and run['exitCode'] == 1
record_path = root / 'window-fp-guard/output_8.cpp.record.json'
record = json.loads(record_path.read_text())
source_path = Path(record['object']).with_suffix('')
assert sha(source_path) == record['sourceSha256']
assert sha(record['object']) == record['objectSha256']
assert build['retainedLinkInputs'][record['object']] == record['objectSha256']
source = source_path.read_text()
dispatch_pc = int(fatal[0][2], 16)
start = source.rfind('\nvoid func_', 0, source.index('loc_80071110: ;'))
end = source.find('\nvoid func_', start + 1)
body = source[start:end if end >= 0 else len(source)]
sites = []
for match in re.finditer(r'loc_([0-9A-F]{8}): ;\n    // 0x\1: ([0-9A-F]{8})\n'
        r'    stock_fp_preinstruction\([^\n]+\);\n'
        r'    std::cerr << "UNIMPLEMENTED Opcode 4 \(ps_\*\) XO " << (24|26)', body):
    sites.append({'address': int(match[1], 16), 'word': int(match[2], 16), 'xo': int(match[3])})
assert sites == [{'address': 0x80071168, 'word': 0x10400834, 'xo': 26},
    {'address': 0x8007116C, 'word': 0x13A01030, 'xo': 24}]
dol_path = project / 'work/private-game/disc/DATA/sys/main.dol'
assert sha(dol_path) == run['dolSha256']
dol = dol_path.read_bytes()
layout = struct.unpack('>64I', dol[:256])
def original_word(address):
    index = next(i for i in range(18) if layout[18 + i] <= address
        and address + 4 <= layout[18 + i] + layout[36 + i])
    return struct.unpack_from('>I', dol, layout[index] + address - layout[18 + index])[0]
assert original_word(dispatch_pc) == 0xC0FE154C
for site in sites:
    assert original_word(site['address']) == site['word']
    site['destinationFpr'] = (site['word'] >> 21) & 31
    site['sourceFpr'] = (site['word'] >> 11) & 31
    site['recordBit'] = bool(site['word'] & 1)
dependencies = {str(path): sha(path) for path in [Path(__file__).resolve(), run_path, build_path,
    tail_path, record_path, source_path, dol_path]}
report = {'result': 'OWNED_EXIT1_PAIRED_ESTIMATE_FATAL_IDENTIFIED',
    'exitCode': 1, 'loggedDispatchPc': dispatch_pc, 'loggedPcOriginalWord': original_word(dispatch_pc),
    'candidateOriginalSites': sites, 'dependencies': dependencies,
    'observed': ['Owned executable exited1 without deadline; retained tail ends in generated opcode4/XO26 fatal.',
        'Original word at logged PC is lfs, not ps_rsqrte: runtime diagnostic PC is stale.',
        'Exact retained compiled source function contains only this ps_rsqrte fatal and following ps_res fatal.'],
    'limits': ['Static attribution of the exact instruction site, not a captured instruction-level register trace.',
        'No CPU instruction implementation or crash fix yet; operand lanes/FPSCR/edge cases need verification.',
        'This does not explain white intro or intermittent lower-half graphics corruption.',
        'Interpreter op31/XO55 also repeats in tail and remains a separate unresolved instruction issue.']}
path = artifacts / 'exit-audit.json'
assert not path.exists(), 'Preserve previous audit evidence.'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
