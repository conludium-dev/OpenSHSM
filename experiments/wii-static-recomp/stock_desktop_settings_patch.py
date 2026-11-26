"""Extend the existing Config and host with desktop look and display settings."""
from stock_desktop_input_patch import replace_once


def header(text):
    text = replace_once(text, '    void load(const std::string& filepath);\n',
        '    void load(const std::string& filepath);\n'
        '    bool save_display(int width, int height, bool fullscreen);\n')
    text = replace_once(text, '    GameProfile game_profile;\n',
        '    GameProfile game_profile;\n    bool fullscreen = false;\n')
    text = replace_once(text, '    Config() = default;\n',
        '    Config() = default;\n    std::string config_file_path;\n')
    return replace_once(text, '    float pointer_speed = 1.0f;\n',
        '    float pointer_speed = 1.0f;\n\n'
        '    float mouse_look_sensitivity = 1.0f;\n'
        '    float gamepad_look_sensitivity = 1.0f;\n')


def source(text):
    text = replace_once(text, '#include <filesystem>\n', '#include <filesystem>\n#include <cmath>\n#include <fstream>\n'
        '#ifdef _WIN32\n#define NOMINMAX\n#include <windows.h>\n#endif\n')
    text = replace_once(text, 'void Config::load(const std::string& filepath) {\n',
        'void Config::load(const std::string& filepath) {\n    config_file_path = filepath;\n')
    text = replace_once(text, '        if (w) window_width = *w;',
        '        if (w && *w >= 320 && *w <= 8192) { window_width = *w; }')
    text = replace_once(text, '        if (h) window_height = *h;',
        '        if (h && *h >= 240 && *h <= 8192) { window_height = *h; }\n'
        '        const auto fullscreen_value = tbl["graphics"]["fullscreen"].value<bool>();\n'
        '        if (fullscreen_value) { fullscreen = *fullscreen_value; }')
    text = replace_once(text, 'void Config::load_game_profile() {', SAVE_DISPLAY + '\nvoid Config::load_game_profile() {')
    return replace_once(text, '        auto gyro = tbl["input"]["gyro_sensitivity"].value<double>();',
        '        const auto look_sensitivity = [&](const char* name, float& destination) {\n'
        '            const auto value = tbl["input"][name].value<double>();\n'
        '            if (value && std::isfinite(*value) && *value >= 0.05 && *value <= 5.0) {\n'
        '                destination = static_cast<float>(*value);\n'
        '            }\n'
        '        };\n'
        '        look_sensitivity("mouse_look_sensitivity", mouse_look_sensitivity);\n'
        '        look_sensitivity("gamepad_look_sensitivity", gamepad_look_sensitivity);\n\n'
        '        auto gyro = tbl["input"]["gyro_sensitivity"].value<double>();')


def host(text):
    text = '#include "stock_display_settings.h"\n' + text
    text = replace_once(text, '    extern void GX_SetWindow(void *);',
        '    if (nwii::runtime::Config::get().fullscreen) {\n'
        '        openshsm::experiment::set_display_mode(window, true);\n    }\n\n'
        '    extern void GX_SetWindow(void *);')
    text = replace_once(text,
        '          if (e.type == SDL_KEYDOWN && e.key.keysym.scancode == SDL_SCANCODE_F1 && !e.key.repeat) {',
        '          if (e.type == SDL_KEYDOWN && e.key.windowID == SDL_GetWindowID(window) && !e.key.repeat) {\n'
        '            if (e.key.keysym.scancode == SDL_SCANCODE_F2) {\n'
        '              openshsm::experiment::show_display_settings(window);\n'
        '            } else if (e.key.keysym.scancode == SDL_SCANCODE_F11) {\n'
        '              openshsm::experiment::toggle_fullscreen(window);\n'
        '            } else if (e.key.keysym.scancode == SDL_SCANCODE_F3) {\n'
        '              debug_overlay.toggle(g_stat_frames);\n            }\n          }\n'
        '          if (e.type == SDL_KEYDOWN && e.key.windowID == SDL_GetWindowID(window)\n'
        '              && e.key.keysym.scancode == SDL_SCANCODE_F1 && !e.key.repeat) {')
    text = text.replace('Shift/Ctrl/боковая кнопка: бег', 'Shift: бег; пробел/Ctrl: действие C')
    text = text.replace('C/пробел/средняя кнопка: фаер', 'C/средняя кнопка: действие Z')
    text = text.replace('Shift/Ctrl/side button: run', 'Shift: run; Space/Ctrl: C action')
    text = text.replace('C/Space/middle button: flare', 'C/middle button: Z action')
    text = replace_once(text, '                "F10: release/capture mouse; F1: this help\\n"\n',
        '                "F10: release/capture mouse; F1: this help\\n"\n'
        '                "F2: display settings; F11: fullscreen/windowed; F3: FPS\\n"\n'
        '                "Look sensitivity: [input] section in config.toml\\n"\n'
        '                "mouse_look_sensitivity / gamepad_look_sensitivity: 0.05–5, default 1\\n"\n')
    return replace_once(text, '                "F10: отпустить/захватить мышь; F1: эта справка\\n"\n',
        '                "F10: отпустить/захватить мышь; F1: эта справка\\n"\n'
        '                "F2: настройки экрана; F11: полный экран / окно; F3: FPS\\n"\n'
        '                "Чувствительность обзора: config.toml, раздел [input]\\n"\n'
        '                "mouse_look_sensitivity / gamepad_look_sensitivity: 0.05–5, по умолчанию 1\\n"\n')


SAVE_DISPLAY = r'''bool Config::save_display(int width, int height, bool fullscreen_value) {
    if (config_file_path.empty() || width < 320 || width > 8192 || height < 240 || height > 8192) {
        return false;
    }
    try {
        const std::filesystem::path path(config_file_path);
        const std::filesystem::path temporary(config_file_path + ".display.tmp");
        if (std::filesystem::is_symlink(path) || std::filesystem::exists(temporary)) {
            return false;
        }
        toml::table table;
        if (std::filesystem::exists(path)) {
            table = toml::parse_file(config_file_path);
        }
        if (!table.contains("graphics")) {
            table.insert("graphics", toml::table{});
        }
        auto* graphics = table["graphics"].as_table();
        if (!graphics) {
            return false;
        }
        graphics->insert_or_assign("window_width", width);
        graphics->insert_or_assign("window_height", height);
        graphics->insert_or_assign("fullscreen", fullscreen_value);
        {
            std::ofstream file(temporary, std::ios::binary);
            file << table;
            file.flush();
            if (!file) {
                return false;
            }
        }
#ifdef _WIN32
        if (!MoveFileExW(temporary.c_str(), path.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
            return false;
        }
#else
        std::filesystem::rename(temporary, path);
#endif
        window_width = width;
        window_height = height;
        fullscreen = fullscreen_value;
        return true;
    } catch (const std::exception& error) {
        std::cerr << "[Config] Display settings were not saved: " << error.what() << '\n';
        return false;
    }
}
'''
