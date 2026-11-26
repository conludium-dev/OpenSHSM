"""Connect the measured SI cause to existing CPU polling and run_game."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_si_irq_native.py'
source = parent.read_text()
marker = "exec(compile(body, str(builder), 'exec'), {'__file__': __file__})"
assert source.count(marker) == 1
namespace = {'__file__': __file__}
exec(compile(source.split(marker)[0], str(parent), 'exec'), namespace)
body = namespace['body'].replace('si-irq-native', 'si-vector-native').replace('verify_si_irq_dolphin.py', 'verify_si_vector_dolphin.py')
body = body.replace('dolphin-si-irq/comparison.json', 'dolphin-si-vector/comparison.json')
body = body.replace("'-DSHSM_PROCESSOR_ADAPTER'", "'-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_PROCESSOR_ADAPTER'")
body = body.replace("'-std=c++20', '-O0', '-include', str(experiment / 'si_query_frontend.h')", "'-std=c++20', '-O0', '-DSHSM_SI_EXTERNAL_DELIVERY', '-include', str(experiment / 'si_query_frontend.h')")
host_before = namespace['host_body']
host_body = host_before
seed = '''    hw::pi_intmr = 8;
    context.msr = 0x2030;
    for (unsigned index = 0; index < 38; ++index) {
        auto word = bat_memory_read32(context, 0x80211ba0 + index * 4);
        if (index == 26) { word = 0x38600004; }
        bat_memory_write32(context, 0x80000500 + index * 4, word);
    }
    const std::array<std::pair<uint32_t, uint32_t>, 9> os_seed{{
        {0x800000c0, 0x00501000}, {0x800000d4, 0x80501000}, {0x800000c4, 0xfffff7ff}, {0x800000c8, 0},
        {0x80003010, 0x80217c60}, {0x8052aad8, 0x80003040}, {0x80003090, 0x8020f850}, {0x8052ab00, 0}, {0x8052ab04, 0}
    }};
    for (const auto& [address, value] : os_seed) { bat_memory_write32(context, address, value); }
'''
host_body = host_body.replace('    hw::pi_intsr = 0x10000;', '    hw::pi_intsr = 0x10000;\n' + seed)
before = '''        context.pc = 0x8020f850;
        context.lr = 0x807f0000;
        context.gpr[3] = 20;
        context.gpr[4] = 0x80501000;'''
after = '''        for (unsigned offset = 0; offset < 0x1c8; offset += 4) {
            bat_memory_write32(context, 0x80501000 + offset, 0);
        }
        context.pc = 0x807f0000;
        context.lr = 0x807f0000;
        context.gpr[30] = 0xc0680000 + index * 736;
        context.msr = 0xa032;'''
assert host_body.count(before) == 1
host_body = host_body.replace(before, after).replace('context.pc != 0x807f0000 || context.msr != 0x2030 || hw::experimentSiQuery.callbackCount',
    'context.pc != 0x807f0000 || context.msr != 0xa032 || siExternalEntries != index + 1 || hw::experimentSiQuery.callbackCount')
diagnostic = '''                std::cerr << "SI_VECTOR_FAILURE pc=" << std::hex << context.pc << " msr=" << context.msr
                    << " r1=" << context.gpr[1] << " r3=" << context.gpr[3] << " r13=" << context.gpr[13] << " r30=" << context.gpr[30]
                    << " srr0=" << context.srr0 << " ctxPC=" << context.mmu.read32(0x80501198)
                    << " lowC0=" << context.mmu.read32(0xc0) << " lowD4=" << context.mmu.read32(0xd4) << '\\n';
'''
host_body = host_body.replace('                throw;\n', diagnostic + '                throw;\n')
marker = '        const auto result = hw::experimentSiQuery.callbackStatus;'
context_print = '''        std::cout << "SI_VECTOR_CONTEXT " << index << ' ' << context.msr << ' '
            << bat_memory_read32(context, 0x80501198) << ' ' << bat_memory_read32(context, 0x8050119c) << ' '
            << bat_memory_read32(context, 0x80501004) << ' ' << bat_memory_read32(context, 0x80501008) << ' '
            << bat_memory_read32(context, 0x80501034) << ' ' << bat_memory_read32(context, 0x80501078) << ' '
            << bat_memory_read16(context, 0x805011a2) << ' ' << bat_memory_read32(context, 0x8052ab00) << ' '
            << bat_memory_read32(context, 0x8052ab04) << ' ' << bat_memory_read32(context, 0x8052aac8) << ' '
            << bat_memory_read16(context, 0x8052aacc) << '\\n';
        context.msr = 0x2030;
'''
assert host_body.count(marker) == 1
host_body = host_body.replace(marker, context_print + marker)
guard_marker = '        std::cout << "SI_QUERY_GUARDS 8\\n";'
extra_guards = '''        const std::array<std::function<void()>, 8> irq_invalid{
            [&] { context.msr = 0xa030; },
            [&] { hw::pi_intmr = 0x18; hw::pi_intsr = 0x10018; },
            [&] { hw::experimentSiControl = 0x20010300; },
            [&] { bat_memory_write32(context, 0x800000c0, 0x00502000); },
            [&] { bat_memory_write32(context, 0x80000568, 0x38600000); },
            [&] { bat_memory_write32(context, 0x8052ab00, 1); },
            [&] { context.vblank_pending = true; },
            [&] { context.dec_irq_pending = true; }
        };
        const auto irq_snapshot = [&] {
            return std::array<uint64_t, 8>{context.pc, context.msr, context.srr0, context.srr1, siExternalEntries,
                hw::pi_intsr.load(), hw::pi_intmr.load(), hw::experimentSiControl};
        };
        for (const auto& invalidate : irq_invalid) {
            context.msr = 0xa032;
            context.pc = 0x807f0000;
            context.is_running = true;
            context.vblank_pending = false;
            context.dec_irq_pending = false;
            hw::pi_intmr = 8;
            hw::pi_intsr = 0x10008;
            hw::experimentSiControl = 0xe0010300;
            bat_memory_write32(context, 0x800000c0, 0x00501000);
            bat_memory_write32(context, 0x80000568, 0x38600004);
            bat_memory_write32(context, 0x8052ab00, 0);
            invalidate();
            const auto before = irq_snapshot();
            const auto before_gpr = context.gpr;
            bool refused = false;
            try { experiment_boot_poll(context); } catch (const std::runtime_error&) { refused = true; }
            if (!refused || irq_snapshot() != before || context.gpr != before_gpr) { return 16; }
        }
        context.vblank_pending = false;
        context.dec_irq_pending = false;
        context.msr = 0x2030;
        if (experiment_boot_poll(context) || siExternalEntries) { return 17; }
        context.msr = 0xa032;
        hw::pi_intmr = 0;
        if (experiment_boot_poll(context) || siExternalEntries) { return 18; }
        hw::pi_intmr = 8;
        hw::pi_intsr = 0x10000;
        if (experiment_boot_poll(context) || siExternalEntries) { return 19; }
        std::cout << "SI_EXTERNAL_GUARDS 8 GATES 3\\n";
'''
assert host_body.count(guard_marker) == 1
host_body = host_body.replace(guard_marker, extra_guards + guard_marker)
assert body.count(repr(host_before)) == 1
body = body.replace(repr(host_before), repr(host_body))
sentinel_before = namespace['sentinel_after']
sentinel_after = sentinel_before.replace('if (context.pc == 0x807f0000)',
    'if (context.pc == 0x807f0000 && !(context.msr == 0xa032 && (hw::pi_intsr.load() & hw::pi_intmr.load()) == 8))')
assert body.count(repr(sentinel_before)) == 1
body = body.replace(repr(sentinel_before), repr(sentinel_after))
vector_changes = [
    ('    // 0x80211BA0: 7C9043A6\n    // unhandled mtspr 272\n', '    // 0x80211BA0: 7C9043A6\n    ctx.sprg[0] = ctx.gpr[4];\n'),
    ('    // 0x80211BAC: 7C7042A6\n    std::cerr << "[WARN] mfspr r" << 3 << " spr=" << 272 << " (stub=0)\\n";\n    ctx.gpr[3] = 0; // unknown spr stub\n',
     '    // 0x80211BAC: 7C7042A6\n    ctx.gpr[3] = ctx.sprg[0];\n'),
    ('    // 0x80211C08: 38600000\n    ctx.gpr[3] = 0; // li r3, 0\n',
     '    // 0x80211C08: 38600000\n    if (bat_memory_read32(ctx, 0x568) != 0x38600004) { throw std::runtime_error("Unverified relocated vector ID"); }\n    ctx.gpr[3] = 4;\n')
]
for index, (before, after) in enumerate(vector_changes):
    instruction = before.splitlines()[0].split(':')[0].split('0x')[1].lower()
    guard = '    nwii::runtime::experiment_template_execution_guard(ctx, 0x' + instruction + ');\n'
    before = before.replace(before.splitlines(True)[0], before.splitlines(True)[0] + guard, 1)
    after = after.replace(after.splitlines(True)[0], after.splitlines(True)[0] + guard, 1)
    vector_changes[index] = (before, after)
vector_changes.append(('nwii::runtime::experiment_template_execution_guard(ctx,', 'nwii::runtime::experiment_si_vector_execution_guard(ctx,'))
marker = '        source.write_text(source_text)'
assert body.count(marker) == 1
transform = ''
for before, after in vector_changes:
    count = 38 if before.startswith('nwii::runtime::experiment_template_execution_guard') else 1
    transform += '            assert source_text.count(' + repr(before) + ') == ' + str(count) + '\n            source_text = source_text.replace(' + repr(before) + ', ' + repr(after) + ')\n'
body = body.replace(marker, "        if row['file'] == 'output_63.cpp':\n" + transform + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/si-vector-native')
path = output / 'build.json'
report = json.loads(path.read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report.update({'irqBuilderSha256': sha(parent), 'baseBuilderSha256': sha(experiment / 'build_si_query_native.py'),
    'hostInputSha256': sha(experiment / 'si_query_host.cpp'), 'hostBody': host_body,
    'hostSentinel': {'before': namespace['sentinel_before'], 'after': sentinel_after},
    'callbackObserver': {'before': namespace['callback_marker'], 'after': namespace['callback_trace'] + namespace['callback_marker']},
    'vectorChanges': vector_changes, 'dispatcherSha256': sha(Path('work/private-game/static-recomp/mass-current/main_output.cpp')),
    'externalDeliverySha256': sha(experiment / 'si_external_delivery.h'), 'pollSha256': sha(experiment / 'boot_poll.h'),
    'batMemorySha256': sha(experiment / 'bat_memory_frontend.h')})
path.write_text(json.dumps(report, indent=2) + '\n')
