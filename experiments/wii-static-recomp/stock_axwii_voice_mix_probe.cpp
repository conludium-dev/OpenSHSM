#include "stock_axwii_voice_mix.h"
#ifdef OPENSHSM_TEST_REMOTE
#include "stock_axwii_remote_mix.h"
#endif
#include "axwii-mix-reference.h"
#include <iostream>

using namespace openshsm::experiment;

static void require(bool passed) {
    if (!passed) {
        throw std::runtime_error("AXWii main mix comparison failed");
    }
}

int main() {
    static_assert(offsetof(AXPBWii, vol_env) == 116);
    static_assert(offsetof(AXPBWii, mixer) == 20);
    static_assert(offsetof(AXPBWii, dpop) == 82);
    static_assert(offsetof(AXPBWii, lpf) == 196);
    static_assert(offsetof(AXPBWii, biquad) == 204);
#ifdef OPENSHSM_TEST_REMOTE
    static_assert(offsetof(AXPBWii, remote) == 224);
    static_assert(offsetof(AXPBWii, remote_mixer) == 228);
    static_assert(offsetof(AXPBWii, remote_dpop) == 260);
    static_assert(offsetof(AXPBWii, remote_src) == 276);
    static_assert(offsetof(AXPBWii, remote_iir) == 286);
#endif
    uint32_t random = 0x5348534d;
    const auto next = [&]() {
        random ^= random << 13;
        random ^= random >> 17;
        random ^= random << 5;
        return random;
    };
    unsigned jobs = 0;
    for (unsigned fixture = 0; fixture < 4096; ++fixture) {
        AxWiiParameterBlock candidate;
        for (auto& word : candidate.words) {
            word = uint16_t(next());
        }
        AXPBWii original;
        std::memcpy(&original, candidate.words.data(), sizeof(original));
        original.running = 1;
        original.initial_time_delay.on = 0;
        original.remote = 0;
#ifdef OPENSHSM_TEST_REMOTE
        original.remote = fixture % 5 != 0;
        original.remote_iir.on = fixture % 3;
        if (original.remote_iir.on == 1) {
            original.remote_iir.lpf.a0 = uint16_t(next() % 32768);
            original.remote_iir.lpf.b0 = int16_t(int(next() % 32768) - 16384);
        }
#endif
        original.lpf.on = fixture & 1;
        original.lpf.a0 = uint16_t(next() % 32768);
        original.lpf.b0 = int16_t(int(next() % 32768) - 16384);
        original.biquad.on = (fixture >> 1) & 1;
        std::memcpy(candidate.words.data(), &original, sizeof(original));
        std::array<int16_t, 96> input;
        for (auto& sample : input) {
            sample = int16_t(next());
        }
        AxWiiMainBuffers actual, expected;
        for (auto& channel : actual) {
            for (auto& sample : channel) {
                sample = int32_t(next() % 2000001) - 1000000;
            }
        }
        expected = actual;
#ifdef OPENSHSM_TEST_REMOTE
        AxWiiRemoteBuffers remote_actual, remote_expected;
        std::array<int16_t, 512> coefficients;
        for (auto& coefficient : coefficients) {
            coefficient = int16_t(next());
        }
        for (auto& channel : remote_actual) {
            for (auto& sample : channel) {
                sample = int32_t(next() % 2000001) - 1000000;
            }
        }
        remote_expected = remote_actual;
#endif
        AXBuffers buffers{};
        for (unsigned channel = 0; channel < 12; ++channel) {
            buffers.regular_ptrs[channel] = expected[channel].data();
        }
#ifdef OPENSHSM_TEST_REMOTE
        for (unsigned channel = 0; channel < 8; ++channel) {
            buffers.wiimote_ptrs[channel] = remote_expected[channel].data();
        }
#endif
        const uint32_t control = fixture < 24 ? 1u << fixture : next() & 0xffffff;
        const unsigned count =
#ifdef OPENSHSM_TEST_REMOTE
            fixture & 1 ? 32 : 96;
#else
            fixture % 3 == 0 ? 96 : 1 + next() % 96;
#endif
        for (unsigned frame = 0; frame < 2; ++frame) {
            fixture_input = std::span(input).first(count);
#ifdef OPENSHSM_TEST_REMOTE
            const auto bank = fixture & 4 ? std::span<const int16_t>(coefficients) : std::span<const int16_t>{};
            ProcessVoice(nullptr, original, buffers, uint16_t(count), AXMixControl(control), bank.empty() ? nullptr : bank.data(), true);
            const auto main_samples = mix_axwii_main_voice(candidate, actual, fixture_input, control);
            mix_axwii_remote(candidate, remote_actual, std::span(main_samples).first(count), bank);
            require(remote_actual == remote_expected);
#else
            ProcessVoice(nullptr, original, buffers, uint16_t(count), AXMixControl(control), nullptr, true);
            (void)mix_axwii_main_voice(candidate, actual, fixture_input, control);
#endif
            require(actual == expected);
            require(std::memcmp(candidate.words.data(), &original, sizeof(original)) == 0);
            ++jobs;
        }
    }
    unsigned refused = 0;
    for (unsigned fixture = 0; fixture < 4; ++fixture) {
        AxWiiParameterBlock pb;
        AxWiiMainBuffers buffers{};
        std::array<int16_t, 96> input;
        input.fill(32767);
        pb.words[58] = 32768;
        uint32_t control = 1;
        if (fixture == 0) {
            control = 0x1000000;
        } else if (fixture == 1) {
            pb.words[98] = 1;
            pb.words[99] = 32767;
            pb.words[100] = 65535;
            pb.words[101] = 32767;
        } else if (fixture == 2) {
            buffers[0][0] = INT32_MAX;
            pb.words[10] = 32768;
        }
        const auto before = pb.words;
        const auto before_buffers = buffers;
        try {
            (void)mix_axwii_main_voice(pb, buffers, std::span(input).first(fixture == 3 ? 0 : 96), control);
        } catch (const std::runtime_error&) {
            ++refused;
        }
        require(pb.words == before && buffers == before_buffers);
    }
    require(refused == 4);
#ifdef OPENSHSM_TEST_REMOTE
    for (unsigned fixture = 0; fixture < 4; ++fixture) {
        AxWiiParameterBlock pb;
        AxWiiRemoteBuffers buffers{};
        std::array<int16_t, 96> input;
        std::array<int16_t, 512> coefficients{};
        input.fill(32767);
        pb.words[112] = 1;
        pb.words[113] = 1;
        pb.words[114] = 32768;
        if (fixture == 2) {
            pb.words[143] = 1;
            pb.words[144] = 32767;
            pb.words[145] = 65535;
            pb.words[146] = 32767;
        } else if (fixture == 3) {
            buffers[0][0] = INT32_MAX;
        }
        const auto before = pb.words;
        const auto before_buffers = buffers;
        try {
            const auto bank = fixture == 1 ? std::span<const int16_t>(coefficients).first(511) : std::span<const int16_t>{};
            mix_axwii_remote(pb, buffers, std::span(input).first(fixture == 0 ? 95 : 96), bank);
        } catch (const std::runtime_error&) {
            ++refused;
        }
        require(pb.words == before && buffers == before_buffers);
    }
    require(refused == 8);
    std::cout << "AXWII_MAIN_REMOTE_MIX_REFERENCE_PASS " << jobs << " jobs;8 transactional refusals\n";
#else
    std::cout << "AXWII_MAIN_VOICE_MIX_REFERENCE_PASS " << jobs << " jobs;4 transactional refusals\n";
#endif
}
