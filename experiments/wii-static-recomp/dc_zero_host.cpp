extern "C" void run_game(nwii::runtime::CPUContext&);
int main(int argc, char** argv) {
    using namespace nwii::runtime;
    if (argc < 2 || argc > 3 || (argc == 3 && std::string(argv[2]) != "guards")) { return 2; }
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
    context.flushSyscall = true;
    for (unsigned index = 0; index < 7; ++index) {
        bat_memory_write32(context, 0xc0000c00 + index * 4, bat_memory_read32(context, 0x8021a120 + index * 4));
    }
    if (argc == 3) {
        for (unsigned test = 0; test < 8; ++test) {
            experimentDcZero = test != 0;
            context.msr = test == 2 ? 0x2030 : 0x2032;
            context.hid0 = test == 3 ? 0x8200 : 0xc200;
            uint32_t address = test == 4 ? 0xc0550000 : test == 5 ? 0xcc003024 : test == 6 ? 0x80006310 : test == 7 ? 0x81800000 : 0x80550007;
            std::ostringstream before;
            before << experimentDcZeroLines;
            for (const auto& set : context.dataLines) {
                for (const auto& line : set) {
                    before << ' ' << line.valid << ' ' << line.dirty << ' ' << line.address;
                    for (auto value : line.bytes) { before << ' ' << unsigned(value); }
                }
            }
            bool refused = false;
            try { experiment_dcbz_line(context, address, test == 1 ? 0x80213080 : 0x8021307c); }
            catch (const std::runtime_error&) { refused = true; }
            std::ostringstream after;
            after << experimentDcZeroLines;
            for (const auto& set : context.dataLines) {
                for (const auto& line : set) {
                    after << ' ' << line.valid << ' ' << line.dirty << ' ' << line.address;
                    for (auto value : line.bytes) { after << ' ' << unsigned(value); }
                }
            }
            if (!refused || before.str() != after.str()) { return 12; }
        }
        experimentDcZero = false;
        context.msr = 0x2032;
        context.hid0 = 0xc200;
        context.gpr[4] = 0;
        context.pc = 0x80213060;
        context.lr = 0x807f0000;
        func_80213060(context);
        if (context.pc != 0x807f0000 || experimentDcZeroLines) { return 13; }
        std::cout << "DCZERO_GUARDS 8 ZERO_DISABLED_RETURN\n";
        return 0;
    }
    experimentDcZero = true;
    const std::array<unsigned, 8> lengths{0, 1, 31, 32, 33, 63, 64, 128};
    for (unsigned index = 0; index < 32; ++index) {
        const uint32_t address = 0x80550000 + (index % 16 < 8 ? 0 : 7);
        const unsigned length = lengths[index % 8];
        context.msr = 0x2032;
        for (unsigned offset = 0; offset < 160; offset += 32) { bat_memory_cache_operation(context, 0x80550000 + offset, 470); }
        for (unsigned offset = 0; offset < 160; offset += 4) {
            bat_memory_write32(context, 0xc0550000 + offset, 0xa5a5a5a5);
            if (index < 16) { bat_memory_write32(context, 0x80550000 + offset, (index + 1) * 0x1020304u + offset * 0x01010101u); }
        }
        context.gpr[1] = 0x80540000;
        context.gpr[2] = 0x805335e0;
        context.gpr[13] = 0x8052e720;
        context.gpr[30] = 0xc0680000 + index * 736;
        context.gpr[31] = 0x55660000 + index;
        context.gpr[3] = address;
        context.gpr[4] = length;
        context.gpr[5] = 0xaabbccdd;
        context.ctr = 0x12345678;
        context.pc = 0x80213060;
        context.lr = 0x807f0000;
        context.inst_count = 0;
        bootPollChecks = 0;
        context.is_running = true;
        experimentDcZeroLines = 0;
        func_80213060(context);
        std::cout << "DCZERO_CASE " << index;
        for (unsigned reg : {3u, 4u, 5u}) { std::cout << ' ' << context.gpr[reg]; }
        std::cout << ' ' << context.ctr;
        for (unsigned reg : {1u, 2u, 13u, 30u, 31u}) { std::cout << ' ' << context.gpr[reg]; }
        std::cout << ' ' << context.pc << ' ' << context.msr << ' ' << context.hid0 << ' ' << experimentDcZeroLines << '\n';
        for (uint32_t start : {0x80550000u, 0xc0550000u}) {
            std::cout << "DCZERO_MEMORY " << index << ' ' << start;
            for (unsigned offset = 0; offset < 160; offset += 4) { std::cout << ' ' << bat_memory_read32(context, start + offset); }
            std::cout << '\n';
        }
        context.gpr[3] = address;
        context.gpr[4] = length;
        context.pc = 0x80212fd0;
        context.lr = 0x807f0000;
        try { run_game(context); }
        catch (const std::runtime_error& failure) {
            if (context.pc != 0x807f0000 || std::string(failure.what()) != "DCZero flush return sentinel") { throw; }
        }
        std::cout << "DCZERO_FLUSHED " << index;
        for (unsigned offset = 0; offset < 160; offset += 4) { std::cout << ' ' << bat_memory_read32(context, 0xc0550000 + offset); }
        std::cout << '\n';
    }
    return 0;
}
