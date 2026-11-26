// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "stock_gx_vertex_sources.h"
#include <algorithm>
#include <bit>
#include <cassert>
#include <cstring>
#include <span>
#include <vector>

namespace pinned_normal {
using u8 = uint8_t;
using s8 = int8_t;
using u16 = uint16_t;
using s16 = int16_t;
using u32 = uint32_t;
enum class CPArray { Normal };
struct VertexLoader { unsigned m_remaining = 0; };
inline std::span<const u8> bytes;
inline size_t cursor = 0;
inline std::vector<float> written;
namespace Common {
template<class T> T FromBigEndian(T value) {
    auto representation = std::bit_cast<std::array<u8, sizeof(T)>>(value);
    if constexpr (std::endian::native == std::endian::little) {
        std::reverse(representation.begin(), representation.end());
    }
    return std::bit_cast<T>(representation);
}
}
namespace VertexLoaderManager {
inline std::array<float, 3> normal_cache{}, tangent_cache{}, binormal_cache{};
struct Bases {
    const u8* value = nullptr;
    const u8* operator[](CPArray) const { return value; }
};
inline Bases cached_arraybases;
}
struct MainState {
    struct Strides {
        u32 value = 0;
        u32 operator[](CPArray) const { return value; }
    } array_strides;
};
inline MainState g_main_cp_state;
inline const u8* DataGetPosition() { return bytes.data() + cursor; }
template<size_t N> void DataSkip() { cursor += N; assert(cursor <= bytes.size()); }
template<class T> T DataRead() {
    assert(cursor + sizeof(T) <= bytes.size());
    T value;
    std::memcpy(&value, bytes.data() + cursor, sizeof(T));
    cursor += sizeof(T);
    return Common::FromBigEndian(value);
}
inline void DataWrite(float value) { written.push_back(value); }
void check(unsigned type, unsigned mode, std::span<const u8> stream, const u8* array,
    u32 stride, const openshsm::experiment::GxVertexSources& source);
}
