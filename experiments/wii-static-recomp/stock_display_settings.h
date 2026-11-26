#pragma once
#include <SDL.h>
#include <runtime/config.h>
#include <string>

namespace openshsm::experiment {

inline bool set_display_mode(SDL_Window* window, bool fullscreen) {
    if (SDL_SetWindowFullscreen(window, fullscreen ? SDL_WINDOW_FULLSCREEN_DESKTOP : 0) != 0) {
        SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "OpenSHSM", SDL_GetError(), window);
        return false;
    }
    auto& config = nwii::runtime::Config::get();
    config.fullscreen = fullscreen;
    if (!fullscreen) {
        SDL_SetWindowSize(window, config.window_width, config.window_height);
        SDL_SetWindowPosition(window, SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED);
    }
    return true;
}

inline void save_display_settings(SDL_Window* window) {
    auto& config = nwii::runtime::Config::get();
    if (!config.save_display(config.window_width, config.window_height, config.fullscreen)) {
        SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_WARNING, "OpenSHSM",
            "Настройки применены, но сохранить config.toml не удалось.", window);
    }
}

inline void toggle_fullscreen(SDL_Window* window) {
    SDL_SetRelativeMouseMode(SDL_FALSE);
    SDL_ShowCursor(SDL_ENABLE);
    const bool fullscreen = (SDL_GetWindowFlags(window) & SDL_WINDOW_FULLSCREEN) != 0;
    if (set_display_mode(window, !fullscreen)) {
        save_display_settings(window);
    }
}

inline void show_display_settings(SDL_Window* window) {
    SDL_SetRelativeMouseMode(SDL_FALSE);
    SDL_ShowCursor(SDL_ENABLE);
    const SDL_MessageBoxButtonData buttons[] = {
        {SDL_MESSAGEBOX_BUTTON_ESCAPEKEY_DEFAULT, 0, "Закрыть"},
        {0, 1, "960 × 540"}, {0, 2, "1280 × 720"}, {0, 3, "1600 × 900"},
        {0, 4, "1920 × 1080"}, {0, 5, "2560 × 1440"}, {0, 6, "Оконный режим"},
        {0, 7, "Полный экран"}};
    SDL_MessageBoxData box{};
    box.flags = SDL_MESSAGEBOX_INFORMATION;
    box.window = window;
    box.title = "OpenSHSM — экран";
    box.message = "Разрешение окна. Полный экран использует разрешение рабочего стола.\n"
        "Режим можно переключать клавишей F11.";
    box.numbuttons = int(sizeof(buttons) / sizeof(buttons[0]));
    box.buttons = buttons;
    int selected = 0;
    if (SDL_ShowMessageBox(&box, &selected) != 0 || selected <= 0 || selected > 7) {
        return;
    }
    auto& config = nwii::runtime::Config::get();
    if (selected <= 5) {
        constexpr int sizes[][2] = {{960, 540}, {1280, 720}, {1600, 900}, {1920, 1080}, {2560, 1440}};
        if (!set_display_mode(window, false)) {
            return;
        }
        config.window_width = sizes[selected - 1][0];
        config.window_height = sizes[selected - 1][1];
        SDL_SetWindowSize(window, config.window_width, config.window_height);
        SDL_SetWindowPosition(window, SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED);
    } else if (!set_display_mode(window, selected == 7)) {
        return;
    }
    save_display_settings(window);
}

}
