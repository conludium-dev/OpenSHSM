"""Extend the existing Wii input sources with desktop button and pointer bindings."""


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f'Input patch site differs: {old!r}')
    return source.replace(old, new, 1)


def keyboard(source):
    source = replace_once(source, '#include <SDL.h>\n',
        '#include <SDL.h>\n#include <algorithm>\n')
    source = replace_once(source,
        '    int w = nwii::runtime::Config::get().window_width;\n'
        '    int h = nwii::runtime::Config::get().window_height;\n'
        '    if (w == 0) w = 640;\n'
        '    if (h == 0) h = 480;\n'
        '    \n'
        '    motes[0].ir_x = (float)mx / (float)w;\n'
        '    motes[0].ir_y = (float)my / (float)h;\n',
        '    int w = nwii::runtime::Config::get().window_width;\n'
        '    int h = nwii::runtime::Config::get().window_height;\n'
        '    SDL_Window *focused = SDL_GetKeyboardFocus();\n'
        '    if (focused) {\n'
        '        SDL_GetWindowSize(focused, &w, &h);\n'
        '    }\n'
        '    if (w <= 0) { w = 640; }\n'
        '    if (h <= 0) { h = 480; }\n'
        '    static float pointer_x = 0.5f, pointer_y = 0.5f;\n'
        '    static bool previous_left_down = false;\n'
        '    const bool left_down = (mouse_state & SDL_BUTTON(SDL_BUTTON_LEFT)) != 0;\n'
        '    bool captured = SDL_GetRelativeMouseMode() == SDL_TRUE;\n'
        '    if (captured && (!focused || keys[SDL_SCANCODE_F10])) {\n'
        '        SDL_SetRelativeMouseMode(SDL_FALSE);\n'
        '        SDL_ShowCursor(SDL_ENABLE);\n'
        '        captured = false;\n'
        '    } else if (!captured && focused && left_down && !previous_left_down &&\n'
        '            !keys[SDL_SCANCODE_F10]) {\n'
        '        pointer_x = std::clamp(static_cast<float>(mx) / w, 0.0f, 1.0f);\n'
        '        pointer_y = std::clamp(static_cast<float>(my) / h, 0.0f, 1.0f);\n'
        '        captured = SDL_SetRelativeMouseMode(SDL_TRUE) == 0;\n'
        '        if (captured) { SDL_ShowCursor(SDL_DISABLE); }\n'
        '    }\n'
        '    previous_left_down = left_down;\n'
        '    if (captured) {\n'
        '        int dx = 0, dy = 0;\n'
        '        SDL_GetRelativeMouseState(&dx, &dy);\n'
        '        pointer_x = std::clamp(pointer_x + static_cast<float>(dx) / w, 0.0f, 1.0f);\n'
        '        pointer_y = std::clamp(pointer_y + static_cast<float>(dy) / h, 0.0f, 1.0f);\n'
        '        motes[0].ir_x = pointer_x;\n'
        '        motes[0].ir_y = pointer_y;\n'
        '    } else {\n'
        '        motes[0].ir_x = std::clamp(static_cast<float>(mx) / w, 0.0f, 1.0f);\n'
        '        motes[0].ir_y = std::clamp(static_cast<float>(my) / h, 0.0f, 1.0f);\n'
        '    }\n')
    source = replace_once(source,
        '    if (mouse_state & SDL_BUTTON(SDL_BUTTON_RIGHT)) motes[0].buttons |= 0x0400; \n',
        '    if (mouse_state & SDL_BUTTON(SDL_BUTTON_RIGHT)) motes[0].buttons |= 0x0400; \n'
        '    if (keys[SDL_SCANCODE_E]) { motes[0].buttons |= 0x0800; }\n'
        '    if (keys[SDL_SCANCODE_Q] || keys[SDL_SCANCODE_BACKSPACE]) { motes[0].buttons |= 0x0400; }\n'
        '    if (keys[SDL_SCANCODE_2]) { motes[0].buttons |= 0x0100; }\n'
        '    if (keys[SDL_SCANCODE_M]) { motes[0].buttons |= 0x1000; }\n'
        '    if (keys[SDL_SCANCODE_H]) { motes[0].buttons |= 0x0080; }\n')
    source = replace_once(source,
        '    if (keys[SDL_SCANCODE_BACKSPACE]) motes[0].buttons |= 0x0001; \n', '')
    source = replace_once(source,
        '    if (keys[SDL_SCANCODE_SPACE]) pads[0].buttons |= 0x0100;\n',
        '    if (keys[SDL_SCANCODE_SPACE] || keys[SDL_SCANCODE_LSHIFT] || '
        '(mouse_state & SDL_BUTTON(SDL_BUTTON_MIDDLE))) { pads[0].buttons |= 0x0100; }\n'
        '    if (keys[SDL_SCANCODE_LCTRL] || keys[SDL_SCANCODE_RCTRL] || '
        '(mouse_state & SDL_BUTTON(SDL_BUTTON_X1))) { pads[0].buttons |= 0x0200; }\n')
    return source


