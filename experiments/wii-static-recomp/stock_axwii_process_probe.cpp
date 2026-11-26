#include "stock_axwii_process.h"
#include "stock_axwii_execute.h"
#include "stock_axwii_aux.h"
#include "axwii-chain-reference.h"
#include <iostream>

using namespace openshsm::experiment;

static void require(bool passed) {
    if (!passed) {
        throw std::runtime_error("AXWii chain comparison failed");
    }
}

int main() {
    unsigned comparisons = 0;
    unsigned programs = 0;
    for (unsigned fixture = 0; fixture < 128; ++fixture) {
        std::array<uint8_t, 4096> samples;
        for (unsigned index = 0; index < samples.size(); ++index) {
            samples[index] = uint8_t(index * 17 + fixture * 13);
        }
        AXWiiUCode reference(samples);
        auto memory = reference.memory.bytes;
        const unsigned nodes = 1 + fixture % 16;
        for (unsigned node = 0; node < nodes; ++node) {
            AxWiiParameterBlock pb;
            const uint32_t next = node + 1 == nodes ? 0 : 320 * (node + 2);
            pb.words[0] = uint16_t(next >> 16);
            pb.words[1] = uint16_t(next);
            pb.words[8] = node % 5 == 0 ? 0 : 1;
            pb.words[4] = fixture % 3;
            pb.words[88] = pb.words[4] == 2 ? 0 : 1;
            pb.words[61] = node % 3 == 0 ? 0 : node % 3 == 1 ? 0x19 : 0x0a;
            pb.words[60] = 1;
            pb.words[63] = pb.words[67] = 34;
            pb.words[65] = 47;
            pb.words[84] = 2048;
            pb.words[85] = 3;
            pb.words[58] = pb.words[10] = pb.words[13] = 32768;
            pb.words[7] = 5;
            const auto wire = encode_axwii_pb(pb, 0x4cc52064);
            std::copy(wire.begin(), wire.end(), memory.begin() + 320 * (node + 1));
        }
        reference.memory.bytes = memory;
        AxWiiMainBuffers main{};
        AxWiiRemoteBuffers remote{};
        uint16_t volume = 0, compressor = 0;
        std::array<uint16_t, 3> aux_volumes{};
        const auto resolve = [&](uint32_t address, size_t size) {
            address &= 0x3fffffffu;
            if (uint64_t(address) + size > memory.size()) {
                throw std::runtime_error("Candidate fixture bounds");
            }
            return std::span(memory).subspan(address, size);
        };
        const auto read = [&](uint32_t address) {
            if (address >= samples.size()) {
                throw std::runtime_error("Candidate sample bounds");
            }
            return samples[address];
        };
        for (unsigned frame = 0; frame < 4; ++frame) {
            reference.ProcessPBList(320);
            if (fixture & 1) {
                std::vector<uint8_t> program;
                const auto word = [&](uint16_t value) {
                    program.push_back(uint8_t(value >> 8));
                    program.push_back(uint8_t(value));
                };
                const auto pointer = [&](uint32_t value) { word(uint16_t(value >> 16)); word(uint16_t(value)); };
                word(4);
                pointer(320);
                word(13);
                uint32_t wm[] = {5600, 5640, 5680, 5720};
                for (auto address : wm) { pointer(address); }
                word(fixture & 2 ? 12 : 11);
                word(uint16_t(1000 + frame * 9000));
                pointer(6000);
                pointer(6800);
                word(14);
                reference.OutputWMSamples(wm);
                reference.OutputSamples(6800, 6000, uint16_t(1000 + frame * 9000), (fixture & 2) != 0);
                std::vector<uint32_t> signals;
                require(execute_axwii_commands(program, 0x4cc52064, main, remote, volume, compressor,
                    aux_volumes, resolve, read, [&](uint32_t mail) noexcept { signals.push_back(mail); }) == nodes);
                require(signals == std::vector<uint32_t>{0xdcd10004} && volume == reference.m_last_main_volume);
                ++programs;
            } else {
                require(process_axwii_pb_list(320, main, remote, resolve, read) == nodes);
            }
            require(memory == reference.memory.bytes && main == reference.main && remote == reference.remote);
            ++comparisons;
        }
    }
    unsigned refusals = 0;
    for (unsigned fixture = 0; fixture < 6; ++fixture) {
        std::array<uint8_t, 100000> memory{};
        AxWiiMainBuffers main{};
        AxWiiRemoteBuffers remote{};
        unsigned resolved = 0, sampled = 0;
        AxWiiParameterBlock pb;
        if (fixture == 3) {
            pb.words[0] = 0xc000;
            pb.words[1] = 320;
        }
        const auto wire = encode_axwii_pb(pb, 0x4cc52064);
        std::copy(wire.begin(), wire.end(), memory.begin() + 320);
        if (fixture == 4) {
            for (unsigned node = 1; node <= 257; ++node) {
                const uint32_t next = node == 257 ? 0 : 320 * (node + 1);
                pb.words[0] = uint16_t(next >> 16);
                pb.words[1] = uint16_t(next);
                const auto bytes = encode_axwii_pb(pb, 0x4cc52064);
                std::copy(bytes.begin(), bytes.end(), memory.begin() + 320 * node);
            }
        }
        const auto before = memory;
        const auto resolve = [&](uint32_t address, size_t size) {
            ++resolved;
            address &= 0x3fffffffu;
            if (fixture == 2) {
                throw std::runtime_error("Rejected MMIO fixture");
            }
            return std::span(memory).subspan(address, fixture == 1 ? size - 1 : size);
        };
        const auto read = [&](uint32_t) { ++sampled; return uint8_t(0); };
        try {
            (void)process_axwii_pb_list(fixture == 0 ? 321 : 320, main, remote, resolve, read,
                {}, fixture == 5 ? 0 : 0x4cc52064);
        } catch (const std::runtime_error&) {
            ++refusals;
        }
        require(memory == before && main == AxWiiMainBuffers{} && remote == AxWiiRemoteBuffers{} && sampled == 0);
        require(resolved == (fixture == 0 || fixture == 5 ? 0u : fixture == 4 ? 256u : 1u));
    }
    require(refusals == 6);
    unsigned program_refusals = 0;
    for (unsigned opcode = 10; opcode <= 11; ++opcode) {
        std::vector<uint8_t> program{0, 0, 0, 0, 0, 120};
        if (opcode == 10) {
            program.insert(program.end(), {0, 15, 0, 14});
        }
        AxWiiMainBuffers main{};
        AxWiiRemoteBuffers remote{};
        uint16_t volume = 0, compressor = 0;
        std::array<uint16_t, 3> aux_volumes{};
        unsigned resolved = 0, sampled = 0, signalled = 0;
        std::array<uint8_t, 120> memory{};
        try {
            (void)execute_axwii_commands(program, 0x4cc52064, main, remote, volume, compressor,
                aux_volumes, [&](uint32_t, size_t) { ++resolved; return std::span(memory); },
                [&](uint32_t) { ++sampled; return uint8_t(0); },
                [&](uint32_t) noexcept { ++signalled; });
        } catch (const std::runtime_error&) {
            ++program_refusals;
        }
        require(resolved == 0 && sampled == 0 && signalled == 0 && volume == 0 && compressor == 0);
        require(main == AxWiiMainBuffers{} && remote == AxWiiRemoteBuffers{});
    }
    require(program_refusals == 2);
    unsigned aux_jobs = 0;
    std::array<uint8_t, 4096> samples{};
    for (unsigned fixture = 0; fixture < 256; ++fixture) {
        for (unsigned mode = 0; mode < 5; ++mode) {
            AXWiiUCode reference(samples);
            for (unsigned channel = 0; channel < 12; ++channel) {
                for (unsigned index = 0; index < 96; ++index) {
                    reference.main[channel][index] = int32_t((fixture * 133 + channel * 17 + index * 71) % 60001) - 30000;
                }
            }
            for (unsigned index = 0; index < reference.memory.bytes.size() / 4; ++index) {
                const uint32_t value = uint32_t(int32_t((index * 133 + fixture * 99) % 60001) - 30000);
                for (unsigned byte = 0; byte < 4; ++byte) {
                    reference.memory.bytes[index * 4 + byte] = uint8_t(value >> (24 - byte * 8));
                }
            }
            auto memory = reference.memory.bytes;
            auto main = reference.main;
            std::array<uint16_t, 3> volumes{};
            const auto resolve = [&](uint32_t address, size_t size) {
                if (uint64_t(address) + size > memory.size()) {
                    throw std::runtime_error("Aux fixture bounds");
                }
                return std::span(memory).subspan(address, size);
            };
            for (unsigned frame = 0; frame < 4; ++frame) {
                const uint16_t volume = uint16_t((fixture * 173 + frame * 12000) & 65535);
                std::vector<uint8_t> program;
                const auto word = [&](uint16_t value) { program.push_back(uint8_t(value >> 8)); program.push_back(uint8_t(value)); };
                const auto pointer = [&](uint32_t value) { word(uint16_t(value >> 16)); word(uint16_t(value)); };
                word(uint16_t(5 + mode));
                word(volume);
                if (mode < 3) {
                    const uint32_t upload = fixture % 3 == 0 ? 0 : 2048;
                    const uint32_t input = fixture % 2 == 0 ? 2048 : 4096;
                    reference.MixAUXSamples(int(mode), upload, input, volume);
                    pointer(upload);
                    pointer(input);
                    if (!(fixture & 1)) {
                        mix_axwii_aux(main, volumes, mode, volume, upload, input, resolve);
                    }
                } else {
                    std::array<uint32_t, 6> addresses{2048, 3200, 4096, 4480, 4864, 5248};
                    if (fixture & 1) {
                        addresses = {2048, 2432, 2048, 2432, 2816, 3200};
                    }
                    reference.UploadAUXMixLRSC(int(mode - 3), addresses.data(), volume);
                    for (auto address : addresses) { pointer(address); }
                    if (!(fixture & 1)) {
                        upload_axwii_aux_lrsc(main, volumes, mode - 3, volume, addresses, resolve);
                    }
                }
                if (fixture & 1) {
                    word(14);
                    AxWiiRemoteBuffers remote{};
                    uint16_t output_volume = 0, compressor = 0;
                    unsigned sampled = 0, signalled = 0;
                    require(execute_axwii_commands(program, 0x4cc52064, main, remote, output_volume,
                        compressor, volumes, resolve, [&](uint32_t) { ++sampled; return uint8_t(0); },
                        [&](uint32_t) noexcept { ++signalled; }) == 0);
                    require(sampled == 0 && signalled == 0 && output_volume == 0 && compressor == 0);
                }
                require(memory == reference.memory.bytes && main == reference.main && volumes == reference.m_last_aux_volumes);
                ++aux_jobs;
            }
        }
    }
    require(aux_jobs == 5120);
    unsigned aux_refusals = 0;
    for (unsigned mode = 0; mode < 2; ++mode) {
        for (unsigned bad = 0; bad < (mode == 0 ? 3u : 7u); ++bad) {
            std::array<uint8_t, 8192> memory{};
            const auto before = memory;
            AxWiiMainBuffers main{};
            const auto before_main = main;
            std::array<uint16_t, 3> volumes{};
            unsigned resolved = 0;
            const auto resolve = [&](uint32_t address, size_t size) {
                ++resolved;
                return std::span(memory).subspan(address, resolved == bad ? size - 1 : size);
            };
            try {
                if (mode == 0) {
                    mix_axwii_aux(main, volumes, bad == 0 ? 3 : 0, 1234, 2048, 4096, resolve);
                } else {
                    upload_axwii_aux_lrsc(main, volumes, bad == 0 ? 2 : 0, 1234,
                        {2048, 3200, 4096, 4480, 4864, 5248}, resolve);
                }
            } catch (const std::runtime_error&) {
                ++aux_refusals;
            }
            require(memory == before && main == before_main && volumes == std::array<uint16_t, 3>{});
        }
    }
    require(aux_refusals == 10);
    require(programs == 256);
    std::cout << "AXWII_PB_CHAIN_REFERENCE_PASS " << comparisons
              << " chains;6 guarded refusals;256 output programs;2 program refusals;5120 aux jobs;10 aux refusals\n";
}
