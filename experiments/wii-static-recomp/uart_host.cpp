int main(int argc, char** argv) {
    using namespace nwii::runtime;
    if (argc < 2 || argc > 3) {
        return 2;
    }
    const std::string mode = argc == 3 ? argv[2] : "normal";
    if (mode != "normal" && mode != "lost" && mode != "full" && mode != "guards") {
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
    hw::experiment_register_exi_masks(MMIODispatcher::get());
    hw::experiment_register_getid_transfer(MMIODispatcher::get());
    hw::experimentExiTransfer.uartAllowed = true;
    hw::pi_intsr = 0x10000;
    g_trace_calls = false;
    memory_context(context).hid0 = 0xc200;
    context.hid2 = 0xa0000000;
    if (mode == "guards") {
        context.msr = 0x2030;
        hw::experiment_getid_csr_write(0xcd006800, 0x140);
        const auto snapshot = [] {
            const auto& state = hw::experimentExiTransfer;
            return std::array<uint32_t, 10>{hw::experimentExiMaskState[0], hw::experimentExiMaskState[1], hw::experimentExiMaskState[2],
                state.control, state.data, state.phase, state.command, state.uartCommand, hw::pi_intsr.load(), uint32_t(state.uartBytes.size())};
        };
        const std::array<std::function<void()>, 7> invalid{
            [&] { experiment_getid_write32(context, 0xcd006800, 0x120); },
            [&] { experiment_getid_write32(context, 0xcd006810, 0xb0000010); },
            [&] { experiment_getid_write32(context, 0xcd00680c, 0x35); },
            [&] { experiment_getid_write32(context, 0xcd006810, 0x41000000); },
            [&] { MMIODispatcher::get().read16(0xcd006810); },
            [&] { experiment_getid_write32(context, 0xcd006804, 0); },
            [&] { experiment_getid_write32(context, 0xcc003000, 0x10); }
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
                return 12;
            }
        }
        std::cout << "UART_GUARDS 7\n";
        return 0;
    }
    const std::array<std::string, 4> payloads{"O", "OS", "OS\n", "OSH\n"};
    for (unsigned index = 0; index < 16; ++index) {
        context.gpr.fill(0);
        context.gpr[1] = 0x80540000;
        context.gpr[2] = 0x805335e0;
        context.gpr[13] = 0x8052e720;
        context.gpr[3] = 0x80500000;
        context.gpr[4] = payloads[index & 3].size();
        context.msr = 0x2030;
        context.fpscr = index >= 8 ? 4 : 0;
        context.lr = 0x807f0000;
        context.pc = 0x80240320;
        context.inst_count = 0;
        context.is_running = true;
        bootPollChecks = 0;
        for (unsigned offset = 0; offset < 64; offset += 4) {
            bat_memory_write32(context, 0x80491f50 + offset, 0);
        }
        bat_memory_write32(context, 0x8052aa08, 0);
        hw::experiment_getid_csr_write(0xcd006800, 0);
        hw::experiment_getid_csr_write(0xcd006800, 0x2000);
        const auto before = hw::experimentExiMaskState[0];
        const auto controlBefore = hw::experimentExiTransfer.control;
        const auto dataBefore = hw::experimentExiTransfer.data;
        const auto causeBefore = hw::pi_intsr.load();
        if (index & 4) {
            hw::experiment_getid_csr_write(0xcd006800, 0x2800);
        }
        bat_memory_write32(context, 0x8052aa70, 0);
        bat_memory_write32(context, 0x8052afa4, 0xa5ff005a);
        bat_memory_write32(context, 0x8052ead8, 4);
        if (index % 8 == 0) {
            bat_memory_write32(context, 0x8052af98, 0);
        }
        bat_memory_write32(context, 0x80500000, 0);
        for (unsigned offset = 0; offset < payloads[index & 3].size(); ++offset) {
            bat_memory_write8(context, 0x80500000 + offset, uint8_t(payloads[index & 3][offset]));
        }
        hw::experimentExiTransfer.observations.clear();
        hw::experimentExiTransfer.uartBytes.clear();
        hw::experimentExiTransfer.loseCompletion = mode == "lost";
        hw::experimentExiTransfer.wrongResponse = mode == "full";
        try {
            func_80240320(context);
        } catch (const std::runtime_error& failure) {
            std::cerr << "UART_BOUNDARY " << std::hex << context.pc << ' ' << failure.what() << '\n';
            return mode == "lost" && (hw::experimentExiTransfer.control & 1) ? 20 : mode == "full" ? 21 : 10;
        }
        if (context.pc != 0x807f0000 || context.msr != 0x2030 || context.fpscr != (index >= 8 ? 4u : 0u)) {
            return 11;
        }
        std::cout << "UART_CASE " << index << ' ' << context.gpr[3] << ' ' << bat_memory_read32(context, 0x80500000)
                  << ' ' << before << ' ' << controlBefore << ' ' << dataBefore << ' ' << causeBefore << ' ' << hw::pi_intsr.load()
                  << ' ' << hw::experimentExiMaskState[0] << ' ' << hw::experimentExiTransfer.control << ' ' << hw::experimentExiTransfer.data
                  << ' ' << bat_memory_read32(context, 0x8052af98);
        for (unsigned offset = 0; offset < 64; offset += 4) {
            std::cout << ' ' << bat_memory_read32(context, 0x80491f50 + offset);
        }
        for (unsigned offset = 0; offset < 16; ++offset) {
            std::cout << ' ' << unsigned(bat_memory_read8(context, 0x80500000 + offset));
        }
        std::cout << '\n';
        for (const auto& phase : hw::experimentExiTransfer.observations) {
            std::cout << "UART_PHASE " << index;
            for (auto value : phase) {
                std::cout << ' ' << value;
            }
            std::cout << '\n';
        }
        std::cout << "UART_BYTES " << index;
        for (auto byte : hw::experimentExiTransfer.uartBytes) {
            std::cout << ' ' << unsigned(byte);
        }
        std::cout << '\n';
    }
    return 0;
}
