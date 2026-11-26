"""Current-object CPU IRQ readiness probe; existing MMIO guards deliberately retained."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-flush-packet-boot'
ack = '--ack-mmio' in sys.argv
output = root / ('stm-irq-native-ack' if ack else 'stm-irq-native-attempt')
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_stm_irq_dolphin.py'), '--cached'], check=True)
build = json.loads((base / 'build.json').read_text())
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for path in base.glob('*.h'):
    (output / path.name).write_bytes(path.read_bytes())
for name in ('mass_boot.cpp', 'processor_adapter.cpp', 'ipc_reset_backend.cpp', 'ai_mask_backend.cpp', 'dsp_startup_backend.cpp'):
    (output / name).write_bytes((base / name).read_bytes())
(output / 'ipc_event_order_probe.cpp').write_bytes((experiment / 'ipc_event_order_probe.cpp').read_bytes())
header = output / 'si_external_delivery.h'
delivery = '#include "ipc_reset_backend.h"\n' + header.read_text().replace('namespace nwii::runtime {', 'namespace nwii::runtime {\ninline bool experimentStmIrq = false;', 1)
marker = '    if (pending != 8 || hw::pi_intmr.load() != 0xf8 || (hw::experimentSiControl & 0xc0000001u) != 0xc0000000u) {'
assert delivery.count(marker) == 1
delivery = delivery.replace(marker, '''    const bool stm = experimentStmIrq && pending == 0x4000 && hw::pi_intmr.load() == 0x40f8;
    if (stm) {
        const auto ipc = hw::experiment_ipc_snapshot();
        if (ipc.ppcMessage != 0x135e0020 || ipc.ppcControl != 0x32 || ipc.armMessage || ipc.armControl ||
            ipc.ppcMask != 0x40000000 || ipc.delay || (hw::pi_intsr.load() & ~0x14000u)) {
            throw std::runtime_error("IPC ACK producer state unverified");
        }
    }
    if ((!stm && (pending != 8 || hw::pi_intmr.load() != 0xf8 ||
        (hw::experimentSiControl & 0xc0000001u) != 0xc0000000u)) ||
        (experimentStmIrq && !stm)) {''')
marker = 'bat_memory_read32(context, 0x80003090) != 0x8020f850 || bat_memory_read32(context, 0x800000c4) != 0xf7fff7f0'
assert delivery.count(marker) == 1
delivery = delivery.replace(marker, '''(stm ? bat_memory_read32(context, 0x800030ac) != 0x80241f00 :
            bat_memory_read32(context, 0x80003090) != 0x8020f850) ||
        bat_memory_read32(context, 0x800000c4) != (stm ? 0xf7fff7e0 : 0xf7fff7f0)''')
header.write_text(delivery)
records = [dict(row) for row in build['records']]
if ack:
    (output / 'ipc_ack_frontend.h').write_bytes((experiment / 'ipc_ack_frontend.h').read_bytes())
    row = next(row for row in records if row['file'] == 'output_67.cpp')
    source = Path(row['source']).read_text()
    transforms = [
        ('    // 0x80241C28: 7C63002E\n    ctx.gpr[3] = nwii::runtime::bat_memory_read32(ctx, ctx.gpr[3] + ctx.gpr[0]); // lwzx',
         '    // 0x80241C28: 7C63002E\n    ctx.gpr[3] = nwii::runtime::experiment_ipc_ack_read(ctx, ctx.gpr[3] + ctx.gpr[0]); // lwzx'),
        ('    // 0x80241C38: 7C83012E\n    nwii::runtime::experiment_ipc_startup_store(ctx, ctx.gpr[3] + ctx.gpr[0], ctx.gpr[4]); // stwx',
         '    // 0x80241C38: 7C83012E\n    nwii::runtime::experiment_ipc_ack_write(ctx, ctx.gpr[3] + ctx.gpr[0], ctx.gpr[4]); // stwx'),
        ('    // 0x80241F70: 90030030\n    nwii::runtime::bat_memory_write32(ctx, ctx.gpr[3] + 48, ctx.gpr[0]); // stw r0, 48(r3)',
         '    // 0x80241F70: 90030030\n    nwii::runtime::experiment_ipc_ack_clear(ctx, ctx.gpr[3] + 48, ctx.gpr[0]); // stw r0, 48(r3)')]
    for before, after in transforms:
        assert source.count(before) == 1
        source = source.replace(before, after)
    target = output / 'output_67.cpp'
    target.write_text(source)
    obj = output / 'output_67.cpp.o'
    result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-DSHSM_SI_EXTERNAL_DELIVERY',
        '-include', str(output / 'ipc_ack_frontend.h'), '-I', str(output), '-I', str(experiment),
        '-I', str(runtime / 'include'), '-I', str(root / 'mass-current'), '-c', str(target), '-o', str(obj)],
        capture_output=True, text=True, timeout=180)
    (output / 'ack-compile.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-3000:]
    row.update(source=str(target), sourceSha256=sha(target), object=str(obj), objectSha256=sha(obj))
evidence_path = root / 'mass-ipc-irq-context-observer/irq-context.json'
evidence = json.loads(evidence_path.read_text())
(output / 'ipc-context.h').write_text('inline constexpr std::array<uint32_t, 198> ipcThreadWords{' +
    ','.join(hex(value) for value in evidence['threadWords']) + '};\n')
prefix = (root / 'si-vector-native/si-query-host.cpp').read_text().split('int unused_getid_main(', 1)[0]
prefix = prefix.split('namespace nwii::runtime {\nbool process_pending_callbacks', 1)[0]
host = output / 'stm-irq-attempt-host.cpp'
host.write_text('#include "finite_mem2_clear.h"\n#include "sram_frontend.h"\n#include "ipc_startup_frontend.h"\n#include "ipc-context.h"\n' + prefix +
    '#define main unused_ipc_event_main\n#include "ipc_event_order_probe.cpp"\n#undef main\n' +
    ('#include "ipc_ack_frontend.h"\n' if ack else '') +
    (experiment / 'stm_irq_attempt_host.cpp').read_text())
sources = [host, output / 'processor_adapter.cpp', output / 'ai_mask_backend.cpp', output / 'dsp_startup_backend.cpp',
    runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp',
    runtime / 'src/core/event_scheduler.cpp']
exe = output / 'stm-irq-attempt'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit',
    '-include', str(output / 'finite_mem2_clear.h'), '-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER',
    *(['-DSHSM_STM_ACK_MMIO'] if ack else []),
    '-I', str(output), '-I', str(experiment), '-I', str(root / 'mass-current'), '-I', str(runtime / 'include'),
    '-I', str(runtime / 'src/hw'), '-I', str(runtime.parent / 'nWiiAnalyzer/include'),
    *map(str, sources), *[row['object'] for row in records], '-o', str(exe)],
    capture_output=True, text=True, timeout=180)
(output / 'build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
(output / 'native.log').write_text(result.stdout + result.stderr)
(output / 'attempt.json').write_text(json.dumps({'builderSha256': sha(Path(__file__)),
    'baseBuildSha256': sha(base / 'build.json'), 'records': records, 'sourceHashes': {str(path): sha(path) for path in sources},
    'transforms': transforms if ack else [],
    'headerHashes': {str(path): sha(path) for path in output.glob('*.h')}, 'contextEvidenceSha256': sha(evidence_path),
    'executableSha256': sha(exe), 'returnCode': result.returncode, 'logSha256': sha(output / 'native.log'),
    'limits': [('Private existing exception profile and three exact ACK MMIO seams;124objects retained, other source bytes unchanged.'
        if ack else 'Private extension of existing exception entry only; original125objects unchanged, hardware guards retained.'),
        'Prepared ACK stimulus; no native completed request/reply/wakeup or general boot permission proof.']}, indent=2) + '\n')
print(result.stdout[-1800:] + result.stderr)
assert result.returncode == 7
