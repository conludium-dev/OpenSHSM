int main(int argc, char** argv) {
    using namespace nwii::runtime;
    if (argc < 2 || argc > 3) {
        return 2;
    }
    const std::string mode = argc == 3 ? argv[2] : "normal";
    if (mode != "normal" && mode != "lost" && mode != "wrong" && mode != "guards") {
        return 2;
    }
    nwii::loader::Executable executable;
    if (!executable.load_dol(argv[1])) {
        return 3;
    }
    SeededBatContext context;
    for (const auto& section : executable.sections) {
        std::copy(section.data.begin(), section.data.end(), context.mmu.get_ptr(section.address));
        if (section.is_text) {
            context.instructionImages.emplace_back(section.address, section.data);
        }
    }
    hw::register_pi(MMIODispatcher::get());
    hw::experiment_register_si_query(MMIODispatcher::get());
    hw::pi_intsr = 0x10000;
    g_trace_calls = false;
    memory_context(context).hid0 = 0xc200;
    context.hid2 = 0xa0000000;
    context.scriptedClock = true;
    context.clockSamples.assign(192, 0);
    if (mode == "guards") {
        context.msr = 0x2030;
        const auto snapshot = [] {
            return std::array<uint32_t, 6>{hw::experimentSiControl, hw::experimentSiControlWritten, hw::experimentSiQuery.status,
                hw::experimentSiQuery.buffer, uint32_t(hw::experimentSiQuery.payloadReady), hw::pi_intsr.load()};
        };
        const std::array<std::function<void()>, 8> invalid{
            [&] { MMIODispatcher::get().write32(0xcd006434, 0x80010301); },
            [&] { MMIODispatcher::get().write32(0xcd006480, 1); },
            [&] { MMIODispatcher::get().write32(0xcd006438, 0x10000000); },
            [&] { MMIODispatcher::get().read16(0xcd006434); },
            [&] { MMIODispatcher::get().write16(0xcd006480, 0); },
            [&] { experiment_si_query_read32(context, 0xcd006438, 0x8020fd5c); },
            [&] { experiment_si_query_write32(context, 0xcd006434, 0x80010301, 0x8020fe90); },
            [&] { context.msr = 0; experiment_si_query_read32(context, 0xcd006438, 0x8020fd58); }
        };
        for (const auto& test : invalid) {
            const auto before = snapshot();
            bool refused = false;
            try {
                test();
            } catch (const std::runtime_error&) {
                refused = true;
            }
            if (!refused || before != snapshot()) {
                return 14;
            }
        }
        std::cout << "SI_QUERY_GUARDS 8\n";
        return 0;
    }
    hw::experimentSiQuery.loseCompletion = mode == "lost";
    hw::experimentSiQuery.wrongResponse = mode == "wrong";
    for (unsigned index = 0; index < 16; ++index) {
        const auto channel = index % 4;
        context.gpr.fill(0);
        context.gpr[1] = 0x80540000;
        context.gpr[2] = 0x805335e0;
        context.gpr[13] = 0x8052e720;
        context.gpr[3] = channel;
        context.gpr[4] = 0x80500000;
        context.gpr[5] = 1;
        context.gpr[6] = 0x80500010;
        context.gpr[7] = 3;
        context.gpr[8] = 0;
        context.msr = 0x2030;
        context.lr = 0x807f0000;
        context.pc = 0x8020fd00;
        context.inst_count = 0;
        context.clockSampleIndex = 0;
        context.is_running = true;
        bootPollChecks = 0;
        bat_memory_write32(context, 0x8042b6f0, 0xffffffff);
        for (unsigned offset = 4; offset <= 16; offset += 4) {
            bat_memory_write32(context, 0x8042b6f0 + offset, 0);
        }
        bat_memory_write32(context, 0x8042b708 + channel * 4, 0x80);
        bat_memory_write32(context, 0x80500000, 0);
        bat_memory_write32(context, 0x80500010, 0xa5a5a5a5);
        const auto pi_before = hw::pi_intsr.load();
        func_8020FD00(context);
        if (context.pc != 0x807f0000 || context.msr != 0x2030) {
            return 11;
        }
        const auto started = context.gpr[3];
        const auto command = hw::experimentSiControlWritten;
        const auto control = hw::experimentSiControl;
        const auto status = hw::experimentSiQuery.status;
        const auto buffer = hw::experimentSiQuery.buffer;
        unsigned polls = 0;
        while (MMIODispatcher::get().read32(0xcd006434) & 1u) {
            if (++polls > 100000) {
                std::cout << "SI_QUERY_LOST_COMPLETION polls=" << polls << '\n';
                return 20;
            }
        }
        const auto done_control = hw::experimentSiControl;
        const auto done_status = hw::experimentSiQuery.status;
        const auto owner = bat_memory_read32(context, 0x8042b6f0);
        const auto pi_done = hw::pi_intsr.load();
        context.pc = 0x8020f550;
        context.lr = 0x807f0000;
        func_8020F550(context);
        if (context.pc != 0x807f0000 || context.msr != 0x2030) {
            return 12;
        }
        const auto result = context.gpr[3];
        const auto type_before_callback = bat_memory_read32(context, 0x8042b708 + channel * 4);
        const auto response = bat_memory_read32(context, 0x80500010);
        const auto after_control = hw::experimentSiControl;
        const auto after_status = hw::experimentSiQuery.status;
        const auto after_owner = bat_memory_read32(context, 0x8042b6f0);
        context.pc = 0x80210110;
        context.lr = 0x807f0000;
        context.gpr[3] = channel;
        context.gpr[4] = result;
        func_80210110(context);
        if (context.pc != 0x807f0000 || context.msr != 0x2030) {
            return 13;
        }
        std::cout << "SI_QUERY_CASE " << index << ' ' << started << ' ' << control << ' ' << status << ' ' << buffer
                  << ' ' << done_control << ' ' << done_status << ' ' << result << ' ' << type_before_callback << ' ' << response
                  << ' ' << after_control << ' ' << after_status << ' ' << owner << ' ' << after_owner << ' ' << pi_before
                  << ' ' << pi_done << ' ' << command << " 0 " << bat_memory_read32(context, 0x8042b708 + channel * 4) << '\n';
    }
    return 0;
}
