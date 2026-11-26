extern "C" void run_game(nwii::runtime::CPUContext&);
int main(int argc, char** argv) {
    using namespace nwii::runtime;
    if (argc != 2 && !(argc == 3 && std::string(argv[2]) == "guards")) { return 2; }
    nwii::loader::Executable executable;
    if (!executable.load_dol(argv[1])) { return 3; }
    SeededBatContext context;
    for (const auto& section : executable.sections) {
        std::copy(section.data.begin(), section.data.end(), context.mmu.get_ptr(section.address));
        if (section.is_text) { context.instructionImages.emplace_back(section.address, section.data); }
    }
    hw::register_pi(MMIODispatcher::get());
    hw::experiment_register_si_query(MMIODispatcher::get());
    hw::experimentSiQuery.interruptProfile = true;
    hw::pi_intsr = 0x10000;
    hw::pi_intmr = 0xf8;
    g_trace_calls = false;
    context.hid0 = 0xc200;
    context.hid2 = 0xa0000000;
    context.msr = 0x2030;
    for (unsigned index = 0; index < 38; ++index) {
        auto word = bat_memory_read32(context, 0x80211ba0 + index * 4);
        if (index == 26) { word = 0x38600004; }
        bat_memory_write32(context, 0x80000500 + index * 4, word);
    }
    for (const auto& seed : std::vector<std::array<uint32_t, 2>>{
            {0x800000c0, 0x492658}, {0x800000d4, 0x80492658}, {0x800000c4, 0xf7fff7f0}, {0x800000c8, 0},
            {0x80003010, 0x80217c60}, {0x8052aad8, 0x80003040}, {0x80003090, 0x8020f850},
            {0x8052ab00, 0}, {0x8052ab04, 0}}) {
        bat_memory_write32(context, seed[0], seed[1]);
    }
    if (argc == 3) {
        for (unsigned test = 0; test < 12; ++test) {
            context.pc = 0x807f0000;
            context.msr = 0xa032;
            context.is_running = true;
            context.vblank_pending = false;
            context.dec_irq_pending = false;
            hw::experimentSiQuery.interruptProfile = true;
            hw::pi_intsr = 0x10008;
            hw::pi_intmr = 0xf8;
            hw::experimentSiControl = 0xe0010300;
            bat_memory_write32(context, 0x800000c0, 0x492658);
            bat_memory_write32(context, 0x800000d4, 0x80492658);
            bat_memory_write32(context, 0x800000c4, 0xf7fff7f0);
            bat_memory_write32(context, 0x8052ab00, 0);
            bat_memory_write32(context, 0x80000568, 0x38600004);
            if (test == 0) { hw::pi_intmr = 8; }
            if (test == 1) { hw::pi_intsr = 0x10018; }
            if (test == 2) { bat_memory_write32(context, 0x800000c0, 0x501000); }
            if (test == 3) { bat_memory_write32(context, 0x800000d4, 0x80501000); }
            if (test == 4) { bat_memory_write32(context, 0x800000c4, 0xfffff7ff); }
            if (test == 5) { bat_memory_write32(context, 0x80000568, 0x38600000); }
            if (test == 6) { bat_memory_write32(context, 0x8052ab00, 1); }
            if (test == 7) { context.msr = 0xa030; }
            if (test == 8) { context.vblank_pending = true; }
            if (test == 9) { hw::experimentSiControl = 0x20010300; }
            if (test == 10) { context.dec_irq_pending = true; }
            if (test == 11) { hw::experimentSiQuery.interruptProfile = false; }
            const auto snapshot = [&] {
                return std::array<uint64_t, 8>{context.pc, context.msr, context.srr0, context.srr1,
                    siExternalEntries, hw::pi_intsr.load(), hw::pi_intmr.load(), hw::experimentSiControl};
            };
            const auto before = snapshot();
            const auto registers = context.gpr;
            bool refused = false;
            try { experiment_boot_poll(context); } catch (const std::runtime_error&) { refused = true; }
            if (!refused || before != snapshot() || registers != context.gpr) { return 7; }
        }
        std::cout << "SI_QUEUE_GUARDS 12\n";
        return 0;
    }
    for (unsigned index = 0; index < 16; ++index) {
        context.gpr.fill(0);
        context.msr = 0x2030;
        context.gpr[1] = 0x80540000;
        context.gpr[2] = 0x805335e0;
        context.gpr[13] = 0x8052e720;
        context.gpr[3] = index % 4;
        context.gpr[4] = 0x80500000;
        context.gpr[5] = 1;
        context.gpr[6] = 0x80500010;
        context.gpr[7] = 3;
        context.gpr[8] = 0x80210110;
        context.pc = 0x8020fd00;
        context.lr = 0x807f0000;
        context.inst_count = 0;
        context.is_running = true;
        context.scriptedClock = true;
        context.clockSamples.assign(512, 800000);
        context.clockSampleIndex = 0;
        bootPollChecks = 0;
        bat_memory_write32(context, 0x8042b6f0, 0xffffffff);
        for (unsigned offset = 4; offset <= 16; offset += 4) { bat_memory_write32(context, 0x8042b6f0 + offset, 0); }
        for (unsigned port = 0; port < 4; ++port) {
            bat_memory_write32(context, 0x80492010 + port * 32, 0xffffffff);
            bat_memory_write32(context, 0x8042b708 + port * 4, 0x80);
        }
        bat_memory_write32(context, 0x80500000, 0);
        bat_memory_write32(context, 0x80500010, 0xa5a5a5a5);
        func_8020FD00(context);
        if (context.pc != 0x807f0000 || context.gpr[3] != 1) { return 4; }
        for (unsigned offset = 0; offset < queueContextWords.size(); ++offset) {
            bat_memory_write32(context, 0x80492658 + offset * 4, queueContextWords[offset]);
        }
        bat_memory_write32(context, 0x800000d8, 0x80492658);
        for (unsigned port = 0; port < 4; ++port) {
            if (port == index % 4) { continue; }
            const std::array<uint32_t, 8> packet{port, 0x8052aa28, 1, 0x8042b708 + port * 4, 3, 0x80210110, 0, 0xf6c};
            for (unsigned offset = 0; offset < packet.size(); ++offset) {
                bat_memory_write32(context, 0x80492010 + port * 32 + offset * 4, packet[offset]);
            }
        }
        context.pc = 0x807f0000;
        context.lr = 0x807f0000;
        context.gpr[30] = 0xc0680000 + index * 736;
        context.msr = 0xa032;
        try { run_game(context); return 5; }
        catch (const std::runtime_error& failure) {
            if (context.pc != 0x807f0000 || std::string(failure.what()) != "SI IRQ oracle return sentinel") {
                std::cerr << "SI_QUEUE_STOP pc=" << std::hex << context.pc << " msr=" << context.msr << std::dec << ' ' << failure.what() << '\n';
                return 6;
            }
        }
        std::cout << "SI_QUEUE_CASE " << index << ' ' << context.msr << ' '
                  << bat_memory_read32(context, 0x804927f0) << ' ' << bat_memory_read32(context, 0x804927f4) << ' '
                  << bat_memory_read32(context, 0x8049265c) << ' ' << bat_memory_read32(context, 0x80492660) << ' '
                  << bat_memory_read32(context, 0x8049268c) << ' ' << bat_memory_read32(context, 0x804926d0) << ' '
                  << bat_memory_read16(context, 0x804927fa);
        for (unsigned port = 0; port < 4; ++port) { std::cout << ' ' << bat_memory_read32(context, 0x8042b708 + port * 4); }
        for (unsigned port = 0; port < 4; ++port) { std::cout << ' ' << bat_memory_read32(context, 0x80492010 + port * 32); }
        for (uint32_t address : {0x8042b6f0u, 0x8042b700u, 0x800000d8u}) { std::cout << ' ' << bat_memory_read32(context, address); }
        std::cout << ' ' << hw::pi_intsr.load() << ' ' << hw::experimentSiQuery.callbackCount << ' ' << siExternalEntries << '\n';
    }
    return 0;
}
