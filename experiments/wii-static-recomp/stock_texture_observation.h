#pragma once
#include "runtime/texture_cache_gl.h"
#include <fstream>
#include <map>
#include <tuple>

namespace nwii::runtime::hle {
uint32_t texture_data_size(uint32_t width, uint32_t height, uint32_t format);
}

namespace openshsm::experiment {
inline void observe_texture(nwii::runtime::CPUContext& ctx,
    const nwii::runtime::gx::TexStage& stage, uint32_t hash, const Image& image) {
    const char* directory = std::getenv("NWII_TEXTURE_OBSERVE");
    if (!directory) {
        return;
    }
    static unsigned sequence = 0;
    static uint64_t bytes_written = 0;
    static std::map<std::tuple<uint32_t, uint32_t, uint32_t, uint8_t>, unsigned> counts;
    if (sequence >= 128 || counts.size() >= 256 || stage.width == 0 || stage.height == 0
        || stage.width > 1024 || stage.height > 1024) {
        return;
    }
    auto key = std::make_tuple(stage.base_addr, stage.width, stage.height, stage.format);
    auto& count = counts[key];
    if (count >= 2) {
        return;
    }
    const auto size = nwii::runtime::hle::texture_data_size(stage.width, stage.height, stage.format);
    const auto physical = stage.base_addr & 0x1FFFFFFF;
    const auto end = physical < 0x01800000 ? 0x01800000u : 0x14000000u;
    if ((physical >= 0x01800000 && physical < 0x10000000) || physical >= end
        || !size || size > end - physical) {
        return;
    }
    auto* raw = ctx.mmu.get_ptr(stage.base_addr);
    if (!raw || ctx.mmu.get_ptr(stage.base_addr + size - 1) != raw + size - 1) {
        return;
    }
    uint32_t palette = stage.format == 8 ? 32 : stage.format == 9 ? 512 : stage.format == 10 ? 32768 : 0;
    auto& state = nwii::runtime::gx::g_state;
    if (palette && (stage.tlut_offset >= sizeof(state.tlutMem)
        || palette > sizeof(state.tlutMem) - stage.tlut_offset)) {
        return;
    }
    const uint64_t rgba_size = uint64_t(stage.width) * stage.height * 4;
    if (!image.data || image.width != int(stage.width) || image.height != int(stage.height)
        || bytes_written + size + rgba_size + palette > 96 * 1024 * 1024) {
        return;
    }
    const auto prefix = std::string(directory) + "/texture-" + std::to_string(sequence);
    std::ofstream data(prefix + ".raw", std::ios::binary);
    std::ofstream rgba(prefix + ".rgba", std::ios::binary);
    std::ofstream tlut(prefix + ".tlut", std::ios::binary);
    std::ofstream meta(prefix + ".txt");
    if (!data || !rgba || !tlut || !meta) {
        return;
    }
    data.write(reinterpret_cast<const char*>(raw), size);
    rgba.write(static_cast<const char*>(image.data), rgba_size);
    if (palette) {
        tlut.write(reinterpret_cast<const char*>(state.tlutMem + stage.tlut_offset), palette);
    }
    meta << sequence << ' ' << stage.base_addr << ' ' << stage.width << ' ' << stage.height
        << ' ' << unsigned(stage.format) << ' ' << stage.tlut_offset << ' ' << unsigned(stage.tlut_format)
        << ' ' << hash << ' ' << size << ' ' << unsigned(state.numTevStages) << '\n';
    for (auto value : state.bp) {
        meta << value << ' ';
    }
    meta << '\n';
    for (const auto& tev : state.tevStages) {
        meta << unsigned(tev.texMap) << ' ' << unsigned(tev.texCoord) << ' ' << unsigned(tev.colorChan)
            << ' ' << unsigned(tev.colorInA) << ' ' << unsigned(tev.colorInB) << ' ' << unsigned(tev.colorInC)
            << ' ' << unsigned(tev.colorInD) << ' ' << unsigned(tev.alphaInA) << ' ' << unsigned(tev.alphaInB)
            << ' ' << unsigned(tev.alphaInC) << ' ' << unsigned(tev.alphaInD) << '\n';
    }
    if (data && rgba && tlut && meta) {
        bytes_written += size + rgba_size + palette;
        ++sequence;
        ++count;
    }
}
}
