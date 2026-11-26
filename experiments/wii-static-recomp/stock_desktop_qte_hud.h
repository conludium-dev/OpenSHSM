#pragma once
#include "stock_debug_font.h"
#include "stock_desktop_qte.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <string>

namespace openshsm::experiment {

inline constexpr int desktop_hud_width = debug_font_width;
inline constexpr int desktop_hud_height = debug_font_height + 36;
inline constexpr int desktop_button_size = 32;

inline std::vector<uint8_t> desktop_hud_pixels(const char* icon_directory = nullptr) {
    std::vector<uint8_t> pixels(size_t(desktop_hud_width) * desktop_hud_height * 4, 0);
    const auto font = debug_font_pixels();
    for (size_t i = 0; i < font.size(); ++i) {
        pixels[i * 4] = pixels[i * 4 + 1] = pixels[i * 4 + 2] = 255;
        pixels[i * 4 + 3] = font[i];
    }
    std::array<std::array<uint8_t, 4096>, 4> icons{};
    bool original = icon_directory != nullptr && icon_directory[0] != '\0';
    constexpr const char* names[] = {"UI_GestureCross.rgba", "UI_GestureTriangle.rgba",
        "UI_GestureSquare.rgba", "UI_GestureCircle.rgba"};
    if (original) {
        for (unsigned i = 0; i < 4; ++i) {
            const auto path = std::filesystem::path(icon_directory) / names[i];
            std::error_code error;
            if (!std::filesystem::is_regular_file(path, error)
                || std::filesystem::file_size(path, error) != icons[i].size() || error) {
                original = false;
                break;
            }
            std::ifstream input(path, std::ios::binary);
            input.read(reinterpret_cast<char*>(icons[i].data()), icons[i].size());
            if (input.gcount() != std::streamsize(icons[i].size()) || input.peek() != EOF) {
                original = false;
                break;
            }
        }
    }
    const uint8_t colors[4][3] = {{115, 160, 255}, {90, 225, 170}, {220, 125, 210}, {255, 135, 145}};
    for (unsigned i = 0; i < 4; ++i) {
        for (int y = 0; y < desktop_button_size; ++y) {
            for (int x = 0; x < desktop_button_size; ++x) {
                const size_t source = size_t(y * desktop_button_size + x) * 4;
                const size_t destination = size_t((debug_font_height + 2 + y) * desktop_hud_width
                    + 2 + int(i) * 34 + x) * 4;
                if (original) {
                    std::copy_n(icons[i].data() + source, 4, pixels.data() + destination);
                    continue;
                }
                const float dx = x - 15.5f, dy = y - 15.5f;
                const float radius = std::hypot(dx, dy);
                bool shape = false;
                if (i == 0) {
                    shape = std::abs(dx) <= 8 && std::abs(dy) <= 8
                        && (std::abs(dx - dy) <= 1.5f || std::abs(dx + dy) <= 1.5f);
                } else if (i == 1) {
                    shape = (std::abs(dy - 7) <= 1.2f && std::abs(dx) <= 9)
                        || (dy >= -10 && dy <= 8 && std::abs(std::abs(dx) - (dy + 10) * 0.5f) <= 1.2f);
                } else if (i == 2) {
                    shape = std::max(std::abs(dx), std::abs(dy)) >= 7
                        && std::max(std::abs(dx), std::abs(dy)) <= 9;
                } else {
                    shape = radius >= 7 && radius <= 9;
                }
                const bool disc = radius <= 14.5f;
                for (unsigned c = 0; c < 3; ++c) {
                    pixels[destination + c] = shape ? colors[i][c] : 24;
                }
                pixels[destination + 3] = disc ? 255 : 0;
            }
        }
    }
    return pixels;
}

struct DesktopHUDPanel {
    int x = 0, y = 0, width = 0, height = 0;
};

inline void desktop_hud_quad(std::vector<float>& points, int width, int height,
    float x, float y, float w, float h, float u, float v, float uw, float vh) {
    const float x0 = 2 * x / width - 1, y0 = 1 - 2 * y / height;
    const float x1 = x0 + 2 * w / width, y1 = y0 - 2 * h / height;
    const float u0 = u / desktop_hud_width, v0 = v / desktop_hud_height;
    const float u1 = u0 + uw / desktop_hud_width, v1 = v0 + vh / desktop_hud_height;
    const float quad[] = {x0,y0,u0,v0, x0,y1,u0,v1, x1,y1,u1,v1,
        x0,y0,u0,v0, x1,y1,u1,v1, x1,y0,u1,v0};
    points.insert(points.end(), std::begin(quad), std::end(quad));
}

inline void desktop_hud_text(std::vector<float>& points, int width, int height,
    int x, int y, int scale, const char* text) {
    for (unsigned column = 0; text[column]; ++column) {
        const unsigned glyph = static_cast<unsigned char>(text[column]) - 32u;
        if (glyph < 95) {
            desktop_hud_quad(points, width, height, float(x + column * debug_font_advance * scale), float(y),
                float(debug_font_cell_width * scale), float(debug_font_cell_height * scale),
                float((glyph % 16) * debug_font_cell_width), float((glyph / 16) * debug_font_cell_height),
                float(debug_font_cell_width), float(debug_font_cell_height));
        }
    }
}

inline DesktopHUDPanel desktop_qte_hud(std::vector<float>& points, int width, int height,
    DesktopQTEPrompt prompt) {
    if (width < 200 || height < 180 || width > 16384 || height > 16384
        || prompt.context == 0 || prompt.target >= 4) {
        return {};
    }
    const int scale = std::min({std::max(1, width / 960), 3, height / 180});
    const int panel_width = 140 * scale, panel_height = 134 * scale;
    DesktopHUDPanel panel{(width - panel_width) / 2, height - panel_height - 24 * scale,
        panel_width, panel_height};
    const char* title = "BREAK FREE";
    const char* action = prompt.blocked ? "WAIT" : "PRESS";
    desktop_hud_text(points, width, height, panel.x + 15 * scale, panel.y + 4 * scale, scale, title);
    desktop_hud_quad(points, width, height, float(panel.x + 38 * scale), float(panel.y + 33 * scale),
        float(64 * scale), float(64 * scale), float(2 + prompt.target * 34), float(debug_font_height + 2),
        float(desktop_button_size), float(desktop_button_size));
    desktop_hud_text(points, width, height,
        panel.x + (140 - int(std::char_traits<char>::length(action)) * debug_font_advance) * scale / 2,
        panel.y + 101 * scale, scale, action);
    return panel;
}

}
