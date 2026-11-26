// Copyright 2009 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <span>
#include <stdexcept>

namespace openshsm::experiment {

using GxTexVector = std::array<float, 3>;

struct GxTexgenInput {
    GxTexVector position{};
    std::array<GxTexVector, 3> normals{};
    std::array<std::array<float, 2>, 8> uv{};
    std::array<std::array<uint8_t, 4>, 2> colors{};
    std::array<uint8_t, 8> matrix_indices{};
};

struct GxTexgenControl {
    uint32_t info = 0;
    uint32_t post_info = 0;
    uint16_t scale_s_minus_one = 0;
    uint16_t scale_t_minus_one = 0;
};

inline GxTexVector gx_tex_normalize(GxTexVector value) {
    const float length = std::sqrt(value[0] * value[0] + value[1] * value[1] + value[2] * value[2]);
    for (auto& component : value) {
        component /= length;
    }
    return value;
}

inline GxTexVector gx_tex_multiply(GxTexVector value, std::span<const float> matrix, bool abc, bool stq) {
    if (matrix.size() < (stq ? 12u : 8u)) {
        throw std::runtime_error("GX texture matrix outside backed bank");
    }
    if (!abc) {
        value[2] = 1.0f;
    }
    GxTexVector result{};
    for (unsigned row = 0; row < (stq ? 3u : 2u); ++row) {
        result[row] = matrix[row * 4] * value[0] + matrix[row * 4 + 1] * value[1] +
            matrix[row * 4 + 2] * value[2] + matrix[row * 4 + 3];
    }
    if (!stq) {
        result[2] = 1.0f;
    }
    return result;
}

inline GxTexVector gx_regular_texcoord(const GxTexgenInput& input,
        const GxTexgenControl& control, unsigned index, std::span<const float> matrices,
        std::span<const float> post_matrices, bool dual) {
    const unsigned source = (control.info >> 7) & 31;
    GxTexVector value{};
    if (source == 0) {
        value = input.position;
    } else if (source == 1) {
        value = input.normals[0];
    } else if (source == 3 || source == 4) {
        value = input.normals[source - 2];
    } else if (source >= 5 && source <= 12) {
        value = {input.uv[source - 5][0], input.uv[source - 5][1], 1.0f};
    } else {
        throw std::runtime_error("Invalid regular GX texture source");
    }
    for (auto& component : value) {
        if (std::isnan(component)) {
            component = 1.0f;
        }
    }
    const size_t base = size_t(input.matrix_indices[index]) * 4;
    if (base > matrices.size()) {
        throw std::runtime_error("GX texture matrix index outside bank");
    }
    GxTexVector result = gx_tex_multiply(value, matrices.subspan(base),
        (control.info & 4) != 0, (control.info & 2) != 0);
    if (dual) {
        const size_t post_base = size_t(control.post_info & 63) * 4;
        if (post_base > post_matrices.size()) {
            throw std::runtime_error("GX post matrix index outside bank");
        }
        auto temporary = result;
        if (control.post_info & 256) {
            temporary = gx_tex_normalize(temporary);
        }
        result = gx_tex_multiply(temporary, post_matrices.subspan(post_base), true, true);
    }
    if (result[2] == 0.0f) {
        result[0] = std::clamp(result[0] / 2.0f, -1.0f, 1.0f);
        result[1] = std::clamp(result[1] / 2.0f, -1.0f, 1.0f);
    }
    return result;
}

inline std::array<GxTexVector, 8> generate_gx_texcoords(const GxTexgenInput& input,
        std::span<const GxTexgenControl> controls, std::span<const float> matrices,
        std::span<const float> post_matrices, bool dual, GxTexVector view_position,
        const std::array<GxTexVector, 3>& transformed_normals,
        const std::array<GxTexVector, 8>& light_positions) {
    if (controls.size() > 8) {
        throw std::runtime_error("Too many GX texture generators");
    }
    std::array<GxTexVector, 8> result{};
    for (unsigned index = 0; index < controls.size(); ++index) {
        const auto& control = controls[index];
        const unsigned type = (control.info >> 4) & 7;
        if (type == 0) {
            result[index] = gx_regular_texcoord(input, control, index, matrices, post_matrices, dual);
        } else if (type == 1) {
            const unsigned previous = (control.info >> 12) & 7;
            const unsigned light = (control.info >> 15) & 7;
            if (previous >= index) {
                throw std::runtime_error("Unverified forward GX emboss dependency");
            }
            GxTexVector direction{};
            for (unsigned axis = 0; axis < 3; ++axis) {
                direction[axis] = light_positions[light][axis] - view_position[axis];
            }
            direction = gx_tex_normalize(direction);
            result[index] = result[previous];
            for (unsigned axis = 0; axis < 2; ++axis) {
                result[index][axis] += direction[0] * transformed_normals[axis + 1][0] +
                    direction[1] * transformed_normals[axis + 1][1] + direction[2] * transformed_normals[axis + 1][2];
            }
        } else if ((type == 2 || type == 3) && !(control.info & 4)) {
            result[index] = {input.colors[type - 2][0] / 255.0f, input.colors[type - 2][1] / 255.0f, 1.0f};
        } else {
            throw std::runtime_error("Invalid GX texture generator type/input form");
        }
    }
    for (unsigned index = 0; index < controls.size(); ++index) {
        result[index][0] *= unsigned(controls[index].scale_s_minus_one) + 1;
        result[index][1] *= unsigned(controls[index].scale_t_minus_one) + 1;
    }
    return result;
}

}
