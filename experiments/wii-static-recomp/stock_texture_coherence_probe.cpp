#include "stock_texture_coherence.h"
#include <cassert>
#include <cstdio>

struct Memory {
    std::vector<uint8_t> bytes = std::vector<uint8_t>(4096, 0xA5);
    unsigned reads = 0;
    bool discontinuous = false;
    uint8_t* get_ptr(uint32_t address) {
        ++reads;
        const uint32_t physical = address & 0x1FFFFFFF;
        if (physical >= bytes.size()) {
            return nullptr;
        }
        if (discontinuous && physical == 127) {
            return bytes.data();
        }
        return bytes.data() + physical;
    }
};
struct Context { Memory mmu; };

int main() {
    using namespace openshsm::experiment;
    Context ctx;
    const auto untouched = ctx.mmu.bytes;
    for (const auto& pair : {std::pair{0x80000000u, 0u}, {0x80000000u, 4194305u},
            {0x817FFFFFu, 2u}, {0x81800000u, 1u}, {0x8D000000u, 16u},
            {0x94000000u, 1u}, {UINT32_MAX, 2u}}) {
        const auto sample = sample_texture_source(ctx, pair.first, pair.second, 17);
        assert(sample.bytes.empty() && ctx.mmu.reads == 0);
    }
    assert(sample_texture_source(ctx, 0x80001000, 16, 17).bytes.empty());
    ctx.mmu.discontinuous = true;
    assert(sample_texture_source(ctx, 0x80000000, 128, 17).bytes.empty());
    ctx.mmu.discontinuous = false;
    const auto before = sample_texture_source(ctx, 0x80000000, 128, 100);
    const auto same = sample_texture_source(ctx, 0x80000000, 128, 101);
    assert(before.bytes.size() == 128 && before.hash == same.hash && ctx.mmu.bytes == untouched);
    const auto equal = compare_texture_sources(before, same);
    assert(equal.comparable && equal.changed == 0 && equal.first == 128);
    ctx.mmu.bytes[0] = 1;
    ctx.mmu.bytes[127] = 2;
    const auto after = sample_texture_source(ctx, 0x80000000, 128, 102);
    const auto changed = compare_texture_sources(before, after);
    assert(changed.comparable && changed.changed == 2 && changed.first == 0 && changed.last == 127);
    assert(before.bytes[0] == 0xA5 && before.bytes[127] == 0xA5 && before.hash != after.hash);
    assert(!compare_texture_sources(before, TextureSourceSample{}).comparable);
    std::puts("TEXTURE_SOURCE_RANGE_CONTIGUITY_COPY_READONLY_DIFFERENCE_PASS");
}
