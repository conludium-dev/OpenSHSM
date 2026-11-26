"""Extend the existing InputManager only in a private generated copy; no second provider."""

def adapt(header, source):
    assert header.count('class InputManager {') == 1
    header = header.replace('#include <memory>', '#include <memory>\n#include <array>\n#include <deque>\n#include <mutex>')
    header = header.replace('class InputManager {', '''struct InputSnapshot {
    GameCubePadState pad{};
    WiimoteState mote{};
    uint64_t generation = 0;
    InputMode mode = InputMode::GamepadClassic;
};

class InputManager {''')
    header = header.replace('InputMode get_mode() const { return current_mode; }', 'InputMode get_mode() const;')
    header = header.replace('WiimoteState get_wiimote_state(int index);', '''WiimoteState get_wiimote_state(int index);
    bool consume_input(int index, InputSnapshot& snapshot);
    uint64_t dropped_input(int index) const;''')
    header = header.replace('std::vector<std::unique_ptr<IInputSource>> sources;', '''std::vector<std::unique_ptr<IInputSource>> sources;
    mutable std::mutex snapshot_mutex;
    uint64_t update_generation = 0;
    std::array<std::deque<InputSnapshot>, 4> pending_snapshots;
    std::array<uint64_t, 4> dropped_snapshots{};''')
    signatures = ['void InputManager::add_source(std::unique_ptr<IInputSource> source)',
        'void InputManager::set_mode(InputMode mode)', 'void InputManager::update()',
        'GameCubePadState InputManager::get_gcpad_state(int index)',
        'WiimoteState InputManager::get_wiimote_state(int index)']
    for signature in signatures:
        assert source.count(signature + ' {') == 1
        source = source.replace(signature + ' {', signature + ' {\n    std::lock_guard<std::mutex> lock(snapshot_mutex);')
    end = '        source->update(gc_pads, wii_motes);\n    }\n}'
    assert source.count(end) == 1
    source = source.replace(end, '''        source->update(gc_pads, wii_motes);
    }
    ++update_generation;
    for (int channel = 0; channel < 4; ++channel) {
        auto& queue = pending_snapshots[channel];
        if (queue.size() == 16) {
            queue.pop_front();
            ++dropped_snapshots[channel];
        }
        queue.push_back({gc_pads[channel], wii_motes[channel], update_generation, current_mode});
    }
}''')
    marker = 'GameCubePadState InputManager::get_gcpad_state(int index) {'
    source = source.replace(marker, '''InputMode InputManager::get_mode() const {
    std::lock_guard<std::mutex> lock(snapshot_mutex);
    return current_mode;
}

bool InputManager::consume_input(int index, InputSnapshot& snapshot) {
    std::lock_guard<std::mutex> lock(snapshot_mutex);
    if (index < 0 || index >= 4 || pending_snapshots[index].empty()) {
        return false;
    }
    snapshot = pending_snapshots[index].front();
    pending_snapshots[index].pop_front();
    return true;
}

uint64_t InputManager::dropped_input(int index) const {
    std::lock_guard<std::mutex> lock(snapshot_mutex);
    return index >= 0 && index < 4 ? dropped_snapshots[index] : 0;
}

''' + marker)
    return header, source