def gamepad(source):
    source = replace_once(source, '#include <cmath>\n', '#include <cmath>\n#include <array>\n#include <algorithm>\n')
    source = replace_once(source,
        '    bool want_pointer = (mode == 3 || mode == 4);\n\n'
        '    for (int i = 0; i < 4; ++i) {\n'
        '        if (!SDL_IsGameController(i))\n'
        '            continue;\n'
        '            \n'
        '        SDL_GameController* controller = SDL_GameControllerOpen(i);\n'
        '        if (!controller) continue;\n',
        '    bool want_pointer = (mode == 3 || mode == 4);\n'
        '    struct ControllerSlot { SDL_JoystickID id = -1; SDL_GameController* handle = nullptr; };\n'
        '    static std::array<ControllerSlot, 4> slots{};\n'
        '    static float stick_x = 0.5f, stick_y = 0.5f;\n'
        '    static int last_mouse_x = 0, last_mouse_y = 0;\n'
        '    static bool mouse_seen = false, stick_active = false;\n\n'
        '    for (int i = 0; i < 4; ++i) {\n'
        '        const SDL_JoystickID id = SDL_IsGameController(i) '
        '? SDL_JoystickGetDeviceInstanceID(i) : -1;\n'
        '        if (slots[i].handle && (slots[i].id != id || '
        '!SDL_GameControllerGetAttached(slots[i].handle))) {\n'
        '            SDL_GameControllerClose(slots[i].handle);\n'
        '            slots[i] = {};\n'
        '            if (i == 0) { stick_active = false; }\n'
        '        }\n'
        '        if (id < 0) { continue; }\n'
        '        if (!slots[i].handle) {\n'
        '            slots[i].handle = SDL_GameControllerOpen(i);\n'
        '            slots[i].id = id;\n'
        '        }\n'
        '        SDL_GameController* controller = slots[i].handle;\n'
        '        if (!controller) { continue; }\n')
    source = replace_once(source,
        '        if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_A)) motes[i].buttons |= 0x0800; \n',
        '        if (mode == 6 && i == 0 && SDL_GetRelativeMouseMode() == SDL_TRUE) {\n'
        '            stick_active = false;\n'
        '        }\n'
        '        if (mode == 6 && i == 0 && SDL_GetRelativeMouseMode() == SDL_FALSE) {\n'
        '            int mx = 0, my = 0;\n'
        '            SDL_GetMouseState(&mx, &my);\n'
        '            const bool mouse_moved = mouse_seen && (mx != last_mouse_x || my != last_mouse_y);\n'
        '            mouse_seen = true;\n'
        '            last_mouse_x = mx;\n'
        '            last_mouse_y = my;\n'
        '            if (mouse_moved) { stick_active = false; }\n'
        '            const int rx = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_RIGHTX);\n'
        '            const int ry = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_RIGHTY);\n'
        '            if (!mouse_moved && (std::abs(rx) > 8000 || std::abs(ry) > 8000)) {\n'
        '                if (!stick_active) {\n'
        '                    stick_x = motes[i].ir_x;\n'
        '                    stick_y = motes[i].ir_y;\n'
        '                }\n'
        '                stick_x = std::clamp(stick_x + rx / 32767.0f * 0.02f * cfg.pointer_speed, 0.0f, 1.0f);\n'
        '                stick_y = std::clamp(stick_y + ry / 32767.0f * 0.02f * cfg.pointer_speed, 0.0f, 1.0f);\n'
        '                stick_active = true;\n'
        '            }\n'
        '            if (stick_active) {\n'
        '                motes[i].ir_x = stick_x;\n'
        '                motes[i].ir_y = stick_y;\n'
        '            }\n'
        '        }\n\n'
        '        if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_A)) motes[i].buttons |= 0x0800; \n')
    source = replace_once(source,
        '        if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_A)) pads[i].buttons |= 0x0100; \n', '')
    source = replace_once(source,
        '        if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_B)) pads[i].buttons |= 0x0200; \n', '')
    source = replace_once(source,
        '        if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_X)) motes[i].buttons |= 0x0002; \n',
        '        if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_X)) { motes[i].buttons |= 0x0100; }\n')
    source = replace_once(source,
        '        if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_Y)) motes[i].buttons |= 0x0001; \n',
        '        if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_Y)) { motes[i].buttons |= 0x1000; }\n')
    source = replace_once(source,
        '        if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_BACK)) motes[i].buttons |= 0x1000;  \n',
        '        if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_BACK)) { motes[i].buttons |= 0x0080; }\n')
    source = replace_once(source,
        '        if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_LEFTSHOULDER)) pads[i].buttons |= 0x0040;  \n',
        '        if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_LEFTSHOULDER)) '
        '{ pads[i].buttons |= 0x0100; }\n')
    source = replace_once(source,
        '        if (SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERRIGHT) > 16384) pads[i].buttons |= 0x0010; \n',
        '        if (SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERLEFT) > 16384) '
        '{ pads[i].buttons |= 0x0200; }\n'
        '        if (SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERRIGHT) > 16384) '
        'pads[i].buttons |= 0x0010; \n')
    return source


