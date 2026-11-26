int main(int argc, char** argv) {
    using namespace nwii::runtime;
    if (argc < 2 || argc > 3) { return 2; }
    const std::string mode = argc == 3 ? argv[2] : "normal";
    if (mode != "normal" && mode != "stalled" && mode != "guards") { return 2; }
    nwii::loader::Executable executable;
    if (!executable.load_dol(argv[1])) { return 3; }
    SeededBatContext context;
    for (const auto& section : executable.sections) {
        std::copy(section.data.begin(), section.data.end(), context.mmu.get_ptr(section.address));
        if (section.is_text) { context.instructionImages.emplace_back(section.address, section.data); }
    }
    hw::experiment_register_ipc_clock_profile(MMIODispatcher::get());
    auto& profile = hw::experimentPcClock;
    profile.enabled = true;
    g_trace_calls = false;
    context.msr = 0x32;
    context.hid2 = 0xa0000000;
    memory_context(context).hid0 = 0xc200;
    bat_memory_write32(context, 0x800000f8, 243000000);
    if (mode == "guards") {
        const auto snapshot = [&] { return std::array<size_t, 3>{profile.mode, profile.phase, profile.writes.size()}; };
        const std::array<std::function<void()>, 8> invalid{
            [&] { MMIODispatcher::get().write32(0xcd800180, 0x200); },
            [&] { MMIODispatcher::get().write32(0xcd8001cc, 0x04640fc0); },
            [&] { MMIODispatcher::get().read16(0xcd800180); },
            [&] { MMIODispatcher::get().write16(0xcd8001d0, 0); },
            [&] { experiment_ai_clock_read32(context, 0xcd800180, 0x80212aec); },
            [&] { experiment_ai_clock_write32(context, 0xcd800180, 0, 0x80212b04); },
            [&] { context.msr = 0x2030; experiment_ai_clock_read32(context, 0xcd800180, 0x80212ae8); },
            [&] { profile.enabled = false; experiment_ai_clock_read32(context, 0xcd800180, 0x80212ae8); }
        };
        for (const auto& test : invalid) {
            context.msr = 0x32;
            profile.enabled = true;
            const auto before = snapshot();
            bool refused = false;
            try { test(); } catch (const std::runtime_error&) { refused = true; }
            if (!refused || snapshot() != before) { return 14; }
        }
        std::cout << "AI_CLOCK_GUARDS 8\n";
        return 0;
    }
    for (unsigned index = 0; index < 16; ++index) {
        context.gpr.fill(0);
        context.gpr[1] = 0x80540000;
        context.gpr[2] = 0x805335e0;
        context.gpr[13] = 0x8052e720;
        context.gpr[30] = 0xc0680000 + index * 736;
        context.gpr[3] = index % 2;
        context.msr = 0x32;
        context.pc = 0x80212ac0;
        context.lr = 0x807f0000;
        context.is_running = true;
        context.inst_count = 0;
        bootPollChecks = 0;
        profile.phase = 0;
        profile.writes.clear();
        profile.timestamps.clear();
        context.scriptedClock = mode == "stalled";
        context.clockSampleIndex = 0;
        context.clockSamples.assign(100010, 0);
        const auto begin = experiment_read_timebase(context);
        try { func_80212AC0(context); }
        catch (const std::runtime_error& error) {
            std::cout << "AI_CLOCK_BOUNDARY " << error.what() << " phase=" << profile.phase << '\n';
            return 20;
        }
        const auto end = experiment_read_timebase(context);
        if (context.pc != 0x807f0000 || context.msr != 0x32 || profile.phase != 6 || end - begin < 194400) { return 12; }
        std::cout << "AI_CLOCK_CASE " << index << ' ' << profile.mode << ' ' << context.msr << ' ' << context.gpr[1] << ' '
            << context.gpr[2] << ' ' << context.gpr[13] << ' ' << context.gpr[30];
        for (const auto& write : profile.writes) {
            for (auto value : write) { std::cout << ' ' << value; }
        }
        std::cout << " AI_CLOCK_TIMES";
        for (const auto timestamp : profile.timestamps) { std::cout << ' ' << timestamp; }
        std::cout << ' ' << end;
        std::cout << " ticks=" << end - begin << '\n';
    }
    return 0;
}
