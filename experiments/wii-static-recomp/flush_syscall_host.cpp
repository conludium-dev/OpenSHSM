extern "C" void run_game(nwii::runtime::CPUContext&);

int main(int argc, char** argv) {
    using namespace nwii::runtime;
    if (argc < 2 || argc > 3 || (argc == 3 && std::string(argv[2]) != "guards")) { return 2; }
    nwii::loader::Executable executable;
    if (!executable.load_dol(argv[1])) { return 3; }
    SeededBatContext context;
    for (const auto& section : executable.sections) {
        std::copy(section.data.begin(), section.data.end(), context.mmu.get_ptr(section.address));
        if (section.is_text) { context.instructionImages.emplace_back(section.address, section.data); }
    }
    g_trace_calls = false;
    context.hid0 = 0xc200;
    context.hid2 = 0xa0000000;
    context.msr = 0x2032;
    context.flushSyscall = true;
    for (unsigned index = 0; index < 7; ++index) {
        bat_memory_write32(context, 0xc0000c00 + index * 4, bat_memory_read32(context, 0x8021a120 + index * 4));
    }
    if (argc == 3) {
        const std::array<std::function<void()>, 7> invalid{
            [&] { context.flushSyscall = false; }, [&] { context.msr = 0x2030; },
            [&] { context.hid0 = 0xc208; }, [&] { context.exceptionVector = 7; },
            [&] { context.flushPhase = 1; }, [&] { bat_memory_write32(context, 0x80000c00, 0); }, [] {}
        };
        for (unsigned test = 0; test < invalid.size(); ++test) {
            context.flushSyscall = true;
            context.msr = 0x2032;
            context.hid0 = 0xc200;
            context.exceptionVector = 0;
            context.flushPhase = 0;
            bat_memory_write32(context, 0x80000c00, bat_memory_read32(context, 0x8021a120));
            invalid[test]();
            const auto snapshot = [&] {
                return std::array<uint64_t, 8>{context.pc, context.msr, context.hid0, context.srr0, context.srr1,
                    context.exceptionVector, context.flushPhase, context.flushEntries};
            };
            const auto before = snapshot();
            bool refused = false;
            try { experiment_flush_syscall_enter(context, test == 6 ? 0x80213028 : 0x80212ff8); }
            catch (const std::runtime_error&) { refused = true; }
            if (!refused || before != snapshot()) { return 12; }
        }
        for (unsigned test = 0; test < 5; ++test) {
            context.flushSyscall = true;
            context.pc = 0x8021a120;
            context.msr = 0x2000;
            context.exceptionVector = 9;
            context.flushPhase = test < 2 ? 2 : test == 2 ? 1 : test == 3 ? 3 : 4;
            context.hid0 = test == 4 ? 0xc200 : 0xc208;
            context.srr0 = test == 4 ? 0x80212ff8 : 0x80212ffc;
            context.srr1 = 0x2032;
            const auto snapshot = [&] {
                return std::array<uint64_t, 8>{context.pc, context.msr, context.hid0, context.srr0, context.srr1,
                    context.exceptionVector, context.flushPhase, context.flushBarriers};
            };
            const auto before = snapshot();
            bool refused = false;
            try {
                if (test == 0 || test == 4) { experiment_flush_return_guard(context); }
                else if (test == 2) { experiment_flush_sync(context); }
                else { experiment_flush_hid0_write(context, test == 3 ? 0xc201 : 0xc200, 0x8021a134); }
            } catch (const std::runtime_error&) { refused = true; }
            if (!refused || before != snapshot()) { return 13; }
        }
        std::cout << "FLUSH_GUARDS 12\n";
        return 0;
    }
    const std::array<unsigned, 8> lengths{0, 1, 31, 32, 33, 63, 64, 128};
    for (unsigned index = 0; index < 16; ++index) {
        context.msr = 0x2032;
        for (unsigned offset = 0; offset < 160; offset += 32) {
            bat_memory_cache_operation(context, 0x80550000 + offset, 470);
        }
        for (unsigned offset = 0; offset < 160; offset += 4) {
            bat_memory_write32(context, 0xc0550000 + offset, 0xa5a5a5a5);
            bat_memory_write32(context, 0x80550000 + offset, (index + 1) * 0x1020304u + offset * 0x01010101u);
        }
        context.gpr.fill(0);
        context.gpr[1] = 0x80540000;
        context.gpr[2] = 0x805335e0;
        context.gpr[13] = 0x8052e720;
        context.gpr[30] = 0xc0680000 + index * 736;
        context.gpr[9] = 0x11223344;
        context.gpr[10] = 0x55667788;
        context.gpr[3] = 0x80550000 + (index >= 8 ? 7 : 0);
        context.gpr[4] = lengths[index % 8];
        context.srr0 = context.srr1 = 0;
        context.flushEntries = context.flushBarriers = 0;
        context.pc = 0x80212fd0;
        context.lr = 0x807f0000;
        context.is_running = true;
        context.inst_count = 0;
        try { run_game(context); } catch (const std::runtime_error& failure) {
            if (context.pc != 0x807f0000 || std::string(failure.what()) != "Flush oracle return sentinel") { throw; }
        }
        std::cout << "FLUSH_CASE " << index << ' ' << context.msr << ' ' << context.hid0 << ' ' << context.srr0 << ' ' << context.srr1;
        for (unsigned reg : {1u, 2u, 13u, 30u, 9u, 10u, 3u, 4u}) { std::cout << ' ' << context.gpr[reg]; }
        std::cout << ' ' << context.pc << ' ' << context.flushEntries << ' ' << context.flushBarriers << '\n';
        std::cout << "FLUSH_MEMORY " << index;
        for (unsigned offset = 0; offset < 160; offset += 4) { std::cout << ' ' << bat_memory_read32(context, 0xc0550000 + offset); }
        std::cout << '\n';
    }
    return 0;
}
