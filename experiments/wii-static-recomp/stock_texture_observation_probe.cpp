#include <processor_adapter.h>
#include "stock_texture_observation.h"
#include <cassert>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <memory>

int main(int argc, char** argv) {
    assert(argc == 2);
    const std::filesystem::path directory(argv[1]);
    std::filesystem::create_directories(directory);
    assert(std::filesystem::is_empty(directory));
    setenv("NWII_TEXTURE_OBSERVE", argv[1], 1);
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    auto& state = nwii::runtime::gx::g_state;
    std::array<uint8_t, sizeof(state)> before{};
    std::memcpy(before.data(), &state, sizeof(state));
    std::array<Color, 32> pixels{};
    Image image{};
    image.data = pixels.data();
    image.width = 8;
    image.height = 4;
    nwii::runtime::gx::TexStage stage{};
    stage.width = 8;
    stage.height = 4;
    stage.format = 1;
    for (auto invalid : {0x017FFFF0u, 0x13FFFFF0u, 0x0D000000u, 0xFFFFFFFFu}) {
        stage.base_addr = invalid;
        openshsm::experiment::observe_texture(ctx, stage, 0, image);
    }
    assert(std::filesystem::is_empty(directory));
    for (unsigned descriptor = 0; descriptor < 64; ++descriptor) {
        stage.base_addr = 0x80560000 + descriptor * 128;
        for (unsigned i = 0; i < 32; ++i) {
            ctx.mmu.write8(stage.base_addr + i, descriptor + i);
        }
        for (unsigned sample = 0; sample < 3; ++sample) {
            openshsm::experiment::observe_texture(ctx, stage, sample, image);
        }
        for (unsigned i = 0; i < 32; ++i) {
            assert(ctx.mmu.read8(stage.base_addr + i) == uint8_t(descriptor + i));
        }
    }
    stage.base_addr = 0x80564000;
    openshsm::experiment::observe_texture(ctx, stage, 0, image);
    assert(std::memcmp(before.data(), &state, sizeof(state)) == 0);
    unsigned count = 0;
    for (const auto& file : std::filesystem::directory_iterator(directory)) {
        ++count;
        assert(file.is_regular_file());
    }
    assert(count == 128 * 4);
    assert(!std::filesystem::exists(directory / "texture-128.txt"));
    assert(std::filesystem::file_size(directory / "texture-0.raw") == 32);
    assert(std::filesystem::file_size(directory / "texture-0.rgba") == 128);
    assert(std::filesystem::file_size(directory / "texture-0.tlut") == 0);
    std::cout << "TEXTURE_OBSERVER_COMPONENT_PASS bounds/two-per-descriptor/128cap/RAM-and-GX-unchanged\n";
}