def roll(source):
    source = replace_once(source, '#include <algorithm>\n',
        '#include <algorithm>\n#include "stock_desktop_roll.h"\n')
    source = replace_once(source, '    static float pointer_x = 0.5f, pointer_y = 0.5f;',
        '    const bool desktop_motion = nwii::runtime::Config::get().input_mode == 6;\n'
        '    int roll_mouse_pixels = 0;\n'
        '    auto& desktop_roll = openshsm::experiment::primary_desktop_roll();\n'
        '    static float pointer_x = 0.5f, pointer_y = 0.5f;')
    source = replace_once(source,
        '        pointer_x = std::clamp(pointer_x + static_cast<float>(dx) / w, 0.0f, 1.0f);\n'
        '        pointer_y = std::clamp(pointer_y + static_cast<float>(dy) / h, 0.0f, 1.0f);',
        '        if (desktop_motion && (keys[SDL_SCANCODE_LALT] || keys[SDL_SCANCODE_RALT])) {\n'
        '            roll_mouse_pixels = dx;\n'
        '        } else {\n'
        '            pointer_x = std::clamp(pointer_x + static_cast<float>(dx) / w, 0.0f, 1.0f);\n'
        '            pointer_y = std::clamp(pointer_y + static_cast<float>(dy) / h, 0.0f, 1.0f);\n'
        '        }')
    source = replace_once(source, '    if (mouse_state & SDL_BUTTON(SDL_BUTTON_LEFT))',
        '    const auto gravity = desktop_roll.update(SDL_GetTicks(), focused && desktop_motion,\n'
        '        keys[SDL_SCANCODE_Z], keys[SDL_SCANCODE_X], keys[SDL_SCANCODE_R], roll_mouse_pixels);\n'
        '    if (desktop_motion) {\n'
        '        motes[0].accel_x = gravity[0];\n'
        '        motes[0].accel_y = gravity[1];\n'
        '        motes[0].accel_z = gravity[2];\n'
        '    }\n\n'
        '    if (mouse_state & SDL_BUTTON(SDL_BUTTON_LEFT))')
    return source


def controller_motion(source):
    source = replace_once(source, '#include <algorithm>\n',
        '#include <algorithm>\n#include "stock_desktop_roll.h"\n#include "stock_controller_mappings.h"\n')
    source = replace_once(source, '    auto& cfg = nwii::runtime::Config::get();',
        '    openshsm::experiment::register_pc_controller_mappings();\n'
        '    auto& cfg = nwii::runtime::Config::get();')
    source = replace_once(source, '    bool want_pointer = (mode == 3 || mode == 4);',
        '    bool want_pointer = (mode == 3 || mode == 4);\n'
        '    if (mode != 6) { openshsm::experiment::primary_desktop_roll().release_gesture(); }')
    source = replace_once(source, '            if (i == 0) { stick_active = false; }',
        '            if (i == 0) {\n'
        '                stick_active = false;\n'
        '                openshsm::experiment::primary_desktop_roll().release_gesture();\n'
        '            }')
    source = replace_once(source, '        if (want_pointer) {',
        '        const bool turn = mode == 6 && i == 0\n'
        '            && SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_A)\n'
        '            && (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_B)\n'
        '                || SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERRIGHT) > 16384);\n'
        '        if (mode == 6 && i == 0) {\n'
        '            const auto gravity = openshsm::experiment::primary_desktop_roll().analog(\n'
        '                SDL_GetTicks(), SDL_GetKeyboardFocus() != nullptr, turn,\n'
        '                std::clamp(SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTX) / 32767.0f, -1.0f, 1.0f),\n'
        '                std::clamp(SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTY) / 32767.0f, -1.0f, 1.0f));\n'
        '            motes[i].accel_x = gravity[0];\n'
        '            motes[i].accel_y = gravity[1];\n'
        '            motes[i].accel_z = gravity[2];\n'
        '        }\n\n'
        '        if (want_pointer) {')
    source = replace_once(source,
        '        if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_B)) motes[i].buttons |= 0x0400; ',
        '        if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_B)\n'
        '            || SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERRIGHT) > 16384) {\n'
        '            motes[i].buttons |= 0x0400;\n'
        '        }')
    source = replace_once(source,
        '        if (mode == 6 && i == 0 && SDL_GetRelativeMouseMode() == SDL_TRUE) {',
        '        if (mode == 6 && i == 0 && SDL_GetRelativeMouseMode() == SDL_TRUE\n'
        '            && (std::abs(SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_RIGHTX)) > 8000\n'
        '                || std::abs(SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_RIGHTY)) > 8000)) {\n'
        '            SDL_SetRelativeMouseMode(SDL_FALSE);\n'
        '            SDL_ShowCursor(SDL_ENABLE);\n'
        '        }\n'
        '        if (mode == 6 && i == 0 && SDL_GetRelativeMouseMode() == SDL_TRUE) {')
    return source
