#pragma once
#include <cstdint>
#include <cstring>
#include <vector>

namespace openshsm::experiment {
struct TextureSourceSample {
    std::vector<uint8_t> bytes;
    uint64_t host_us = 0;
    uint32_t hash = 2166136261u;
};

inline uint32_t texture_source_hash(const uint8_t* bytes, size_t size) {
    uint32_t hash = 2166136261u;
    for (size_t index = 0; index < size; ++index) {
        hash = (hash ^ bytes[index]) * 16777619u;
    }
    return hash;
}

template <class Context>
TextureSourceSample sample_texture_source(Context& ctx, uint32_t address, uint32_t size, uint64_t host_us) {
    TextureSourceSample sample;
    const uint32_t physical = address & 0x1FFFFFFF;
    const uint32_t end = physical < 0x01800000 ? 0x01800000u : 0x14000000u;
    if (size == 0 || size > 4 * 1024 * 1024 ||
        (physical >= 0x01800000 && physical < 0x10000000) ||
        physical >= end || size > end - physical) {
        return sample;
    }
    const uint8_t* raw = ctx.mmu.get_ptr(address);
    if (!raw || ctx.mmu.get_ptr(address + size - 1) != raw + size - 1) {
        return sample;
    }
    sample.bytes.resize(size);
    std::memcpy(sample.bytes.data(), raw, size);
    sample.host_us = host_us;
    sample.hash = texture_source_hash(sample.bytes.data(), sample.bytes.size());
    return sample;
}

struct TextureSourceDifference {
    bool comparable = false;
    size_t changed = 0;
    size_t first = 0;
    size_t last = 0;
};
inline TextureSourceDifference compare_texture_sources(const TextureSourceSample& before,
    const TextureSourceSample& after) {
    TextureSourceDifference result;
    if (before.bytes.empty() || before.bytes.size() != after.bytes.size()) {
        return result;
    }
    result.comparable = true;
    result.first = before.bytes.size();
    for (size_t index = 0; index < before.bytes.size(); ++index) {
        if (before.bytes[index] != after.bytes[index]) {
            if (result.changed == 0) {
                result.first = index;
            }
            result.last = index;
            ++result.changed;
        }
    }
    return result;
}
}
