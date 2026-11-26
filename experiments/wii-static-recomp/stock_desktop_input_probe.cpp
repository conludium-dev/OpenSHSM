#include "input/sources/mouse_keyboard_source.h"
#include "input/sources/gamepad_source.h"
#include "runtime/config.h"
#include "stock_desktop_roll.h"
#include <SDL.h>
#include <array>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <limits>

static std::array<Uint8, SDL_NUM_SCANCODES> keys{};
static std::array<Uint8, SDL_CONTROLLER_BUTTON_MAX> buttons{};
static Uint32 mouse_buttons = 0;
static int mouse_x = 0;
static int mouse_y = 0;
static int window_w = 800;
static int window_h = 600;
static Sint16 left_trigger = 20000;
static Sint16 right_trigger = 0;
static int mapping_calls = 0;
static Sint16 right_x = 0;
static Sint16 left_x = 0;
static Sint16 left_y = 0;
static Sint16 right_y = 0;
static bool controller_present = true;
static int controller_opens = 0;
static int controller_closes = 0;
static SDL_bool relative_mode = SDL_FALSE;
static int cursor_visible = SDL_ENABLE;
static int relative_x = 0;
static int relative_y = 0;
static bool mouse_focused = true;
static Uint32 fake_ticks = 0;

extern "C" int SDLCALL SDL_GameControllerAddMapping(const char* mapping) {
    assert(std::strstr(mapping, "03000000c82d00001b30000001000000,") == mapping);
    assert(std::strstr(mapping, "lefttrigger:a5,") && std::strstr(mapping, "righttrigger:a4,"));
    ++mapping_calls;
    return 1;
}

extern "C" Uint32 SDLCALL SDL_GetTicks(void) {
    return fake_ticks;
}

extern "C" char* SDLCALL SDL_getenv(const char*) {
    return nullptr;
}

extern "C" const Uint8* SDLCALL SDL_GetKeyboardState(int* count) {
    if (count) {
        *count = SDL_NUM_SCANCODES;
    }
    return keys.data();
}

extern "C" Uint32 SDLCALL SDL_GetMouseState(int* x, int* y) {
    *x = mouse_x;
    *y = mouse_y;
    return mouse_buttons;
}

extern "C" SDL_Window* SDLCALL SDL_GetKeyboardFocus(void) {
    return mouse_focused ? reinterpret_cast<SDL_Window*>(&window_w) : nullptr;
}

extern "C" SDL_bool SDLCALL SDL_GetRelativeMouseMode(void) {
    return relative_mode;
}

extern "C" int SDLCALL SDL_SetRelativeMouseMode(SDL_bool enabled) {
    relative_mode = enabled;
    return 0;
}

extern "C" int SDLCALL SDL_ShowCursor(int toggle) {
    if (toggle != SDL_QUERY) {
        cursor_visible = toggle;
    }
    return cursor_visible;
}

extern "C" Uint32 SDLCALL SDL_GetRelativeMouseState(int* x, int* y) {
    *x = relative_x;
    *y = relative_y;
    relative_x = 0;
    relative_y = 0;
    return mouse_buttons;
}

extern "C" void SDLCALL SDL_GetWindowSize(SDL_Window*, int* w, int* h) {
    *w = window_w;
    *h = window_h;
}

extern "C" SDL_bool SDLCALL SDL_IsGameController(int index) {
    return index == 0 && controller_present ? SDL_TRUE : SDL_FALSE;
}

extern "C" SDL_GameController* SDLCALL SDL_GameControllerOpen(int index) {
    if (index != 0 || !controller_present) {
        return nullptr;
    }
    ++controller_opens;
    return reinterpret_cast<SDL_GameController*>(buttons.data());
}

extern "C" SDL_JoystickID SDLCALL SDL_JoystickGetDeviceInstanceID(int index) {
    return index == 0 && controller_present ? 7 : -1;
}

extern "C" SDL_bool SDLCALL SDL_GameControllerGetAttached(SDL_GameController*) {
    return controller_present ? SDL_TRUE : SDL_FALSE;
}

