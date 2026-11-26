"""Current-object real sleep readiness probe; idle exception guards deliberately retained."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
subprocess.run(['python3', str(experiment / 'verify_stm_sleep_dolphin.py')], check=True)
host = (experiment / 'stm_reply_host.cpp').read_text()
start = host.index('bool process_pending_callbacks(CPUContext& context) {')
end = host.index('\n}\n}\nextern "C"', start) + 2
callback = '''bool process_pending_callbacks(CPUContext& context) {
    if (context.inst_count > 100000) { throw std::runtime_error("STM sleep instruction budget"); }
    if (context.pc == 0x807f0000 && context.msr == 0x2032 && stmProduced == 1) {
        throw std::runtime_error("Original sleep returned");
    }
    if (context.msr & 0x8000) {
        EventScheduler::get().advance(context, EventScheduler::get().now() + 1);
        hw::experiment_ipc_irq_update();
    }
    return experiment_boot_poll(context);
}'''
host = host[:start] + callback + host[end:]
host = host.replace('            bat_memory_write32(context, 0x80690000 + slot * 4, ipcThreadWords[slot]);\n', '')
host = host.replace('        experiment_ipc_store_be32(packet + 44, 0x80690000);\n        experiment_ipc_store_be32(packet + 48, 0x80690000);\n', '')
start = host.index('            {0x806902c8,')
end = host.index('}) {', start)
host = host[:start] + host[end:]
host = host.replace('        context.msr = 0xa032;\n        context.pc = context.lr = 0x807f0000;',
    '        context.msr = 0x2032;\n        context.gpr[3] = (physical | 0x80000000) + 44;\n        context.pc = 0x8021b4e0;\n        context.lr = 0x807f0000;')
host = host.replace('Original reply/wakeup returned', 'Original sleep returned')
start = host.index('        std::cout << "STM_REPLY_CASE "')
end = host.index('        for (bool cached', start)
host = host[:start] + '''        std::cout << "STM_SLEEP_CASE " << index << ' ' << context.msr << ' ' << context.pc << ' '
            << context.gpr[1] << ' ' << context.gpr[2] << ' ' << context.gpr[13] << ' ' << context.gpr[30]
            << ' ' << hw::ipc_ppc_ctrl << ' ' << hw::ipc_arm_msg << ' ' << hw::pi_intsr.load()
            << ' ' << siExternalEntries << ' ' << stmProduced;
        for (uint32_t address : {0x80528b70u, 0x8052ab00u, 0x8052ab04u, 0x8052ab08u, 0x800000e4u,
            0x804929f0u, 0x804929f4u, 0x80492920u, 0x80492928u, 0x80492934u,
            0x80492938u, 0x8049293cu, 0x804927f0u, 0x804927f4u,
            0x8049265cu, 0x80492660u, 0x8049268cu, 0x80492c08u, 0x80492c0cu,
            0x800000d4u, 0x800000c0u, 0x800000d8u}) {
            std::cout << ' ' << bat_memory_read32(context, address);
        }
        std::cout << '\\n';
''' + host[end:]
marker = '                return 7;'
snapshot = '''                if (context.msr & 0x10) {
                std::cout << "STM_SLEEP_LAYOUT" << std::hex;
                for (uint32_t address : {0x800000c0u, 0x800000d4u, 0x800000d8u, 0x800000e4u,
                    0x8052ab00u, 0x8052ab04u, 0x8052ab08u, 0x80492920u, 0x804927f0u}) {
                    std::cout << ' ' << address << ' ' << bat_memory_read32(context, address);
                }
                std::cout << " threadstate=" << bat_memory_read16(context, 0x80492920)
                    << " queue=" << bat_memory_read32(context, (physical | 0x80000000) + 44)
                    << " physicalqueue=" << experiment_ipc_be32(packet + 44) << std::dec << std::endl;
                }
'''
assert host.count(marker) == 1
host = host.replace(marker, snapshot + marker)
parent = experiment / 'build_stm_reply_native.py'
body = parent.read_text()
idle = '--idle-profile' in sys.argv
variant = 'stm-sleep-native' if idle else 'stm-sleep-native-attempt'
line = next(line for line in body.splitlines() if line.startswith('variant = '))
body = body.replace(line, 'variant = ' + repr(variant))
marker = "    (experiment / 'stm_reply_host.cpp').read_text()"
assert marker in body or "\"experiment / 'stm_reply_host.cpp'\"" in body
body = body.replace("experiment / 'stm_reply_host.cpp'", "experiment / 'stm_sleep_host.cpp'")
marker = 'exec(compile(body, str(parent), \'exec\'), {\'__file__\': __file__})'
assert body.count(marker) == 1
body = body.replace(marker, "body = body.replace(\"(experiment / 'stm_sleep_host.cpp').read_text()\", " + repr(repr(host)) + ")\n" + marker)
if idle:
    profile = '''delivery = delivery.replace('inline uint32_t bat_memory_read32(CPUContext& context, uint32_t address);',
    'inline uint32_t bat_memory_read32(CPUContext& context, uint32_t address);\\ninline uint16_t bat_memory_read16(CPUContext& context, uint32_t address);')
delivery = delivery.replace('    if (context.msr != 0xa032 || !hw::experimentSiQuery.interruptProfile) {',
    '    const bool stmIdle = experimentStmIrq && context.msr == 0x8032;\\n    if ((context.msr != 0xa032 && !stmIdle) || !hw::experimentSiQuery.interruptProfile) {')
delivery = delivery.replace('(!fpu && (context.msr != 0x2000 || !siExternalEntries))',
    '(!fpu && ((context.msr != 0x2000 && !(experimentStmIrq && context.msr == 0)) || !siExternalEntries))')
delivery = delivery.replace('!= 0x00492658 ||', '!= (stmIdle ? 0x00492a70 : 0x00492658) ||')
delivery = delivery.replace('!= 0x80492658\\n', '!= (stmIdle ? 0x80492a70 : 0x80492658)\\n')
delivery = delivery.replace('|| bat_memory_read32(context, 0x8052ab04))',
    '|| bat_memory_read32(context, 0x8052ab04) != (stmIdle ? 1u : 0u))')
check = ''' + repr('''    if (stmIdle && (bat_memory_read32(context, 0x800000e4) ||
        bat_memory_read32(context, 0x800000d8) != 0x80492658 ||
        bat_memory_read16(context, 0x80492920) != 4 || bat_memory_read32(context, 0x8052ab08) ||
        bat_memory_read32(context, (hw::experiment_ipc_snapshot().ppcMessage | 0x80000000u) + 44) != 0x80492658)) {
        throw std::runtime_error("IPC idle thread/queue unverified");
    }
''') + '''
delivery = delivery.replace('    context.srr0 = context.pc;', check + '    context.srr0 = context.pc;', 1)
cache_path = output / 'bat_memory_frontend.h'
cache = cache_path.read_text().replace('namespace nwii::runtime {', 'namespace nwii::runtime {\\nextern bool experimentStmIrq;', 1)
cache = cache.replace('(context.msr == 0 && bat_context(context).exceptionVector == 7)',
    '(context.msr == 0 && (bat_context(context).exceptionVector == 7 || experimentStmIrq))')
cache_path.write_text(cache)
pi_path = output / 'si_query_frontend.h'
pi = pi_path.read_text()
marker = 'if (context.msr != 0x2030 || !hw::experimentSiQuery.interruptProfile ||'
assert pi.count(marker) == 1
pi = pi.replace(marker, 'if ((context.msr != 0x2030 && !(experimentStmIrq && context.msr == 0x30 && bat_memory_read32(context, 0x800000d4) == 0x80492a70 && !bat_memory_read32(context, 0x800000e4))) || !hw::experimentSiQuery.interruptProfile ||')
pi = pi.replace('throw std::runtime_error("SI external dispatcher PI mapping unverified");',
    'throw std::runtime_error("STM idle PI mapping unverified: msr=" + std::to_string(context.msr) + " physical=" + std::to_string(mapping.physical) + " wimg=" + std::to_string(mapping.wimg) + " slot=" + std::to_string(mapping.slot) + " current=" + std::to_string(bat_memory_read32(context, 0x800000d4)) + " exception=" + std::to_string(bat_memory_read32(context, 0x800000e4)));')
pi_path.write_text(pi)
'''
    profile += "header.write_text(delivery)\n"
    new_front = '''frontend = frontend.replace('context.msr != 0x2030',
    '(context.msr != 0x2030 && !(context.msr == 0x30 && bat_memory_read32(context, 0x800000d4) == 0x80492a70 && !bat_memory_read32(context, 0x800000e4)))')
'''
    recompile_one = '''row = next(row for row in records if row['file'] == file)
target = output / file
target.write_bytes(Path(row['source']).read_bytes())
obj = output / (file + '.o')
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-DSHSM_SI_EXTERNAL_DELIVERY',
    '-include', str(output / 'finite_mem2_clear.h'), '-I', str(output), '-I', str(experiment),
    '-I', str(runtime / 'include'), '-I', str(root / 'mass-current'), '-c', str(target), '-o', str(obj)],
    capture_output=True, text=True, timeout=180)
(output / (file + '-idle-compile.log')).write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
row.update(source=str(target), sourceSha256=sha(target), object=str(obj), objectSha256=sha(obj))
'''
    recompile = "for file in ('output_62.cpp', 'output_63.cpp', 'output_64.cpp'):\n" + ''.join('    ' + line + '\n' for line in recompile_one.splitlines())
    inject = "body = body.replace('header.write_text(delivery)', " + repr(profile) + ", 1)\n"
    inject += "body = body.replace(\"    (output / 'ipc_ack_frontend.h').write_text(frontend)\", " + repr('    ' + new_front.replace('\n', '\n    ').rstrip() + "\n    (output / 'ipc_ack_frontend.h').write_text(frontend)") + ", 1)\n"
    inject += "body = body.replace(\"evidence_path = root / 'mass-ipc-irq-context-observer/irq-context.json'\", " + repr(recompile + "evidence_path = root / 'mass-ipc-irq-context-observer/irq-context.json'") + ", 1)\n"
    body = body.replace(marker, inject + marker, 1)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = root / variant
report_path = output / 'attempt.json'
report = json.loads(report_path.read_text())
report['sleepOracleSha256'] = hashlib.sha256((root / 'dolphin-stm-sleep/comparison.json').read_bytes()).hexdigest()
report['sleepHostParentSha256'] = hashlib.sha256((experiment / 'stm_reply_host.cpp').read_bytes()).hexdigest()
report['limits'] = ['Actual original compiled OSSleepThread attempted on current objects; idle exception/MMIO profile remains guarded.',
    'Prepared native ACK/scheduled real OPEN producer, not original native X1 sender; no completed sleep/context-return claim until comparison.',
    'General startup/release remains unchanged.']
report['recompiledProfileObjects'] = ['output_62.cpp', 'output_63.cpp', 'output_64.cpp', 'output_67.cpp'] if idle else ['output_67.cpp']
report_path.write_text(json.dumps(report, indent=2) + '\n')
