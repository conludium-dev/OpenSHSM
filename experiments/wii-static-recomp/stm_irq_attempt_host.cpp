namespace nwii::runtime {
bool process_pending_callbacks(CPUContext& context) {
    if (context.inst_count > 100000) { throw std::runtime_error("IPC IRQ instruction budget"); }
    if (context.pc == 0x807f0000 && siExternalEntries && !(hw::pi_intsr.load() & hw::pi_intmr.load())) {
        throw std::runtime_error("Original ACK returned; reply producer not activated");
    }
    return experiment_boot_poll(context);
}
}

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
    g_trace_calls = false;
    context.msr = 0x2032;
    context.hid0 = 0xc200;
    context.hid2 = 0xa0000000;
    for (unsigned index = 0; index < 38; ++index) {
        auto word = bat_memory_read32(context, 0x80211ba0 + index * 4);
        bat_memory_write32(context, 0x80000500 + index * 4, index == 26 ? 0x38600004 : word);
    }
    for (unsigned index = 0; index < ipcThreadWords.size(); ++index) {
        bat_memory_write32(context, 0x80492658 + index * 4, ipcThreadWords[index]);
    }
    for (const auto& seed : std::vector<std::array<uint32_t, 2>>{
        {0x800000c0, 0x492658}, {0x800000c4, 0xf7fff7e0}, {0x800000c8, 0}, {0x800000d4, 0x80492658},
        {0x800000d8, 0x80492658}, {0x800000e4, 0x80492658}, {0x80003010, 0x80217c60},
        {0x8052aad8, 0x80003040}, {0x800030ac, 0x80241f00}, {0x8052ab00, 0}, {0x8052ab04, 0}, {0x8052ab08, 0},
        {0x80528b70, 0}, {0x804b2a80, 1}, {0x804b2a84, 1}, {0x804b2a88, 1}, {0x804b2a8c, 1}}) {
        bat_memory_write32(context, seed[0], seed[1]);
    }
    hw::register_pi(MMIODispatcher::get());
    hw::experimentSiQuery.interruptProfile = true;
    hw::pi_intsr = 0x14000;
    hw::pi_intmr = 0x40f8;
    hw::ipc_ppc_ctrl = 0x32;
    hw::experimentPpcFlags = 0x40000000;
    hw::ipc_ppc_msg = 0x135e0020;
    hw::ipc_arm_msg = hw::ipc_arm_ctrl = 0;
    experimentStmIrq = true;
#ifdef SHSM_STM_ACK_MMIO
    if (argc == 3) {
        for (unsigned test = 0; test < 10; ++test) {
            experimentStmIrq = true;
            context.pc = test < 7 ? 0x80241c20 : test < 9 ? 0x80241c30 : 0x80241f68;
            context.lr = test < 7 ? 0x80241f24 : 0x80241f68;
            context.msr = 0x2030;
            context.hid0 = 0xc200;
            hw::pi_intmr = 0x40f8;
            hw::ipc_ppc_ctrl = test == 9 ? 0x30 : 0x32;
            if (test == 0) { experimentStmIrq = false; }
            if (test == 1) { context.msr = 0xa032; }
            if (test == 2 || test == 8) { context.lr = 0x807f0000; }
            if (test == 4) { hw::pi_intmr = 0xf8; }
            if (test == 5) { hw::ipc_ppc_ctrl = 0x34; }
            if (test == 6) { context.hid0 = 0xc208; }
            const auto snapshot = [&] {
                const auto state = hw::experiment_ipc_snapshot();
                return std::array<uint64_t, 12>{state.ppcMessage, state.armMessage, state.ppcControl, state.armControl,
                    state.ppcMask, uint64_t(state.delay), hw::pi_intsr.load(), hw::pi_intmr.load(),
                    hw::experiment_ipc_irq_snapshot().ppcFlags, context.srr0, context.srr1, siExternalEntries};
            };
            const auto before = snapshot();
            bool refused = false;
            try {
                if (test < 7) { experiment_ipc_ack_read(context, test == 3 ? 0xcd000008 : 0xcd000004); }
                else if (test < 9) { experiment_ipc_ack_write(context, 0xcd000004, test == 7 ? 0x31 : 0x32); }
                else { experiment_ipc_ack_clear(context, 0xcd000030, 0); }
            } catch (const std::runtime_error&) { refused = true; }
            if (!refused || before != snapshot()) { return 9; }
        }
        std::cout << "IPC_ACK_GUARDS 10\n";
        return 0;
    }
#else
    if (argc == 3) { return 2; }
#endif
    context.gpr[1] = 0x80540000;
    context.gpr[2] = 0x805335e0;
    context.gpr[13] = 0x8052e720;
    context.gpr[30] = 0xc0680000;
    context.msr = 0xa032;
    context.pc = context.lr = 0x807f0000;
    context.is_running = true;
    try { run_game(context); }
    catch (const std::runtime_error& failure) {
        std::cout << "IPC_NATIVE_BOUNDARY pc=" << std::hex << context.pc << " lr=" << context.lr << " msr=" << context.msr
            << " r0=" << context.gpr[0] << " r3=" << context.gpr[3] << " r4=" << context.gpr[4] << std::dec
            << " entries=" << siExternalEntries << " reason=" << failure.what() << '\n';
        const auto ipc = hw::experiment_ipc_snapshot();
        std::cout << "IPC_ACK_STATE " << context.pc << ' ' << context.msr << ' ' << context.srr0 << ' ' << context.srr1
            << ' ' << context.gpr[1] << ' ' << context.gpr[2] << ' ' << context.gpr[13] << ' ' << context.gpr[30]
            << ' ' << ipc.ppcControl << ' ' << ipc.ppcMessage << ' ' << ipc.armMessage << ' ' << hw::pi_intsr.load()
            << ' ' << hw::pi_intmr.load() << ' ' << bat_memory_read32(context, 0x80528b70)
            << ' ' << bat_memory_read32(context, 0x8052ab00) << ' ' << bat_memory_read32(context, 0x800000e4)
            << ' ' << bat_memory_read16(context, 0x8052aacc) << '\n';
        return 7;
    }
    return 8;
}
