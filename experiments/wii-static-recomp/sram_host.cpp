int main(int argc, char** argv) {
    using namespace nwii::runtime;
    if (argc < 3 || argc > 4) {
        return 2;
    }
    const std::string mode = argc == 4 ? argv[3] : "normal";
    if (mode != "normal" && mode != "lost" && mode != "lost-dma" && mode != "wrong" && mode != "guards") {
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
    auto& transfer = hw::experimentExiTransfer;
    std::ifstream settings(argv[2], std::ios::binary);
    if (!settings.read(reinterpret_cast<char*>(transfer.sramResponse.data()), transfer.sramResponse.size()) || settings.peek() != EOF) {
        return 4;
    }
    hw::register_pi(MMIODispatcher::get());
    hw::experiment_register_exi_masks(MMIODispatcher::get());
    hw::experiment_register_getid_transfer(MMIODispatcher::get());
    transfer.sramAllowed = true;
    unsigned dma_count = 0;
    experiment_sram_attach_memory(context);
    const auto original_dma_write = transfer.dmaWrite;
    transfer.dmaWrite = [&, original_dma_write](uint32_t address, const std::array<uint8_t, 64>& bytes) {
        original_dma_write(address, bytes);
        ++dma_count;
    };
    g_trace_calls = false;
    memory_context(context).hid0 = 0xc200;
    context.hid2 = 0xa0000000;
    context.scriptedClock = true;
    context.clockSamples.assign(192, 0);
    if (mode == "guards") {
        context.msr = 0x2030;
        hw::experimentExiMaskState[0] = 0x1938;
        transfer.phase = 1;
        transfer.command = true;
        transfer.data = 0x20000100;
        transfer.control = 0x34;
        transfer.dmaAddress = 0x80492600;
        transfer.dmaLength = 64;
        const auto snapshot = [&] {
            return std::array<uint32_t, 9>{hw::experimentExiMaskState[0], transfer.control, transfer.data, transfer.phase,
                transfer.dmaAddress, transfer.dmaLength, uint32_t(transfer.command), hw::pi_intsr.load(), dma_count};
        };
        const std::array<std::function<void()>, 10> invalid{
            [&] { MMIODispatcher::get().write32(0xcd006804, 0x80492620); },
            [&] { MMIODispatcher::get().write32(0xcd006808, 32); },
            [&] { MMIODispatcher::get().write32(0xcd00680c, 7); },
            [&] { MMIODispatcher::get().write32(0xcd006810, 0x20000200); },
            [&] { MMIODispatcher::get().read16(0xcd006804); },
            [&] { MMIODispatcher::get().write16(0xcd006808, 64); },
            [&] { experiment_sram_write32(context, 0xcd006804, 0x80492600, 0x8020dc64); },
            [&] { experiment_sram_read32(context, 0xcd006808, 0x8020dc64); },
            [&] { hw::experiment_getid_csr_write(0xcd006800, 0x150); },
            [&] { context.msr = 0; experiment_sram_write32(context, 0xcd006804, 0x80492600, 0x8020dc60); }
        };
        for (const auto& test : invalid) {
            const auto before = snapshot();
            bool refused = false;
            try { test(); } catch (const std::runtime_error&) { refused = true; }
            context.msr = 0x2030;
            if (!refused || before != snapshot()) {
                return 14;
            }
        }
        std::cout << "SRAM_GUARDS 10\n";
        return 0;
    }
    transfer.loseCompletion = mode == "lost";
    transfer.loseDmaCompletion = mode == "lost-dma";
    transfer.wrongResponse = mode == "wrong";
    for (unsigned index = 0; index < 16; ++index) {
        context.gpr.fill(0);
        context.gpr[1] = 0x80540000;
        context.gpr[2] = 0x805335e0;
        context.gpr[13] = 0x8052e720;
        context.gpr[30] = 0xc0680000 + index * 736;
        context.msr = 0x2030;
        context.fpscr = index >= 8 ? 4 : 0;
        context.pc = 0x80219670;
        context.lr = 0x807f0000;
        context.is_running = true;
        context.inst_count = 0;
        context.clockSampleIndex = 0;
        bootPollChecks = 0;
        transfer.observations.clear();
        for (unsigned offset = 0; offset < 64; offset += 4) {
            bat_memory_write32(context, 0x80491f50 + offset, 0);
        }
        for (unsigned offset = 0; offset < 80; offset += 4) {
            bat_memory_write32(context, 0x80492600 + offset, 0xa5a5a5a5);
        }
        hw::experimentExiMaskState[0] = index == 0 ? 0x3800 : 0x3808;
        hw::pi_intsr = 0x10000;
        const auto before_csr = hw::experimentExiMaskState[0];
        const auto before_control = transfer.control;
        const auto before_data = transfer.data;
        try {
            func_80219670(context);
        } catch (const std::runtime_error& error) {
            std::cout << "SRAM_BOUNDARY " << error.what() << " phase=" << transfer.phase << " control=" << transfer.control << " dma=" << dma_count << '\n';
            return 20;
        }
        if (context.pc != 0x807f0000 || context.msr != 0x2030 || dma_count != index + 1 || transfer.observations.size() != 2) {
            return 12;
        }
        std::cout << "SRAM_CASE " << index << ' ' << context.gpr[3] << ' ' << context.msr << ' ' << before_csr << ' '
            << before_control << ' ' << before_data << " 65536 " << hw::experimentExiMaskState[0] << ' '
            << transfer.control << ' ' << transfer.data << ' ' << hw::pi_intsr.load();
        for (unsigned offset = 0; offset < 80; ++offset) {
            std::cout << ' ' << unsigned(bat_memory_read8(context, 0x80492600 + offset));
        }
        for (unsigned offset = 0; offset < 64; offset += 4) {
            std::cout << ' ' << bat_memory_read32(context, 0x80491f50 + offset);
        }
        for (unsigned register_index : {1u, 2u, 13u, 30u}) {
            std::cout << ' ' << context.gpr[register_index];
        }
        for (const auto& phase : transfer.observations) {
            for (const auto value : phase) { std::cout << ' ' << value; }
        }
        std::cout << ' ' << transfer.dmaAddress << ' ' << transfer.dmaLength << ' ' << dma_count;
        for (unsigned offset = 0; offset < 64; ++offset) {
            std::cout << ' ' << unsigned(*context.mmu.get_ptr(0x00492600 + offset));
        }
        std::cout << '\n';
    }
    return 0;
}
