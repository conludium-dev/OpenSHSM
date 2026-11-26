"""Extend the existing desktop sources and snapshot with independent look input."""
from stock_desktop_input_patch import replace_once


def manager_header(text):
    text = replace_once(text, '#pragma once\n', '#pragma once\n#include "stock_desktop_look.h"\n')
    return replace_once(text, '    InputMode mode = InputMode::GamepadClassic;\n',
        '    InputMode mode = InputMode::GamepadClassic;\n'
        '    openshsm::experiment::DesktopLookSample look{};\n')


def manager(text):
    text = replace_once(text, '#include <algorithm>\n', '#include <algorithm>\n#include "runtime/config.h"\n')
    text = replace_once(text, '            queue.pop_front();\n', '''            if (channel == 0 && nwii::runtime::Config::get().input_mode == 6) {
                const auto& dropped = queue.front();
                auto& next = queue[1];
                const auto& a = dropped.look;
                auto& b = next.look;
                const bool inspection = a.inspection_context != 0
                    && a.inspection_context == b.inspection_context && a.context == 0 && b.context == 0;
                const bool camera = a.inspection_context == 0 && b.inspection_context == 0
                    && a.context != 0 && a.context == b.context && !a.menu_context && !b.menu_context;
                if (dropped.mode == next.mode && dropped.mote.err == 0 && next.mote.err == 0
                    && (camera || inspection) && a.focused && b.focused
                    && !a.suspended && !b.suspended && a.interaction_context == 0 && b.interaction_context == 0
                    && a.qte_context == 0 && b.qte_context == 0
                    && std::isfinite(a.mouse_x) && std::isfinite(a.mouse_y)
                    && std::isfinite(b.mouse_x) && std::isfinite(b.mouse_y)) {
                    b.mouse_x = std::clamp(a.mouse_x + b.mouse_x, -4096.0f, 4096.0f);
                    b.mouse_y = std::clamp(a.mouse_y + b.mouse_y, -4096.0f, 4096.0f);
                }
            }
            queue.pop_front();
''')
    text = replace_once(text, '    for (auto& source : sources) {\n',
        '    auto& desktop_look = openshsm::experiment::primary_desktop_look_input();\n'
        '    desktop_look.begin();\n'
        '    for (auto& source : sources) {\n')
    return replace_once(text,
        '        queue.push_back({gc_pads[channel], wii_motes[channel], update_generation, current_mode});',
        '        queue.push_back({gc_pads[channel], wii_motes[channel], update_generation, current_mode,\n'
        '            channel == 0 ? desktop_look.sample() : openshsm::experiment::DesktopLookSample{}});')


