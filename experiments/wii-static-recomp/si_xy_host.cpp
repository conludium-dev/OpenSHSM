int main(int argc, char** argv) {
    using namespace nwii::runtime;
    if (argc != 2) {
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
    hw::experiment_register_si_xy(MMIODispatcher::get());
    hw::pi_intsr = 0x10000;
    g_trace_calls = false;
    memory_context(context).hid0 = 0xc200;
    context.hid2 = 0xa0000000;
    for (unsigned index = 0; index < 16; ++index) {
        context.gpr.fill(0);
        context.gpr[1] = 0x80540000;
        context.gpr[2] = 0x805335e0;
        context.gpr[13] = 0x8052e720;
        context.gpr[3] = index < 8 ? 492 : 28;
        context.gpr[4] = index < 8 ? 2 : 19;
        context.msr = 0x2030;
        context.lr = 0x807f0000;
        context.pc = 0x8020feb0;
        context.inst_count = 0;
        context.is_running = true;
        bootPollChecks = 0;
        bat_memory_write32(context, 0x8042b6f4, (index % 8) * 0x04000001);
        func_8020FEB0(context);
        if (context.pc != 0x807f0000 || context.msr != 0x2030) {
            return 11;
        }
        std::cout << "SI_XY_CASE " << index << ' ' << context.gpr[3] << ' '
                  << MMIODispatcher::get().read32(0xcd006430) << ' '
                  << bat_memory_read32(context, 0x8042b6f4) << ' ' << context.msr << '\n';
    }
    const std::array<std::function<void()>, 5> invalid{
        [&] { MMIODispatcher::get().write32(0xcd006431, 0x01ec0200); },
        [&] { MMIODispatcher::get().write32(0xcd006430, 0); },
        [&] { MMIODispatcher::get().read16(0xcd006430); },
        [&] { MMIODispatcher::get().write16(0xcd006430, 0); },
        [&] { context.msr = 0; experiment_si_xy_write32(context, 0xcd006430, 0x01ec0200, 0x8020feec); }
    };
    for (const auto& test : invalid) {
        const auto before = hw::experimentSiPoll;
        bool refused = false;
        try {
            test();
        } catch (const std::runtime_error&) {
            refused = true;
        }
        if (!refused || before != hw::experimentSiPoll) {
            return 12;
        }
    }
    std::cout << "SI_XY_GUARDS 5\n";
    return 0;
}
