#include "stock_pc_boot_notices.h"
#include <array>
#include <cassert>
#include <string>

struct Memory {
    uint32_t value = 0;
    unsigned reads = 0;
    unsigned writes = 0;
    uint32_t read32(uint32_t address) {
        assert(address == 0x80560010);
        ++reads;
        return value;
    }
    void write32(uint32_t address, uint32_t next) {
        assert(address == 0x80560010);
        ++writes;
        value = next;
    }
};
struct Context {
    std::array<uint32_t, 32> gpr{};
    Memory mmu;
};
int main(int argc, char** argv) {
    assert(argc == 2);
    const bool enabled = std::string(argv[1]) == "1";
    unsigned cases = 0;
    for (uint32_t index : {0u, 1u, 2u, 3u, 4u, 5u, 6u, 7u, 8u, 9u, 10u, 11u, 0xFFFFFFFFu}) {
        Context ctx;
        ctx.gpr[15] = 0x80560000;
        ctx.gpr[18] = 0x803F2418;
        ctx.mmu.value = index;
        const auto before = ctx.gpr;
        openshsm::experiment::skip_pc_boot_notices(ctx);
        const auto expected = enabled && index < 4 ? 4 : index == 5 ? 6 : index;
        assert(ctx.mmu.value == expected && ctx.gpr == before);
        assert(ctx.mmu.writes == (expected != index));
        ++cases;
    }
    for (uint32_t object : {0u, 0x80560001u, 0x93FFFFF0u, 0x81800000u, 0x8FFFFFFCu}) {
        Context ctx;
        ctx.gpr[15] = object;
        ctx.gpr[18] = 0x803F2418;
        openshsm::experiment::skip_pc_boot_notices(ctx);
        assert(ctx.mmu.reads == 0 && ctx.mmu.writes == 0);
        ++cases;
    }
    Context wrong;
    wrong.gpr[15] = 0x80560000;
    wrong.gpr[18] = 0x803F241C;
    openshsm::experiment::skip_pc_boot_notices(wrong);
    assert(wrong.mmu.reads == 0 && wrong.mmu.writes == 0);
    std::cout << "PC_BOOT_ADAPTER_PASS " << cases + 1 << '\n';
}
