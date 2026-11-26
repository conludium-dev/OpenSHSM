#include "runtime/gx/fifo_parser.h"
#include <algorithm>
#include <bit>
#include <cassert>
#include <iostream>
#ifdef OPENSHSM_SOURCE_VERTEX
#include "stock_gx_attribute_bounds.h"
#include "stock_gx_texgen_bridge.h"
namespace nwii::runtime { extern MMU* g_mmu; }
#ifdef OPENSHSM_PINNED_NORMAL
#include "stock_gx_normal_reference_fixture.h"
#endif
#endif

static void append_float(std::vector<uint8_t>& bytes, float value) {
    const auto bits = std::bit_cast<uint32_t>(value);
    for (int shift = 24; shift >= 0; shift -= 8) {
        bytes.push_back(uint8_t(bits >> shift));
    }
}

int main(int argc, char**) {
    using namespace nwii::runtime::gx;
    const bool baseline = argc == 2;
#ifdef OPENSHSM_SOURCE_VERTEX
    GXState texgen_state{};
    texgen_state.numTexGens = 1;
    texgen_state.posMatrices[0] = 1.0f;
    texgen_state.posMatrices[5] = 1.0f;
    const std::array<float, 256> post_matrices{};
    const std::array<std::array<uint8_t, 4>, 2> lit_colors{};
    const std::array<openshsm::experiment::GxTexVector, 3> transformed_normals{};
    const std::array<openshsm::experiment::GxTexVector, 8> light_positions{};
#endif
    unsigned cases = 0;
    for (unsigned mask = 1; mask < 256; ++mask) {
        for (unsigned components = 1; components <= 2; ++components) {
            GXCommand command{};
            command.type = GXCommandType::DrawPrimitive;
            command.raw = std::make_shared<DrawRaw>();
            auto retained_raw = command.raw;
            auto& raw = *retained_raw;
            raw.count = 2;
            raw.vat.posMask = VtxAttrMask::Direct;
            raw.vat.posType = VtxAttrType::F32;
            raw.vat.posElements = true;
            for (unsigned slot = 0; slot < 8; ++slot) {
                raw.vat.texMask[slot] = mask & (1u << slot) ? VtxAttrMask::Direct : VtxAttrMask::None;
                raw.vat.texType[slot] = VtxAttrType::F32;
                raw.vat.texElements[slot] = components == 2;
            }
            for (unsigned vertex = 0; vertex < 2; ++vertex) {
                for (unsigned axis = 0; axis < 3; ++axis) {
                    append_float(raw.bytes, float(vertex * 10 + axis));
                }
                for (unsigned slot = 0; slot < 8; ++slot) {
                    if (mask & (1u << slot)) {
                        for (unsigned axis = 0; axis < components; ++axis) {
                            append_float(raw.bytes, float(vertex * 100 + slot * 10 + axis + 1));
                        }
                    }
                }
            }
            const auto saved_bytes = raw.bytes;
            FifoParser::DecodeDraw(command);
            assert(command.vertices.size() == 2);
            for (unsigned vertex = 0; vertex < 2; ++vertex) {
                const auto& actual = command.vertices[vertex];
                assert(actual.pos[2] == float(vertex * 10 + 2));
#ifdef OPENSHSM_SOURCE_VERTEX
                if (!baseline) {
                    assert(command.raw && command.raw != retained_raw);
                    assert(command.raw->bytes.empty() && command.raw->sources.size() == 2);
                    assert(raw.bytes == saved_bytes && raw.sources.empty());
                    assert(command.raw->sources[vertex].position[2] == actual.pos[2]);
                    for (unsigned slot = 0; slot < 8; ++slot) {
                        assert(command.raw->sources[vertex].has_uv[slot] == actual.has_tex[slot]);
                        assert(command.raw->sources[vertex].uv[slot][0] == actual.tex[slot][0]);
                        if (actual.has_tex[slot]) {
                            texgen_state.xf[0x40] = (slot + 5) << 7;
                            const auto coordinates = openshsm::experiment::generate_draw_texcoords(
                                command.raw->sources[vertex], texgen_state, post_matrices,
                                lit_colors, {0.0f, 0.0f, 0.0f}, transformed_normals,
                                light_positions);
                            assert(coordinates[0][0] == actual.tex[slot][0]);
                            assert(coordinates[0][1] == actual.tex[slot][1]);
                            assert(coordinates[0][2] == 1.0f);
                        }
                    }
                }
#endif
                for (unsigned slot = 0; slot < 8; ++slot) {
                    const bool present = (mask & (1u << slot)) && (!baseline || slot == 0);
                    assert(actual.has_tex[slot] == present);
                    if (present) {
                        assert(actual.tex[slot][0] == float(vertex * 100 + slot * 10 + 1));
                        if (components == 2) {
                            assert(actual.tex[slot][1] == float(vertex * 100 + slot * 10 + 2));
                        }
                    }
                }
            }
            command.vertices.clear();
            command.raw = retained_raw;
            raw.bytes = saved_bytes;
            raw.bytes.pop_back();
            FifoParser::DecodeDraw(command);
            assert(command.vertices.size() == 1);
            ++cases;
        }
    }
    std::cout << (baseline ? "UV_BASELINE_LOSS_REPRODUCED " : "UV_EIGHT_DIRECT_ATTRIBUTES_PASS ")
              << cases << " masks/components/twovertices/truncation\n";
#ifdef OPENSHSM_SOURCE_VERTEX
    if (!baseline) {
        GXCommand command{};
        command.type = GXCommandType::DrawPrimitive;
        command.raw = std::make_shared<DrawRaw>();
        auto& raw = *command.raw;
        raw.count = 1;
        raw.vat.posMask = VtxAttrMask::Direct;
        raw.vat.posType = VtxAttrType::F32;
        raw.vat.posElements = true;
        raw.vat.nrmMask = VtxAttrMask::Direct;
        raw.vat.nrmType = VtxAttrType::F32;
        raw.vat.nrmElements = true;
        raw.need_normal = false;
        raw.have_snap_mtx = true;
        const float position_matrix[] = {2, 0, 0, 5, 0, 3, 0, 6, 0, 0, 4, 7};
        const float normal_matrix[] = {5, 0, 0, 0, 6, 0, 0, 0, 7};
        std::copy_n(position_matrix, 12, raw.snap_pos_mtx);
        std::copy_n(normal_matrix, 9, raw.snap_nrm_mtx);
        for (float value : {2.0f, 3.0f, 4.0f}) {
            append_float(raw.bytes, value);
        }
        for (unsigned index = 1; index <= 9; ++index) {
            append_float(raw.bytes, float(index));
        }
        for (unsigned color = 0; color < 2; ++color) {
            raw.vat.clrMask[color] = VtxAttrMask::Direct;
            raw.vat.clrType[color] = VtxAttrType(5);
        }
        raw.bytes.insert(raw.bytes.end(), {51, 102, 153, 204, 255, 127, 63, 31});
        FifoParser::DecodeDraw(command);
        assert(command.raw && raw.sources.size() == 1 && command.vertices.size() == 1);
        const auto& source = raw.sources[0];
        const auto& vertex = command.vertices[0];
        assert(source.has_position && source.has_normal && source.has_nbt);
        assert((source.position == std::array<float, 3>{2, 3, 4}));
        assert(vertex.pre_xf && vertex.pos[0] == 9 && vertex.pos[1] == 15 && vertex.pos[2] == 23);
        assert(vertex.norm[0] == 5 && vertex.norm[1] == 12 && vertex.norm[2] == 21);
        for (unsigned normal = 0; normal < 3; ++normal) {
            for (unsigned axis = 0; axis < 3; ++axis) {
                assert(source.normals[normal][axis] == float(normal * 3 + axis + 1));
            }
        }
        assert(source.has_color[0] && source.has_color[1]);
        assert(source.colors[0][0] == 51.0f / 255 && source.colors[1][1] == 127.0f / 255);
        command.vertices.clear();
        raw.vat.nrmMask = VtxAttrMask::Index8;
        raw.vat.nrmIndex3 = true;
        for (float value : {2.0f, 3.0f, 4.0f}) {
            append_float(raw.bytes, value);
        }
        raw.bytes.insert(raw.bytes.end(), {1, 2, 3});
        FifoParser::DecodeDraw(command);
        assert(command.vertices.empty() && raw.sources.empty());
        auto mmu = std::make_unique<nwii::runtime::MMU>();
        nwii::runtime::g_mmu = mmu.get();
        unsigned normal_cases = 0;
        for (unsigned type = 0; type < 8; ++type) {
            const unsigned width = type < 2 ? 1 : type < 4 ? 2 : 4;
            const float divisor = type == 0 ? 128 : type == 1 ? 64 : type == 2 ? 32768 : type == 3 ? 16384 : 1;
            const auto value = [&](unsigned entry, unsigned component) {
                float result = float(entry * 20 + component + 1);
                if ((type == 1 || type == 3) && (component & 1)) {
                    result = -result;
                }
                return type >= 4 ? result / 4 : result;
            };
            const auto bits = [&](float scalar) {
                return type >= 4 ? std::bit_cast<uint32_t>(scalar) : uint32_t(int32_t(scalar));
            };
            const auto append = [&](uint32_t scalar) {
                for (int shift = int(width - 1) * 8; shift >= 0; shift -= 8) {
                    raw.bytes.push_back(uint8_t(scalar >> shift));
                }
            };
            constexpr uint32_t array = 0x80001000;
            for (unsigned entry = 1; entry <= 3; ++entry) {
                for (unsigned component = 0; component < 9; ++component) {
                    const uint32_t scalar = bits(value(entry, component));
                    for (unsigned byte = 0; byte < width; ++byte) {
                        mmu->write8(array + entry * 64 + component * width + byte,
                            uint8_t(scalar >> ((width - 1 - byte) * 8)));
                    }
                }
            }
            for (unsigned mode = 0; mode < 8; ++mode) {
                command.vertices.clear();
                raw.bytes.clear();
                raw.vat.nrmType = VtxAttrType(type);
                raw.vat.nrmElements = mode == 1 || mode >= 4;
                raw.vat.nrmIndex3 = mode >= 6;
                raw.vat.nrmMask = mode < 2 ? VtxAttrMask::Direct : (mode & 1) ? VtxAttrMask::Index16 : VtxAttrMask::Index8;
                raw.arrayBase[1] = array;
                raw.arrayStride[1] = 64;
                raw.vat.clrMask[0] = raw.vat.clrMask[1] = VtxAttrMask::None;
                raw.vat.texMask[0] = VtxAttrMask::Direct;
                raw.vat.texType[0] = VtxAttrType::F32;
                raw.vat.texElements[0] = true;
                for (float scalar : {2.0f, 3.0f, 4.0f}) {
                    append_float(raw.bytes, scalar);
                }
                const unsigned vectors = raw.vat.nrmElements ? 3 : 1;
                if (mode < 2) {
                    for (unsigned component = 0; component < vectors * 3; ++component) {
                        append(bits(value(1, component)));
                    }
                } else {
                    for (unsigned index = 1; index <= (raw.vat.nrmIndex3 ? 3u : 1u); ++index) {
                        if (raw.vat.nrmMask == VtxAttrMask::Index16) {
                            raw.bytes.push_back(0);
                        }
                        raw.bytes.push_back(uint8_t(index));
                    }
                }
                append_float(raw.bytes, 7);
                append_float(raw.bytes, 8);
                const auto normal_stream = raw.bytes;
                FifoParser::DecodeDraw(command);
                assert(command.vertices.size() == 1 && raw.sources.size() == 1);
                for (unsigned normal = 0; normal < vectors; ++normal) {
                    for (unsigned axis = 0; axis < 3; ++axis) {
                        const unsigned entry = raw.vat.nrmIndex3 ? normal + 1 : 1;
                        assert(raw.sources[0].normals[normal][axis] == value(entry, normal * 3 + axis) / divisor);
                    }
                }
                assert(raw.sources[0].uv[0][0] == 7 && raw.sources[0].uv[0][1] == 8);
#ifdef OPENSHSM_PINNED_NORMAL
                pinned_normal::check(type, mode, normal_stream, mmu->get_ptr(array), 64, raw.sources[0]);
#endif
                ++normal_cases;
            }
        }
        assert(normal_cases == 64);
        assert(openshsm::experiment::gx_attribute_pointer(*mmu, 0x80001000, 36));
        assert(!openshsm::experiment::gx_attribute_pointer(*mmu, 0x817fffff, 2));
        assert(!openshsm::experiment::gx_attribute_pointer(*mmu, 0x93ffffff, 2));
        assert(!openshsm::experiment::gx_attribute_pointer(*mmu, 0xe003ffff, 2));
        assert(!openshsm::experiment::gx_attribute_pointer(*mmu, 0xcc005000, 4));
        unsigned malformed = 0;
        for (unsigned guard = 0; guard < 3; ++guard) {
            command.vertices.clear();
            raw.bytes.clear();
            raw.arrayBase[1] = guard == 0 ? 0xffffffc0u : guard == 1 ? 0x817fffbdu : 0x80001000u;
            for (float scalar : {2.0f, 3.0f, 4.0f}) {
                append_float(raw.bytes, scalar);
            }
            raw.bytes.insert(raw.bytes.end(), {0, 1, 0, 2});
            if (guard != 2) {
                raw.bytes.insert(raw.bytes.end(), {0, 3});
                append_float(raw.bytes, 7);
                append_float(raw.bytes, 8);
            }
            FifoParser::DecodeDraw(command);
            assert(command.vertices.empty() && raw.sources.empty());
            ++malformed;
        }
        assert(malformed == 3);
        unsigned uv_cases = 0;
        const float uv_values[5][2] = {
            {64, 32}, {-64, 32}, {256, 64}, {-256, 64}, {1.5f, -2.25f}
        };
        const uint32_t uv_bits[5][2] = {
            {64, 32}, {0xc0, 32}, {0x0100, 64}, {0xff00, 64},
            {std::bit_cast<uint32_t>(1.5f), std::bit_cast<uint32_t>(-2.25f)}
        };
        for (unsigned slot = 0; slot < 8; ++slot) {
            for (unsigned type = 0; type < 5; ++type) {
                const unsigned width = type < 2 ? 1 : type < 4 ? 2 : 4;
                for (unsigned shift : {0u, 3u, 31u}) {
                    for (unsigned components = 1; components <= 2; ++components) {
                        for (unsigned mode = 0; mode < 3; ++mode) {
                            GXCommand uv_command{};
                            uv_command.type = GXCommandType::DrawPrimitive;
                            uv_command.raw = std::make_shared<DrawRaw>();
                            auto& uv_raw = *uv_command.raw;
                            uv_raw.count = 1;
                            uv_raw.vat.posMask = VtxAttrMask::Direct;
                            uv_raw.vat.posType = VtxAttrType::F32;
                            uv_raw.vat.posElements = true;
                            uv_raw.vat.texMask[slot] = mode == 0 ? VtxAttrMask::Direct :
                                mode == 1 ? VtxAttrMask::Index8 : VtxAttrMask::Index16;
                            uv_raw.vat.texType[slot] = VtxAttrType(type);
                            uv_raw.vat.texShift[slot] = shift;
                            uv_raw.vat.texElements[slot] = components == 2;
                            uv_raw.defTexMtxIdx[slot] = uint8_t(slot + 3);
                            uv_raw.arrayBase[4 + slot] = 0x80002000u + slot * 0x100u;
                            uv_raw.arrayStride[4 + slot] = 16;
                            for (float scalar : {2.0f, 3.0f, 4.0f}) {
                                append_float(uv_raw.bytes, scalar);
                            }
                            for (unsigned component = 0; component < components; ++component) {
                                const uint32_t bits = uv_bits[type][component];
                                for (unsigned byte = 0; byte < width; ++byte) {
                                    const uint8_t value = uint8_t(bits >> ((width - 1 - byte) * 8));
                                    if (mode == 0) {
                                        uv_raw.bytes.push_back(value);
                                    } else {
                                        mmu->write8(uv_raw.arrayBase[4 + slot] + 16 + component * width + byte, value);
                                    }
                                }
                            }
                            if (mode == 1) {
                                uv_raw.bytes.push_back(1);
                            } else if (mode == 2) {
                                uv_raw.bytes.insert(uv_raw.bytes.end(), {0, 1});
                            }
                            FifoParser::DecodeDraw(uv_command);
                            assert(uv_command.vertices.size() == 1 && uv_command.raw->sources.size() == 1);
                            const auto& vertex = uv_command.vertices[0];
                            const auto& saved = uv_command.raw->sources[0];
                            assert(saved.matrix_indices[slot] == slot + 3);
                            for (unsigned other = 0; other < 8; ++other) {
                                assert(saved.has_uv[other] == (other == slot));
                            }
                            for (unsigned component = 0; component < components; ++component) {
                                float expected = uv_values[type][component];
                                if (type < 4) {
                                    expected /= float(uint32_t(1) << shift);
                                }
                                assert(vertex.tex[slot][component] == expected);
                                assert(saved.uv[slot][component] == expected);
                            }
                            texgen_state.xf[0x40] = (slot + 5) << 7;
                            const unsigned base = (slot + 3) * 4;
                            std::fill_n(texgen_state.posMatrices + base, 8, 0.0f);
                            texgen_state.posMatrices[base] = 1.0f;
                            texgen_state.posMatrices[base + 5] = 1.0f;
                            const auto coordinates = openshsm::experiment::generate_draw_texcoords(
                                saved, texgen_state, post_matrices, lit_colors,
                                {0.0f, 0.0f, 0.0f}, transformed_normals, light_positions);
                            assert(coordinates[0][0] == vertex.tex[slot][0]);
                            assert(coordinates[0][1] == vertex.tex[slot][1]);
                            assert(coordinates[0][2] == 1.0f);
                            ++uv_cases;
                        }
                    }
                }
            }
        }
        assert(uv_cases == 720);
        for (unsigned guard = 0; guard < 3; ++guard) {
            GXCommand uv_command{};
            uv_command.type = GXCommandType::DrawPrimitive;
            uv_command.raw = std::make_shared<DrawRaw>();
            auto& uv_raw = *uv_command.raw;
            uv_raw.count = 1;
            uv_raw.vat.posMask = VtxAttrMask::Direct;
            uv_raw.vat.posType = VtxAttrType::F32;
            uv_raw.vat.posElements = true;
            uv_raw.vat.texMask[7] = VtxAttrMask::Index8;
            uv_raw.vat.texType[7] = VtxAttrType::U16;
            uv_raw.vat.texElements[7] = true;
            uv_raw.arrayBase[11] = guard == 0 ? 0x817fffffu : guard == 1 ? 0xfffffff0u : 0x80002000u;
            uv_raw.arrayStride[11] = guard == 1 ? 64 : 0;
            for (float scalar : {2.0f, 3.0f, 4.0f}) {
                append_float(uv_raw.bytes, scalar);
            }
            if (guard != 2) {
                uv_raw.bytes.push_back(1);
            }
            FifoParser::DecodeDraw(uv_command);
            assert(uv_command.vertices.empty() && uv_raw.sources.empty());
        }
        nwii::runtime::g_mmu = nullptr;
#ifdef OPENSHSM_PINNED_NORMAL
        std::cout << "PINNED_NORMAL_LOADER_64_PASS normalized values/index3 offsets/stream position\n";
#endif
        std::cout << "GX_DECODE_TO_TEXGEN_BRIDGE_PASS 8source-rows/510draw+720numeric-fixtures\n";
        std::cout << "RAW_VERTEX_SOURCES_UV_PASS VertexData=" << sizeof(VertexData)
                  << " GXCommand=" << sizeof(GXCommand) << " RawPrefix=" << offsetof(DrawRaw, sources)
                  << ";raw/view-position,NBT,color1;shared-cache-preserved;64normal-format/index jobs;720direct/indexed/fixed-UV jobs;4bank-boundaries;6malformed-index guards\n";
    }
#endif
}
