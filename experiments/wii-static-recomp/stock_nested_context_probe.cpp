#include <processor_adapter.h>
#include <fstream>
#include <iostream>
#include <iterator>
#include <memory>
#include <vector>
#include <string>

int main(int argc, char** argv) {
    if (argc != 2 && argc != 3) {
        return 1;
    }
    std::ifstream file(argv[1], std::ios::binary);
    std::vector<uint8_t> data((std::istreambuf_iterator<char>(file)), {});
    if (data.size() != 24 + 2 * 0x1C8) {
        return 2;
    }
    auto word = [&](unsigned offset) {
        return (uint32_t(data[offset]) << 24) | (uint32_t(data[offset + 1]) << 16)
            | (uint32_t(data[offset + 2]) << 8) | uint32_t(data[offset + 3]);
    };
    const uint32_t nested = word(0), thread = word(4);
    if (nested < 0x80004000 || nested > 0x817FFE00 || thread < 0x80004000 || thread > 0x817FFE00) {
        return 3;
    }
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    for (unsigned i = 0; i < 0x1C8; ++i) {
        ctx.mmu.write8(nested + i, data[24 + i]);
        ctx.mmu.write8(thread + i, data[24 + 0x1C8 + i]);
    }
    ctx.mmu.write32(0x800000D4, nested);
    ctx.mmu.write32(0x800000E4, thread);
    ctx.dispatch_saved_ctx = nested;
    ctx.pc = 0xFFFFFFFC;
    ctx.in_callback = false;
    ctx.ext_resched_pending = false;
    if (!nwii::runtime::process_pending_callbacks(ctx)) {
        return 4;
    }
    std::cout << "NESTED_SELECTION " << std::hex << nested << ' ' << thread << ' '
        << ctx.mmu.read32(0x800000D4) << ' ' << ctx.pc << ' ' << ctx.ctr << ' ' << ctx.gpr[1]
        << ' ' << ctx.lr << ' ' << word(8) << ' ' << word(12) << ' ' << word(16) << ' ' << word(20) << '\n';
    const bool selects_thread = ctx.mmu.read32(0x800000D4) == thread
        && ctx.pc == word(24 + 0x1C8 + 0x198);
    if (argc == 3 && std::string(argv[2]) == "fixed") {
        return ctx.mmu.read32(0x800000D4) == nested && ctx.pc == word(8) && ctx.ctr == word(12)
            && ctx.gpr[1] == word(16) && ctx.lr == word(20) ? 0 : 6;
    }
    return selects_thread && ctx.pc != word(8) ? 0 : 5;
}
