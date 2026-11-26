#include "stock_axwii_voice.h"
#include "stock_axwii_sample_memory.h"
#include "axwii-full-voice-reference.h"
#include <iostream>
#include <source_location>

using namespace openshsm::experiment;

static void require(bool passed, std::source_location location = std::source_location::current()) {
    if (!passed) {
        throw std::runtime_error("AXWii full voice comparison failed at line " + std::to_string(location.line()));
    }
}

int main() {
    static_assert(offsetof(AXPBWii, initial_time_delay) == 68);
    uint32_t random = 0x5348534d;
    const auto next = [&]() {
        random ^= random << 13;
        random ^= random >> 17;
        random ^= random << 5;
        return random;
    };
    AXWiiUCode mask_reference;
    constexpr unsigned shifts[] = {0, 16, 21, 26};
    for (uint32_t combination = 0; combination < (1u << 20); ++combination) {
        uint32_t original = next() & 0x8000ffe0;
        for (unsigned group = 0; group < 4; ++group) {
            original |= ((combination >> (group * 5)) & 31) << shifts[group];
        }
        require(axwii_mixer_control(original) == uint32_t(mask_reference.ConvertMixerControl(original)));
    }
    unsigned jobs = 0;
    for (unsigned fixture = 0; fixture < 128; ++fixture) {
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
                    AXPBWii original;
                    std::memcpy(&original, candidate.words.data(), sizeof(original));
                    original.src_type = mode == 3 ? 0 : mode;
                    original.coef_select = fixture % 4;
                    original.running = 1;
                    original.is_stream = loop == 2;
                    original.initial_time_delay.on = 0;
                    original.audio_addr.looping = loop != 0;
                    original.audio_addr.sample_format = format;
                    original.audio_addr.loop_addr_hi = original.audio_addr.end_addr_hi = original.audio_addr.cur_addr_hi = 0;
                    original.audio_addr.loop_addr_lo = original.audio_addr.cur_addr_lo = 34;
                    original.audio_addr.end_addr_lo = fixture % 3 == 0 ? 47 : fixture % 3 == 1 ? 48 : 49;
                    original.src.ratio_hi = fixture % 5 == 0 ? 4 : 0;
                    original.src.ratio_lo = fixture % 5 == 0 ? 0 : uint16_t(128 + next() % 65408);
                    if (original.src_type == 2) {
                        original.src.ratio_hi = original.src.ratio_lo = fixture & 1 ? 65535 : 0;
                    }
                    for (auto& coefficient : original.adpcm.coefs) {
                        coefficient = int16_t(int(next() % 8193) - 4096);
                    }
                    original.lpf.on = fixture & 1;
                    original.lpf.a0 = uint16_t(next() % 32768);
                    original.lpf.b0 = int16_t(int(next() % 32768) - 16384);
                    original.biquad.on = (fixture >> 1) & 1;
                    original.remote = fixture % 5 != 0;
                    original.remote_iir.on = fixture % 3;
                    if (original.remote_iir.on == 1) {
                        original.remote_iir.lpf.a0 = uint16_t(next() % 32768);
                        original.remote_iir.lpf.b0 = int16_t(int(next() % 32768) - 16384);
                    }
                    std::memcpy(candidate.words.data(), &original, sizeof(original));
                    AxWiiMainBuffers main{}, expected_main{};
                    AxWiiRemoteBuffers remote{}, expected_remote{};
                    AXBuffers buffers{};
                    for (unsigned channel = 0; channel < 12; ++channel) {
                        main[channel].fill(int32_t(next() % 2000001) - 1000000);
                        expected_main[channel] = main[channel];
                        buffers.regular_ptrs[channel] = expected_main[channel].data();
                    }
                    for (unsigned channel = 0; channel < 8; ++channel) {
                        remote[channel].fill(int32_t(next() % 2000001) - 1000000);
                        expected_remote[channel] = remote[channel];
                        buffers.wiimote_ptrs[channel] = expected_remote[channel].data();
                    }
                    const auto coefficients = mode == 3 ? std::span<const int16_t>{} : std::span<const int16_t>(banks);
                    for (unsigned frame = 0; frame < 2; ++frame) {
                        Oracle accelerator(memory, AxWiiSampleState{});
                        const uint32_t mask = uint32_t(original.mixer_control_hi) << 16 | original.mixer_control_lo;
                        ProcessVoice(&accelerator, original, buffers, 96, mask_reference.ConvertMixerControl(mask),
                            coefficients.empty() ? nullptr : coefficients.data(), true);
                        if (fixture & 1) {
                            process_axwii_voice_from(candidate, main, remote,
                                AxWiiSampleMemory{memory, {}, 4095, 4095}, coefficients);
                        } else {
                            process_axwii_voice(candidate, main, remote, memory, coefficients);
                        }
                        require(std::memcmp(candidate.words.data(), &original, sizeof(original)) == 0);
                        require(main == expected_main && remote == expected_remote);
                        ++jobs;
                    }
                }
            }
        }
    }
    unsigned inactive = 0;
    for (unsigned fixture = 0; fixture < 1024; ++fixture) {
        AxWiiParameterBlock pb;
        for (auto& word : pb.words) {
            word = uint16_t(next());
        }
        pb.words[8] = fixture == 0 ? 0 : uint16_t(2 + fixture);
        const auto before = pb.words;
        AXPBWii original;
        std::memcpy(&original, pb.words.data(), sizeof(original));
        AXBuffers reference_buffers{};
        ProcessVoice(nullptr, original, reference_buffers, 96, AXMixControl(0xffffff), nullptr, true);
        AxWiiMainBuffers main{};
        AxWiiRemoteBuffers remote{};
        process_axwii_voice(pb, main, remote, {});
        require(pb.words == before && main == AxWiiMainBuffers{} && remote == AxWiiRemoteBuffers{});
        require(std::memcmp(&original, pb.words.data(), sizeof(original)) == 0);
        ++inactive;
    }
    unsigned refused = 0;
    for (unsigned fixture = 0; fixture < 3; ++fixture) {
        AxWiiParameterBlock pb;
        AxWiiMainBuffers main{};
        AxWiiRemoteBuffers remote{};
        std::array<uint8_t, 4096> memory;
        memory.fill(0x7f);
        pb.words[8] = 1;
        pb.words[4] = 2;
        pb.words[88] = 1;
        pb.words[61] = 0xa;
        pb.words[60] = 1;
        pb.words[84] = 2048;
        pb.words[58] = pb.words[10] = 32768;
        pb.words[7] = 1;
        pb.words[112] = pb.words[113] = 1;
        pb.words[114] = 32768;
        if (fixture == 0) {
            pb.words[34] = 1;
        } else if (fixture == 1) {
            pb.words[67] = 2047;
        } else {
            remote[0][0] = INT32_MAX;
        }
        const auto before = pb.words;
        const auto before_main = main;
        const auto before_remote = remote;
        try {
            if (fixture == 1) {
                process_axwii_voice_from(pb, main, remote,
                    AxWiiSampleMemory{memory, {}, UINT32_MAX, UINT32_MAX});
            } else {
                process_axwii_voice(pb, main, remote, memory);
            }
        } catch (const std::runtime_error&) {
            ++refused;
        }
        require(pb.words == before && main == before_main && remote == before_remote);
    }
    require(refused == 3);
    std::cout << "AXWII_FULL_VOICE_REFERENCE_PASS " << jobs
              << " jobs;1048576 masks;" << inactive << " inactive;3 transactional refusals\n";
}
