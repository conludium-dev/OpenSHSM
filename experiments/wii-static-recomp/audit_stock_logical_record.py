"""Execute byte-checked regenerated logical-record statements with adversarial stale CR0."""
from pathlib import Path
import hashlib
import json
import re
import shlex
import subprocess
import argparse
from stock_psq_patch import lower_indexed
from stock_byte_reverse_patch import lower_byte_reverse
from stock_logical_record_patch import lower_logical_record, pattern

parser = argparse.ArgumentParser()
parser.add_argument('--optimized', action='store_true')
parser.add_argument('--run-label', default='window-logical-record-headless-windowed-logical40')
parser.add_argument('--capture-index', type=int, default=1800)
parser.add_argument('--tag', default='logical40')
args = parser.parse_args()
assert re.fullmatch(r'[a-z0-9-]{1,100}', args.run_label)
assert re.fullmatch(r'[a-z0-9-]{1,40}', args.tag)
assert 300 <= args.capture_index <= 6000 and args.capture_index % 300 == 0

project = Path('.').resolve()
root = project / 'work/private-game/static-recomp/stock-baseline'
variant = 'window-optimized' if args.optimized else 'window-logical-record'
exe_name = 'OpenSHSMStockOptimized' if args.optimized else 'OpenSHSMStockLogicalRecord'
output = root / variant
build = root / 'export/build'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest = json.loads((output / 'build.json').read_text())
dol = (project / 'work/private-game/disc/DATA/sys/main.dol').read_bytes()
functions, entries = [], []
for module in manifest['modules']:
    original = root / 'export' / f'output_{module["index"]}.cpp'
    text, _ = lower_indexed(original.read_text(), dol)
    text, _ = lower_byte_reverse(text, dol)
    corrected, sites = lower_logical_record(text, dol)
    assert sites == module['logicalSites']
    assert (output / original.name).read_text() == corrected
    assert sha(output / f'{original.name}.o') == module['objectSha256']
    for match in pattern.finditer(text):
        statement, site = lower_logical_record(match[0], dol)
        assert len(site) == 1
        body = statement.split('\n', 2)[2]
        name = f'case_{len(entries)}'
        functions.append(f'void {name}(nwii::runtime::CPUContext& ctx) {{\n{body}\n}}')
        entry = site[0]
        entries.append(f'{{{name}, {entry["ra"]}, {entry["rs"]}, {entry["immediate"]}u}}')
assert len(entries) == 9
prefix = (project / 'experiments/wii-static-recomp/stock_psq_contract.cpp').read_text().split('int main() {')[0]
source = output / 'logical-record-contract.cpp'
source.write_text(prefix + '\n'.join(functions) + '''
struct Case { void (*run)(nwii::runtime::CPUContext&); unsigned ra, rs; uint32_t mask; };
int main() {
    nwii::runtime::CPUContext ctx;
    Case cases[] = {''' + ','.join(entries) + '''};
    unsigned count = 0;
    for (const auto& test : cases) {
        for (uint32_t value : {0u, 0x245Cu, 1u, 0x80000000u, 0x7FFFFFFFu, 0xFFFFFFFFu}) {
            for (unsigned so = 0; so < 2; ++so) {
                for (unsigned stale = 0; stale < 4; ++stale) {
                    ctx.gpr[test.rs] = value;
                    const auto before = ctx.gpr;
                    ctx.xer = 0x12345678u | (so << 31);
                    ctx.cr[0].lt = stale & 1;
                    ctx.cr[0].gt = stale & 2;
                    ctx.cr[0].eq = !(stale & 1);
                    ctx.cr[0].so = !so;
                    ctx.cr[3].eq = true;
                    test.run(ctx);
                    const uint32_t result = value & test.mask;
                    assert(ctx.gpr[test.ra] == result);
                    assert(ctx.cr[0].lt == ((int32_t)result < 0));
                    assert(ctx.cr[0].gt == ((int32_t)result > 0));
                    assert(ctx.cr[0].eq == (result == 0));
                    assert(ctx.cr[0].so == bool(so));
                    assert(ctx.xer == (0x12345678u | (so << 31)));
                    assert(ctx.cr[3].eq);
                    for (unsigned i = 0; i < 32; ++i) {
                        if (i != test.ra) {
                            assert(ctx.gpr[i] == before[i]);
                        }
                    }
                    ++count;
                }
            }
        }
    }
    std::cout << "PASS " << count << " emitted logical-record result/CR0/SO/stale-flags cases\\n";
}
''')
flags = (build / 'CMakeFiles/OpenSHSMStockBaseline.dir/flags.make').read_text()
compiler = re.search(r'# compile CXX with (.+)', flags)[1]
arguments = []
for name in ('CXX_DEFINES', 'CXX_INCLUDES', 'CXX_FLAGS'):
    arguments += shlex.split(re.search(r'^' + name + r' = (.*)$', flags, re.M)[1])
if args.optimized:
    arguments += ['-O2', '-fno-strict-aliasing', '-fwrapv', '-ffp-contract=off']
probe = output / 'logical-record-contract'
subprocess.run([compiler, *arguments, '-I', str(output), str(source), '-o', str(probe)], check=True, timeout=60)
result = subprocess.run([str(probe)], capture_output=True, text=True, timeout=20)
assert result.returncode == 0, result.stdout + result.stderr
for name, digest in manifest['retainedGuestObjects'].items():
    assert sha(build / name) == digest
assert sha(root / 'ipc-cpbp/libnwiiruntime.a') == manifest['archiveSha256']
run_path = root / (args.run_label + '-result.json')
run = json.loads(run_path.read_text())
log = root / (args.run_label + '.log')
log_text = log.read_text()
assert run['terminalReturncode'] == 0 and run['deadlineReached']
assert run['variant'] == variant and run['tag'] == args.tag
assert run['executableSha256'] == sha(output / exe_name)
assert run['logSha256'] == sha(log)
assert 'WILD JUMP' not in log_text and 'Aborting:' not in log_text and 'UNIMPLEMENTED' not in log_text
assert '0x9000fd94 = 0x244c pc=0x8034c1b0' in log_text
from PIL import Image
bmp = root / f'{variant}-{args.tag}-efb_{args.capture_index}.bmp'
png = bmp.with_suffix('.png')
assert Image.open(bmp).convert('RGBA').tobytes() == Image.open(png).convert('RGBA').tobytes()
(output / 'logical-record-audit.json').write_text(json.dumps({
    'result': 'LOGICAL_RECORD_STATEMENT_CONTRACT_PASS', 'emittedSites': len(entries),
    'contract': result.stdout.strip(), 'executableSha256': sha(output / exe_name),
    'run': run, 'capturePngSha256': sha(png), 'captureBmpSha256': sha(bmp),
    'visualObservation': 'Separate visual inspection required for this capture.' if args.optimized else 'Separately inspected original fully visible SHSM title/copyright, not menu.',
    'limits': ['Actual generated statements/actual context, host-trap fixture; no live Wii oracle.',
        'Whole startup/capture acceptance is separate; original andi sites already recording are unchanged.']
}, indent=2) + '\n')
print(result.stdout.strip())
