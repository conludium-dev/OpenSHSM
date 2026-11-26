int main(int argc, char** argv) {
    using namespace nwii::runtime;
    if (argc != 2) { return 2; }
    nwii::loader::Executable executable;
    if (!executable.load_dol(argv[1])) { return 3; }
    SeededBatContext context;
    for (const auto& section : executable.sections) {
        std::copy(section.data.begin(), section.data.end(), context.mmu.get_ptr(section.address));
        if (section.is_text) { context.instructionImages.emplace_back(section.address, section.data); }
    }
    hw::register_pi(MMIODispatcher::get());
    g_trace_calls = false;
    auto prepare = [&] {
        hw::experiment_ipc_control_no_request(6);
        hw::pi_intsr = 0x10000;
        hw::pi_intmr = 0x40f8;
        context.pc = 0x80241c30;
        context.lr = 0x80242140;
        context.msr = 0xa032;
        context.hid0 = 0xc200;
        context.gpr.fill(0);
        context.gpr[1] = 0x80540000;
        context.gpr[2] = 0x805335e0;
        context.gpr[13] = 0x8052e720;
        context.gpr[3] = 1;
        context.gpr[4] = 0x38;
        experimentIpcStartup = true;
    };
    for (unsigned index = 0; index < 16; ++index) {
        prepare();
        const auto before = hw::experiment_ipc_snapshot();
        const auto causeBefore = hw::pi_intsr.load();
        func_80241C30(context);
        const auto after = hw::experiment_ipc_snapshot();
        if (context.pc != 0x80242140 || experimentIpcStartupWrites != index + 1) { return 4; }
        std::cout << "IPC_STARTUP_CASE " << index << ' ' << before.ppcControl << ' ' << causeBefore << ' ' << context.gpr[0]
                  << ' ' << context.gpr[3] << ' ' << context.gpr[4] << ' ' << context.gpr[1] << ' ' << context.gpr[2]
                  << ' ' << context.gpr[13] << ' ' << context.pc << ' ' << context.msr << ' ' << after.ppcControl
                  << ' ' << hw::pi_intsr.load() << ' ' << hw::pi_intmr.load() << '\n';
    }
    for (unsigned test = 0; test < 10; ++test) {
        prepare();
        if (test == 0) { experimentIpcStartup = false; }
        if (test == 1) { context.pc = 0x80241c34; }
        if (test == 2) { context.lr = 0x807f0000; }
        if (test == 3) { context.msr = 0x2032; }
        if (test == 4) { context.hid0 = 0x8200; }
        if (test == 5) { hw::pi_intsr = 0x14000; }
        if (test == 6) { hw::pi_intmr = 0xf8; }
        if (test == 7) { context.vblank_pending = true; }
        if (test == 8) { context.callback_depth = 1; }
        const auto snapshot = [&] {
            const auto ipc = hw::experiment_ipc_snapshot();
            return std::array<uint64_t, 9>{ipc.ppcMessage, ipc.armMessage, ipc.ppcControl, ipc.armControl,
                ipc.ppcMask, uint64_t(ipc.delay), hw::pi_intsr.load(), hw::pi_intmr.load(), experimentIpcStartupWrites};
        };
        const auto before = snapshot();
        bool refused = false;
        try { experiment_ipc_startup_store(context, 0xcd000004, test == 9 ? 1 : 0x38); }
        catch (const std::runtime_error&) { refused = true; }
        if (!refused || snapshot() != before) { return 5; }
        context.vblank_pending = false;
        context.callback_depth = 0;
    }
    std::cout << "IPC_STARTUP_GUARDS 10\n";
    return 0;
}
