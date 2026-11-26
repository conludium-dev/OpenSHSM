// Copyright 2009 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "Matrix.h"
#include <cassert>
#include <cstring>

namespace pinned {
using u32 = uint32_t;
using u8 = uint8_t;
using Vec3 = Common::Vec3;
enum class SourceRow : u32 { Geom, Normal, Colors, BinormalT, BinormalB, Tex0, Tex1, Tex2, Tex3, Tex4, Tex5, Tex6, Tex7 };
enum class TexSize : u32 { ST, STQ };
enum class TexInputForm : u32 { AB11, ABC1 };
enum class TexGenType : u32 { Regular, EmbossMap, Color0, Color1 };
struct SourceField {
    SourceRow value{};
    operator SourceRow() const { return value; }
    SourceRow Value() const { return value; }
};
struct TexMtxInfo {
    SourceField sourcerow;
    TexSize projection{};
    TexInputForm inputform{};
    TexGenType texgentype{};
    u32 embosssourceshift = 0, embosslightshift = 0;
};
struct PostMtxInfo { u32 index = 0; bool normalize = false; };
struct InputVertexData {
    Vec3 position{};
    Vec3 normal[3]{};
    Vec3 texCoords[8]{};
    u32 texMtx[8]{};
};
struct OutputVertexData {
    Vec3 mvPosition{};
    Vec3 normal[3]{};
    u8 color[2][4]{};
    Vec3 texCoords[8]{};
};
struct LightPointer {
    u32 reserved[3]{};
    u8 color[4]{};
    Vec3 cosatt{}, distatt{}, pos{}, dir{};
};
struct XfFixture {
    float posMatrices[256]{}, postMatrices[256]{};
    TexMtxInfo texMtxInfo[8]{};
    PostMtxInfo postMtxInfo[8]{};
    struct { u32 numTexGens = 0; } numTexGen;
    struct { bool enabled = false; } dualTexTrans;
    LightPointer lights[8]{};
};
inline XfFixture xfmem;
struct BpFixture {
    struct Scale { u32 scale_minus_1 = 0; };
    struct { Scale s, t; } texcoords[8];
};
inline BpFixture bpmem;
void TransformTexCoord(const InputVertexData*, OutputVertexData*);

inline void check(const openshsm::experiment::GxTexgenInput& input,
        std::span<const openshsm::experiment::GxTexgenControl> controls,
        std::span<const float> matrices, std::span<const float> post, bool dual,
        openshsm::experiment::GxTexVector position,
        const std::array<openshsm::experiment::GxTexVector, 3>& normals,
        const std::array<openshsm::experiment::GxTexVector, 8>& lights,
        const std::array<openshsm::experiment::GxTexVector, 8>& actual) {
    xfmem = {};
    bpmem = {};
    InputVertexData src{};
    OutputVertexData dst{};
    const auto vector = [](const auto& value) { return Vec3{value[0], value[1], value[2]}; };
    src.position = vector(input.position);
    dst.mvPosition = vector(position);
    for (unsigned index = 0; index < 3; ++index) {
        src.normal[index] = vector(input.normals[index]);
        dst.normal[index] = vector(normals[index]);
    }
    for (unsigned index = 0; index < 8; ++index) {
        src.texCoords[index] = {input.uv[index][0], input.uv[index][1], 0};
        src.texMtx[index] = input.matrix_indices[index];
        xfmem.lights[index].pos = vector(lights[index]);
    }
    std::memcpy(dst.color, input.colors.data(), sizeof(dst.color));
    assert(matrices.size() <= 256 && post.size() <= 256);
    std::copy(matrices.begin(), matrices.end(), xfmem.posMatrices);
    std::copy(post.begin(), post.end(), xfmem.postMatrices);
    xfmem.dualTexTrans.enabled = dual;
    xfmem.numTexGen.numTexGens = controls.size();
    for (unsigned index = 0; index < controls.size(); ++index) {
        const auto& control = controls[index];
        auto& info = xfmem.texMtxInfo[index];
        info.sourcerow.value = SourceRow((control.info >> 7) & 31);
        info.projection = TexSize((control.info >> 1) & 1);
        info.inputform = TexInputForm((control.info >> 2) & 1);
        info.texgentype = TexGenType((control.info >> 4) & 7);
        info.embosssourceshift = (control.info >> 12) & 7;
        info.embosslightshift = (control.info >> 15) & 7;
        xfmem.postMtxInfo[index] = {control.post_info & 63, (control.post_info & 256) != 0};
        bpmem.texcoords[index].s.scale_minus_1 = control.scale_s_minus_one;
        bpmem.texcoords[index].t.scale_minus_1 = control.scale_t_minus_one;
    }
    TransformTexCoord(&src, &dst);
    for (unsigned index = 0; index < controls.size(); ++index) {
        for (unsigned axis = 0; axis < 3; ++axis) {
            const float expected = dst.texCoords[index].data[axis];
            assert((std::isnan(expected) && std::isnan(actual[index][axis])) ||
                std::bit_cast<uint32_t>(expected) == std::bit_cast<uint32_t>(actual[index][axis]));
        }
    }
}
}