def keyboard(text):
    text = replace_once(text, '    const Uint8 *keys = SDL_GetKeyboardState(NULL);\n',
        '    int key_count = 0;\n'
        '    const Uint8 *keys = SDL_GetKeyboardState(&key_count);\n')
    text = replace_once(text, '#include "stock_desktop_roll.h"\n',
        '#include "stock_desktop_roll.h"\n#include "stock_desktop_look.h"\n')
    text = replace_once(text, '    int roll_mouse_pixels = 0;\n',
        '    int roll_mouse_pixels = 0;\n'
        '    auto& desktop_look = openshsm::experiment::primary_desktop_look_input();\n'
        '    const bool look_suspended = !desktop_motion\n'
        '        || (((mouse_state & SDL_BUTTON(SDL_BUTTON_LEFT)) || keys[SDL_SCANCODE_E])\n'
        '            && ((mouse_state & SDL_BUTTON(SDL_BUTTON_RIGHT)) || keys[SDL_SCANCODE_Q] || keys[SDL_SCANCODE_BACKSPACE]))\n'
        '        || keys[SDL_SCANCODE_LALT] || keys[SDL_SCANCODE_RALT]\n'
        '        || keys[SDL_SCANCODE_Z] || keys[SDL_SCANCODE_X];\n'
        '    desktop_look.mouse(0, 0, focused != nullptr, look_suspended);\n'
        '    if (desktop_motion) {\n'
        '        if (focused && (mouse_state != 0 || std::any_of(keys, keys + std::clamp(key_count, 0, int(SDL_NUM_SCANCODES)),\n'
        '            [](Uint8 key) { return key != 0; }))) {\n'
        '            desktop_look.activity(openshsm::experiment::DesktopInputDevice::KeyboardMouse);\n'
        '        }\n'
        '        desktop_look.buttons(uint8_t((keys[SDL_SCANCODE_UP] ? 1 : 0)\n'
        '            | (keys[SDL_SCANCODE_DOWN] ? 2 : 0)\n'
        '            | (keys[SDL_SCANCODE_LEFT] ? 4 : 0)\n'
        '            | (keys[SDL_SCANCODE_RIGHT] ? 8 : 0)), focused != nullptr);\n'
        '    }\n')
    text = replace_once(text, '    static float pointer_x = 0.5f, pointer_y = 0.5f;\n',
        '    static float pointer_x = 0.5f, pointer_y = 0.5f;\n'
        '    static uint32_t look_context = 0;\n'
        '    const uint32_t next_look_context = desktop_look.sample().context;\n'
        '    if (next_look_context != 0 && next_look_context != look_context) {\n'
        '        pointer_x = pointer_y = 0.5f;\n'
        '    }\n'
        '    look_context = next_look_context;\n')
    text = replace_once(text, '        } else {\n            pointer_x = std::clamp(pointer_x + static_cast<float>(dx) / w, 0.0f, 1.0f);',
        '        } else if (desktop_motion && desktop_look.world() && !look_suspended) {\n'
        '            pointer_x = pointer_y = 0.5f;\n'
        '            desktop_look.mouse(float(dx), float(dy), focused != nullptr, false);\n'
        '        } else {\n            pointer_x = std::clamp(pointer_x + static_cast<float>(dx) / w, 0.0f, 1.0f);')
    text = replace_once(text, '        motes[0].ir_x = pointer_x;\n        motes[0].ir_y = pointer_y;',
        '        motes[0].ir_x = desktop_look.world() && !look_suspended ? 0.5f : pointer_x;\n'
        '        motes[0].ir_y = desktop_look.world() && !look_suspended ? 0.5f : pointer_y;')

    start = text.index('    static bool previous_left_down = false;\n')
    end = text.index('    if (captured) {\n', start)
    text = text[:start] + '    const bool captured = focused && SDL_GetRelativeMouseMode() == SDL_TRUE;\n' + text[end:]
    text = replace_once(text,
        '        motes[0].ir_x = std::clamp(static_cast<float>(mx) / w, 0.0f, 1.0f);\n'
        '        motes[0].ir_y = std::clamp(static_cast<float>(my) / h, 0.0f, 1.0f);',
        '        motes[0].ir_x = desktop_motion && desktop_look.world() && !look_suspended\n'
        '            ? 0.5f : std::clamp(static_cast<float>(mx) / w, 0.0f, 1.0f);\n'
        '        motes[0].ir_y = desktop_motion && desktop_look.world() && !look_suspended\n'
        '            ? 0.5f : std::clamp(static_cast<float>(my) / h, 0.0f, 1.0f);')
    text = replace_once(text, '    desktop_look.mouse(0, 0, focused != nullptr, look_suspended);\n',
        '    desktop_look.mouse(0, 0, focused != nullptr, look_suspended);\n'
        '    if (!focused) {\n'
        '        if (desktop_motion) {\n'
        '            motes[0] = {};\n'
        '            motes[0].err = 0;\n'
        '            motes[0].accel_y = -1.0f;\n'
        '        }\n'
        '        motes[0].ir_x = motes[0].ir_y = -1.0f;\n'
        '        pads[0].err = 0;\n'
        '        openshsm::experiment::primary_desktop_roll().release_gesture();\n'
        '        return;\n'
        '    }\n')
    site = '    static float pointer_x = 0.5f, pointer_y = 0.5f;\n'
    text = replace_once(text, site,
        '    const bool qte = desktop_motion && desktop_look.sample().qte_context != 0;\n' + site)
    for key in ('UP', 'DOWN', 'LEFT', 'RIGHT'):
        site = f'if (keys[SDL_SCANCODE_{key}])'
        if text.count(site) != 2:
            raise ValueError('Keyboard QTE isolation site differs')
        text = text.replace(site, f'if (!qte && keys[SDL_SCANCODE_{key}])')
    text = replace_once(text,
        '    if (keys[SDL_SCANCODE_M]) { motes[0].buttons |= 0x1000; }\n',
        '    if (keys[SDL_SCANCODE_M] || (desktop_motion && (keys[SDL_SCANCODE_TAB] || keys[SDL_SCANCODE_BACKSPACE]))) { motes[0].buttons |= 0x1000; }\n'
        '    if (desktop_motion && desktop_look.world() && !qte && keys[SDL_SCANCODE_G]) {\n'
        '        motes[0].buttons |= 0x0004;\n'
        '    }\n')
    text = replace_once(text,
        '    if (keys[SDL_SCANCODE_SPACE] || keys[SDL_SCANCODE_LSHIFT] || (mouse_state & SDL_BUTTON(SDL_BUTTON_MIDDLE))) { pads[0].buttons |= 0x0100; }\n',
        '    if ((!desktop_motion && keys[SDL_SCANCODE_SPACE]) || keys[SDL_SCANCODE_LSHIFT]\n'
        '        || (desktop_motion && keys[SDL_SCANCODE_C]) || (mouse_state & SDL_BUTTON(SDL_BUTTON_MIDDLE))) { pads[0].buttons |= 0x0100; }\n')
    text = replace_once(text,
        '    if (keys[SDL_SCANCODE_LCTRL] || keys[SDL_SCANCODE_RCTRL] || (mouse_state & SDL_BUTTON(SDL_BUTTON_X1))) { pads[0].buttons |= 0x0200; }\n',
        '    if (keys[SDL_SCANCODE_LCTRL] || keys[SDL_SCANCODE_RCTRL] || (desktop_motion && keys[SDL_SCANCODE_SPACE])\n'
        '        || (mouse_state & SDL_BUTTON(SDL_BUTTON_X1))) { pads[0].buttons |= 0x0200; }\n')
    before = 'keys[SDL_SCANCODE_Q] || keys[SDL_SCANCODE_BACKSPACE]'
    if text.count(before) != 2:
        raise ValueError('Keyboard back/zoom sites differ')
    text = text.replace(before,
        'keys[SDL_SCANCODE_Q] || (!desktop_motion && keys[SDL_SCANCODE_BACKSPACE])')
    text = replace_once(text, '        SDL_GetRelativeMouseState(&dx, &dy);\n',
        '        SDL_GetRelativeMouseState(&dx, &dy);\n'
        '        if (desktop_motion && (dx != 0 || dy != 0)) {\n'
        '            desktop_look.activity(openshsm::experiment::DesktopInputDevice::KeyboardMouse);\n'
        '        }\n')
    text = text.replace('desktop_look.world()', 'desktop_look.direct()')
    text = replace_once(text,
        '} else if (desktop_motion && desktop_look.direct() && !look_suspended) {',
        '} else if (desktop_motion && (desktop_look.direct() || desktop_look.sample().inspection_context != 0) && !look_suspended) {')
    return text.replace('desktop_look.direct() && !qte && keys[SDL_SCANCODE_G]',
        'desktop_look.world() && !qte && keys[SDL_SCANCODE_G]')



