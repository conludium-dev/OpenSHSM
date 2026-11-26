extern "C" void run_game(nwii::runtime::CPUContext&);
namespace nwii::runtime {
extern MMU* g_mmu;
extern CPUContext* g_ctx_ptr;
}

int main(int argc, char** argv) {
    using namespace nwii::runtime;
    if (argc < 2 || argc > 3) { return 2; }
    const std::string mode = argc == 3 ? argv[2] : "normal";
    if (mode != "normal" && mode != "lost-dma" && mode != "lost-mail" && mode != "wrong-mail") { return 2; }
    nwii::loader::Executable executable;
    if (!executable.load_dol(argv[1])) { return 3; }
    SeededBatContext context;
    for (const auto& section : executable.sections) {
        std::copy(section.data.begin(), section.data.end(), context.mmu.get_ptr(section.address));
        if (section.is_text) { context.instructionImages.emplace_back(section.address, section.data); }
    }
    hw::register_pi(MMIODispatcher::get());
    hw::register_dsp(MMIODispatcher::get());
    hw::experiment_register_ipc_clock_profile(MMIODispatcher::get());
    g_trace_calls = false;
    context.hid0 = 0xc200;
    context.hid2 = 0xa0000000;
    context.flushSyscall = true;
    context.msr = 0x2032;
    for (unsigned index = 0; index < 7; ++index) {
        bat_memory_write32(context, 0xc0000c00 + index * 4, bat_memory_read32(context, 0x8021a120 + index * 4));
    }
    bat_memory_write32(context, 0x800000f8, 243000000);
    hw::experimentPcClock = {};
    hw::experimentPcClock.enabled = true;
    for (unsigned test = 0; test < 3; ++test) {
        hw::experimentPcClock.audioStartupFp = test != 0;
        context.msr = test == 2 ? 0x2030 : 0x2032;
        bool refused = false;
        try { experiment_ai_clock_read32(context, 0xcd800180, 0x80212ae8); }
        catch (const std::runtime_error&) { refused = true; }
        if (refused != (test != 1) || hw::experimentPcClock.phase) { return 12; }
    }
    std::cout << "AUDIO_CLOCK_GUARDS 3\n";
    for (unsigned index = 0; index < (mode == "normal" ? 16u : 1u); ++index) {
        EventScheduler::get().reset();
        hw::experiment_dsp_startup_reset();
        hw::experimentDspStartup.enabled = true;
        hw::experimentDspStartup.lostDma = mode == "lost-dma";
        hw::experimentDspStartup.lostMail = mode == "lost-mail";
        hw::experimentDspStartup.wrongMail = mode == "wrong-mail";
        hw::experimentPcClock = {};
        hw::experimentPcClock.enabled = true;
        hw::experimentPcClock.audioStartupFp = true;
        context.msr = 0x2032;
        context.gpr.fill(0);
        context.gpr[1] = 0x80540000;
        context.gpr[2] = 0x805335e0;
        context.gpr[13] = 0x8052e720;
        context.gpr[30] = 0xc0680000 + index * 736;
        context.gpr[31] = 0x55660000 + index;
        bat_memory_write32(context, 0x8052aa98, 0x81700000);
        bat_memory_write32(context, 0x8052aa38, index % 2);
        for (unsigned offset = 0; offset < 128; offset += 4) {
            bat_memory_write32(context, 0x81000000 + offset, (index + 1) * 0x1020304u + offset * 0x01010101u);
        }
        context.pc = 0x80212ce0;
        context.lr = 0x807f0000;
        context.inst_count = 0;
        context.is_running = true;
        bootPollChecks = 0;
        bool returned = false;
        try { run_game(context); }
        catch (const std::runtime_error& failure) {
            returned = context.pc == 0x807f0000 && std::string(failure.what()) == "Audio oracle return sentinel";
            if (!returned) {
                std::cout << "AUDIO_STOP " << mode << ' ' << context.pc << ' ' << hw::experimentDspStartup.command
                          << ' ' << hw::experimentDspStartup.completedDmas << ' ' << failure.what() << '\n';
                return mode == "normal" ? 10 : 0;
            }
        }
        if (!returned) { return 11; }
        std::cout << "AUDIO_CASE " << index << ' ' << context.msr << ' ' << context.hid0;
        for (unsigned reg : {1u, 2u, 13u, 30u, 31u}) { std::cout << ' ' << context.gpr[reg]; }
        std::cout << ' ' << context.pc;
        for (uint32_t offset : {0x12u, 0xau, 4u, 6u, 0x20u, 0x22u, 0x24u, 0x26u, 0x28u, 0x2au}) {
            std::cout << ' ' << hw::experiment_dsp_startup_read(context, 0xcc005000 + offset, 2);
        }
        std::cout << ' ' << bat_memory_read32(context, 0x800000f8) << '\n';
        std::cout << "AUDIO_MEMORY " << index;
        for (uint32_t address : {0x81000000u, 0xc1000000u, 0x816fff80u, 0xd0000000u}) {
            for (unsigned offset = 0; offset < (address == 0xd0000000 ? 32u : 128u); offset += 4) {
                std::cout << ' ' << bat_memory_read32(context, address + offset);
            }
        }
        std::cout << '\n';
        for (unsigned number = 0; number < hw::experimentDspStartup.accesses.size(); ++number) {
            const auto& access = hw::experimentDspStartup.accesses[number];
            std::cout << "AUDIO_ACCESS " << index;
            for (auto value : access) { std::cout << ' ' << value; }
            std::cout << ' ' << hw::experimentDspStartup.accessTicks.at(number) << '\n';
        }
        if (g_mmu || g_ctx_ptr) { return 13; }
    }
    return 0;
}
