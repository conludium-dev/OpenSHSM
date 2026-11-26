#pragma once
#include "stock_desktop_qte_hud.h"
#include "stock_desktop_look.h"
#include <glad/glad.h>
#include <SDL.h>
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

namespace openshsm::experiment {

inline const char* debug_glyph(char c) {
    static const char* alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ.:/-";
    static const char* rows[] = {
        "0E11131519110E", "040C040404040E", "0E11010204081F", "1E01010601111E",
        "02060A121F0202", "1F101E0101110E", "06101E1111110E", "1F010204080808",
        "0E11110E11110E", "0E11110F01020C", "0E11111F111111", "1E11111E11111E",
        "0E11101010110E", "1E11111111111E", "1F10101E10101F", "1F10101E101010",
        "0E11101711110F", "1111111F111111", "0E04040404040E", "0702020212120C",
        "11121418141211", "1010101010101F", "111B1515111111", "11191513111111",
        "0E11111111110E", "1E11111E101010", "0E11111115120D", "1E11111E141211",
        "0F10100E01011E", "1F040404040404", "1111111111110E", "11111111110A04",
        "11111115151B11", "11110A040A1111", "11110A04040404", "1F01020408101F",
        "00000000000C0C", "000C0C000C0C00", "01020204080810", "0000001F000000"
    };
    const char* match = std::strchr(alphabet, c);
    return match ? rows[match - alphabet] : "00000000000000";
}

class DebugOverlay {
public:
    DebugOverlay() : enabled(std::getenv("NWII_DEBUG_OVERLAY") != nullptr) {}

    void toggle(uint64_t gx_frames) {
        enabled = !enabled;
        epoch = std::chrono::steady_clock::now();
        previous_gx = gx_frames;
        present_count = empty = pulls = supplied_frames = short_pulls = errors = 0;
        min_queue = UINT32_MAX;
    }

    void callback_audio(uint64_t calls, uint64_t supplied, uint64_t shorts, uint64_t failed) {
        pulls += calls - callback_calls;
        supplied_frames += supplied - callback_supplied;
        short_pulls += shorts - callback_shorts;
        errors += failed - callback_errors;
        callback_calls = calls;
        callback_supplied = supplied;
        callback_shorts = shorts;
        callback_errors = failed;
    }

    void audio(uint32_t queued, size_t supplied, bool pulled, bool failed) {
        if (!enabled) {
            return;
        }
        min_queue = std::min(min_queue, queued);
        empty += queued == 0;
        if (pulled) {
            ++pulls;
            short_pulls += supplied < 1024;
            supplied_frames += supplied;
        }
        errors += failed;
    }