def gamepad(text):
    text = replace_once(text, '#include "stock_desktop_roll.h"\n',
        '#include "stock_desktop_roll.h"\n#include "stock_desktop_look.h"\n')
    text = replace_once(text, '    static bool mouse_seen = false, stick_active = false;\n',
        '    static bool mouse_seen = false, stick_active = false;\n'
        '    static uint32_t look_context = 0;\n'
        '    static bool previous_world_look = false;\n')
    text = replace_once(text, '        if (mode == 6 && i == 0) {\n            const auto gravity',
        '        auto& desktop_look = openshsm::experiment::primary_desktop_look_input();\n'
        '        const bool world_look = mode == 6 && i == 0 && desktop_look.direct()\n'
        '            && !desktop_look.sample().suspended && !turn;\n'
        '        if (mode == 6 && i == 0) {\n'
        '            bool device_active = false;\n'
        '            for (int button = 0; button < SDL_CONTROLLER_BUTTON_MAX; ++button) {\n'
        '                device_active |= SDL_GameControllerGetButton(controller, SDL_GameControllerButton(button)) != 0;\n'
        '            }\n'
        '            for (int axis = 0; axis < SDL_CONTROLLER_AXIS_MAX; ++axis) {\n'
        '                device_active |= std::abs(int(SDL_GameControllerGetAxis(controller, SDL_GameControllerAxis(axis)))) > 6553;\n'
        '            }\n'
        '            if (device_active && SDL_GetKeyboardFocus() != nullptr) {\n'
        '                desktop_look.activity(openshsm::experiment::DesktopInputDevice::Gamepad);\n'
        '            }\n'
        '            desktop_look.buttons(uint8_t(\n'
        '                (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_A) ? 1 : 0)\n'
        '                | (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_Y) ? 2 : 0)\n'
        '                | (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_X) ? 4 : 0)\n'
        '                | (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_B) ? 8 : 0)),\n'
        '                SDL_GetKeyboardFocus() != nullptr, id);\n'
        '            const uint32_t next_context = desktop_look.sample().context;\n'
        '            const bool changed = next_context != 0 && next_context != look_context;\n'
        '            if (changed || world_look) {\n'
        '                stick_active = false;\n'
        '                mouse_seen = false;\n'
        '            }\n'
        '            if (world_look || (turn && (previous_world_look || changed))) {\n'
        '                motes[i].ir_x = motes[i].ir_y = 0.5f;\n'
        '            }\n'
        '            previous_world_look = world_look;\n'
        '            look_context = next_context;\n'
        '            desktop_look.stick(\n'
        '                SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_RIGHTX) / 32767.0f,\n'
        '                SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_RIGHTY) / 32767.0f,\n'
        '                SDL_GetKeyboardFocus() != nullptr, turn);\n'
        '        }\n'
        '        if (mode == 6 && i == 0) {\n            const auto gravity')
    text = replace_once(text,
        '        if (mode == 6 && i == 0 && SDL_GetRelativeMouseMode() == SDL_TRUE\n',
        '        if (mode == 6 && i == 0 && !world_look && SDL_GetRelativeMouseMode() == SDL_TRUE\n')
    text = replace_once(text,
        '        if (mode == 6 && i == 0 && SDL_GetRelativeMouseMode() == SDL_FALSE) {',
        '        if (mode == 6 && i == 0 && !world_look && SDL_GetRelativeMouseMode() == SDL_FALSE) {')

    start = text.index('        if (mode == 6 && i == 0 && !world_look && SDL_GetRelativeMouseMode() == SDL_TRUE\n')
    end = text.index('            int mx = 0, my = 0;\n', start)
    text = text[:start] + '        if (mode == 6 && i == 0 && !world_look) {\n' + text[end:]
    text = replace_once(text, '    int mode = cfg.input_mode;\n',
        '    int mode = cfg.input_mode;\n'
        '    if (mode == 6 && !SDL_GetKeyboardFocus()) {\n'
        '        openshsm::experiment::primary_desktop_roll().release_gesture();\n'
        '        return;\n'
        '    }\n')
    text = replace_once(text,
        '            const bool mouse_moved = mouse_seen && (mx != last_mouse_x || my != last_mouse_y);\n',
        '            const bool mouse_moved = SDL_GetRelativeMouseMode() == SDL_FALSE\n'
        '                && mouse_seen && (mx != last_mouse_x || my != last_mouse_y);\n')
    text = replace_once(text, '            if (mouse_moved) { stick_active = false; }\n',
        '            if (mouse_moved) {\n'
        '                stick_active = false;\n'
        '                desktop_look.activity(openshsm::experiment::DesktopInputDevice::KeyboardMouse);\n'
        '            }\n')
    return ps2_button_positions(qte_gamepad(interaction_gamepad(text)))


