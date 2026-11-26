"""Adapt existing desktop input help and host-loop pacing."""


def adapt(source):
    before = '          if (e.type == SDL_QUIT) quit = true;\n'
    after = (
        '          if (e.type == SDL_QUIT) quit = true;\n'
        '          if (e.type == SDL_KEYDOWN && e.key.windowID == SDL_GetWindowID(window)\n'
        '              && e.key.keysym.scancode == SDL_SCANCODE_F10 && !e.key.repeat) {\n'
        '            mouse_released = !mouse_released;\n'
        '          }\n'
        '          if (e.type == SDL_KEYDOWN && e.key.keysym.scancode == SDL_SCANCODE_F1 && !e.key.repeat) {\n'
        '            SDL_SetRelativeMouseMode(SDL_FALSE);\n'
        '            SDL_ShowCursor(SDL_ENABLE);\n'
        '            SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_INFORMATION,\n'
        '              openshsm::experiment::ui_text("OpenSHSM — controls", "OpenSHSM — управление"),\n'
        '              openshsm::experiment::ui_text(\n'
        '                "Mouse capture follows window focus; LMB/E: action\\n"\n'
        '                "Mouse/right stick: look; menus and items: pointer\\n"\n'
        '                "Right mouse button/Q: zoom\\n"\n'
        '                "F10: release/capture mouse; F1: this help\\n"\n'
        '                "Item: hold LMB/E; Alt+mouse/Z/X: rotate; R: reset\\n"\n'
        '                "WASD: move; Shift/Ctrl/side button: run\\n"\n'
        '                "C/Space/middle button: flare; G: look back\\n"\n'
        '                "Tab/M: phone; Backspace: phone/back; F: flashlight\\n"\n'
        '                "Enter/Escape: pause; 2: delete; H: Home; arrows: navigate\\n"\n'
        '                "Gamepad: bottom button — action; right — phone/back\\n"\n'
        '                "Left button — flashlight; top — delete\\n"\n'
        '                "QTE: Cross=up/A, Triangle=down/Y, Square=left/X, Circle=right/B\\n"\n'
        '                "LT: run; RT: zoom; RB: look back; LB: flare\\n"\n'
        '                "Item: hold bottom button and move left stick; knob: circle the stick",\n'
        '                "Захват мыши автоматически по фокусу окна; ЛКМ/E: действие\\n"\n'
        '                "Мышь/правый стик: обзор; меню и предметы: указатель\\n"\n'
        '                "Правая кнопка мыши/Q: приближение\\n"\n'
        '                "F10: отпустить/захватить мышь; F1: эта справка\\n"\n'
        '                "Предмет: держать ЛКМ/E; Alt+мышь/Z/X: вращать; R: прямо\\n"\n'
        '                "WASD: движение; Shift/Ctrl/боковая кнопка: бег\\n"\n'
        '                "C/пробел/средняя кнопка: фаер; G: взгляд назад\\n"\n'
        '                "Tab/M: телефон; Backspace: телефон/назад; F: фонарь\\n"\n'
        '                "Enter/Escape: пауза; 2: удалить; H: Home; стрелки: навигация\\n"\n'
        '                "Геймпад: нижняя кнопка — действие; правая — телефон/назад\\n"\n'
        '                "Левая кнопка — фонарь; верхняя — удалить\\n"\n'
        '                "QTE: крест=вверх/A, треугольник=вниз/Y, квадрат=влево/X, круг=вправо/B\\n"\n'
        '                "LT: бег; RT: приближение; RB: взгляд назад; LB: фаер\\n"\n'
        '                "Предмет: держать нижнюю кнопку, двигать левым стиком; ручка — круг стиком"), window);\n'
        '          }\n'
    )
    if source.count(before) != 1:
        raise ValueError('Host SDL event site differs')
    source = source.replace(before, after, 1)
    site = '        SDL_GL_SwapWindow(window);\n'
    if source.count(site) != 1:
        raise ValueError('Host QTE presentation boundary differs')
    source = source.replace(site, site + '        host_presented = true;\n        debug_overlay.did_present();\n', 1)
    source = source.replace('#include <SDL.h>', '#include <SDL.h>\n#include "stock_controller_mappings.h"\n#include "stock_host_pacing.h"\n#include "stock_ui_locale.h"', 1)
    site = '    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);'
    if source.count(site) != 1:
        raise ValueError('Host SDL initialization site differs')
    source = source.replace(site,
        '    if (!openshsm::experiment::fallback_pc_controller_backend()) { return 1; }\n\n' + site, 1)
    site = '    while (!quit && ctx->is_running) {\n      host_phases.begin(g_stat_frames);'
    if source.count(site) != 1:
        raise ValueError('Windowed host loop boundary differs')
    source = source.replace(site,
        '    auto next_input_sample = std::chrono::steady_clock::time_point::min();\n'
        '    bool mouse_released = false;\n'
        '    bool mouse_had_focus = false;\n'
        '    while (!quit && ctx->is_running) {\n'
        '      const auto host_tick_started = std::chrono::steady_clock::now();\n'
        '      bool host_presented = false;\n'
        '      host_phases.begin(g_stat_frames);', 1)
    site = '      if (trace_startup) { startup_trace("poll end/input begin"); }'
    if source.count(site) != 1:
        raise ValueError('Host input focus boundary differs')
    source = source.replace(site,
        '      if (!headless) {\n'
        '        const Uint32 flags = SDL_GetWindowFlags(window);\n'
        '        const bool mouse_focused = SDL_GetKeyboardFocus() == window\n'
        '            && (flags & SDL_WINDOW_INPUT_FOCUS) != 0\n'
        '            && (flags & (SDL_WINDOW_MINIMIZED | SDL_WINDOW_HIDDEN)) == 0;\n'
        '        if (mouse_focused && !mouse_had_focus) {\n'
        '          mouse_released = false;\n'
        '        }\n'
        '        mouse_had_focus = mouse_focused;\n'
        '        const bool want_capture = !quit && mouse_focused && !mouse_released\n'
        '            && nwii::runtime::Config::get().input_mode == 6;\n'
        '        if (want_capture != (SDL_GetRelativeMouseMode() == SDL_TRUE)) {\n'
        '          if (SDL_SetRelativeMouseMode(want_capture ? SDL_TRUE : SDL_FALSE) != 0) {\n'
        '            SDL_Log("OpenSHSM mouse capture failed: %s", SDL_GetError());\n'
        '          }\n'
        '          int discarded_x = 0, discarded_y = 0;\n'
        '          SDL_GetRelativeMouseState(&discarded_x, &discarded_y);\n'
        '        }\n'
        '        SDL_ShowCursor(SDL_GetRelativeMouseMode() == SDL_TRUE ? SDL_DISABLE : SDL_ENABLE);\n'
        '      }\n\n' + site, 1)
    site = ('      if (trace_startup) { startup_trace("poll end/input begin"); }\n'
        '      nwii::runtime::input::InputManager::get().update();')
    if source.count(site) != 1:
        raise ValueError('Host input sampling site differs')
    source = source.replace(site,
        '      if (trace_startup) { startup_trace("poll end/input begin"); }\n'
        '      if (headless || host_tick_started >= next_input_sample) {\n'
        '          nwii::runtime::input::InputManager::get().update();\n'
        '          next_input_sample = openshsm::experiment::host_sleep_deadline(\n'
        '              host_tick_started, true, false);\n'
        '      }', 1)
    site = '      host_phases.mark(7);\n      std::this_thread::sleep_for(std::chrono::milliseconds(16));'
    if source.count(site) != 1:
        raise ValueError('Windowed host sleep boundary differs')
    return source.replace(site,
        '      host_phases.mark(7);\n'
        '      std::this_thread::sleep_until(openshsm::experiment::host_sleep_deadline(\n'
        '          host_tick_started, host_presented, headless));', 1)
