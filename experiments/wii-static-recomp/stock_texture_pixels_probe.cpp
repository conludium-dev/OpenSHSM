#include "runtime/texture_cache_gl.h"
#include <SDL.h>
#include <glad/glad.h>
#include <array>
#include <chrono>
#include <cstdio>
#include <memory>
#include <vector>

int main(int argc, char** argv) {
    using namespace nwii::runtime;
    if (argc != 2 || SDL_Init(SDL_INIT_VIDEO) != 0) {
        return 1;
    }
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
    auto* window = SDL_CreateWindow("OpenSHSM texture pixel probe", SDL_WINDOWPOS_UNDEFINED,
        SDL_WINDOWPOS_UNDEFINED, 32, 32, SDL_WINDOW_OPENGL | SDL_WINDOW_HIDDEN);
    if (!window) {
        return 2;
    }
    auto context = SDL_GL_CreateContext(window);
    if (!context || !gladLoadGLLoader(reinterpret_cast<GLADloadproc>(SDL_GL_GetProcAddress))) {
        return 3;
    }
    FILE* output = std::fopen(argv[1], "wb");
    if (!output) {
        return 4;
    }
    auto owned = std::make_unique<CPUContext>();
    auto& ctx = *owned;
    auto& cache = hle::TextureCache::get();
    unsigned cases = 0;
    for (unsigned format : {0u, 1u, 2u, 3u, 4u, 5u, 6u, 8u, 9u, 10u, 14u}) {
        for (auto dimensions : {std::pair{8u, 8u}, std::pair{13u, 9u}, std::pair{16u, 16u}, std::pair{640u, 480u}}) {
            const bool paletted = format >= 8 && format <= 10;
            for (unsigned palette = 0; palette < (paletted ? 3u : 1u); ++palette) {
                cache.clear();
                gx::TexStage stage{};
                stage.base_addr = 0x80560000;
                stage.width = dimensions.first;
                stage.height = dimensions.second;
                stage.format = format;
                stage.tlut_offset = 32;
                stage.tlut_format = palette;
                GLuint previous = 0;
                for (unsigned version = 0; version < (paletted ? 3u : 2u); ++version) {
                    auto* input = ctx.mmu.get_ptr(stage.base_addr);
                    if (version < 2) {
                        for (unsigned i = 0; i < 2 * 1024 * 1024; ++i) {
                            input[i] = uint8_t((i * 37 + format * 29 + version * 113) ^ (i >> 7));
                        }
                    }
                    for (unsigned i = 0; i < sizeof(gx::g_state.tlutMem); ++i) {
                        gx::g_state.tlutMem[i] = uint8_t(i * 13 + palette * 23 + version * 71);
                    }
                    glActiveTexture(GL_TEXTURE3);
                    const auto start = std::chrono::steady_clock::now();
                    const GLuint texture = cache.get_texture(ctx, stage);
                    const auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
                        std::chrono::steady_clock::now() - start).count();
                    if (!texture || (previous && texture == previous) || cache.get_texture(ctx, stage) != texture) {
                        return 5;
                    }
                    previous = texture;
                    GLint active = 0;
                    glGetIntegerv(GL_ACTIVE_TEXTURE, &active);
                    if (active != GL_TEXTURE3) {
                        return 6;
                    }
                    glBindTexture(GL_TEXTURE_2D, texture);
                    std::vector<uint8_t> pixels(stage.width * stage.height * 4);
                    glGetTexImage(GL_TEXTURE_2D, 0, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());
                    std::array<uint32_t, 6> header{format, stage.width, stage.height, palette, version, uint32_t(pixels.size())};
                    if (glGetError() != GL_NO_ERROR || std::fwrite(header.data(), sizeof(header), 1, output) != 1 ||
                        std::fwrite(pixels.data(), 1, pixels.size(), output) != pixels.size()) {
                        return 7;
                    }
                    std::printf("PIXEL_CASE %u %u %u %u %u %lld\n", format, stage.width, stage.height, palette, version, (long long)ns);
                    ++cases;
                }
            }
        }
    }
    GLuint efb = 0;
    glGenTextures(1, &efb);
    glBindTexture(GL_TEXTURE_2D, efb);
    const std::array<uint8_t, 16> efb_pixels{0, 1, 2, 3, 11, 12, 13, 14, 21, 22, 23, 24, 31, 32, 33, 34};
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, 2, 2, 0, GL_RGBA, GL_UNSIGNED_BYTE, efb_pixels.data());
    cache.register_efb_texture(0x80080000, efb);
    gx::TexStage efb_stage{};
    efb_stage.base_addr = 0x80080000;
    efb_stage.width = efb_stage.height = 2;
    if (cache.get_texture(ctx, efb_stage) != efb) {
        return 8;
    }
    cache.clear();
    if (cache.find_efb_texture(efb_stage.base_addr) != efb || !glIsTexture(efb)) {
        return 9;
    }
    glDeleteTextures(1, &efb);
    if (glGetError() != GL_NO_ERROR || std::fclose(output) != 0) {
        return 10;
    }
    SDL_GL_DeleteContext(context);
    SDL_DestroyWindow(window);
    SDL_Quit();
    std::printf("NATIVE_TEXTURE_PIXEL_HIT_INVALIDATION_EFB_PASS %u\n", cases);
    return 0;
}
