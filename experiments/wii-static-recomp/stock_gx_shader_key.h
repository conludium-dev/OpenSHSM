#pragma once
#include "runtime/gx_state.h"
#include <cstdint>
#include <cstdlib>

namespace openshsm::experiment {

inline uint64_t semantic_tev_shader_key(const nwii::runtime::gx::GXState& state) {
    uint64_t hash = 14695981039346656037ull;
    const auto add8 = [&](uint8_t value) {
        hash = (hash ^ value) * 1099511628211ull;
    };
    const auto add32 = [&](uint32_t value) {
        for (unsigned byte = 0; byte < 4; ++byte) {
            add8(uint8_t(value >> (8 * byte)));
        }
    };
    const unsigned stages = state.numTevStages == 0 ? 1 : state.numTevStages;
    add8(uint8_t(stages));
    for (unsigned index = 0; index < stages; ++index) {
        const auto& stage = state.tevStages[index];
        const uint8_t fields[] = {
            stage.colorInA, stage.colorInB, stage.colorInC, stage.colorInD,
            stage.colorOp, stage.colorBias, stage.colorScale, stage.colorClamp,
            stage.colorRegId, stage.alphaInA, stage.alphaInB, stage.alphaInC,
            stage.alphaInD, stage.alphaOp, stage.alphaBias, stage.alphaScale,
            stage.alphaClamp, stage.alphaRegId, stage.texMap, stage.texCoord,
            stage.colorChan
        };
        for (uint8_t field : fields) {
            add8(field);
        }
        add8(uint8_t(state.bp[0xC1 + 2 * index] & 15));
    }
    for (unsigned index = 0; index < (stages + 1) / 2; ++index) {
        add32(state.bp[0xF6 + index]);
    }
    for (unsigned index = 0; index < 8; ++index) {
        add8(uint8_t(state.bp[0xF6 + index] & 15));
    }
    add8(state.alphaTest.ref0);
    add8(state.alphaTest.ref1);
    add8(state.alphaTest.comp0);
    add8(state.alphaTest.comp1);
    add8(state.alphaTest.logic);
    add8(std::getenv("NWII_FLATCOLOR") != nullptr);
    add8(std::getenv("NWII_NOALPHATEST") != nullptr);
    return hash;
}

}
