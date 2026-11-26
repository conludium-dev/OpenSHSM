#include "stock_axwii_buffers.h"
#include "axwii-output-reference.h"
#include <iostream>
#include <fstream>

using namespace openshsm::experiment;

static void require(bool passed) {
    if (!passed) {
        throw std::runtime_error("AXWii buffer comparison failed");
    }
}

int main(int argc, char** argv) {
    require(argc == 1 || argc == 2);
    std::array<uint8_t, 4032> original_table{};
    if (argc == 2) {
        std::ifstream stream(argv[1], std::ios::binary);
        require(bool(stream.read(reinterpret_cast<char*>(original_table.data()), original_table.size())));
        require(stream.peek() == std::ifstream::traits_type::eof());
    }
    uint32_t random = 0x5348534d;
    const auto next = [&]() {
        random ^= random << 13;
        random ^= random >> 17;
        random ^= random << 5;
        return random;
    };
    const auto write32 = [](uint8_t* bytes, int32_t value) {
        for (unsigned index = 0; index < 4; ++index) {
            bytes[index] = uint8_t(uint32_t(value) >> (24 - index * 8));
        }
    };
    unsigned cases = 0;
    for (unsigned fixture = 0; fixture < 4096; ++fixture) {
        AXWiiUCode reference;
        std::array<uint8_t, 120> init;
        std::array<uint8_t, 768> input;
        for (unsigned channel = 0; channel < 20; ++channel) {
            const int32_t value = fixture % 3 == 0 ? 0 : int32_t(next() % 2000001) - 1000000;
            write32(init.data() + channel * 6, value);
            const uint16_t delta = uint16_t(next());
            init[channel * 6 + 4] = uint8_t(delta >> 8);
            init[channel * 6 + 5] = uint8_t(delta);
        }
        for (unsigned index = 0; index < 192; ++index) {
            write32(input.data() + index * 4, int32_t(next() % 2000001) - 1000000);
        }
        std::copy(init.begin(), init.end(), reference.system.memory.bytes.begin() + 128);
        std::copy(input.begin(), input.end(), reference.system.memory.bytes.begin() + 512);
        const auto memory_before = reference.system.memory.bytes;
        AxWiiMainBuffers main{};
        AxWiiRemoteBuffers remote{};
        setup_axwii_buffers(main, remote, init);
        reference.SetupProcessing(128);
        require(main == reference.main && remote == reference.remote);
        for (unsigned mode = 0; mode < 3; ++mode) {
            auto candidate = main;
            reference.main = main;
            if (mode == 2) {
                add_axwii_lr(candidate, input, false, true);
                reference.AddSubToLR(512);
            } else {
                add_axwii_lr(candidate, std::span(input).first(384), mode == 1);
                reference.AddToLR(512, mode == 1);
            }
            require(candidate == reference.main && remote == reference.remote);
            require(reference.system.memory.bytes == memory_before);
            ++cases;
        }
    }
    unsigned refusals = 0;
    unsigned compressed = 0;
    for (unsigned fixture = 0; fixture < 4096; ++fixture) {
        AXWiiUCode reference;
        std::array<uint8_t, 4032> table;
        for (unsigned index = 0; index < table.size() / 2; ++index) {
            const uint16_t value = uint16_t(next() % 32769);
            table[index * 2] = uint8_t(value >> 8);
            table[index * 2 + 1] = uint8_t(value);
        }
        if (argc == 2) {
            table = original_table;
        }
        std::copy(table.begin(), table.end(), reference.system.memory.bytes.begin() + 64);
        const auto memory_before = reference.system.memory.bytes;
        uint16_t position = uint16_t(fixture % 11);
        reference.m_compressor_pos = position;
        for (unsigned frame = 0; frame < (argc == 2 ? 16u : 4u); ++frame) {
            AxWiiMainBuffers main;
            for (auto& channel : main) {
                for (auto& sample : channel) {
                    const bool quiet = argc == 2 ? frame != 0 && frame != 12 : bool(frame % 2);
                    sample = int32_t(next() % (quiet ? 2001 : 200001)) - (quiet ? 1000 : 100000);
                }
            }
            const uint16_t threshold = argc == 2 ? 32768 : fixture % 2 ? 32768 : 65535;
            const uint16_t release = argc == 2 ? 10 : uint16_t(fixture % 11);
            reference.main = main;
            compress_axwii_buffers(main, position, threshold, release, table);
            reference.RunCompressor(threshold, release, 64, 3);
            require(main == reference.main && position == reference.m_compressor_pos);
            require(reference.system.memory.bytes == memory_before);
            ++compressed;
        }
    }
    const auto refuses = [&](auto operation) {
        AxWiiMainBuffers main{};
        AxWiiRemoteBuffers remote{};
        main[0][95] = 2147483647;
        remote[7][17] = 123;
        const auto before_main = main;
        const auto before_remote = remote;
        bool failed = false;
        try {
            operation(main, remote);
        } catch (const std::runtime_error&) {
            failed = true;
        }
        require(failed && main == before_main && remote == before_remote);
        ++refusals;
    };
    std::array<uint8_t, 120> bad_init{};
    write32(bad_init.data() + 19 * 6, 2147483647);
    bad_init[119] = 1;
    refuses([&](auto& main, auto& remote) { setup_axwii_buffers(main, remote, bad_init); });
    refuses([&](auto& main, auto& remote) { setup_axwii_buffers(main, remote, std::span(bad_init).first(119)); });
    std::array<uint8_t, 768> bad_input{};
    write32(bad_input.data() + 95 * 4, 1);
    refuses([&](auto& main, auto&) { add_axwii_lr(main, std::span(bad_input).first(384), false); });
    refuses([&](auto& main, auto&) { add_axwii_lr(main, std::span(bad_input).first(383), false); });
    refuses([&](auto& main, auto&) { add_axwii_lr(main, bad_input, true, true); });
    write32(bad_input.data(), std::numeric_limits<int32_t>::min());
    refuses([&](auto& main, auto&) { add_axwii_lr(main, std::span(bad_input).first(384), true); });
    const auto compressor_refuses = [&](auto configure, uint16_t initial, std::span<const uint8_t> table) {
        AxWiiMainBuffers main{};
        configure(main);
        const auto before = main;
        uint16_t position = initial;
        bool failed = false;
        try {
            compress_axwii_buffers(main, position, 32768, 10, table);
        } catch (const std::runtime_error&) {
            failed = true;
        }
        require(failed && main == before && position == initial);
        ++refusals;
    };
    std::array<uint8_t, 192> coefficients;
    coefficients.fill(255);
    compressor_refuses([](auto& main) { main[0][0] = 40000; }, 0, std::span(coefficients).first(191));
    compressor_refuses([](auto&) {}, 10, coefficients);
    compressor_refuses([](auto& main) { main[0][95] = 2147483647; }, 0, coefficients);
    compressor_refuses([](auto& main) { main[1][95] = std::numeric_limits<int32_t>::min(); }, 0, coefficients);
    AxWiiMainBuffers idle{};
    uint16_t idle_position = 0;
    compress_axwii_buffers(idle, idle_position, 0, 10, {});
    require(idle == AxWiiMainBuffers{} && idle_position == 0);
    std::cout << "AXWII_BUFFERS_REFERENCE_PASS " << cases << " cases;" << compressed <<
        " compressor frames;" << refusals << " transactional refusals\n";
}
