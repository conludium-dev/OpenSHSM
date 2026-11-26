"""Rebuild existing flush batches for the measured MEM2 packet line and return caller."""
from pathlib import Path
import subprocess

experiment = Path('experiments/wii-static-recomp')
subprocess.run(['python3', str(experiment / 'verify_flush_packet_dolphin.py')], check=True)
parent = experiment / 'build_flush_ee_native.py'
body = parent.read_text().replace('flush-ee-profile', 'flush-packet-profile')
body = body.replace('build_flush_ee_profile.py', 'build_flush_packet_profile.py')
marker = "host = output / 'flush-ee-host.cpp'"
assert body.count(marker) == 1
injection = '''prefix = prefix.replace('context.pc == 0x8024262c', '(context.pc == 0x8024262c || context.pc == 0x80242240)')
body = body.replace('0x80550000', 'cached').replace('0xc0550000', 'uncached')
body = body.replace('0x8024262c', 'caller')
body = body.replace('    using namespace nwii::runtime;', '    using namespace nwii::runtime;\\n    const uint32_t caller = std::getenv("SHSM_FLUSH_OLD_CALLER") ? 0x8024262c : 0x80242240;\\n    const uint32_t cached = std::getenv("SHSM_FLUSH_MEM1") ? 0x80550000 : 0x935e0020;\\n    const uint32_t uncached = std::getenv("SHSM_FLUSH_MEM1") ? 0xc0550000 : 0xd35e0020;')
body = body.replace('    experimentFlushEe = true;', '    experimentFlushEe = true;\\n    experimentFlushPacket = true;', 1)
marker = '        std::cout << "FLUSH_GUARDS 16\\\\n";'
assert body.count(marker) == 1
extra = ''' + repr(r'''        experimentFlushEe = true;
        experimentFlushPacket = false;
        context.lr = 0x80242240;
        context.msr = 0xa032;
        context.hid0 = 0xc200;
        context.exceptionVector = context.flushPhase = 0;
        context.in_callback = false;
        hw::pi_intsr = 0;
        const auto before = std::array<uint64_t, 7>{context.pc, context.msr, context.hid0,
            context.srr0, context.srr1, context.flushEntries, context.flushBarriers};
        bool refused = false;
        try { experiment_flush_syscall_enter(context, 0x80212ff8); }
        catch (const std::runtime_error&) { refused = true; }
        const auto after = std::array<uint64_t, 7>{context.pc, context.msr, context.hid0,
            context.srr0, context.srr1, context.flushEntries, context.flushBarriers};
        if (!refused || before != after) { return 15; }
        std::cout << "FLUSH_GUARDS 17\n";''') + '''
body = body.replace(marker, extra)
'''
body = body.replace(marker, injection + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
