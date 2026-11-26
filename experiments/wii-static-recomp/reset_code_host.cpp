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
    hw::register_pi(MMIODispatcher::get());
    g_trace_calls = false;
    context.msr = 0x2032;
    if (argc == 3) {
        const auto bank = context.dbat;
        for (unsigned test = 0; test < 7; ++test) {
            context.dbat = bank;
            experimentResetCode = test != 0;
            context.msr = test == 2 ? 0x2030 : 0x2032;
            bat_memory_write32(context, 0x80492240, test == 5 ? 1 : 0);
            if (test == 3) { context.dbat[1].upper = 0; }
            if (test == 4) { context.dbat[1].lower ^= 8; }
            if (test == 6) {
                MMIODispatcher::get().clear();
                MMIODispatcher::get().register_region(0xcc003024, 0xcc003027,
                    [](uint32_t) -> uint32_t { return 8; }, [](uint32_t, uint32_t) { throw std::runtime_error("Reset lab write forbidden"); });
                if (MMIODispatcher::get().read32(0xcc003024) != 8) { return 14; }
            }
            const auto before = std::array<uint32_t, 3>{experimentResetCodeReads, hw::pi_intsr.load(), hw::pi_intmr.load()};
            bool refused = false;
            try { experiment_reset_code_read32(context, 0xcc003024, test == 1 ? 0x80219508 : 0x80219504); }
            catch (const std::runtime_error&) { refused = true; }
            if (!refused || before != std::array<uint32_t, 3>{experimentResetCodeReads, hw::pi_intsr.load(), hw::pi_intmr.load()}) {
                std::cout << "RESET_GUARD_FAILED " << test << '\n';
                return 12;
            }
        }
        context.dbat = bank;
        context.msr = 0x2032;
        experimentResetCode = false;
        bat_memory_write32(context, 0x80492240, 1);
        bat_memory_write32(context, 0x80492244, 7);
        context.pc = 0x802194e0;
        context.lr = 0x807f0000;
        func_802194E0(context);
        if (context.pc != 0x807f0000 || context.gpr[3] != 0x80000007 || experimentResetCodeReads) { return 13; }
        std::cout << "RESET_GUARDS 7 WARM_DISABLED_RETURN\n";
        return 0;
    }
    experimentResetCode = true;
    const std::array<uint32_t, 8> values{0, 1, 7, 8, 0x7fffffff, 0x80000000, 0xffffffff, 0x12345678};
    for (unsigned index = 0; index < 16; ++index) {
        const uint32_t flag = index % 2 == 0 ? 0 : index < 8 ? 1 : 0x80000000;
        const uint32_t value = values[index / 2];
        context.gpr.fill(0);
        context.gpr[1] = 0x80540000;
        context.gpr[2] = 0x805335e0;
        context.gpr[13] = 0x8052e720;
        context.gpr[30] = 0xc0680000 + index * 736;
        context.gpr[31] = 0x55660000 + index;
        bat_memory_write32(context, 0x80492240, flag);
        bat_memory_write32(context, 0x80492244, value);
        context.pc = 0x802194e0;
        context.lr = 0x807f0000;
        experimentResetCodeReads = 0;
        func_802194E0(context);
        std::cout << "RESET_CASE " << index << ' ' << context.gpr[3] << ' ' << context.gpr[0] << ' ' << context.msr;
        for (unsigned reg : {1u, 2u, 13u, 30u, 31u}) { std::cout << ' ' << context.gpr[reg]; }
        std::cout << ' ' << context.pc << ' ' << bat_memory_read32(context, 0x80492240) << ' '
                  << bat_memory_read32(context, 0x80492244) << ' ' << MMIODispatcher::get().read32(0xcc003024)
                  << ' ' << experimentResetCodeReads << '\n';
    }
    return 0;
}
