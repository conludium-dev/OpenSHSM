#include "stock_gx_shader_key.h"
#include "runtime/gx/tev_shader_gen.h"
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <random>
#include <string>
#include <unordered_set>

int main() {
    using namespace nwii::runtime::gx;
    using openshsm::experiment::semantic_tev_shader_key;
    GXState state{};
    state.numTevStages = 1;
    state.tevStages[0].texMap = 0xff;
    state.tevStages[0].colorInA = 15;
    state.tevStages[0].colorInB = 15;
    state.tevStages[0].colorInC = 15;
    state.tevStages[0].colorInD = 14;
    state.tevStages[0].colorClamp = 1;
    state.alphaTest.comp0 = state.alphaTest.comp1 = 7;
    state.bp[0xF6] = 0x0C << 4;
    const auto source = GenerateTEVShader(state, 0x90);
    const uint64_t key = semantic_tev_shader_key(state);
    const uint64_t old_key = state.GetShaderHash(0x90);
    state.bp[0x41] = 0x123456;
    state.bp[0xE0] = 0x765432;
    state.cp[0x50] = 0xCAFEBABE;
    state.xf[0x3F] = 0x87654321;
    state.texStages[0].format = 8;
    assert(state.GetShaderHash(0x90) != old_key);
    assert(semantic_tev_shader_key(state) == key);
    assert(GenerateTEVShader(state, 0x98).vertex_source == source.vertex_source);
    assert(GenerateTEVShader(state, 0x98).fragment_source == source.fragment_source);
    state.bp[0xF6] = 0x0D << 4;
    assert(semantic_tev_shader_key(state) != key);
    assert(GenerateTEVShader(state, 0x90).fragment_source != source.fragment_source);
    state.bp[0xF6] = 0x0C << 4;
    std::unordered_set<uint64_t> old_keys;
    std::unordered_set<uint64_t> semantic_keys;
    for (unsigned index = 0; index < 256; ++index) {
        state.bp[0x41] = index;
        state.texStages[0].format = uint8_t(index);
        old_keys.insert(state.GetShaderHash(0x90));
        semantic_keys.insert(semantic_tev_shader_key(state));
    }
    assert(old_keys.size() == 256 && semantic_keys.size() == 1);

    std::mt19937 rng(0x5A17);
    for (unsigned trial = 0; trial < 2048; ++trial) {
        state = {};
        state.numTevStages = uint8_t(1 + rng() % 16);
        state.alphaTest.ref0 = uint8_t(rng());
        state.alphaTest.ref1 = uint8_t(rng());
        state.alphaTest.comp0 = uint8_t(rng() % 8);
        state.alphaTest.comp1 = uint8_t(rng() % 8);
        state.alphaTest.logic = uint8_t(rng() % 4);
        for (unsigned index = 0; index < state.numTevStages; ++index) {
            auto& stage = state.tevStages[index];
            stage.colorInA = uint8_t(rng() % 16);
            stage.colorInB = uint8_t(rng() % 16);
            stage.colorInC = uint8_t(rng() % 16);
            stage.colorInD = uint8_t(rng() % 16);
            stage.colorOp = uint8_t(rng() % 2);
            stage.colorBias = uint8_t(rng() % 3);
            stage.colorScale = uint8_t(rng() % 4);
            stage.colorClamp = uint8_t(rng() % 2);
            stage.colorRegId = uint8_t(rng() % 4);
            stage.alphaInA = uint8_t(rng() % 8);
            stage.alphaInB = uint8_t(rng() % 8);
            stage.alphaInC = uint8_t(rng() % 8);
            stage.alphaInD = uint8_t(rng() % 8);
            stage.alphaOp = uint8_t(rng() % 2);
            stage.alphaBias = uint8_t(rng() % 3);
            stage.alphaScale = uint8_t(rng() % 4);
            stage.alphaClamp = uint8_t(rng() % 2);
            stage.alphaRegId = uint8_t(rng() % 4);
            stage.texMap = uint8_t(rng() % 9 == 8 ? 0xff : rng() % 8);
            stage.texCoord = uint8_t(rng() % 8);
            stage.colorChan = uint8_t(rng() % 3);
        }
        for (unsigned index = 0; index < (state.numTevStages + 1) / 2; ++index) {
            state.bp[0xF6 + index] = rng();
        }
        const uint64_t before = semantic_tev_shader_key(state);
        const auto generated = GenerateTEVShader(state, 0x80);
        state.bp[0x41] = rng();
        state.bp[0xE0] = rng();
        state.cp[0x50] = rng();
        state.texStages[0].format = uint8_t(rng());
        assert(semantic_tev_shader_key(state) == before);
        const auto repeated = GenerateTEVShader(state, 0xA0);
        assert(repeated.vertex_source == generated.vertex_source);
        assert(repeated.fragment_source == generated.fragment_source);
        const uint8_t prior = state.tevStages[0].colorInD;
        state.tevStages[0].colorInD ^= 1;
        assert(semantic_tev_shader_key(state) != before);
        state.tevStages[0].colorInD = prior;
    }
    std::puts("GX_SEMANTIC_SHADER_KEY_PASS 2048");
}
