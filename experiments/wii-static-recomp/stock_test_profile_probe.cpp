#include "stock_test_profile_source.h"
#include <cassert>

int main() {
    using namespace nwii::runtime::input;
    using openshsm::experiment::TestProfileSource;
    GameCubePadState pads[4]{};
    WiimoteState motes[4]{};
    pads[1].buttons = 0x1234;
    motes[1].buttons = 0x5678;
    TestProfileSource source(100, 2000);
    for (uint64_t elapsed : {0u, 99u, 100u, 849u, 850u, 1999u, 2000u, 2749u, 2750u, 180000u}) {
        source.apply(elapsed, pads, motes);
        const uint32_t expected = elapsed >= 100 && elapsed < 850 ? 0xC00 :
            (elapsed >= 2000 && elapsed < 2750 ? 0x800 : 0);
        assert(motes[0].buttons == expected && pads[0].buttons == 0);
        assert(motes[0].err == 0 && pads[0].err == 0);
        assert(motes[1].buttons == 0x5678 && pads[1].buttons == 0x1234);
    }
    unsigned rejected = 0;
    for (auto [ab, select] : {std::pair{100u, 1849u}, std::pair{0u, 179251u}, std::pair{180001u, 180000u}}) {
        try {
            TestProfileSource invalid(ab, select);
        } catch (const std::runtime_error&) {
            ++rejected;
        }
    }
    for (const char* value : {"", "-1", "+1", " 1", "12x", "9999999", "180001"}) {
        try {
            openshsm::experiment::profile_test_time(value);
        } catch (const std::runtime_error&) {
            ++rejected;
        }
    }
    assert(rejected == 10);
    TestProfileSource sequence(100, 2000, {4000, 6000});
    for (uint64_t elapsed : {3999u, 4000u, 4749u, 4750u, 5999u, 6000u, 6749u, 6750u}) {
        sequence.apply(elapsed, pads, motes);
        assert(motes[0].buttons == ((elapsed >= 4000 && elapsed < 4750) ||
            (elapsed >= 6000 && elapsed < 6750) ? 0x800u : 0u));
        assert(motes[1].buttons == 0x5678 && pads[1].buttons == 0x1234);
    }
    assert(openshsm::experiment::profile_test_extra_times("4000,6000") ==
        std::vector<uint32_t>({4000, 6000}));
    unsigned invalid_extra = 0;
    for (const char* value : {"", ",1", "1,", "1,,2", " 1", "1,2x", "180001", "1,2,3,4,5,6,7,8,9"}) {
        try {
            openshsm::experiment::profile_test_extra_times(value);
        } catch (const std::runtime_error&) {
            ++invalid_extra;
        }
    }
    for (const std::vector<uint32_t>& values : {std::vector<uint32_t>{3749}, {4000, 3900},
            {179251}, {4000, 5750, 7500, 9250, 11000, 12750, 14500, 16250, 18000}}) {
        try {
            TestProfileSource invalid(100, 2000, values);
        } catch (const std::runtime_error&) {
            ++invalid_extra;
        }
    }
    assert(invalid_extra == 12);
    using openshsm::experiment::ProfileButtonPulse;
    const auto pulses = openshsm::experiment::profile_test_button_pulses("4000:2:100,6000:2048:1000");
    TestProfileSource buttons(100, 2000, {}, pulses);
    for (uint64_t elapsed : {3999u, 4000u, 4099u, 4100u, 5999u, 6000u, 6999u, 7000u}) {
        buttons.apply(elapsed, pads, motes);
        assert(motes[0].buttons == (elapsed >= 4000 && elapsed < 4100 ? 2u :
            (elapsed >= 6000 && elapsed < 7000 ? 2048u : 0u)));
        assert(motes[1].buttons == 0x5678 && pads[1].buttons == 0x1234);
    }
    unsigned bad_pulses = 0;
    for (const char* value : {"", "1", "1:2", "1:2:3:4", "1::100", "1:2:",
            "1:2:100,", "-1:2:100", "1:2:100x"}) {
        try {
            openshsm::experiment::profile_test_button_pulses(value);
        } catch (const std::runtime_error&) {
            ++bad_pulses;
        }
    }
    for (const std::vector<ProfileButtonPulse>& values : {
            std::vector<ProfileButtonPulse>{{4000, 0, 100}}, {{4000, 32, 100}},
            {{4000, 2, 99}}, {{4000, 2, 1001}}, {{179901, 2, 100}},
            {{4000, 2, 100}, {4199, 2, 100}}, {{6000, 2, 100}, {4000, 2, 100}},
            {{2000, 2, 100}}, {{0, 2, 100}}, {{2800, 2, 100}}}) {
        try {
            TestProfileSource invalid(100, 2000, {}, values);
        } catch (const std::runtime_error&) {
            ++bad_pulses;
        }
    }
    for (const std::string& text : {std::string(2049, '1'),
            std::string("4000:2:100,") + [] {
                std::string value;
                for (int i = 0; i < 64; ++i) {
                    value += "4000:2:100";
                    if (i != 63) { value += ','; }
                }
                return value;
            }()}) {
        try {
            openshsm::experiment::profile_test_button_pulses(text.c_str());
        } catch (const std::runtime_error&) {
            ++bad_pulses;
        }
    }
    try {
        TestProfileSource invalid(100, 2000, {}, std::vector<ProfileButtonPulse>(65, {4000, 2, 100}));
    } catch (const std::runtime_error&) {
        ++bad_pulses;
    }
    assert(bad_pulses == 22);
    TestProfileSource last(100, 2000, {}, {{179900, 2, 100}});
    last.apply(179999, pads, motes);
    assert(motes[0].buttons == 2);
    last.apply(180000, pads, motes);
    assert(motes[0].buttons == 0);
    auto& manager = InputManager::get();
    manager.add_source(std::make_unique<TestProfileSource>(0, 2000));
    manager.update();
    InputSnapshot snapshot;
    assert(manager.consume_input(0, snapshot) && snapshot.mote.buttons == 0xC00);
    std::cout << "PRIVATE_PROFILE_BOUNDARIES_QUEUE_PASS\n";
}
