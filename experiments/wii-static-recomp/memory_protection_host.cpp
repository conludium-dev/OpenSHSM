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
    hw::experiment_register_mi_mask(MMIODispatcher::get());
    hw::experiment_register_mi_protection(MMIODispatcher::get());
    g_trace_calls = false;
    context.hid0 = 0xc200;
    context.hid2 = 0xa0000000;
    if (argc == 3) {
        auto snapshot = [&] {
            std::ostringstream result;
            result << context.msr << ' ' << context.pc << ' ' << context.srr0 << ' ' << context.srr1 << ' ' << context.lr << ' '
                   << experimentMemoryProtection.enabled << ' ' << experimentMemoryProtection.phase << ' '
                   << experimentMemoryProtection.realOwner << ' ' << experimentMemoryProtection.realTarget << ' '
                   << experimentMemoryProtection.realStep << ' ' << experimentMemoryProtection.realEntries << ' '
                   << experimentMemoryProtection.writes.size() << ' ' << hw::experimentMiMask << ' '
                   << hw::experimentMiProtection << ' ' << hw::experimentMiUnknown20;
            for (const auto* bank : {&context.ibat, &context.dbat}) {
                for (const auto& pair : *bank) { result << ' ' << pair.upper << ' ' << pair.lower; }
            }
            return result.str();
        };
        auto refuse = [&](const std::function<void()>& operation) {
            const auto before = snapshot();
            bool refused = false;
            try { operation(); } catch (const std::runtime_error&) { refused = true; }
            if (!refused || before != snapshot()) { throw std::runtime_error("MI guard accepted or changed state"); }
        };
        for (unsigned test = 0; test < 6; ++test) {
            experimentMemoryProtection = {};
            experimentMemoryProtection.enabled = test != 4;
            context.msr = test == 3 ? 0x2030 : 0x2032;
            refuse([&] {
                if (test == 5) { MMIODispatcher::get().write32(0xcc004020, 0); }
                else { experiment_memory_protection_write16(context, test == 2 ? 0xcc004022 : 0xcc004020,
                    test == 1 ? 1 : 0, test == 0 ? 0x802186bc : 0x802186ac); }
            });
        }
        const uint32_t originalWord = context.mmu.read32(0x00218070);
        auto prepare = [&] {
            experimentMemoryProtection = {};
            experimentMemoryProtection.enabled = true;
            experimentMemoryProtection.phase = 2;
            context.msr = 0x2032;
            context.pc = 0x802184f0;
            context.srr0 = 0x00218070;
            context.srr1 = 0x2002;
            context.lr = 0x80218578;
            context.gpr[30] = 0x000ba2cf;
            context.mmu.write32(0x00218070, originalWord);
            for (const auto& seed : std::array<std::array<uint32_t, 2>, 4>{{
                {0x80003100, 0x01800000}, {0x80003104, 0x01800000}, {0x8000311c, 0x04000000}, {0x80003120, 0x93400000}}}) {
                bat_memory_write32(context, seed[0], seed[1]);
            }
        };
        for (unsigned test = 0; test < 8; ++test) {
            prepare();
            if (test == 0) { experimentMemoryProtection.enabled = false; }
            if (test == 1) { context.srr0 = 0x002181d0; }
            if (test == 2) { context.srr1 = 0x2000; }
            if (test == 3) { bat_memory_write32(context, 0x80003104, 0); }
            if (test == 4) { context.mmu.write32(0x00218070, originalWord ^ 1); }
            if (test == 5) { experimentMemoryProtection.realOwner = &context; }
            if (test == 6) { experimentMemoryProtection.realEntries = 1; }
            if (test == 7) { context.gpr[30] = 0x000ca2cf; }
            refuse([&] { experiment_memory_protection_real_enter(context); });
        }
        for (unsigned test = 0; test < 8; ++test) {
            prepare();
            experiment_memory_protection_real_enter(context);
            context.msr = test == 4 ? 0x2032 : 0x2002;
            context.pc = 0x80218070;
            if (test == 5) { experimentMemoryProtection.enabled = false; }
            if (test == 6) { experimentMemoryProtection.realOwner = nullptr; }
            if (test == 7) { experimentMemoryProtection.realStep = 1; }
            refuse([&] { experiment_memory_protection_bat_write(context, test == 3, test == 2 ? 1 : 0, false,
                test == 0 ? 1 : 0, test == 1 ? 0x8021809c : 0x80218098); });
        }
        for (unsigned test = 0; test < 4; ++test) {
            prepare();
            experiment_memory_protection_real_enter(context);
            context.pc = 0x80218070;
            context.msr = test == 3 ? 0x2032 : 0x2002;
            context.srr0 = test == 1 ? 0x80218574 : 0x80218578;
            context.srr1 = 0x2032;
            experimentMemoryProtection.realStep = test == 0 ? 0 : 12;
            refuse([&] { experiment_memory_protection_real_return(context, test == 2 ? 0x802181c0 : 0x802180ec); });
        }
        std::cout << "MI_GUARDS 26\n";
        return 0;
    }
    for (unsigned index = 0; index < 16; ++index) {
        context.msr = 0x2032;
        context.gpr.fill(0);
        context.gpr[1] = 0x80540000;
        context.gpr[2] = 0x805335e0;
        context.gpr[13] = 0x8052e720;
        context.gpr[30] = 0xc0680000 + index * 736;
        context.gpr[31] = 0x55660000 + index;
        if (index % 2 == 0) {
            experimentMemoryProtection = {};
            experimentMemoryProtection.enabled = true;
            for (const auto& seed : std::vector<std::array<uint32_t, 2>>{
                {0x8052aae0, 0}, {0x8052aad8, 0x80003040}, {0x8052aaf8, 0}, {0x8052aafc, 0},
                {0x800000c4, 0xfffffff0}, {0x800000c8, 0}, {0x80003100, 0x01800000}, {0x80003104, 0x01800000},
                {0x8000311c, 0x04000000}, {0x80003120, 0x93400000}, {0x8042cfd0, 0}, {0x8042cfd4, 0}}) {
                bat_memory_write32(context, seed[0], seed[1]);
            }
            for (unsigned offset = 0; offset < 128; offset += 4) { bat_memory_write32(context, 0x80003040 + offset, 0); }
        }
        std::cout << "MI_BEFORE " << index;
        for (const auto* bank : {&context.ibat, &context.dbat}) {
            for (unsigned i = 0; i < 4; ++i) { std::cout << ' ' << (*bank)[i].upper << ' ' << (*bank)[i].lower; }
        }
        for (const auto* bank : {&context.ibat, &context.dbat}) {
            for (unsigned i = 4; i < 8; ++i) { std::cout << ' ' << (*bank)[i].upper << ' ' << (*bank)[i].lower; }
        }
        std::cout << '\n';
        context.pc = 0x80218680;
        context.lr = 0x807f0000;
        context.inst_count = 0;
        context.is_running = true;
        bootPollChecks = 0;
        bool returned = false;
        try { run_game(context); }
        catch (const std::runtime_error& failure) {
            returned = context.pc == 0x807f0000 && std::string(failure.what()) == "MI oracle return sentinel";
            if (!returned) {
                std::cout << "MI_STOP " << std::hex << context.pc << ' ' << context.msr << std::dec << ' '
                          << experimentMemoryProtection.phase << ' ' << failure.what() << '\n';
                return 10;
            }
        }
        if (!returned) { return 11; }
        std::cout << "MI_CASE " << index << ' ' << context.msr << ' ' << context.hid0;
        for (unsigned reg : {1u, 2u, 13u, 30u, 31u}) { std::cout << ' ' << context.gpr[reg]; }
        std::cout << ' ' << context.pc << ' ' << context.hid4;
        for (uint32_t address : {0x8052aae0u, 0x800000c4u, 0x800000c8u, 0x8052aaf8u, 0x8052aafcu,
                0x8042cfd0u, 0x8042cfd4u, 0x80003040u, 0x80003044u, 0x80003048u, 0x8000304cu, 0x80003050u}) {
            std::cout << ' ' << bat_memory_read32(context, address);
        }
        for (uint32_t address : {0xcc004010u, 0xcc00401cu, 0xcc004020u}) { std::cout << ' ' << MMIODispatcher::get().read16(address); }
        std::cout << '\n';
        std::cout << "MI_AFTER " << index;
        for (const auto* bank : {&context.ibat, &context.dbat}) {
            for (unsigned i = 0; i < 4; ++i) { std::cout << ' ' << (*bank)[i].upper << ' ' << (*bank)[i].lower; }
        }
        for (const auto* bank : {&context.ibat, &context.dbat}) {
            for (unsigned i = 4; i < 8; ++i) { std::cout << ' ' << (*bank)[i].upper << ' ' << (*bank)[i].lower; }
        }
        std::cout << '\n';
        if (experimentMemoryProtection.phase != 3 || experimentMemoryProtection.realOwner || experimentMemoryProtection.realTarget ||
            experimentMemoryProtection.realStep || experimentMemoryProtection.realEntries != 2 || experimentMemoryProtection.writes.size() != 3) { return 12; }
        std::cout << "MI_COUNTS " << index << ' ' << experimentMemoryProtection.phase << ' '
                  << experimentMemoryProtection.writes.size() << ' ' << experimentMemoryProtection.realEntries << '\n';
    }
    return 0;
}
