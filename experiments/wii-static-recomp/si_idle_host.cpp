int main(int argc, char** argv) {
    using namespace nwii::runtime;
    if (argc != 2) {
        return 2;
    }
    SeededBatContext context;
    context.msr = 0x2030;
    memory_context(context).hid0 = 0xc200;
    context.hid2 = 0xa0000000;
    hw::register_pi(MMIODispatcher::get());
    hw::experiment_register_si_idle(MMIODispatcher::get());
    hw::pi_intsr = 0x10000;
    for (unsigned index = 0; index < 16; ++index) {
        const auto before = hw::experimentSiControl;
        const auto cause = hw::pi_intsr.load();
        context.inst_count = 0;
        experiment_si_idle_block(context);
        if (context.inst_count != 8) {
            return 11;
        }
        std::cout << "SI_IDLE_CASE " << index << ' ' << before << ' ' << hw::experimentSiControlWritten << ' '
                  << MMIODispatcher::get().read32(0xcd006434) << ' ' << cause << ' ' << hw::pi_intsr.load() << '\n';
    }
    const std::array<std::function<void()>, 7> invalid{
        [&] { MMIODispatcher::get().write32(0xcd006435, 0x80000000); },
        [&] { MMIODispatcher::get().write32(0xcd006434, 1); },
        [&] { MMIODispatcher::get().read16(0xcd006434); },
        [&] { MMIODispatcher::get().write16(0xcd006434, 0); },
        [&] { experiment_si_idle_read32(context, 0xcd006434, 0x8020fc9c); },
        [&] { experiment_si_idle_write32(context, 0xcd006434, 0x80000000, 0x8020fcac); },
        [&] { context.msr = 0; experiment_si_idle_read32(context, 0xcd006434, 0x8020fc98); }
    };
    for (const auto& test : invalid) {
        const std::array<uint32_t, 3> before{hw::experimentSiControl, hw::experimentSiControlWritten, hw::pi_intsr.load()};
        bool refused = false;
        try {
            test();
        } catch (const std::runtime_error&) {
            refused = true;
        }
        if (!refused || before != std::array<uint32_t, 3>{hw::experimentSiControl, hw::experimentSiControlWritten, hw::pi_intsr.load()}) {
            return 12;
        }
    }
    hw::experimentSiControl = 1;
    bool refused = false;
    try {
        MMIODispatcher::get().read32(0xcd006434);
    } catch (const std::runtime_error&) {
        refused = true;
    }
    if (!refused || hw::experimentSiControl != 1) {
        return 13;
    }
    std::cout << "SI_IDLE_GUARDS 8\n";
    return 0;
}