def ps2_button_positions(text):
    text = replace_once(text, '            motes[i].buttons |= interaction ? 0x1000 : 0x0400;',
        '            motes[i].buttons |= mode == 6 ? 0x1000 : 0x0400;')
    for button, before, after in (('X', '0x0100', '0x0010'), ('Y', '0x1000', '0x0100')):
        text = replace_once(text,
            f'        if (!qte && SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_{button})) {{\n'
            f'            motes[i].buttons |= {before};\n        }}',
            f'        if (!qte && SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_{button})) {{\n'
            f'            motes[i].buttons |= mode == 6 ? {after} : {before};\n        }}')
    text = replace_once(text,
        '        if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_RIGHTSHOULDER)) motes[i].buttons |= 0x0010;',
        '        if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_RIGHTSHOULDER)) {\n'
        '            motes[i].buttons |= mode == 6 ? (!qte && world_look && !desktop_look.pov() ? 0x0004 : 0) : 0x0010;\n'
        '        }')
    text = replace_once(text,
        '        const bool turn = mode == 6 && i == 0 && !qte\n'
        '            && SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_A)\n'
        '            && (interaction || SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_B)\n'
        '                || SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERRIGHT) > 16384);',
        '        const bool turn = mode == 6 && i == 0 && !qte && interaction\n'
        '            && SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_A)\n'
        '            && !SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_B);')
    return text


