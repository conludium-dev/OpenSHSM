#pragma once
#include "stock_gx_texgen.h"
#include "stock_gx_vertex_sources.h"
#include "runtime/gx_state.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <span>
#include <stdexcept>

namespace openshsm::experiment {

inline GxTexVector generate_draw_regular_texcoord(
        const GxVertexSources& source, const nwii::runtime::gx::GXState& state,
        std::span<const float> post_matrices, unsigned index) {
    if (index >= state.numTexGens || index >= 8) {
        throw std::runtime_error("GX texture generator index outside bank");
    }
    GxTexgenControl control{};
    control.info = state.xf[0x40 + index];
    control.post_info = state.xf[0x50 + index];
    control.scale_s_minus_one = state.bp[0x30 + 2 * index] & 0xffff;
    control.scale_t_minus_one = state.bp[0x31 + 2 * index] & 0xffff;
    if (((control.info >> 4) & 7) != 0) {
        throw std::runtime_error("GX texture generator is not regular");
    }
    const unsigned row = (control.info >> 7) & 31;
    const bool present = row == 0 ? source.has_position :
        row == 1 ? source.has_normal :
        (row == 3 || row == 4) ? source.has_nbt :
        (row >= 5 && row <= 12) ? source.has_uv[row - 5] : false;
    if (!present) {
        throw std::runtime_error("GX texture generator source not decoded");
    }
    GxTexgenInput input{};
    input.position = source.position;
    input.normals = source.normals;
    input.uv = source.uv;
    input.matrix_indices = source.matrix_indices;
    auto result = gx_regular_texcoord(input, control, index,
        std::span<const float>(state.posMatrices), post_matrices,
        (state.xf[0x12] & 1) != 0);
    result[0] *= unsigned(control.scale_s_minus_one) + 1;
    result[1] *= unsigned(control.scale_t_minus_one) + 1;
    return result;
}

inline std::array<GxTexVector, 8> generate_draw_texcoords(
        const GxVertexSources& source, const nwii::runtime::gx::GXState& state,
        std::span<const float> post_matrices,
        const std::array<std::array<uint8_t, 4>, 2>& post_lighting_colors,
        GxTexVector view_position,
        const std::array<GxTexVector, 3>& transformed_normals,
        const std::array<GxTexVector, 8>& light_positions) {
    if (state.numTexGens > 8) {
        throw std::runtime_error("GX draw has more than eight texture generators");
    }
    GxTexgenInput input{};
    input.position = source.position;
    input.normals = source.normals;
    input.uv = source.uv;
    input.colors = post_lighting_colors;
    input.matrix_indices = source.matrix_indices;

    std::array<GxTexgenControl, 8> controls{};
    for (unsigned index = 0; index < state.numTexGens; ++index) {
        auto& control = controls[index];
        control.info = state.xf[0x40 + index];
        control.post_info = state.xf[0x50 + index];
        control.scale_s_minus_one = state.bp[0x30 + 2 * index] & 0xffff;
        control.scale_t_minus_one = state.bp[0x31 + 2 * index] & 0xffff;

        if (((control.info >> 4) & 7) == 0) {
            const unsigned row = (control.info >> 7) & 31;
            const bool present = row == 0 ? source.has_position :
                row == 1 ? source.has_normal :
                (row == 3 || row == 4) ? source.has_nbt :
                (row >= 5 && row <= 12) ? source.has_uv[row - 5] : false;
            if (!present) {
                throw std::runtime_error("GX texture generator source not decoded");
            }
        }
    }

    return generate_gx_texcoords(input,
        std::span<const GxTexgenControl>(controls.data(), state.numTexGens),
        std::span<const float>(state.posMatrices), post_matrices,
        (state.xf[0x12] & 1) != 0, view_position,
        transformed_normals, light_positions);
}

}
