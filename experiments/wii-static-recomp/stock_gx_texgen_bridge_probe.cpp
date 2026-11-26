#include "stock_gx_texgen_bridge.h"
#include <cassert>
#include <cmath>
#include <cstdio>

using namespace openshsm::experiment;

int main() {
    nwii::runtime::gx::GXState state{};
    GxVertexSources source{};
    source.position = {4.0f, 5.0f, 6.0f};
    source.has_position = true;
    source.uv[2] = {2.0f, 3.0f};
    source.has_uv[2] = true;
    source.normals[1] = {7.0f, 8.0f, 9.0f};
    source.has_normal = true;
    source.has_nbt = true;
    source.matrix_indices = {0, 3, 6, 0, 0, 0, 0, 0};
    state.numTexGens = 3;
    state.xf[0x40] = 7 << 7;
    state.xf[0x41] = (0 << 7) | 2 | 4;
    state.xf[0x42] = (3 << 7) | 4;
    state.bp[0x30] = 1;
    state.bp[0x31] = 2;
    state.posMatrices[0] = 1.0f;
    state.posMatrices[5] = 1.0f;
    state.posMatrices[12] = 2.0f;
    state.posMatrices[17] = 3.0f;
    state.posMatrices[22] = 1.0f;
    state.posMatrices[24] = 1.0f;
    state.posMatrices[29] = 1.0f;

    std::array<float, 256> post{};
    const std::array<std::array<uint8_t, 4>, 2> colors{};
    const std::array<GxTexVector, 3> transformed_normals{};
    const std::array<GxTexVector, 8> lights{};
    auto run = [&] {
        return generate_draw_texcoords(source, state, post, colors,
            {0.0f, 0.0f, 0.0f}, transformed_normals, lights);
    };
    const auto first = run();
    assert(first[0] == (GxTexVector{4.0f, 9.0f, 1.0f}));
    assert(first[1] == (GxTexVector{8.0f, 15.0f, 6.0f}));
    assert(first[2] == (GxTexVector{7.0f, 8.0f, 1.0f}));
    source.has_uv[2] = false;
    assert(generate_draw_regular_texcoord(source, state, post, 1) == first[1]);
    assert(generate_draw_regular_texcoord(source, state, post, 2) == first[2]);
    source.has_uv[2] = true;

    state.xf[0x12] = 1;
    state.xf[0x50] = 2;
    post[8] = 4.0f;
    post[13] = 5.0f;
    post[18] = 1.0f;
    const auto second = run();
    assert(second[0] == (GxTexVector{16.0f, 45.0f, 1.0f}));

    source.has_uv[2] = false;
    bool rejected = false;
    try {
        (void)run();
    } catch (const std::runtime_error&) {
        rejected = true;
    }
    assert(rejected);
    source.has_uv[2] = true;
    state.numTexGens = 9;
    rejected = false;
    try {
        (void)run();
    } catch (const std::runtime_error&) {
        rejected = true;
    }
    assert(rejected);
    std::puts("GX_TEXGEN_BRIDGE_PASS 3channels/dualpost/2guards");
}