    void draw(int width, int height, uint64_t gx_frames) {
        pending_prompt = 0;
        const uint32_t prompt_time = desktop_look_time_ms();
        const auto prompt = primary_desktop_qte_prompt().read(prompt_time);
        if ((!enabled && prompt.context == 0) || width <= 0 || height <= 0 || render_failed) {
            return;
        }
        if (enabled) {
            ++present_count;
            const auto now = std::chrono::steady_clock::now();
            const double seconds = std::chrono::duration<double>(now - epoch).count();
            if (seconds >= 1.0) {
                present_fps = present_count / seconds;
                gx_fps = (gx_frames - previous_gx) / seconds;
                queue_ms = min_queue == UINT32_MAX ? 0.0 : min_queue / 128.0;
                short_count = short_pulls;
                std::cout << "[AVDebug] seconds=" << seconds << " present=" << present_count
                          << " gx=" << gx_frames - previous_gx << " queueMinBytes=" << min_queue
                          << " empty=" << empty << " pulls=" << pulls << " suppliedFrames=" << supplied_frames
                          << " short=" << short_pulls << " errors=" << errors << '\n';
                present_count = empty = pulls = supplied_frames = short_pulls = errors = 0;
                min_queue = UINT32_MAX;
                previous_gx = gx_frames;
                epoch = now;
            }
        }
        if (!program && !initialize()) {
            render_failed = true;
            std::cerr << "[AVDebug] overlay shader initialization failed\n";
            return;
        }
        char line1[80], line2[80], line3[80];
        std::snprintf(line1, sizeof(line1), "GX FPS %.1F   OUTPUT FPS %.1F", gx_fps, present_fps);
        if (gx_fps > 0.0) {
            std::snprintf(line2, sizeof(line2), "GX FRAME %.1F MS", 1000.0 / gx_fps);
        } else {
            std::snprintf(line2, sizeof(line2), "GX FRAME -- MS");
        }
        std::snprintf(line3, sizeof(line3), "AUDIO CALLBACK SHORT %llu",
            static_cast<unsigned long long>(short_count));
        const int scale = std::max(1, width / 960);
        std::vector<float> points;
        size_t longest = 0;
        if (enabled) {
            for (unsigned line = 0; line < 3; ++line) {
                const char* text = line == 0 ? line1 : (line == 1 ? line2 : line3);
                longest = std::max(longest, std::strlen(text));
                desktop_hud_text(points, width, height, 8, 8 + line * debug_font_cell_height * scale, scale, text);
            }
        }
        const auto qte_panel = desktop_qte_hud(points, width, height, prompt);
        if (points.empty()) {
            return;
        }
        GLint old_program, old_vao, old_buffer, old_draw, viewport[4], scissor[4];
        GLfloat clear[4];
        GLint old_active, old_texture, old_sampler, blend_src_rgb, blend_dst_rgb, blend_src_alpha,
            blend_dst_alpha, blend_equation_rgb, blend_equation_alpha, polygon[2];
        GLboolean mask[4];
        glGetIntegerv(GL_CURRENT_PROGRAM, &old_program);
        glGetIntegerv(GL_VERTEX_ARRAY_BINDING, &old_vao);
        glGetIntegerv(GL_ARRAY_BUFFER_BINDING, &old_buffer);
        glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &old_draw);
        glGetIntegerv(GL_VIEWPORT, viewport);
        glGetIntegerv(GL_SCISSOR_BOX, scissor);
        glGetFloatv(GL_COLOR_CLEAR_VALUE, clear);
        glGetIntegerv(GL_ACTIVE_TEXTURE, &old_active);
        glActiveTexture(GL_TEXTURE0);
        glGetIntegerv(GL_TEXTURE_BINDING_2D, &old_texture);
        glGetIntegerv(GL_SAMPLER_BINDING, &old_sampler);
        glGetIntegerv(GL_BLEND_SRC_RGB, &blend_src_rgb);
        glGetIntegerv(GL_BLEND_DST_RGB, &blend_dst_rgb);
        glGetIntegerv(GL_BLEND_SRC_ALPHA, &blend_src_alpha);
        glGetIntegerv(GL_BLEND_DST_ALPHA, &blend_dst_alpha);
        glGetIntegerv(GL_BLEND_EQUATION_RGB, &blend_equation_rgb);
        glGetIntegerv(GL_BLEND_EQUATION_ALPHA, &blend_equation_alpha);
        glGetIntegerv(GL_POLYGON_MODE, polygon);
        glGetBooleanv(GL_COLOR_WRITEMASK, mask);
        const GLenum capabilities[] = {GL_BLEND, GL_DEPTH_TEST, GL_SCISSOR_TEST, GL_PROGRAM_POINT_SIZE,
            GL_STENCIL_TEST, GL_RASTERIZER_DISCARD, GL_CULL_FACE};
        GLboolean states[7];
        for (unsigned i = 0; i < 7; ++i) {
            states[i] = glIsEnabled(capabilities[i]);
            glDisable(capabilities[i]);
        }
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, 0);
        glViewport(0, 0, width, height);
        glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
        glEnable(GL_SCISSOR_TEST);
        glClearColor(0, 0, 0, 1);
        if (enabled) {
            glScissor(4, std::max(0, height - 12 - 3 * debug_font_cell_height * scale),
                std::max(0, std::min(width - 4, int(longest * debug_font_advance + 12) * scale)),
                3 * debug_font_cell_height * scale + 8);
            glClear(GL_COLOR_BUFFER_BIT);
        }
        if (qte_panel.width != 0) {
            glScissor(qte_panel.x, height - qte_panel.y - qte_panel.height, qte_panel.width, qte_panel.height);
            glClear(GL_COLOR_BUFFER_BIT);
        }
        glDisable(GL_SCISSOR_TEST);
        glUseProgram(program);
        glBindTexture(GL_TEXTURE_2D, font_texture);
        glBindSampler(0, 0);
        glUniform1i(glGetUniformLocation(program, "font"), 0);
        glEnable(GL_BLEND);
        glBlendFuncSeparate(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_ONE, GL_ONE_MINUS_SRC_ALPHA);
        glBlendEquationSeparate(GL_FUNC_ADD, GL_FUNC_ADD);
        glPolygonMode(GL_FRONT_AND_BACK, GL_FILL);
        glBindVertexArray(vao);
        glBindBuffer(GL_ARRAY_BUFFER, vbo);
        glBufferData(GL_ARRAY_BUFFER, points.size() * sizeof(float), points.data(), GL_STREAM_DRAW);
        glDrawArrays(GL_TRIANGLES, 0, static_cast<GLsizei>(points.size() / 4));
        glBindTexture(GL_TEXTURE_2D, old_texture);
        glBindSampler(0, old_sampler);
        glActiveTexture(old_active);
        glBlendFuncSeparate(blend_src_rgb, blend_dst_rgb, blend_src_alpha, blend_dst_alpha);
        glBlendEquationSeparate(blend_equation_rgb, blend_equation_alpha);
        glPolygonMode(GL_FRONT_AND_BACK, polygon[0]);
        glBindVertexArray(old_vao);
        glBindBuffer(GL_ARRAY_BUFFER, old_buffer);
        glUseProgram(old_program);
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, old_draw);
        glViewport(viewport[0], viewport[1], viewport[2], viewport[3]);
        glScissor(scissor[0], scissor[1], scissor[2], scissor[3]);
        glClearColor(clear[0], clear[1], clear[2], clear[3]);
        glColorMask(mask[0], mask[1], mask[2], mask[3]);
        for (unsigned i = 0; i < 7; ++i) {
            if (states[i]) {
                glEnable(capabilities[i]);
            } else {
                glDisable(capabilities[i]);
            }
        }
        pending_prompt = qte_panel.width != 0 ? prompt.context : 0;
        if (enabled) {
            capture(width, height);
        }
    }

    void did_present() {
        primary_desktop_qte_prompt().presented(pending_prompt, desktop_look_time_ms());
        pending_prompt = 0;
    }

    void release() {
        pending_prompt = 0;
        primary_desktop_qte_prompt().presented(0, desktop_look_time_ms());
        if (program) {
            glDeleteProgram(program);
            glDeleteBuffers(1, &vbo);
            glDeleteVertexArrays(1, &vao);
            glDeleteTextures(1, &font_texture);
            program = vao = vbo = font_texture = 0;
        }
    }

