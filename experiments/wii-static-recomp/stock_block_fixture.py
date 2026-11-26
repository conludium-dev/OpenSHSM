"""Retain bounded host copies of original IDCT entry state, write only failing fixtures."""

def adapt_block_fixtures(text):
    helper = '''
struct IDCTBlockFixture {
    uint32_t entry = 0, lr = 0, ctr = 0, xer = 0, msr = 0, fpscr = 0, cr = 0;
    std::array<uint32_t, 32> gpr;
    std::array<double, 32> fpr, ps1;
    std::array<uint32_t, 8> gqr;
    std::vector<std::pair<uint32_t, std::vector<uint8_t>>> memory;
    unsigned serial = 0;
};
static IDCTBlockFixture last_idct_block;
static void remember_idct_block(nwii::runtime::CPUContext& ctx, uint32_t entry) {
    if (!std::getenv("NWII_THPDUMP")) {
        return;
    }
    auto& state = last_idct_block;
    state.entry = entry; state.lr = ctx.lr; state.ctr = ctx.ctr; state.xer = ctx.xer;
    state.msr = ctx.msr; state.fpscr = ctx.fpscr;
    state.gpr = ctx.gpr; state.fpr = ctx.fpr; state.ps1 = ctx.ps1; state.gqr = ctx.gqr;
    state.cr = 0;
    for (unsigned i = 0; i < 8; ++i) {
        const auto& field = ctx.cr[i];
        state.cr |= ((field.lt ? 8u : 0) | (field.gt ? 4u : 0)
            | (field.eq ? 2u : 0) | (field.so ? 1u : 0)) << (28 - 4 * i);
    }
    state.memory.clear();
    auto copy = [&](uint32_t address, unsigned bytes) {
        if (address > 0xFFFFFFFFu - bytes || !ctx.mmu.get_ptr(address)
            || !ctx.mmu.get_ptr(address + bytes - 1)) {
            state.entry = 0;
            return;
        }
        const uint8_t* data = ctx.mmu.get_ptr(address);
        state.memory.emplace_back(address, std::vector<uint8_t>(data, data + bytes));
    };
    copy(ctx.gpr[3], 128);
    copy(ctx.mmu.read32(ctx.gpr[13] - 15904u), 256);
    copy(ctx.gpr[13] - 16000u, 512);
    copy(ctx.gpr[2] - 19232u, 20);
    copy(0x80491E00, 1024);
    copy(ctx.gpr[1] - 256u, 320);
    copy(0xE0000000, 16384);
    ++state.serial;
}
static void save_idct_block(nwii::runtime::CPUContext& ctx, uint32_t store, unsigned reg, uint32_t target) {
    static unsigned saved = 0, last_serial = 0;
    const auto& state = last_idct_block;
    if (!state.entry || saved >= 3 || last_serial == state.serial) {
        return;
    }
    const char* prefix = std::getenv("NWII_THPDUMP");
    if (!prefix) {
        return;
    }
    const std::string path = std::string(prefix) + "-block" + std::to_string(saved) + ".txt";
    std::ofstream file(path);
    if (!file) {
        return;
    }
    file << state.entry << " " << state.lr << " " << state.ctr << " " << state.xer
        << " " << state.msr << " " << state.fpscr << " " << state.cr << " " << store << " " << target << "\\n";
    for (uint32_t value : state.gpr) { file << value << " "; }
    file << "\\n";
    for (uint32_t value : state.gqr) { file << value << " "; }
    file << "\\n" << std::hexfloat;
    for (unsigned i = 0; i < 32; ++i) { file << state.fpr[i] << " " << state.ps1[i] << " "; }
    file << "\\n" << ctx.fpr[reg] << " " << ctx.ps1[reg] << "\\n";
    file << std::defaultfloat << state.memory.size() << "\\n";
    for (const auto& range : state.memory) {
        file << std::dec << range.first << " ";
        for (uint8_t byte : range.second) {
            file << std::hex << std::setw(2) << std::setfill('0') << unsigned(byte);
        }
        file << "\\n";
    }
    file.close();
    if (file) {
        std::fprintf(stderr, "[BlockFixture] index=%u entry=%08x store=%08x target=%08x serial=%u\\n", saved, state.entry, store, target, state.serial);
        last_serial = state.serial;
        ++saved;
    }
}
'''
    assert 'ctx.mmu.write' not in helper
    marker = 'static bool observe_psq_anomaly('
    assert text.count(marker) == 1
    text = text.replace(marker, helper + marker)
    marker = '        ++count;\n'
    assert text.count(marker) == 1
    text = text.replace(marker, marker + '        save_idct_block(ctx, pc, reg, address);\n')
    for address in (0x8020AFD0, 0x8020B460):
        marker = f'    observe_idct(ctx, 0x{address:08X}, true, ctx.gpr[3]);'
        assert text.count(marker) == 1
        text = text.replace(marker, marker + f'\n    remember_idct_block(ctx, 0x{address:08X});')
    return '#include <fstream>\n' + text
