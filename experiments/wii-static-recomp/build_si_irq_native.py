"""Execute the compiled original SI handler through the existing dispatcher."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_si_query_native.py'
body = builder.read_text().replace('si-query-native', 'si-irq-native').replace('verify_si_query_dolphin.py', 'verify_si_irq_dolphin.py')
body = body.replace('dolphin-si-query-callback/comparison.json', 'dolphin-si-irq/comparison.json')
callback_marker = '    // 0x80210110: 9421FFE0\n'
callback_trace = '    nwii::runtime::hw::experimentSiQuery.callbackChannel = ctx.gpr[3];\n    nwii::runtime::hw::experimentSiQuery.callbackStatus = ctx.gpr[4];\n    ++nwii::runtime::hw::experimentSiQuery.callbackCount;\n'
marker = "source.write_text(''.join(lines))"
assert body.count(marker) == 1
body = body.replace(marker, "source_text = ''.join(lines)\n        if row['file'] == 'output_63.cpp':\n            assert source_text.count(" + repr(callback_marker) + ") == 1\n            source_text = source_text.replace(" + repr(callback_marker) + ', ' + repr(callback_trace + callback_marker) + ')\n        source.write_text(source_text)')
host_input = (experiment / 'si_query_host.cpp').read_text()
registration = '    hw::experiment_register_si_query(MMIODispatcher::get());'
assert host_input.count(registration) == 1
host_body = host_input.replace(registration, registration + '\n    hw::experimentSiQuery.interruptProfile = true;')
host_body = host_body.replace('        context.gpr[8] = 0;', '        context.gpr[8] = 0x80210110;')
seed = '        bat_memory_write32(context, 0x8042b708 + channel * 4, 0x80);'
host_body = host_body.replace(seed, '        for (unsigned offset = 0; offset < 128; offset += 32) {\n            bat_memory_write32(context, 0x80492010 + offset, 0xffffffff);\n        }\n' + seed)
start = host_body.index('        context.pc = 0x8020f550;')
end = host_body.index('        std::cout << "SI_QUERY_CASE "', start)
host_body = host_body[:start] + '''        context.pc = 0x8020f850;
        context.lr = 0x807f0000;
        context.gpr[3] = 20;
        context.gpr[4] = 0x80501000;
        try {
            run_game(context);
            return 15;
        } catch (const std::runtime_error& failure) {
            if (context.pc != 0x807f0000 || std::string(failure.what()) != "SI IRQ oracle return sentinel") {
                throw;
            }
        }
        if (context.pc != 0x807f0000 || context.msr != 0x2030 || hw::experimentSiQuery.callbackCount != index + 1) {
            return 12;
        }
        const auto result = hw::experimentSiQuery.callbackStatus;
        const auto type_before_callback = bat_memory_read32(context, 0x8042b708 + channel * 4);
        const auto response = bat_memory_read32(context, 0x80500010);
        const auto after_control = hw::experimentSiControl;
        const auto after_status = hw::experimentSiQuery.status;
        const auto after_owner = bat_memory_read32(context, 0x8042b6f0);
''' + host_body[end:]
host_body = host_body.replace('SI_QUERY_CASE ', 'SI_IRQ_CASE ')
before_tail = ' << " 0 " << bat_memory_read32(context, 0x8042b708 + channel * 4) << \'\\n\';'
after_tail = ' << " 0 " << bat_memory_read32(context, 0x8042b708 + channel * 4) << \' \' << hw::pi_intsr.load() << \' \' << bat_memory_read32(context, 0x8042b700) << \' \' << hw::experimentSiQuery.callbackChannel << \' \' << hw::experimentSiQuery.callbackStatus << \'\\n\';'
assert host_body.count(before_tail) == 1
host_body = host_body.replace(before_tail, after_tail)
host_body = 'extern "C" void run_game(nwii::runtime::CPUContext&);\n' + host_body
host_marker = "(experiment / 'si_query_host.cpp').read_text()"
assert body.count(host_marker) == 1
body = body.replace(host_marker, repr(host_body))
sentinel_before = '    return experiment_boot_poll(context);'
sentinel_after = '    if (context.pc == 0x807f0000) {\n        throw std::runtime_error("SI IRQ oracle return sentinel");\n    }\n' + sentinel_before
marker = 'host.write_text('
assert body.count(marker) == 1
body = body.replace(marker, 'assert body.count(' + repr(sentinel_before) + ') == 1\nbody = body.replace(' + repr(sentinel_before) + ', ' + repr(sentinel_after) + ')\n' + marker)
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/si-irq-native/build.json')
report = json.loads(path.read_text())
report['baseBuilderSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['hostInputSha256'] = hashlib.sha256(host_input.encode()).hexdigest()
report['hostBody'] = host_body
report['hostSentinel'] = {'before': sentinel_before, 'after': sentinel_after}
report['callbackObserver'] = {'before': callback_marker, 'after': callback_trace + callback_marker}
report['dispatcherSha256'] = hashlib.sha256(Path('work/private-game/static-recomp/mass-current/main_output.cpp').read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
