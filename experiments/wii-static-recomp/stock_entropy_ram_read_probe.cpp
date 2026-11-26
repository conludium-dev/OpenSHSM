#include <processor_adapter.h>
#include "stock_entropy_ram_read.h"
#include "runtime/hw/hw.h"
#include <cassert>
#include <cstdio>
#include <memory>

struct ObservedMemory {
    nwii::runtime::MMU& actual;
    std::vector<uint8_t>& mem1;
    std::vector<uint8_t>& mem2;
    unsigned fallback = 0;
    uint32_t read32(uint32_t address) {
        ++fallback;
        return actual.read32(address);
    }
};

int main() {
    using namespace nwii::runtime;
    auto ctx = std::make_unique<CPUContext>();
    auto& memory = ctx->mmu;
    auto& bus = MMIODispatcher::get();
    hw::register_pe(bus);
    bus.write32(0xCC00100E, 0x1234);
    ObservedMemory observed{memory, memory.mem1, memory.mem2};
    unsigned cases = 0;
    auto check = [&](uint32_t address, bool expected_fallback) {
        const auto value = memory.read32(address);
        const auto before = observed.fallback;
        assert(stock_entropy_read32(observed, address) == value);
        assert(observed.fallback - before == unsigned(expected_fallback));
        ++cases;
    };
    uint32_t random = 0x5348534D;
    for (unsigned bank = 0; bank < 2; ++bank) {
        const uint32_t base = bank ? 0x10000000 : 0;
        auto& bytes = bank ? memory.mem2 : memory.mem1;
        const uint32_t usable = uint32_t(bytes.size() - 8);
        for (unsigned index = 0; index < 1024; ++index) {
            random = random * 1664525u + 1013904223u;
            const uint32_t offset = index < 8 ? index : index < 16 ? usable - (index - 7) : random % usable;
            for (unsigned byte = 0; byte < 4; ++byte) {
                bytes[offset + byte] = uint8_t(random >> (byte * 8));
            }
            for (uint32_t alias : {0u, 0x80000000u, 0xC0000000u}) {
                check((base + offset) | alias, false);
            }
        }
        check(base + usable, true);
    }
    memory.mem1[12] = 0xFF;
    check(0xC, false);
    check(0x8000000C, false);
    memory.locked_cache[0] = 0x7A;
    for (uint32_t address : {0xE0000000u, 0xE003FFFFu, 0xE0040000u,
        0xCC00100Eu, 0xCD000000u, 0x08000000u, 0xFFFFFFFFu}) {
        check(address, true);
    }
    std::printf("ACTUAL_MMU_RAM_READ_ALIASES_UNALIGNED_PAD_NULL_LOCKED_MMIO_PASS%u\n", cases);
}