def qte_gamepad(text):
    site = '        const bool interaction = mode == 6 && i == 0 && desktop_look.interaction();\n'
    text = replace_once(text, site,
        '        const bool qte = mode == 6 && i == 0 && desktop_look.sample().qte_context != 0;\n' + site)
    text = replace_once(text, '        const bool turn = mode == 6 && i == 0\n',
        '        const bool turn = mode == 6 && i == 0 && !qte\n')
    for button, mask in (('A', '0x0800'), ('X', '0x0100'), ('Y', '0x1000')):
        site = f'if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_{button}))'
        if button == 'A':
            text = replace_once(text, site + f' motes[i].buttons |= {mask};',
                f'if (!qte && SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_{button})) {{\n'
                f'            motes[i].buttons |= {mask};\n        }}')
        else:
            text = replace_once(text, site + f' {{ motes[i].buttons |= {mask}; }}',
                f'if (!qte && SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_{button})) {{\n'
                f'            motes[i].buttons |= {mask};\n        }}')
    text = replace_once(text,
        '        if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_B)) {',
        '        if (!qte && SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_B)) {')
    text = replace_once(text,
        '        if (SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERRIGHT) > 16384) {',
        '        if (!qte && SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERRIGHT) > 16384) {')
    for button, mask in (('X', '0x0400'), ('Y', '0x0800')):
        text = replace_once(text,
            f'if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_{button})) pads[i].buttons |= {mask};',
            f'if (!qte && SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_{button})) {{\n'
            f'            pads[i].buttons |= {mask};\n        }}')
    return text


