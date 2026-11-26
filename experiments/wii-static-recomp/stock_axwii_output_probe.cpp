#include "stock_axwii_output.h"
#include "axwii-output-reference.h"
#include <iostream>

using namespace openshsm::experiment;

static void require(bool passed) {
    if (!passed) {
        throw std::runtime_error("AXWii output comparison failed");
    }
}

int main() {
    uint32_t random = 0x5348534d;
    const auto next = [&]() {
        random ^= random << 13;
        random ^= random >> 17;
        random ^= random << 5;
        return random;
    };
    unsigned cases = 0;
    for (unsigned fixture = 0; fixture < 4096; ++fixture) {
        AXWiiUCode reference;
        AxWiiMainBuffers main;
        AxWiiRemoteBuffers remote;
        for (auto& channel : main) {
            for (auto& sample : channel) {
                sample = int32_t(next());
            }
        }
        for (auto& channel : remote) {
            for (auto& sample : channel) {
                sample = int32_t(next());
            }
        }
        reference.main = main;
        reference.remote = remote;
        reference.m_last_main_volume = fixture == 0 ? 65535 : fixture == 1 ? 0 : uint16_t(next());
        const uint16_t volume = fixture == 0 ? 0 : fixture == 1 ? 65535 : uint16_t(next());
        const bool auxc = fixture & 1;
        const auto unchanged_main = main;
        const auto unchanged_remote = remote;
        const auto output = prepare_axwii_output(main, remote, reference.m_last_main_volume, volume, auxc);
        uint32_t wm_addresses[] = {3000, 3040, 3080, 3120};
        const uint32_t lr_address = fixture % 3 == 0 ? 1024 : fixture % 3 == 1 && auxc ? 1408 : 2048;
        reference.OutputWMSamples(wm_addresses);
        reference.OutputSamples(lr_address, 1024, volume, auxc);
        require(main == unchanged_main && remote == unchanged_remote);
        require(reference.main == output.next_main && reference.remote == remote);
        require(reference.m_last_main_volume == output.next_volume && output.next_volume == volume);
        const auto& memory = reference.system.memory.bytes;
        require(std::equal(output.stereo.begin(), output.stereo.end(), memory.begin() + lr_address));
        if (lr_address != 1024) {
            require(std::equal(output.surround.begin(), output.surround.end(), memory.begin() + 1024));
        }
        if (auxc && lr_address != 1408) {
            require(std::equal(output.auxc.begin(), output.auxc.end(), memory.begin() + 1408));
        }
        for (unsigned channel = 0; channel < 4; ++channel) {
            require(std::equal(output.wiimote[channel].begin(), output.wiimote[channel].end(), memory.begin() + wm_addresses[channel]));
        }
        std::array<bool, 4096> touched{};
        for (unsigned index = 1024; index < (auxc ? 1792 : 1408); ++index) {
            touched[index] = true;
        }
        for (unsigned index = lr_address; index < lr_address + 384; ++index) {
            touched[index] = true;
        }
        for (const auto address : wm_addresses) {
            for (unsigned index = address; index < address + 36; ++index) {
                touched[index] = true;
            }
        }
        for (unsigned index = 0; index < memory.size(); ++index) {
            require(touched[index] || memory[index] == 0xa5);
        }
        const std::vector<uint32_t> expected = auxc ? std::vector<uint32_t>{3000, 3040, 3080, 3120, 1024, 1408, lr_address, output.sync_mail} :
            std::vector<uint32_t>{3000, 3040, 3080, 3120, 1024, lr_address, output.sync_mail};
        require(reference.events == expected);
        std::array<uint8_t, 4096> candidate_memory;
        candidate_memory.fill(0xa5);
        const auto resolve = [&](uint32_t address, size_t size) -> std::span<uint8_t> {
            if (uint64_t(address) + size > candidate_memory.size()) {
                throw std::runtime_error("Candidate fixture bounds");
            }
            return std::span(candidate_memory).subspan(address, size);
        };
        uint16_t candidate_volume = reference.m_last_main_volume;
        unsigned sync_count = 0;
        bool complete_at_signal = false;
        commit_axwii_wm_output(output, {3000, 3040, 3080, 3120}, resolve);
        commit_axwii_output(output, main, candidate_volume, lr_address, 1024, resolve,
            [&](uint32_t mail) noexcept {
                ++sync_count;
                complete_at_signal = mail == output.sync_mail && candidate_memory == memory &&
                    main == reference.main && candidate_volume == volume;
            });
        require(sync_count == 1 && complete_at_signal && candidate_memory == memory);
        ++cases;
    }
    unsigned refusals = 0;
    for (unsigned failure = 0; failure < 15; ++failure) {
        AxWiiMainBuffers main{};
        AxWiiRemoteBuffers remote{};
        main[0][95] = 456;
        const auto before_main = main;
        uint16_t volume = 789;
        const auto output = prepare_axwii_output(main, remote, volume, 32768, true);
        std::array<uint8_t, 4096> memory;
        memory.fill(0xa5);
        const auto before_memory = memory;
        unsigned calls = 0;
        unsigned signals = 0;
        const auto resolve = [&](uint32_t address, size_t size) -> std::span<uint8_t> {
            const unsigned call = calls++;
            const unsigned selected = failure < 6 ? failure % 3 : (failure - 6) % 4;
            if (call == selected) {
                if (failure < 3 || (failure >= 6 && failure < 10)) {
                    throw std::runtime_error("Injected invalid RAM span");
                }
                return std::span(memory).subspan(address, size - 1);
            }
            return std::span(memory).subspan(address, size);
        };
        bool rejected = false;
        try {
            if (failure == 14) {
                commit_axwii_output(output, main, volume, 2048, UINT32_MAX - 100, resolve,
                    [&](uint32_t) noexcept { ++signals; });
            } else if (failure >= 6) {
                commit_axwii_wm_output(output, {3000, 3040, 3080, 3120}, resolve);
            } else {
                commit_axwii_output(output, main, volume, 2048, 1024, resolve,
                    [&](uint32_t) noexcept { ++signals; });
            }
        } catch (const std::runtime_error&) {
            rejected = true;
        }
        require(rejected && memory == before_memory && main == before_main && volume == 789 && signals == 0);
        ++refusals;
    }
    std::cout << "AXWII_OUTPUT_PACKING_REFERENCE_PASS " << cases <<
        " cases;reference write-before-sync order;" << refusals << " transactional refusals\n";
}
