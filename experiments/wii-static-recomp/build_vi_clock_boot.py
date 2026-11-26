"""Extend the existing VI callback privately with the measured loader clock."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'mass-vi-clock-boot'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_vi_clock_dolphin.py')], check=True)
vendor = runtime / 'src/hw/hw_vi.cpp'
before = '            if (addr == 0xCC00202E) return 1;'
after = before + '\n            if (addr == 0xCC00206C) return 1;'
assert vendor.read_text().count(before) == 1
generated = output / 'hw_vi-clock.inc'
generated.write_text(vendor.read_text().replace(before, after))
backend = output / 'vi-clock-backend.cpp'
backend.write_text('''#define get_os_time experiment_vi_unverified_time
#include "hw_vi-clock.inc"
#undef get_os_time
#include <stdexcept>
namespace nwii::runtime {
uint64_t experiment_vi_unverified_time() {
    throw std::runtime_error("VI timing outside measured clock profile");
}
}
''')
builder = experiment / 'build_uart_boot.py'
body = builder.read_text().replace('mass-uart-boot', 'mass-vi-clock-boot').replace('uart_next_observer.h', 'vi_clock_frontend.h')
store_before = '    // 0x8020FEEC: 93E46430\n    nwii::runtime::experiment_getid_write32(ctx, ctx.gpr[4] + 25648, ctx.gpr[31]); // stw r31, 25648(r4)\n'
store_after = store_before.replace('experiment_getid_write32(ctx, ctx.gpr[4] + 25648, ctx.gpr[31])', 'experiment_vi_next_write32(ctx, ctx.gpr[4] + 25648, ctx.gpr[31], 0x8020feec)')
call_before = '    // 0x8021063C: 4BFFF875\n    ctx.lr = 0x80210640; // save return address\n'
call_after = call_before.replace('    ctx.lr', '    std::cout << "VI_SAMPLING_ARGS x=" << std::dec << ctx.gpr[3] << " y=" << ctx.gpr[4] << "\\n";\n    ctx.lr')
marker = 'source.write_text(source_body.replace(before, after))'
assert body.count(marker) == 1
insert = 'assert source_body.count(' + repr(store_before) + ') == 1\n'
insert += 'assert source_body.count(' + repr(call_before) + ') == 2\n'
insert += 'source_body = source_body.replace(' + repr(store_before) + ', ' + repr(store_after) + ').replace(' + repr(call_before) + ', ' + repr(call_after) + ')\n'
body = body.replace(marker, insert + marker)
marker = "replacement = '    nwii::runtime::hw::experimentExiTransfer.uartAllowed = true;\\n' + call"
assert body.count(marker) == 1
replacement = '    nwii::runtime::hw::experimentExiTransfer.uartAllowed = true;\n    nwii::runtime::hw::register_vi(nwii::runtime::MMIODispatcher::get());\n'
body = body.replace(marker, 'replacement = ' + repr(replacement) + ' + call')
marker = "exec(compile(body, str(builder), 'exec'), {'__file__': __file__})"
assert body.count(marker) == 1
insert = "body = body.replace('sources = [wrapper,', \"sources = [output / 'vi-clock-backend.cpp', wrapper,\")\n"
body = body.replace(marker, insert + marker)
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = output / 'boot.json'
report = json.loads(path.read_text())
report['result'] = 'VI_CLOCK_BOOT_ADVANCE_REQUIRES_AUDIT'
report['viClock'] = {'vendorSource': str(vendor), 'vendorSha256': sha(vendor), 'generatedSha256': sha(generated),
    'backendSha256': sha(backend), 'before': before, 'after': after,
    'originalProofSha256': sha(private / 'dolphin-vi-clock/comparison.json'), 'baseBuilderSha256': sha(builder)}
report['viClock']['sourceTransforms'] = [{'before': store_before, 'after': store_after, 'sites': 1}, {'before': call_before, 'after': call_after, 'sites': 2}]
report['limits'] = ['Read-only measured loader clock profile at original instruction80210620 only; other VI accesses retain BAT refusal.',
    'Private generated vendor callback extension, original vendor file unchanged; no full SI, video timing, first frame or controller support.']
path.write_text(json.dumps(report, indent=2) + '\n')