def interaction_gamepad(text):
    text = replace_once(text, '    static bool previous_world_look = false;\n',
        '    static bool previous_world_look = false;\n'
        '    static uint32_t interaction_context = 0, pointer_ticks = 0;\n')
    before = '''        const bool turn = mode == 6 && i == 0
            && SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_A)
            && (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_B)
                || SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERRIGHT) > 16384);
        auto& desktop_look = openshsm::experiment::primary_desktop_look_input();
'''
    after = '''        auto& desktop_look = openshsm::experiment::primary_desktop_look_input();
        const bool interaction = mode == 6 && i == 0 && desktop_look.interaction();
        const bool twisting = interaction && openshsm::experiment::primary_desktop_roll().twist_context();
        const bool turn = mode == 6 && i == 0
            && SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_A)
            && (interaction || SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_B)
                || SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERRIGHT) > 16384);
        float pointer_seconds = 0;
        if (mode == 6 && i == 0) {
            const uint32_t next_interaction = desktop_look.sample().interaction_context;
            const uint32_t now = SDL_GetTicks();
            if (next_interaction != interaction_context && (next_interaction == 0 || interaction_context == 0)) {
                stick_active = false;
                mouse_seen = false;
            } else if (interaction) {
                pointer_seconds = std::min(uint32_t(now - pointer_ticks), uint32_t(100)) * 0.001f;
            }
            interaction_context = next_interaction;
            pointer_ticks = now;
        }
'''
    text = replace_once(text, before, after)
    text = replace_once(text,
        '            const int rx = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_RIGHTX);\n'
        '            const int ry = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_RIGHTY);\n',
        '            const int rx = SDL_GameControllerGetAxis(controller, interaction ? SDL_CONTROLLER_AXIS_LEFTX : SDL_CONTROLLER_AXIS_RIGHTX);\n'
        '            const int ry = SDL_GameControllerGetAxis(controller, interaction ? SDL_CONTROLLER_AXIS_LEFTY : SDL_CONTROLLER_AXIS_RIGHTY);\n')
    text = replace_once(text,
        '            if (!mouse_moved && (std::abs(rx) > 8000 || std::abs(ry) > 8000)) {',
        '            if (!mouse_moved && !(twisting && turn) && (std::abs(rx) > 8000 || std::abs(ry) > 8000)) {')
    for axis, raw in (('x', 'rx'), ('y', 'ry')):
        text = replace_once(text,
            f'                stick_{axis} = std::clamp(stick_{axis} + {raw} / 32767.0f * 0.02f * cfg.pointer_speed, 0.0f, 1.0f);',
            f'                stick_{axis} = std::clamp(stick_{axis} + {raw} / 32767.0f\n'
            f'                    * (interaction ? pointer_seconds * (turn ? 0.45f : 1.2f) : 0.02f) * cfg.pointer_speed, 0.0f, 1.0f);')
    text = replace_once(text, '        int lx = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTX);\n',
        '        if (mode == 6 && i == 0 && !qte && !interaction && desktop_look.sample().menu_context\n'
        '            && desktop_look.sample().device == openshsm::experiment::DesktopInputDevice::Gamepad) {\n'
        '            const int menu_x = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTX);\n'
        '            const int menu_y = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTY);\n'
        '            if (menu_x < -16000) { motes[i].buttons |= 0x0001; }\n'
        '            if (menu_x > 16000) { motes[i].buttons |= 0x0002; }\n'
        '            if (menu_y < -16000) { motes[i].buttons |= 0x0008; }\n'
        '            if (menu_y > 16000) { motes[i].buttons |= 0x0004; }\n'
        '            motes[i].ir_x = motes[i].ir_y = -1.0f;\n'
        '        }\n\n'
        '        int lx = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTX);\n')
    return replace_once(text,
        '        if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_B)\n'
        '            || SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERRIGHT) > 16384) {\n'
        '            motes[i].buttons |= 0x0400;\n        }',
        '        if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_B)) {\n'
        '            motes[i].buttons |= interaction ? 0x1000 : 0x0400;\n        }\n'
        '        if (SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERRIGHT) > 16384) {\n'
        '            motes[i].buttons |= 0x0400;\n        }')
