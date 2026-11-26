#include <input/input_manager.h>
#include <atomic>
#include <iostream>
#include <memory>
#include <thread>

class SequenceSource : public nwii::runtime::input::IInputSource {
public:
    unsigned sequence = 0;
    void update(nwii::runtime::input::GameCubePadState pads[4], nwii::runtime::input::WiimoteState motes[4]) override {
        ++sequence;
        pads[0].err = 0;
        pads[0].buttons = sequence & 0xFFFF;
        motes[0].err = 0;
        motes[0].buttons = sequence;
        motes[0].ir_x = float(sequence);
    }
};

int main() {
    using namespace nwii::runtime::input;
    auto& input = InputManager::get();
    InputSnapshot snapshot;
    snapshot.generation = 123;
    if (input.consume_input(0, snapshot) || snapshot.generation != 123) {
        return 1;
    }
    input.add_source(std::make_unique<SequenceSource>());
    input.set_mode(InputMode::MouseKeyboard);
    for (unsigned i = 1; i <= 8; ++i) {
        input.update();
        if (!input.consume_input(0, snapshot) || snapshot.generation != i || snapshot.mote.buttons != i
            || snapshot.pad.buttons != i || snapshot.mote.ir_x != float(i) || snapshot.mode != InputMode::MouseKeyboard) {
            return 2;
        }
        if (input.consume_input(0, snapshot)) {
            return 3;
        }
        for (int channel = 1; channel < 4; ++channel) {
            if (!input.consume_input(channel, snapshot) || snapshot.pad.err != -1 || snapshot.mote.err != -1
                || input.consume_input(channel, snapshot)) {
                return 4;
            }
        }
        snapshot.generation = 123;
        if (input.consume_input(-1, snapshot) || input.consume_input(4, snapshot) || snapshot.generation != 123) {
            return 5;
        }
    }
    for (unsigned i = 0; i < 18; ++i) {
        input.update();
    }
    if (input.dropped_input(0) != 2) {
        return 7;
    }
    for (unsigned expected = 11; expected <= 26; ++expected) {
        if (!input.consume_input(0, snapshot) || snapshot.generation != expected || snapshot.mote.buttons != expected) {
            return 8;
        }
    }
    if (input.consume_input(0, snapshot)) {
        return 9;
    }
    std::atomic<bool> done = false;
    std::thread producer([&]() {
        for (unsigned i = 0; i < 10000; ++i) {
            input.update();
            if ((i % 64) == 0) {
                std::this_thread::yield();
            }
        }
        done = true;
    });
    uint64_t previous = 26;
    unsigned observed = 0;
    bool coherent = true;
    while (!done || previous != 10026) {
        if (!input.consume_input(0, snapshot)) {
            std::this_thread::yield();
            continue;
        }
        coherent &= snapshot.generation > previous && snapshot.generation == snapshot.mote.buttons
            && snapshot.pad.buttons == (snapshot.mote.buttons & 0xFFFF)
            && snapshot.mote.ir_x == float(snapshot.mote.buttons);
        previous = snapshot.generation;
        ++observed;
    }
    producer.join();
    if (!coherent || previous != 10026 || observed == 0 || observed + input.dropped_input(0) - 2 != 10000) {
        return 6;
    }
    std::cout << "INPUT_SNAPSHOT_PASS sequential8/channels4/invalid2/bounded16-overflow2/concurrent10000 observed="
        << observed << " dropped=" << input.dropped_input(0) << '\n';
}
