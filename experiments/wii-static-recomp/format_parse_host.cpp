extern "C" void run_game(nwii::runtime::CPUContext&);

int main(int argc, char** argv) {
    using namespace nwii::runtime;
    if (argc != 2 && (argc != 3 || std::string(argv[2]) != "dispatch")) {
        return 2;
    }
    nwii::loader::Executable executable;
    if (!executable.load_dol(argv[1])) {
        return 3;
    }
    SeededBatContext context;
    memory_context(context).hid0 = 0;
    for (const auto& section : executable.sections) {
        std::copy(section.data.begin(), section.data.end(), context.mmu.get_ptr(section.address));
    }
    g_trace_calls = false;
    std::string encoded;
    unsigned ni;
    while (std::cin >> encoded >> ni) {
        if (encoded.size() % 2 || encoded.size() > 128 || ni > 1) {
            return 8;
        }
        context.msr = 0x2030;
        context.fpscr = ni * 4;
        context.inst_count = 0;
        bootPollChecks = 0;
        context.cr.fill({});
        context.xer = 0;
        context.ctr = 0;
        context.lr = 0x807f0000;
        context.pc = 0x80199a24;
        context.is_running = true;
        for (unsigned index = 0; index < 32; ++index) {
            context.gpr[index] = 0x11110000 + index;
        }
        context.gpr[1] = 0x80540000;
        context.gpr[2] = 0x805335e0;
        context.gpr[13] = 0x8052e720;
        context.gpr[3] = 0x806a0000;
        context.gpr[4] = 0x806a0100;
        context.gpr[5] = 0x806a0200;
        std::fill(context.mmu.get_ptr(0x8053ff80), context.mmu.get_ptr(0x80540080), 0);
        std::fill(context.mmu.get_ptr(0x806a0000), context.mmu.get_ptr(0x806a0400), 0);
        for (unsigned offset = 0; offset < encoded.size(); offset += 2) {
            unsigned byte;
            const auto parsed = std::from_chars(encoded.data() + offset, encoded.data() + offset + 2, byte, 16);
            if (parsed.ec != std::errc() || parsed.ptr != encoded.data() + offset + 2) {
                return 8;
            }
            bat_memory_write8(context, 0x806a0000 + offset / 2, byte);
        }
        bat_memory_write32(context, 0x806a0104, 0x806a0300);
        bat_memory_write32(context, 0x806a0108, 0x806a0300);
        bat_memory_write32(context, 0x806a0300, 7);
        bat_memory_write32(context, 0x806a0304, 3);
        if (argc == 3) {
            try {
                run_game(context);
                return 9;
            } catch (const std::runtime_error& failure) {
                if (context.pc != 0x807f0000 || std::string(failure.what()) != "Format oracle return sentinel") {
                    throw;
                }
            }
        } else {
            func_80199A24(context);
        }
        std::cout << "FORMAT_CASE " << (context.pc == 0x807f0000);
        for (auto value : context.gpr) {
            std::cout << ' ' << value;
        }
        uint32_t cr = 0;
        for (const auto& field : context.cr) {
            cr = (cr << 4) | (field.lt ? 8 : 0) | (field.gt ? 4 : 0) | (field.eq ? 2 : 0) | (field.so ? 1 : 0);
        }
        std::cout << ' ' << cr << ' ' << context.xer << ' ' << context.ctr << ' ' << context.lr;
        for (const auto& range : std::array<std::pair<uint32_t, unsigned>, 3>{{{0x8053ff80, 256}, {0x806a0100, 16}, {0x806a0200, 16}}}) {
            for (unsigned offset = 0; offset < range.second; ++offset) {
                std::cout << ' ' << unsigned(bat_memory_read8(context, range.first + offset));
            }
        }
        std::cout << '\n';
    }
    return std::cin.eof() ? 0 : 8;
}