private:
    void capture(int width, int height) {
        const char* prefix = std::getenv("OPENSHSM_DEBUG_CAPTURE");
        const bool once = prefix != nullptr;
        if (!prefix) {
            prefix = std::getenv("NWII_SCREENSHOT");
        }
        if (!prefix || width > 3840 || height > 2160) {
            return;
        }
        ++capture_count;
        if ((once && capture_count != 30) || (!once && capture_count % 300 != 0)) {
            return;
        }
        GLint old_read, old_read_buffer, old_pack, old_row;
        glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING, &old_read);
        glGetIntegerv(GL_READ_BUFFER, &old_read_buffer);
        glGetIntegerv(GL_PACK_ALIGNMENT, &old_pack);
        glGetIntegerv(GL_PACK_ROW_LENGTH, &old_row);
        glBindFramebuffer(GL_READ_FRAMEBUFFER, 0);
        glReadBuffer(GL_BACK);
        glPixelStorei(GL_PACK_ALIGNMENT, 1);
        glPixelStorei(GL_PACK_ROW_LENGTH, 0);
        std::vector<unsigned char> pixels(size_t(width) * height * 4), flipped(pixels.size());
        glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());
        for (int y = 0; y < height; ++y) {
            std::memcpy(flipped.data() + size_t(y) * width * 4,
                pixels.data() + size_t(height - y - 1) * width * 4, size_t(width) * 4);
        }
        SDL_Surface* surface = SDL_CreateRGBSurfaceFrom(flipped.data(), width, height, 32, width * 4,
            0xFF, 0xFF00, 0xFF0000, 0);
        if (surface) {
            const std::string path = std::string(prefix) + "_debug_" + std::to_string(capture_count) + ".bmp";
            SDL_SaveBMP(surface, path.c_str());
            SDL_FreeSurface(surface);
        }
        glPixelStorei(GL_PACK_ALIGNMENT, old_pack);
        glPixelStorei(GL_PACK_ROW_LENGTH, old_row);
        glBindFramebuffer(GL_READ_FRAMEBUFFER, old_read);
        glReadBuffer(old_read_buffer);
    }

    bool initialize() {
        const char* vertex = "#version 330 core\nlayout(location=0) in vec4 p; out vec2 uv; void main(){gl_Position=vec4(p.xy,0,1);uv=p.zw;}";
        const char* fragment = "#version 330 core\nin vec2 uv; uniform sampler2D font; out vec4 c; void main(){c=texture(font,uv);}";
        GLuint shaders[2] = {glCreateShader(GL_VERTEX_SHADER), glCreateShader(GL_FRAGMENT_SHADER)};
        const char* sources[2] = {vertex, fragment};
        program = glCreateProgram();
        for (unsigned i = 0; i < 2; ++i) {
            glShaderSource(shaders[i], 1, &sources[i], nullptr);
            glCompileShader(shaders[i]);
            glAttachShader(program, shaders[i]);
        }
        glLinkProgram(program);
        for (GLuint shader : shaders) {
            glDeleteShader(shader);
        }
        GLint linked = 0;
        glGetProgramiv(program, GL_LINK_STATUS, &linked);
        if (!linked) {
            release();
            return false;
        }
        GLint old_vao, old_buffer, old_active, old_texture, unpack, row, skip_rows, skip_pixels, unpack_buffer;
        glGetIntegerv(GL_VERTEX_ARRAY_BINDING, &old_vao);
        glGetIntegerv(GL_ARRAY_BUFFER_BINDING, &old_buffer);
        glGetIntegerv(GL_ACTIVE_TEXTURE, &old_active);
        glActiveTexture(GL_TEXTURE0);
        glGetIntegerv(GL_TEXTURE_BINDING_2D, &old_texture);
        glGetIntegerv(GL_UNPACK_ALIGNMENT, &unpack);
        glGetIntegerv(GL_UNPACK_ROW_LENGTH, &row);
        glGetIntegerv(GL_UNPACK_SKIP_ROWS, &skip_rows);
        glGetIntegerv(GL_UNPACK_SKIP_PIXELS, &skip_pixels);
        glGetIntegerv(GL_PIXEL_UNPACK_BUFFER_BINDING, &unpack_buffer);
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0);
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
        glPixelStorei(GL_UNPACK_ROW_LENGTH, 0);
        glPixelStorei(GL_UNPACK_SKIP_ROWS, 0);
        glPixelStorei(GL_UNPACK_SKIP_PIXELS, 0);
        glGenTextures(1, &font_texture);
        glBindTexture(GL_TEXTURE_2D, font_texture);
        const auto pixels = desktop_hud_pixels(std::getenv("OPENSHSM_PS2_BUTTON_ICONS"));
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, desktop_hud_width, desktop_hud_height, 0, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
        glBindTexture(GL_TEXTURE_2D, old_texture);
        glActiveTexture(old_active);
        glPixelStorei(GL_UNPACK_ALIGNMENT, unpack);
        glPixelStorei(GL_UNPACK_ROW_LENGTH, row);
        glPixelStorei(GL_UNPACK_SKIP_ROWS, skip_rows);
        glPixelStorei(GL_UNPACK_SKIP_PIXELS, skip_pixels);
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, unpack_buffer);
        glGenVertexArrays(1, &vao);
        glGenBuffers(1, &vbo);
        glBindVertexArray(vao);
        glBindBuffer(GL_ARRAY_BUFFER, vbo);
        glEnableVertexAttribArray(0);
        glVertexAttribPointer(0, 4, GL_FLOAT, GL_FALSE, 4 * sizeof(float), nullptr);
        glBindVertexArray(old_vao);
        glBindBuffer(GL_ARRAY_BUFFER, old_buffer);
        return true;
    }

    bool enabled;
    bool render_failed = false;
    uint32_t pending_prompt = 0;
    GLuint program = 0, vao = 0, vbo = 0, font_texture = 0;
    std::chrono::steady_clock::time_point epoch = std::chrono::steady_clock::now();
    uint64_t present_count = 0, previous_gx = 0, empty = 0, pulls = 0, supplied_frames = 0;
    uint64_t short_pulls = 0, errors = 0, short_count = 0;
    uint64_t capture_count = 0;
    uint64_t callback_calls = 0, callback_supplied = 0, callback_shorts = 0, callback_errors = 0;
    uint32_t min_queue = UINT32_MAX;
    double present_fps = 0.0, gx_fps = 0.0, queue_ms = 0.0;
};

}
