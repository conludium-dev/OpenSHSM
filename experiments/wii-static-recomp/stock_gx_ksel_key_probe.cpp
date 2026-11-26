#include "runtime/gx_state.h"
#include "runtime/gx/tev_shader_gen.h"
#include <cassert>
#include <cstdio>
#include <string>

int main() {
    nwii::runtime::gx::GXState state{};
    state.numTevStages = 1;
    state.tevStages[0].colorInD = 14;
    state.bp[0xF6] = 0x0C << 4;
    const auto first = nwii::runtime::gx::GenerateTEVShader(state, 0x90);
    const auto first_hash = state.GetShaderHash(0x90);
    state.bp[0xF6] = 0x0D << 4;
    const auto second = nwii::runtime::gx::GenerateTEVShader(state, 0x90);
    assert(first_hash == state.GetShaderHash(0x90));
    assert(first.fragment_source != second.fragment_source);
    assert(first.fragment_source.find("uTevKColor[0].rgb") != std::string::npos);
    assert(second.fragment_source.find("uTevKColor[1].rgb") != std::string::npos);
    std::puts("GX_KSEL_OLD_HASH_COLLISION_CONFIRMED");
}
