#include "stock_gx_texgen.h"
#include <cassert>
#include <iostream>
#include <limits>
#ifdef OPENSHSM_PINNED_TEXGEN
#include "stock_gx_texgen_reference_fixture.h"
#endif

static auto evaluate(const openshsm::experiment::GxTexgenInput& input,
        std::span<const openshsm::experiment::GxTexgenControl> controls,
        std::span<const float> matrices, std::span<const float> post, bool dual,
        openshsm::experiment::GxTexVector position,
        const std::array<openshsm::experiment::GxTexVector, 3>& normals,
        const std::array<openshsm::experiment::GxTexVector, 8>& lights) {
    const auto actual = openshsm::experiment::generate_gx_texcoords(input, controls,
        matrices, post, dual, position, normals, lights);
#ifdef OPENSHSM_PINNED_TEXGEN
    pinned::check(input, controls, matrices, post, dual, position, normals, lights, actual);
#endif
    return actual;
}

int main() {
    using namespace openshsm::experiment;
    GxTexgenInput input;
    input.position = {2, 3, 4};
    input.normals = {{{5, 6, 7}, {8, 9, 10}, {11, 12, 13}}};
    input.colors = {{{51, 102, 153, 255}, {204, 255, 102, 51}}};
    for (unsigned index = 0; index < 8; ++index) {
        input.uv[index] = {float(index + 1), float(index + 2)};
    }
    const std::array<float, 12> identity = {1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0};
    std::array<GxTexVector, 8> lights{};
    std::array<GxTexVector, 3> normals{};
    unsigned cases = 0;
    for (unsigned source : {0u, 1u, 3u, 4u, 5u, 6u, 7u, 8u, 9u, 10u, 11u, 12u}) {
        GxTexVector expected{};
        if (source == 0) {
            expected = input.position;
        } else if (source == 1) {
            expected = input.normals[0];
        } else if (source < 5) {
            expected = input.normals[source - 2];
        } else {
            expected = {input.uv[source - 5][0], input.uv[source - 5][1], 1};
        }
        for (unsigned form = 0; form < 2; ++form) {
            for (unsigned projection = 0; projection < 2; ++projection) {
                for (bool dual : {false, true}) {
                    std::array<GxTexgenControl, 8> controls{};
                    for (auto& control : controls) {
                        control.info = source << 7 | form << 2 | projection << 1;
                        control.scale_s_minus_one = 1;
                        control.scale_t_minus_one = 2;
                    }
                    const auto actual = evaluate(input, controls, identity, identity, dual, {}, normals, lights);
                    for (const auto& coordinate : actual) {
                        assert(coordinate[0] == expected[0] * 2 && coordinate[1] == expected[1] * 3);
                        assert(coordinate[2] == (form && projection ? expected[2] : 1));
                    }
                    ++cases;
                }
            }
        }
    }
    std::array<GxTexgenControl, 2> controls{};
    controls[0].info = 5u << 7;
    controls[1].info = 1u << 4;
    lights[0] = {1, 0, 0};
    normals[1] = {1, 0, 0};
    normals[2] = {0, 1, 0};
    auto output = evaluate(input, controls, identity, identity, false, {}, normals, lights);
    assert((output[1] == GxTexVector{2, 2, 1}));
    controls[0].info = 2u << 4;
    controls[1].info = 3u << 4;
    output = evaluate(input, controls, identity, identity, false, {}, normals, lights);
    assert(output[0][0] == 51.0f / 255 && output[1][1] == 1);
    controls[0].info = 5u << 7 | 2;
    auto qzero = identity;
    qzero[10] = 0;
    output = evaluate(input, std::span(controls).first(1), qzero, identity, false, {}, normals, lights);
    assert((output[0] == GxTexVector{0.5f, 1, 0}));
    input.uv[0][0] = std::numeric_limits<float>::quiet_NaN();
    output = evaluate(input, std::span(controls).first(1), identity, identity, false, {}, normals, lights);
    assert(output[0][0] == 1);
    unsigned refusals = 0;
    for (unsigned invalid : {2u << 7, 31u << 7, 7u << 4, 1u << 4}) {
        controls[0].info = invalid;
        try {
            (void)generate_gx_texcoords(input, std::span(controls).first(1), identity, identity, false, {}, normals, lights);
        } catch (const std::runtime_error&) {
            ++refusals;
        }
    }
    assert(refusals == 4);
    uint32_t random = 0x5348534d;
    const auto next = [&]() {
        random = random * 1664525u + 1013904223u;
        return random;
    };
    const auto scalar = [&]() { return float(int(next() & 255) - 128) / 32.0f; };
    std::array<float, 256> bank{}, post{};
    std::array<GxTexgenControl, 8> varied{};
    for (unsigned job = 0; job < 4096; ++job) {
        for (auto& value : bank) {
            value = scalar();
        }
        for (auto& value : post) {
            value = scalar();
        }
        for (auto& value : input.position) {
            value = scalar();
        }
        for (auto& vector : input.normals) {
            for (auto& value : vector) {
                value = scalar();
            }
        }
        for (auto& vector : normals) {
            for (auto& value : vector) {
                value = scalar();
            }
        }
        for (auto& vector : lights) {
            for (auto& value : vector) {
                value = scalar();
            }
        }
        for (auto& uv : input.uv) {
            uv = {scalar(), scalar()};
        }
        const unsigned sources[] = {0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12};
        for (unsigned index = 0; index < 8; ++index) {
            unsigned type = next() % 4;
            if (type == 1 && index == 0) {
                type = 0;
            }
            varied[index].info = type << 4;
            if (type == 0) {
                varied[index].info |= sources[next() % 12] << 7 | (next() & 1) << 2 | (next() & 1) << 1;
            } else if (type == 1) {
                varied[index].info |= (next() % index) << 12 | (next() % 8) << 15;
            }
            varied[index].post_info = next() % 62 | (next() & 1) << 8;
            varied[index].scale_s_minus_one = uint16_t(next());
            varied[index].scale_t_minus_one = uint16_t(next());
            input.matrix_indices[index] = uint8_t(next() % 62);
        }
        (void)evaluate(input, varied, bank, post, (job & 1) != 0, {scalar(), scalar(), scalar()}, normals, lights);
    }
#ifdef OPENSHSM_PINNED_TEXGEN
    std::cout << "GX_TEXGEN_PINNED_DIFFERENTIAL_PASS ";
#else
    std::cout << "GX_TEXGEN_MANUAL_SMOKE_PASS ";
#endif
    std::cout << cases << " regular jobs;4096 varied banks/post-normalization/scales/emboss jobs;colors/qzero/NaN;4refusals;NOT_GAME_RENDER\n";
}
