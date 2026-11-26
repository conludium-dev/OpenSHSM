#include "stock_axwii_voice_input.h"
#include "axwii-voice-input-reference.h"
#include <iostream>

using namespace openshsm::experiment;

static void require(bool passed) {
    if (!passed) {
        throw std::runtime_error("AXWii voice input comparison failed");
    }
}

int main() {
    static_assert(offsetof(AXPBWii, audio_addr) == 120);
    static_assert(offsetof(AXPBWii, adpcm) == 136);
    static_assert(offsetof(AXPBWii, src) == 176);
    static_assert(offsetof(AXPBWii, adpcm_loop_info) == 190);
    static_assert(sizeof(AXPBWii) == 310);
    uint32_t random = 0x5348534d;
    const auto next = [&]() {
        random ^= random << 13;
        random ^= random >> 17;
        random ^= random << 5;
        return random;
    };
    unsigned jobs = 0;
    for (unsigned fixture = 0; fixture < 256; ++fixture) {
        std::array<uint8_t, 4096> memory;
        std::array<int16_t, 2048> banks;
        for (auto& byte : memory) {
            byte = uint8_t(next());
        }
        for (auto& value : banks) {
            value = int16_t(next());
        }
        for (uint16_t format : {uint16_t(0), uint16_t(0x19), uint16_t(0xa)}) {
            for (unsigned mode = 0; mode < 4; ++mode) {
                for (unsigned loop = 0; loop < 3; ++loop) {
                    AxWiiParameterBlock candidate;
                    for (auto& word : candidate.words) {
                        word = uint16_t(next());
                    }
                    std::fill_n(candidate.words.begin() + 53, 5, 0);
                    AXPBWii original;
                    std::memcpy(&original, candidate.words.data(), sizeof(original));
                    original.src_type = mode == 3 ? 0 : mode;
                    original.coef_select = fixture % 4;
                    original.running = 1;
                    original.is_stream = loop == 2;
                    original.audio_addr.looping = loop != 0;
                    original.audio_addr.sample_format = format;
                    original.audio_addr.loop_addr_hi = 0;
                    original.audio_addr.loop_addr_lo = 34;
                    original.audio_addr.end_addr_hi = 0;
                    original.audio_addr.end_addr_lo = fixture % 3 == 0 ? 47 : fixture % 3 == 1 ? 48 : 49;
                    original.audio_addr.cur_addr_hi = 0;
                    original.audio_addr.cur_addr_lo = 34;
                    original.src.ratio_hi = fixture % 5 == 0 ? 4 : 0;
                    original.src.ratio_lo = fixture % 5 == 0 ? 0 : uint16_t(128 + next() % 65408);
                    if (original.src_type == 2) {
                        original.src.ratio_hi = original.src.ratio_lo = fixture & 1 ? 65535 : 0;
                    }
                    for (auto& coefficient : original.adpcm.coefs) {
                        coefficient = int16_t(int(next() % 8193) - 4096);
                    }
                    std::memcpy(candidate.words.data(), &original, sizeof(original));
                    const auto coefficients = mode == 3 ? std::span<const int16_t>{} : std::span<const int16_t>(banks);
                    for (unsigned frame = 0; frame < 2; ++frame) {
                        const auto actual = get_axwii_voice_input(candidate, memory, 96, coefficients);
                        Oracle accelerator(memory, AxWiiSampleState{});
                        std::array<int16_t, 98> expected;
                        expected.fill(12345);
                        GetInputSamples(&accelerator, original, expected.data() + 1, 96,
                            coefficients.empty() ? nullptr : coefficients.data());
                        require(std::equal(actual.output.begin(), actual.output.end(), expected.begin() + 1));
                        require(expected.front() == 12345 && expected.back() == 12345);
                        require(std::memcmp(candidate.words.data(), &original, sizeof(original)) == 0);
                        ++jobs;
                    }
                }
            }
        }
    }
    unsigned refusals = 0;
    for (unsigned fixture = 0; fixture < 5; ++fixture) {
        AxWiiParameterBlock pb;
        pb.words[4] = 2;
        pb.words[88] = 1;
        pb.words[61] = 0xa;
        pb.words[84] = 2048;
        std::array<uint8_t, 8192> memory{};
        std::array<int16_t, 2048> banks{};
        if (fixture == 0) {
            pb.words[5] = 4;
        } else if (fixture == 1) {
            pb.words[4] = 3;
        } else if (fixture == 2) {
            pb.words[4] = 0;
            pb.words[88] = 5;
        } else if (fixture == 3) {
            pb.words[67] = 4095;
        }
        const auto before = pb.words;
        try {
            (void)get_axwii_voice_input(pb, memory, 96, std::span(banks).first(fixture == 4 ? 2047 : 2048));
        } catch (const std::runtime_error&) {
            ++refusals;
        }
        require(pb.words == before);
    }
    require(refusals == 5);
    std::cout << "AXWII_VOICE_INPUT_REFERENCE_CHAIN_PASS " << jobs << " jobs;5 transactional refusals\n";
}
