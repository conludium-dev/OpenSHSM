#pragma once
#include <array>
#include <cstdint>

namespace openshsm::experiment {

struct GxVertexSources {
    std::array<float, 3> position{};
    std::array<std::array<float, 3>, 3> normals{};
    std::array<std::array<float, 4>, 2> colors{};
    std::array<std::array<float, 2>, 8> uv{};
    std::array<uint8_t, 8> matrix_indices{};
    std::array<bool, 2> has_color{};
    std::array<bool, 8> has_uv{};
    bool has_position = false;
    bool has_normal = false;
    bool has_nbt = false;
};

}
