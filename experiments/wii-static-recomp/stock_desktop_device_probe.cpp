#include "input/input_manager.h"
#include "stock_desktop_qte.h"
#include <memory>

int main() {
    using namespace nwii::runtime;
    using namespace nwii::runtime::input;
    using namespace openshsm::experiment;
    auto& manager = InputManager::get();
    manager.add_source(std::make_unique<MouseKeyboardSource>());
    manager.add_source(std::make_unique<GamepadSource>());
    Config::get().input_mode = 6;
    left_trigger = right_trigger = left_x = left_y = right_x = right_y = 0;
    const auto next = [&]() {
        manager.update();
        InputSnapshot snapshot;
        assert(manager.consume_input(0, snapshot));
        return snapshot.look;
    };
    assert(next().device == DesktopInputDevice::Unknown);
    keys[SDL_SCANCODE_UP] = 1;
    auto sample = next();
    assert(sample.qte_controller == 7 && sample.device == DesktopInputDevice::KeyboardMouse);
    assert(sample.qte_buttons == 1);
    keys.fill(0);
    assert(next().device == DesktopInputDevice::KeyboardMouse);
    buttons[SDL_CONTROLLER_BUTTON_A] = 1;
    assert(next().device == DesktopInputDevice::Gamepad);
    buttons.fill(0);
    assert(next().device == DesktopInputDevice::Gamepad);
    keys[SDL_SCANCODE_W] = 1;
    assert(next().device == DesktopInputDevice::KeyboardMouse);
    keys.fill(0);
    left_x = 6553;
    assert(next().device == DesktopInputDevice::KeyboardMouse);
    left_x = 6554;
    assert(next().device == DesktopInputDevice::Gamepad);
    left_x = 0;
    mouse_buttons = SDL_BUTTON(SDL_BUTTON_LEFT);
    assert(next().device == DesktopInputDevice::KeyboardMouse);
    mouse_buttons = 0;
    right_trigger = 20000;
    assert(next().device == DesktopInputDevice::Gamepad);
    right_trigger = 0;
    mouse_focused = false;
    keys[SDL_SCANCODE_UP] = 1;
    assert(next().device == DesktopInputDevice::Gamepad);
    mouse_focused = true;
    controller_present = false;
    sample = next();
    assert(sample.qte_controller == -1 && sample.device == DesktopInputDevice::KeyboardMouse);
    keys.fill(0);
    controller_present = true;
    assert(next().device == DesktopInputDevice::KeyboardMouse);
    keys[SDL_SCANCODE_UP] = 1;
    buttons[SDL_CONTROLLER_BUTTON_A] = 1;
    sample = next();
    assert(sample.qte_buttons == 1 && sample.device == DesktopInputDevice::Gamepad);
    keys.fill(0);
    buttons.fill(0);
    assert(next().device == DesktopInputDevice::Gamepad);

    DesktopLookInput input;
    input.begin(10);
    input.buttons(0x80, true, 7);
    input.buttons(1, false, 7);
    input.buttons(1, true, -2);
    input.activity(DesktopInputDevice(3));
    assert(input.sample().device == DesktopInputDevice::Unknown && input.sample().qte_buttons == 0);
    input.mouse(std::numeric_limits<float>::quiet_NaN(), 0, true, false);
    input.stick(1, 0, false, false);
    assert(input.sample().device == DesktopInputDevice::Unknown);
    input.mouse(1, 0, true, false);
    input.begin(11);
    input.buttons(0, true, 7);
    assert(input.sample().device == DesktopInputDevice::KeyboardMouse && input.sample().qte_controller == 7);

    unsigned cases = 0;
    DesktopQTEPromptChannel channel;
    for (uint32_t context : {1u, DesktopQTEPromptChannel::max_context}) {
        for (uint32_t now : {0u, 0xFFFFFFF0u}) {
            for (unsigned target = 0; target < 4; ++target) {
                for (unsigned device = 0; device < 3; ++device) {
                    for (bool blocked : {false, true}) {
                        channel.publish(context, target, blocked, now, DesktopInputDevice(device));
                        const auto prompt = channel.read(now + 250);
                        assert(prompt.context == context && prompt.target == target && prompt.blocked == blocked);
                        assert(prompt.device == DesktopInputDevice(device));
                        assert(channel.read(now + 251).context == 0);
                        ++cases;
                    }
                }
            }
        }
    }
    channel.publish(1, 0, false, 10, DesktopInputDevice(3));
    assert(channel.read(10).context == 0);
    channel.publish(DesktopQTEPromptChannel::max_context + 1, 0, false, 10);
    assert(channel.read(10).context == 0);
    channel.publish(0, 0, false, 10);
    assert(channel.read(10).context == 0);
    std::printf("DESKTOP_ACTIVE_DEVICE_SOURCES_AND_PROMPT_PASS cases=%u\n", cases);
}
