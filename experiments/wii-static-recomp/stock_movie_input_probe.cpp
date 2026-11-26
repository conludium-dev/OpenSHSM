#include "stock_movie_input.h"
#include <array>
#include <vector>

struct ProbeContext {
    struct Memory {
        std::vector<uint8_t> mem1 = std::vector<uint8_t>(24 * 1024 * 1024 + 8);
        std::vector<uint8_t> mem2 = std::vector<uint8_t>(64 * 1024 * 1024 + 8);
    } mmu;
    std::array<uint32_t, 32> gpr{};
};

int main() {
    ProbeContext ctx;
    auto write = [&](uint32_t address, uint32_t value) {
        auto* bytes = const_cast<uint8_t*>(stock_movie_input::ram(ctx, address, 4));
        for (unsigned i = 0; i < 4; ++i) {
            bytes[i] = uint8_t(value >> (24 - i * 8));
        }
    };
    ctx.gpr[30] = 0x80001000;
    ctx.gpr[23] = 0x80002000;
    ctx.gpr[26] = 0;
    ctx.gpr[28] = ctx.gpr[30];
    ctx.gpr[25] = 0x90001008;
    ctx.gpr[24] = ctx.gpr[3] = 0x90001010;
    ctx.gpr[1] = 0x80010000;
    write(ctx.gpr[30] + 0x6C, 2);
    write(ctx.gpr[23], 0x90001000);
    write(ctx.gpr[23] + 4, 117);
    write(ctx.gpr[25], 4);
    write(0x800000D4, 0x80004000);
    ctx.mmu.mem2[0x1010] = 0xFF;
    ctx.mmu.mem2[0x1011] = 0xD8;
    stock_movie_input::Packet packet;
    if (!stock_movie_input::prepare(ctx, packet) || packet.size != 4 || packet.descriptor_field4 != 117) {
        return 1;
    }
    const auto registers = ctx.gpr;
    const auto mem1 = ctx.mmu.mem1;
    const auto mem2 = ctx.mmu.mem2;
    for (uint32_t bad : {0u, 17u}) {
        write(ctx.gpr[30] + 0x6C, bad);
        if (stock_movie_input::prepare(ctx, packet)) {
            return 2;
        }
    }
    write(ctx.gpr[30] + 0x6C, 2);
    for (unsigned index : {3u, 23u, 24u, 25u, 26u, 28u, 30u}) {
        const auto value = ctx.gpr[index];
        ctx.gpr[index] = 0xFFFFFFFF;
        if (stock_movie_input::prepare(ctx, packet)) {
            return 3;
        }
        ctx.gpr[index] = value;
    }
    for (uint32_t size : {0u, 1u, 1048577u, 0xFFFFFFFFu}) {
        write(ctx.gpr[25], size);
        if (stock_movie_input::prepare(ctx, packet)) {
            return 4;
        }
    }
    write(ctx.gpr[25], 4);
    if (stock_movie_input::ram(ctx, 0x93FFFFFE, 8) || stock_movie_input::ram(ctx, 0xCC000000, 4) ||
        stock_movie_input::ram(ctx, 0xFFFFFFFF, 4) || stock_movie_input::ram(ctx, 0x81800000, 1)) {
        return 5;
    }
    for (unsigned i = 0; i < 130; ++i) {
        stock_movie_input::observe(ctx, 0x8009C5E0, 42 + i);
    }
    if (registers != ctx.gpr || mem1 != ctx.mmu.mem1 || mem2 != ctx.mmu.mem2) {
        return 6;
    }
    std::puts("MOVIE_INPUT_READ_ONLY_METADATA_REFUSALS_PASS");
    return 0;
}
