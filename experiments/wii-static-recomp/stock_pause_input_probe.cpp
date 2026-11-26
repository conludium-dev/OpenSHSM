#include "input/sources/mouse_keyboard_source.h"
#include "input/sources/gamepad_source.h"
#include "input/input_manager.h"
#include <SDL.h>
#include <array>
#include <cassert>
#include <cstdio>
#include <initializer_list>
#include <memory>

static std::array<Uint8, SDL_NUM_SCANCODES> keys{};
static std::array<Uint8, SDL_CONTROLLER_BUTTON_MAX> gamepad_buttons{};

extern "C" const Uint8* SDLCALL SDL_GetKeyboardState(int* count) {
    if (count) {
        *count = SDL_NUM_SCANCODES;
    }
    return keys.data();
}

extern "C" Uint32 SDLCALL SDL_GetMouseState(int* x, int* y) {
    if (x) {
        *x = 320;
    }
    if (y) {
        *y = 240;
    }
    return 0;
}

extern "C" SDL_bool SDLCALL SDL_IsGameController(int index) {
    return index == 0 ? SDL_TRUE : SDL_FALSE;
}

extern "C" SDL_GameController* SDLCALL SDL_GameControllerOpen(int index) {
    return index == 0 ? reinterpret_cast<SDL_GameController*>(&gamepad_buttons) : nullptr;
}

extern "C" Uint8 SDLCALL SDL_GameControllerGetButton(SDL_GameController*, SDL_GameControllerButton button) {
    return gamepad_buttons[button];
}

extern "C" Sint16 SDLCALL SDL_GameControllerGetAxis(SDL_GameController*, SDL_GameControllerAxis) {
    return 0;
}

extern "C" SDL_bool SDLCALL SDL_GameControllerHasSensor(SDL_GameController*, SDL_SensorType) {
    return SDL_FALSE;
}

extern "C" int SDLCALL SDL_GameControllerSetSensorEnabled(SDL_GameController*, SDL_SensorType, SDL_bool) {
    return 0;
}

extern "C" int SDLCALL SDL_GameControllerGetSensorData(SDL_GameController*, SDL_SensorType, float*, int) {
    return -1;
}

int main() {
    using namespace nwii::runtime::input;
    MouseKeyboardSource source;
    auto sample = [&](std::initializer_list<SDL_Scancode> pressed, uint32_t expected) {
        keys.fill(0);
        for (SDL_Scancode key : pressed) {
            keys[key] = 1;
        }
        GameCubePadState pads[4]{};
        WiimoteState motes[4]{};
        source.update(pads, motes);
        assert(motes[0].err == 0);
        assert(motes[0].buttons == expected);
    };
    sample({}, 0);
    sample({SDL_SCANCODE_RETURN}, 0x0200);
    sample({SDL_SCANCODE_ESCAPE}, 0x0200);
    sample({SDL_SCANCODE_F}, 0x0010);
    sample({SDL_SCANCODE_RETURN, SDL_SCANCODE_F}, 0x0210);
    sample({SDL_SCANCODE_RIGHT}, 0x0002);
    GamepadSource controller;
    auto gamepad_sample = [&](SDL_GameControllerButton button, uint32_t expected_wii,
            uint16_t expected_pad) {
        gamepad_buttons.fill(0);
        gamepad_buttons[button] = 1;
        GameCubePadState pads[4]{};
        WiimoteState motes[4]{};
        controller.update(pads, motes);
        assert(motes[0].err == 0 && pads[0].err == 0);
        assert(motes[0].buttons == expected_wii);
        assert(pads[0].buttons == expected_pad);
    };
    gamepad_sample(SDL_CONTROLLER_BUTTON_START, 0x0200, 0x1000);
    gamepad_sample(SDL_CONTROLLER_BUTTON_RIGHTSHOULDER, 0x0010, 0x0020);
    gamepad_sample(SDL_CONTROLLER_BUTTON_A, 0x0800, 0x0100);
    struct PulseSource : IInputSource {
        uint32_t buttons = 0;
        void update(GameCubePadState[4], WiimoteState motes[4]) override {
            motes[0].err = 0;
            motes[0].buttons |= buttons;
        }
    };
    auto pulse = std::make_unique<PulseSource>();
    PulseSource* pulse_control = pulse.get();
    auto& input = InputManager::get();
    input.add_source(std::move(pulse));
    input.update();
    InputSnapshot snapshot;
    assert(input.consume_input(0, snapshot) && snapshot.mote.buttons == 0);
    pulse_control->buttons = 0x0200;
    input.update();
    pulse_control->buttons = 0;
    for (int i = 0; i < 32; ++i) {
        input.update();
        assert(input.get_wiimote_state(0).buttons == 0);
    }
    int pause_samples = 0;
    int total_samples = 0;
    while (input.consume_input(0, snapshot)) {
        pause_samples += snapshot.mote.buttons == 0x0200;
        ++total_samples;
    }
    assert(total_samples == 16 && pause_samples == 1);
    assert(input.dropped_input(0) == 17);
    std::puts("PAUSE_INPUT_HEADLESS_PROBE_PASS 15");
}
