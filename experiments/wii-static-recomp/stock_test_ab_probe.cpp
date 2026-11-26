#include "stock_test_ab_source.h"
#include <cassert>
#include <iostream>

int main(int argc, char**) {
    using namespace nwii::runtime::input;
    using openshsm::experiment::TestABSource;
    if (argc == 2) {
        try {
            openshsm::experiment::install_test_ab_source(InputManager::get());
        } catch (const std::runtime_error&) {
            std::cout << "PRIVATE_AB_INVALID_ENV_REFUSED\n";
            return 0;
        }
        return 9;
    }
    GameCubePadState pads[4]{};
    WiimoteState motes[4]{};
    pads[1].buttons = 0x5678;
    motes[1].buttons = 0x1234;
    TestABSource source(100, 750);
    for (uint64_t time : {0u, 99u, 100u, 849u, 850u, 180000u}) {
        source.apply(time, pads, motes);
        const auto expected = time >= 100 && time < 850 ? 0xC00u : 0u;
        assert(motes[0].buttons == expected && pads[0].buttons == 0);
        assert(motes[0].err == 0 && pads[0].err == 0 && motes[0].ir_x == 0.5f);
        assert(motes[1].buttons == 0x1234 && pads[1].buttons == 0x5678);
    }
    unsigned rejected = 0;
    for (const auto& [start, duration] : {std::pair{180001u, 750u}, std::pair{0u, 0u}, std::pair{0u, 1001u}}) {
        try { TestABSource invalid(start, duration); }
        catch (const std::runtime_error&) { ++rejected; }
    }
    assert(rejected == 3);
    auto& manager = InputManager::get();
    manager.add_source(std::make_unique<TestABSource>(0, 1000));
    manager.update();
    InputSnapshot snapshot;
    assert(manager.consume_input(0, snapshot));
    assert(snapshot.mote.buttons == 0xC00 && snapshot.mote.err == 0 && snapshot.pad.err == 0);
    std::cout << "PRIVATE_AB_SOURCE_BOUNDARIES_QUEUE_PASS\n";
}
