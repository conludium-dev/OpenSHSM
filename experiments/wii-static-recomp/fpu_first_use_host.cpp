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
    context.fpuFirstUse = true;
    context.msr = 0x2032;
    for (unsigned index = 0; index < 38; ++index) {
        auto word = bat_memory_read32(context, 0x80211ba0 + index * 4);
        if (index == 26) { word = 0x38600007; }
        bat_memory_write32(context, 0xc0000800 + index * 4, word);
    }
    for (unsigned index = 0; index < 16; ++index) {
        context.msr = 0x2032;
        for (unsigned offset = 0; offset < 0x1c8; offset += 4) {
            bat_memory_write32(context, 0x80501000 + offset, 0);
        }
        for (const auto& [address, value] : std::array<std::pair<uint32_t, uint32_t>, 4>{{
            {0x800000c0, 0x00501000}, {0x800000d4, 0x80501000}, {0x800000d8, 0}, {0x8000301c, 0x80213dc0}
        }}) { bat_memory_write32(context, address, value); }
        for (unsigned offset = 0; offset < 128; offset += 4) {
            bat_memory_write32(context, 0x80550000 + offset, (index + 1) * 0x1020304u + offset * 0x01010101u);
            bat_memory_write32(context, 0x80560000 + offset, 0xa5a5a5a5);
        }
        context.gpr.fill(0);
        context.gpr[1] = 0x80540000;
        context.gpr[2] = 0x805335e0;
        context.gpr[13] = 0x8052e720;
        context.gpr[30] = 0xc0680000 + index * 736;
        context.gpr[3] = 0x80560000;
        context.gpr[4] = 0x80550000;
        context.gpr[5] = 128;
        context.pc = 0x80005f34;
        context.lr = 0x807f0000;
        context.msr = index % 2 == 0 ? 0x32 : 0x2032;
        context.exceptionVector = 0;
        context.fpuEntries = 0;
        context.inst_count = 0;
        context.is_running = true;
        if (argc == 3) {
            const std::array<std::function<void()>, 10> invalid{
                [&] { context.fpuFirstUse = false; }, [&] { context.msr = 0x30; },
                [&] { context.exceptionVector = 7; },
                [&] { bat_memory_write32(context, 0x800000d8, 0x80502000); },
                [&] { bat_memory_write32(context, 0x8000301c, 0); },
                [&] { bat_memory_write16(context, 0x805011a2, 1); },
                [&] { bat_memory_write32(context, 0x800000c0, 0x00502000); },
                [&] { bat_memory_write32(context, 0x80000868, 0x38600000); },
                [] {}, [] {}
            };
            for (unsigned test = 0; test < invalid.size(); ++test) {
                context.fpuFirstUse = true;
                context.exceptionVector = 0;
                context.msr = 0x32;
                bat_memory_write32(context, 0x800000d8, 0);
                bat_memory_write32(context, 0x8000301c, 0x80213dc0);
                bat_memory_write16(context, 0x805011a2, 0);
                bat_memory_write32(context, 0x800000c0, 0x00501000);
                bat_memory_write32(context, 0x80000868, 0x38600007);
                invalid[test]();
                const auto snapshot = [&] {
                    return std::array<uint64_t, 8>{context.pc, context.msr, context.srr0, context.srr1,
                        context.exceptionVector, context.fpuResume, context.fpuEntries, bat_memory_read32(context, 0x800000d8)};
                };
                const auto before = snapshot();
                const auto beforeGpr = context.gpr;
                bool refused = false;
                try {
                    experiment_fpu_first_use_transfer(context, test == 8 ? 0xc824fff0 : 0xc824fff8,
                        test == 9 ? 0x800060f8 : 0x800060f4);
                } catch (const std::runtime_error&) { refused = true; }
                if (!refused || snapshot() != before || context.gpr != beforeGpr) { return 12; }
            }
            std::cout << "FPU_GUARDS 10\n";
            return 0;
        }
        try { run_game(context); } catch (const std::runtime_error& failure) {
            if (context.pc != 0x807f0000 || std::string(failure.what()) != "FPU oracle return sentinel") {
                std::cerr << "FPU_FAILURE pc=" << std::hex << context.pc << " msr=" << context.msr << ' ' << failure.what() << '\n';
                throw;
            }
        }
        std::cout << "FPU_CASE " << index << ' ' << context.msr << ' ' << bat_memory_read32(context, 0x800000d8)
                  << ' ' << bat_memory_read32(context, 0x80501198) << ' ' << bat_memory_read32(context, 0x8050119c)
                  << ' ' << bat_memory_read16(context, 0x805011a2) << ' ' << context.gpr[3] << ' ' << context.gpr[1]
                  << ' ' << context.gpr[2] << ' ' << context.gpr[13] << ' ' << context.gpr[30] << ' ' << context.pc
                  << ' ' << context.fpuEntries << '\n';
        std::cout << "FPU_COPY " << index;
        for (unsigned offset = 0; offset < 128; offset += 4) {
            std::cout << ' ' << bat_memory_read32(context, 0x80560000 + offset)
                      << ' ' << bat_memory_read32(context, 0x80550000 + offset);
        }
        std::cout << '\n';
    }
    return 0;
}
