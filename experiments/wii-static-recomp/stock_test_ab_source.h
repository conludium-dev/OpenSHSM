#pragma once
#include <input/input_manager.h>
#include <chrono>
#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>

namespace openshsm::experiment {

class TestABSource : public nwii::runtime::input::IInputSource {
public:
    TestABSource(uint32_t start, uint32_t duration) : start_ms(start), duration_ms(duration) {
        if (start > 180000 || duration == 0 || duration > 1000) {
            throw std::runtime_error("Invalid bounded A+B test timing");
        }
    }

    void apply(uint64_t elapsed, nwii::runtime::input::GameCubePadState pads[4],
        nwii::runtime::input::WiimoteState motes[4]) const {
        pads[0] = {};
        pads[0].err = 0;
        motes[0] = {};
        motes[0].err = 0;
        motes[0].ir_x = motes[0].ir_y = 0.5f;
        motes[0].accel_z = 1.0f;
        if (elapsed >= start_ms && elapsed < uint64_t(start_ms) + duration_ms) {
            motes[0].buttons = 0xC00;
        }
    }

    void update(nwii::runtime::input::GameCubePadState pads[4],
        nwii::runtime::input::WiimoteState motes[4]) override {
        const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - created).count();
        apply(uint64_t(elapsed), pads, motes);
        const bool pressed = motes[0].buttons != 0;
        if (pressed != previous_pressed) {
            std::cout << "[TestAB] elapsedMs=" << elapsed << " pressed=" << pressed << '\n';
            previous_pressed = pressed;
        }
    }

private:
    uint32_t start_ms, duration_ms;
    std::chrono::steady_clock::time_point created = std::chrono::steady_clock::now();
    bool previous_pressed = false;
};

inline void install_test_ab_source(nwii::runtime::input::InputManager& manager) {
    const char* value = std::getenv("NWII_TEST_AB_AT_MS");
    if (!value) {
        return;
    }
    const std::string text(value);
    if (text.empty() || text.size() > 6 || text.find_first_not_of("0123456789") != std::string::npos) {
        throw std::runtime_error("Invalid A+B test timing string");
    }
    const auto start = std::stoul(text);
    manager.add_source(std::make_unique<TestABSource>(uint32_t(start), 750));
    std::cout << "[TestAB] private process source registered, delayMs=" << start << '\n';
}

}
