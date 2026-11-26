#define main baseline_frontend_probe_main
#include "memory_frontend_probe.cpp"
#undef main

int main() {
    using namespace nwii::runtime;
    MemoryContext context;
    context.msr = 0x2030;
    context.hid0 = 0x4000;
    const std::vector<std::vector<unsigned>> patterns = {
        {}, {0}, {7}, {0, 1, 2, 3}, {7, 6, 5, 4}, {0, 2, 4, 6}, {1, 3, 5, 7}, {3, 3, 0, 7, 2}
    };
    for (unsigned trial = 0; trial < patterns.size(); ++trial) {
        const uint32_t start = 0x80680000 + trial * 32;
        for (unsigned index = 0; index < 10; ++index) {
            memory_cache_operation(context, start + index * 4096, 470);
            memory_write32(context, (start + index * 4096) | 0x40000000, 0x1000 + index);
        }
        for (unsigned index = 0; index < 8; ++index) {
            memory_write32(context, start + index * 4096, 0x2000 + index);
        }
        for (unsigned index : patterns[trial]) {
            memory_read32(context, start + index * 4096);
        }
        memory_write32(context, start + 8 * 4096, 0x2008);
        std::cout << trial;
        for (unsigned index = 0; index < 10; ++index) {
            std::cout << ' ' << memory_read32(context, (start + index * 4096) | 0x40000000);
        }
        memory_write32(context, start + 9 * 4096, 0x2009);
        for (unsigned index = 0; index < 10; ++index) {
            std::cout << ' ' << memory_read32(context, (start + index * 4096) | 0x40000000);
        }
        std::cout << '\n';
    }
}