extern "C" void SDLCALL SDL_GameControllerClose(SDL_GameController*) {
    ++controller_closes;
}

extern "C" Uint8 SDLCALL SDL_GameControllerGetButton(SDL_GameController*, SDL_GameControllerButton button) {
    return buttons[button];
}

extern "C" Sint16 SDLCALL SDL_GameControllerGetAxis(SDL_GameController*, SDL_GameControllerAxis axis) {
    if (axis == SDL_CONTROLLER_AXIS_TRIGGERLEFT) {
        return left_trigger;
    }
    if (axis == SDL_CONTROLLER_AXIS_TRIGGERRIGHT) {
        return right_trigger;
    }
    if (axis == SDL_CONTROLLER_AXIS_LEFTX) {
        return left_x;
    }
    if (axis == SDL_CONTROLLER_AXIS_LEFTY) {
        return left_y;
    }
    if (axis == SDL_CONTROLLER_AXIS_RIGHTX) {
        return right_x;
    }
    if (axis == SDL_CONTROLLER_AXIS_RIGHTY) {
        return right_y;
    }
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
    MouseKeyboardSource keyboard;
    GameCubePadState pads[4]{};
    WiimoteState motes[4]{};
    mouse_x = 400;
    mouse_y = 300;
    keys[SDL_SCANCODE_E] = 1;
    keys[SDL_SCANCODE_Q] = 1;
    keys[SDL_SCANCODE_2] = 1;
    keys[SDL_SCANCODE_M] = 1;
    keys[SDL_SCANCODE_H] = 1;
    keys[SDL_SCANCODE_RETURN] = 1;
    keys[SDL_SCANCODE_F] = 1;
    keys[SDL_SCANCODE_W] = 1;
    keys[SDL_SCANCODE_LSHIFT] = 1;
    keys[SDL_SCANCODE_LCTRL] = 1;
    mouse_buttons = SDL_BUTTON(SDL_BUTTON_LEFT) | SDL_BUTTON(SDL_BUTTON_RIGHT);
    keyboard.update(pads, motes);
    assert(motes[0].ir_x == 0.5f && motes[0].ir_y == 0.5f);
    assert(motes[0].buttons == (0x0800 | 0x0400 | 0x0100 | 0x1000 | 0x0080 | 0x0200 | 0x0010));
    assert(pads[0].buttons == (0x0100 | 0x0200 | 0x1000));
    assert(pads[0].stick_y == 127);
    assert(relative_mode == SDL_TRUE);
    assert(cursor_visible == SDL_DISABLE);
    keys[SDL_SCANCODE_F10] = 1;
    mouse_buttons = 0;
    pads[0] = {};
    motes[0] = {};
    keyboard.update(pads, motes);
    assert(relative_mode == SDL_FALSE);
    assert(cursor_visible == SDL_ENABLE);
    keys.fill(0);
    mouse_buttons = 0;
    mouse_x = -10;
    mouse_y = 900;
    window_w = 1600;
    window_h = 900;
    pads[0] = {};
    motes[0] = {};
    keyboard.update(pads, motes);
    assert(motes[0].ir_x == 0.0f && motes[0].ir_y == 1.0f);
    assert(motes[0].buttons == 0 && pads[0].buttons == 0);
    mouse_x = 800;
    mouse_y = 450;
    mouse_buttons = SDL_BUTTON(SDL_BUTTON_LEFT);
    relative_x = 160;
    relative_y = -90;
    pads[0] = {};
    motes[0] = {};
    keyboard.update(pads, motes);
    assert(relative_mode == SDL_TRUE);
    assert(std::abs(motes[0].ir_x - 0.6f) < 0.0001f);
    assert(std::abs(motes[0].ir_y - 0.4f) < 0.0001f);
    mouse_focused = false;
    keyboard.update(pads, motes);
    assert(relative_mode == SDL_FALSE);
    mouse_focused = true;
    mouse_buttons = 0;
    keyboard.update(pads, motes);

    GamepadSource gamepad;
    buttons[SDL_CONTROLLER_BUTTON_A] = 1;
    buttons[SDL_CONTROLLER_BUTTON_B] = 1;
    buttons[SDL_CONTROLLER_BUTTON_X] = 1;
    buttons[SDL_CONTROLLER_BUTTON_Y] = 1;
    buttons[SDL_CONTROLLER_BUTTON_BACK] = 1;
    buttons[SDL_CONTROLLER_BUTTON_START] = 1;
    buttons[SDL_CONTROLLER_BUTTON_RIGHTSHOULDER] = 1;
    buttons[SDL_CONTROLLER_BUTTON_LEFTSHOULDER] = 1;
    pads[0] = {};
    motes[0] = {};
    gamepad.update(pads, motes);
    assert(motes[0].buttons == (0x0800 | 0x0400 | 0x0100 | 0x1000 | 0x0080 | 0x0200 | 0x0010));
    assert((pads[0].buttons & 0x0300) == 0x0300);
    buttons.fill(0);
    left_trigger = 0;
    buttons[SDL_CONTROLLER_BUTTON_A] = 1;
    buttons[SDL_CONTROLLER_BUTTON_B] = 1;
    pads[0] = {};
    motes[0] = {};
    gamepad.update(pads, motes);
    assert(motes[0].buttons == (0x0800 | 0x0400));
    assert((pads[0].buttons & 0x0300) == 0);
    assert(controller_opens == 1 && controller_closes == 0);
    buttons.fill(0);
    mouse_x = 400;
    mouse_y = 300;
    right_x = 16000;
    pads[0] = {};
    motes[0] = {};
    keyboard.update(pads, motes);
    gamepad.update(pads, motes);
    const float mouse_pointer = motes[0].ir_x;
    pads[0] = {};
    motes[0] = {};
    keyboard.update(pads, motes);
    gamepad.update(pads, motes);
    assert(motes[0].ir_x > mouse_pointer);
    const float first_stick_pointer = motes[0].ir_x;
    pads[0] = {};
    motes[0] = {};
    keyboard.update(pads, motes);
    gamepad.update(pads, motes);
    assert(motes[0].ir_x > first_stick_pointer);
    mouse_x = 600;
    pads[0] = {};
    motes[0] = {};
    keyboard.update(pads, motes);
    gamepad.update(pads, motes);
    assert(motes[0].ir_x == 0.375f);
    mouse_buttons = SDL_BUTTON(SDL_BUTTON_LEFT);
    pads[0] = {};
    motes[0] = {};
    keyboard.update(pads, motes);
    gamepad.update(pads, motes);
    assert(relative_mode == SDL_FALSE && motes[0].ir_x > 0.375f);
    const float switched_pointer = motes[0].ir_x;
    keys[SDL_SCANCODE_F10] = 1;
    mouse_buttons = 0;
    right_x = 0;
    pads[0] = {};
    motes[0] = {};
    keyboard.update(pads, motes);
    gamepad.update(pads, motes);
    assert(relative_mode == SDL_FALSE && motes[0].ir_x == switched_pointer);
    controller_present = false;
    gamepad.update(pads, motes);
    assert(controller_opens == 1 && controller_closes == 1);
    nwii::runtime::Config::get().input_mode = 6;
    keys.fill(0);
    mouse_x = 400;
    mouse_y = 300;
    window_w = 800;
    window_h = 600;
    relative_x = relative_y = 0;
    mouse_buttons = SDL_BUTTON(SDL_BUTTON_LEFT) | SDL_BUTTON(SDL_BUTTON_RIGHT);
    keyboard.update(pads, motes);
    const float original_x = motes[0].ir_x, original_y = motes[0].ir_y;
    relative_x = 120;
    relative_y = 40;
    fake_ticks += 20;
    keyboard.update(pads, motes);
    assert(motes[0].accel_x == 0 && motes[0].accel_y == -1 && motes[0].accel_z == 0);
    assert(motes[0].ir_x > original_x && motes[0].ir_y > original_y);
    const float before_x = motes[0].ir_x, before_y = motes[0].ir_y;
    keys[SDL_SCANCODE_LALT] = 1;
    relative_x = 120;
    keyboard.update(pads, motes);
    assert(std::abs(motes[0].accel_x + 0.5f) < 0.00001f);
    assert(std::abs(motes[0].accel_y + 0.8660254f) < 0.00001f);
    assert(motes[0].ir_x == before_x && motes[0].ir_y == before_y);
    assert((motes[0].buttons & 0xC00) == 0xC00);
    mouse_buttons = SDL_BUTTON(SDL_BUTTON_LEFT);
    keys[SDL_SCANCODE_LALT] = 1;
    relative_x = -120;
    relative_y = 0;
    keyboard.update(pads, motes);
    assert(std::abs(motes[0].accel_x) < 0.00001f && std::abs(motes[0].accel_y + 1) < 0.00001f);
    assert(motes[0].ir_x == before_x && motes[0].ir_y == before_y);

    relative_x = relative_y = 0;
    keys.fill(0);
    keys[SDL_SCANCODE_R] = 1;
    keyboard.update(pads, motes);
    keys.fill(0);
    keys[SDL_SCANCODE_X] = 1;
    for (unsigned i = 0; i < 10; ++i) {
        fake_ticks += 100;
        keyboard.update(pads, motes);
    }
    assert(std::abs(motes[0].accel_x + 1) < 0.00001f && std::abs(motes[0].accel_z) < 0.00001f);
    keys.fill(0);
    fake_ticks += 100;
    keyboard.update(pads, motes);
    assert(std::abs(motes[0].accel_x + 1) < 0.00001f);
    mouse_focused = false;
    keyboard.update(pads, motes);
    assert(motes[0].accel_x == 0 && motes[0].accel_y == -1 && motes[0].accel_z == 0);
    mouse_focused = true;
    nwii::runtime::Config::get().input_mode = 3;
    motes[0].accel_x = 7;
    motes[0].accel_y = 8;
    motes[0].accel_z = 9;
    keyboard.update(pads, motes);
    assert(motes[0].accel_x == 7 && motes[0].accel_y == 8 && motes[0].accel_z == 9);
    nwii::runtime::Config::get().input_mode = 6;
    mouse_buttons = 0;
    keys.fill(0);

    controller_present = true;
    relative_mode = SDL_FALSE;
    buttons.fill(0);
    buttons[SDL_CONTROLLER_BUTTON_A] = 1;
    right_trigger = 32767;
    left_x = 32767;
    right_x = 0;
    right_y = 0;
    openshsm::experiment::primary_desktop_roll().publish_twist_context(true);
    keyboard.update(pads, motes);
    const float grab_x = motes[0].ir_x, grab_y = motes[0].ir_y;
    gamepad.update(pads, motes);
    for (unsigned frame = 0; frame < 10; ++frame) {
        fake_ticks += 100;
        pads[0] = {};
        motes[0] = {};
        keyboard.update(pads, motes);
        gamepad.update(pads, motes);
        assert((motes[0].buttons & 0xC00) == 0xC00);
        assert(motes[0].ir_x == grab_x && motes[0].ir_y == grab_y);
    }
    assert(motes[0].accel_x == 0 && motes[0].accel_y == -1 && motes[0].accel_z == 0);
    for (unsigned frame = 1; frame <= 10; ++frame) {
        const double radians = frame * 10.0 * 3.14159265358979323846 / 180.0;
        left_x = Sint16(std::lround(std::cos(radians) * 32767));
        left_y = Sint16(std::lround(std::sin(radians) * 32767));
        fake_ticks += 100;
        keyboard.update(pads, motes);
        gamepad.update(pads, motes);
    }
    const float circle_pose = motes[0].accel_x;
    assert(std::abs(circle_pose + 0.35836795f) < 0.00001f);
    controller_present = false;
    gamepad.update(pads, motes);
    controller_present = true;
    left_x = -32767;
    left_y = 0;
    fake_ticks += 100;
    gamepad.update(pads, motes);
    assert(motes[0].accel_x == circle_pose);
    buttons.fill(0);
    right_trigger = 0;
    right_x = 0;
    left_x = 0;
    left_y = 0;
    keyboard.update(pads, motes);
    gamepad.update(pads, motes);
    assert(motes[0].accel_x == circle_pose);
    keys[SDL_SCANCODE_R] = 1;
    keyboard.update(pads, motes);
    gamepad.update(pads, motes);
    assert(motes[0].accel_x == 0 && motes[0].accel_y == -1 && motes[0].accel_z == 0);
    keys.fill(0);
    assert(mapping_calls == 1);
    relative_mode = SDL_TRUE;
    right_x = 20000;
    const float pointer_before = motes[0].ir_x;
    gamepad.update(pads, motes);
    assert(relative_mode == SDL_FALSE);
    assert(motes[0].ir_x > pointer_before);
    right_x = 0;


    for (uint32_t step : {1u, 10u, 16u, 33u, 100u}) {
        openshsm::experiment::DesktopRoll roll;
        roll.update(0, true, false, true, false, 0);
        std::array<float, 3> gravity{};
        uint32_t tick = 0;
        while (tick < 1000) {
            tick = std::min(tick + step, uint32_t(1000));
            gravity = roll.update(tick, true, false, true, false, 0);
        }
        assert(std::abs(gravity[0] + 1) < 0.00001f && std::abs(gravity[2]) < 0.00001f);
    }
    openshsm::experiment::DesktopRoll wrapped;
    wrapped.update(0xFFFFFFCDu, true, false, true, false, 0);
    const auto quarter = wrapped.update(49, true, false, true, false, 0);
    assert(std::abs(quarter[0] + 0.15643447f) < 0.00001f);
    const auto reset = wrapped.update(1000, false, true, true, false, 2147483647);
    assert(reset[0] == 0 && reset[1] == -1 && reset[2] == 0);
    for (int direction : {-1, 1}) {
        openshsm::experiment::DesktopRoll circle;
        uint32_t tick = 0xFFFFFF00u;
        const auto sample = [&](int degrees, bool focused = true, bool grabbed = true) {
            tick += 16;
            const double radians = degrees * 3.14159265358979323846 / 180.0;
            return circle.analog(tick, focused, grabbed, float(std::cos(radians)), float(std::sin(radians)));
        };
        for (unsigned i = 0; i <= 15; ++i) {
            assert(sample(direction * int(i) * 10)[0] == 0);
        }
        circle.publish_twist_context(true, 0x80600000);
        std::array<float, 3> pose{};
        for (unsigned i = 0; i <= 15; ++i) {
            pose = sample(direction * int(i) * 10);
        }
        const float expected = float(std::sin(direction * 5.76 * 3.14159265358979323846 / 180.0));
        assert(std::abs(pose[0] + expected) < 0.00001f);
        for (unsigned i = 0; i < 120; ++i) {
            assert(sample(direction * 150) == pose);
        }
        sample(150, true, false);
        assert(sample(0) == pose);
        circle.publish_twist_context(false, 0x80600000);
        circle.publish_twist_context(true, 0x80600000);
        assert(sample(direction * 60) == pose);
        circle.publish_twist_context(true, 0x80610000);
        assert(sample(direction * 120) == pose);
        for (float invalid : {std::numeric_limits<float>::quiet_NaN(),
                std::numeric_limits<float>::infinity(), 2.0f}) {
            assert(circle.analog(tick += 16, true, true, invalid, 0) == pose);
            assert(sample(0) == pose);
        }
        assert(circle.analog(tick += 16, true, true, 0, 0) == pose);
        assert(sample(direction * 90) == pose);
        const auto lost = sample(0, false);
        assert(lost[0] == 0 && lost[1] == -1 && lost[2] == 0);
        const auto resumed = sample(0);
        assert(resumed[0] == 0 && resumed[1] == -1 && resumed[2] == 0);
    }
    std::puts("DESKTOP_WII_INPUT_BINDINGS_PASS");
}
