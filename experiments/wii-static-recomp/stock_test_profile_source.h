#pragma once
#include "stock_test_ab_source.h"
#include <vector>

namespace openshsm::experiment {

struct ProfileButtonPulse {
    uint32_t start_ms, buttons, duration_ms;
};

class TestProfileSource : public nwii::runtime::input::IInputSource {
public:
    TestProfileSource(uint32_t ab_start, uint32_t select_start,
        const std::vector<uint32_t>& extra = {},
        const std::vector<ProfileButtonPulse>& pulses = {}) :
        ab(ab_start, 750), select_ms{select_start}, button_pulses(pulses) {
        if (select_start > 179250 || uint64_t(select_start) < uint64_t(ab_start) + 1750) {
            throw std::runtime_error("Invalid bounded profile test timing");
        }
        if (extra.size() > 8) {
            throw std::runtime_error("Too many bounded profile test inputs");
        }
        for (uint32_t value : extra) {
            if (value > 179250 || uint64_t(value) < uint64_t(select_ms.back()) + 1750) {
                throw std::runtime_error("Invalid bounded profile test sequence");
            }
            select_ms.push_back(value);
        }
        if (button_pulses.size() > 64) {
            throw std::runtime_error("Too many bounded button pulses");
        }
        uint64_t previous_end = 0;
        for (const auto& pulse : button_pulses) {
            const uint64_t end = uint64_t(pulse.start_ms) + pulse.duration_ms;
            if (!pulse.buttons || (pulse.buttons & ~0x1F9Fu) || pulse.duration_ms < 100 ||
                pulse.duration_ms > 1000 || end > 180000 ||
                (previous_end && pulse.start_ms < previous_end + 100)) {
                throw std::runtime_error("Invalid bounded button pulse");
            }
            auto separated = [&](uint32_t legacy_start) {
                return end + 100 <= legacy_start || uint64_t(legacy_start) + 850 <= pulse.start_ms;
            };
            if (!separated(ab_start)) {
                throw std::runtime_error("Button pulse overlaps profile input");
            }
            for (uint32_t value : select_ms) {
                if (!separated(value)) {
                    throw std::runtime_error("Button pulse overlaps profile input");
                }
            }
            previous_end = end;
        }
    }

    void apply(uint64_t elapsed, nwii::runtime::input::GameCubePadState pads[4],
        nwii::runtime::input::WiimoteState motes[4]) const {
        ab.apply(elapsed, pads, motes);
        for (uint32_t value : select_ms) {
            if (elapsed >= value && elapsed < uint64_t(value) + 750) {
                motes[0].buttons = 0x800;
            }
        }
        for (const auto& pulse : button_pulses) {
            if (elapsed >= pulse.start_ms && elapsed < uint64_t(pulse.start_ms) + pulse.duration_ms) {
                motes[0].buttons = pulse.buttons;
            }
        }
    }

    void update(nwii::runtime::input::GameCubePadState pads[4],
        nwii::runtime::input::WiimoteState motes[4]) override {
        const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - created).count();
        apply(uint64_t(elapsed), pads, motes);
        if (motes[0].buttons != previous_buttons) {
            std::cout << "[TestProfile] elapsedMs=" << elapsed << " buttons=" << motes[0].buttons << '\n';
            previous_buttons = motes[0].buttons;
        }
    }

private:
    TestABSource ab;
    std::vector<uint32_t> select_ms;
    std::vector<ProfileButtonPulse> button_pulses;
    uint32_t previous_buttons = 0;
    std::chrono::steady_clock::time_point created = std::chrono::steady_clock::now();
};

inline uint32_t profile_test_time(const char* value) {
    const std::string text(value);
    if (text.empty() || text.size() > 6 || text.find_first_not_of("0123456789") != std::string::npos) {
        throw std::runtime_error("Invalid profile test timing string");
    }
    const auto result = std::stoul(text);
    if (result > 180000) {
        throw std::runtime_error("Invalid profile test timing range");
    }
    return uint32_t(result);
}

inline std::vector<uint32_t> profile_test_extra_times(const char* value) {
    std::vector<uint32_t> result;
    const std::string text(value);
    size_t start = 0;
    while (true) {
        const size_t end = text.find(',', start);
        result.push_back(profile_test_time(text.substr(start, end - start).c_str()));
        if (result.size() > 8) {
            throw std::runtime_error("Too many bounded profile test inputs");
        }
        if (end == std::string::npos) {
            return result;
        }
        start = end + 1;
    }
}

inline std::vector<ProfileButtonPulse> profile_test_button_pulses(const char* value) {
    const std::string text(value);
    if (text.size() > 2048) {
        throw std::runtime_error("Bounded button pulse string is too long");
    }
    std::vector<ProfileButtonPulse> result;
    size_t start = 0;
    while (true) {
        const size_t end = text.find(',', start);
        const std::string item = text.substr(start, end - start);
        const size_t first = item.find(':');
        const size_t second = first == std::string::npos ? first : item.find(':', first + 1);
        if (first == std::string::npos || second == std::string::npos ||
            item.find(':', second + 1) != std::string::npos) {
            throw std::runtime_error("Expected start:buttons:duration button pulse");
        }
        result.push_back({profile_test_time(item.substr(0, first).c_str()),
            profile_test_time(item.substr(first + 1, second - first - 1).c_str()),
            profile_test_time(item.substr(second + 1).c_str())});
        if (result.size() > 64) {
            throw std::runtime_error("Too many bounded button pulses");
        }
        if (end == std::string::npos) {
            return result;
        }
        start = end + 1;
    }
}

inline void install_test_profile_source(nwii::runtime::input::InputManager& manager) {
    const char* ab = std::getenv("NWII_TEST_AB_AT_MS");
    const char* select = std::getenv("NWII_TEST_SELECT_AT_MS");
    const char* extra = std::getenv("NWII_TEST_EXTRA_A_AT_MS");
    const char* pulses = std::getenv("NWII_TEST_BUTTON_PULSES");
    if (!ab && !select && !extra && !pulses) {
        return;
    }
    if (!ab || !select) {
        throw std::runtime_error("Both profile test times are required");
    }
    manager.add_source(std::make_unique<TestProfileSource>(profile_test_time(ab), profile_test_time(select),
        extra ? profile_test_extra_times(extra) : std::vector<uint32_t>{},
        pulses ? profile_test_button_pulses(pulses) : std::vector<ProfileButtonPulse>{}));
    std::cout << "[TestProfile] private process source registered\n";
}

}
