#include "memory_frontend.h"
#define ProcessorContext MemoryContext
#define SHSM_FPSCR_MAIN_NAME memory_fixture_main
#include "fpscr_boot.cpp"
#undef SHSM_FPSCR_MAIN_NAME
#undef ProcessorContext

int main() {
    using namespace nwii::runtime;
    MemoryContext context;
    context.msr = 0x30;
    g_trace_calls = true;
    constexpr uint32_t table = 0x80477328;
    constexpr uint32_t stack = 0x80100000;
    constexpr uint32_t sentinel = 0xf0001000;
    std::vector<uint32_t> values;
    for (uint32_t value = 0; value <= 128; ++value) {
        values.push_back(value);
    }
    for (uint32_t value : {0x7ffffffeu, 0x7fffffffu, 0x80000000u, 0xfffffffeu, 0xffffffffu}) {
        values.push_back(value);
    }
    for (unsigned cached = 0; cached < 2; ++cached) {
        context.hid0 = cached ? 0x4000 : 0;
        for (uint32_t value : values) {
            for (uint32_t direction : {0u, 1u, 2u, 0xffffffffu}) {
                for (uint32_t address = table & ~31u; address <= (table + 64); address += 32) {
                    memory_cache_operation(context, address, 470);
                }
                for (unsigned index = 0; index < 17; ++index) {
                    memory_write32(context, (table + index * 4) | 0x40000000, index == 16 ? value : 0xabcdef01);
                }
                context.gpr.fill(0);
                for (unsigned index = 14; index < 32; ++index) {
                    context.gpr[index] = 0x12340000 + index * 0x100;
                }
                const auto before = context.gpr;
                context.gpr[1] = stack;
                context.gpr[4] = direction;
                context.lr = sentinel;
                context.pc = 0x800f3e60;
                calls = 0;
                func_800F3E60(context);
                bool abi = context.gpr[1] == stack && context.lr == sentinel && context.pc == sentinel;
                for (unsigned index = 14; index < 32; ++index) {
                    abi &= context.gpr[index] == before[index];
                }
                for (unsigned index = 0; index < 16; ++index) {
                    abi &= memory_read32(context, table + index * 4) == 0xabcdef01;
                }
                const uint32_t observed = memory_read32(context, table + 64);
                const uint32_t backing = memory_read32(context, (table + 64) | 0x40000000);
                memory_cache_operation(context, table + 64, 54);
                const uint32_t written = memory_read32(context, (table + 64) | 0x40000000);
                std::cout << "MEMORY_ORIGINAL " << cached << ' ' << value << ' ' << direction << ' '
                          << observed << ' ' << abi << ' ' << calls << ' ' << backing << ' ' << written << '\n';
            }
        }
    }
}
