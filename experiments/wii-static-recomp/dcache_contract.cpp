#include "dcache_adapter.h"
#define main unused_frontend_main
#include "memory_frontend_probe.cpp"
#undef main

int main() {
    using namespace nwii::runtime;
    MemoryContext context;
    context.msr = 0x30;
    context.instructionImages.emplace_back(0x80600000, std::vector<uint8_t>(16, 0x60));
    std::fill_n(context.mmu.get_ptr(0x80600000), 16, 0x60);
    experiment_write_hid0_dcache(context, 0x8000);
    experiment_write_hid0_dcache(context, 0xc000);
    experiment_write_hid0_dcache(context, 0xc800);
    assert(context.hid0 == 0xc000 && context.instructionCacheInvalidations == 1);
    unsigned refusals = 0;
    for (unsigned mode = 0; mode < 8; ++mode) {
        context.hid0 = mode == 0 ? 0xc000 : 0x8000;
        context.msr = mode == 1 ? 0x4030 : mode == 2 ? 0x20 : 0x30;
        context.dataLines[0][0].valid = mode == 3;
        auto saved = context.instructionImages;
        if (mode == 4) {
            context.instructionImages.clear();
        }
        if (mode == 5) {
            context.mmu.get_ptr(0x80600000)[0] = 0;
        }
        if (mode == 6) {
            context.instructionImages[0].second.clear();
        }
        const uint32_t before = context.hid0;
        const auto invalidations = context.instructionCacheInvalidations;
        try {
            experiment_write_hid0_dcache(context, mode == 0 ? 0x8000 : mode == 7 ? 0xc400 : 0xc000);
            return 2;
        } catch (const std::runtime_error&) {
            assert(context.hid0 == before && context.instructionCacheInvalidations == invalidations);
            ++refusals;
        }
        context.instructionImages = saved;
        context.mmu.get_ptr(0x80600000)[0] = 0x60;
    }
    assert(refusals == 8);
    std::cout << "DCE_CONTRACT 3accepts 8refusals rollback PASS\n";
}
