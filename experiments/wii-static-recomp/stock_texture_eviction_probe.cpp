#include "runtime/texture_cache_gl.h"
#include <SDL.h>
#include <glad/glad.h>
#include <array>
#include <cassert>
#include <iostream>
#include <memory>
#include <string>

int main(int argc, char** argv) {
    using namespace nwii::runtime;
    const bool corrected = argc == 2 && std::string(argv[1]) == "corrected";
    assert(SDL_Init(SDL_INIT_VIDEO) == 0);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
    auto* window = SDL_CreateWindow("OpenSHSM eviction probe", SDL_WINDOWPOS_UNDEFINED,
        SDL_WINDOWPOS_UNDEFINED, 32, 32, SDL_WINDOW_OPENGL | SDL_WINDOW_HIDDEN);
    assert(window);
    auto context = SDL_GL_CreateContext(window);
    assert(context && gladLoadGLLoader(reinterpret_cast<GLADloadproc>(SDL_GL_GetProcAddress)));
    auto owned = std::make_unique<CPUContext>();
    auto& ctx = *owned;
    auto stage = [](unsigned index) {
        gx::TexStage result{};
        result.base_addr = 0x80560000 + index * 64;
        result.width = 8;
        result.height = 4;
        result.format = 1;
        return result;
    };
    auto& cache = hle::TextureCache::get();
    cache.clear();
    GLuint first = 0;
    std::array<GLuint, 512> prefilled{};
    for (unsigned i = 0; i < 512; ++i) {
        auto item = stage(i);
        for (unsigned j = 0; j < 32; ++j) { ctx.mmu.write8(item.base_addr + j, uint8_t(i)); }
        const auto texture = cache.get_texture(ctx, item);
        if (i == 0) { first = texture; }
        prefilled[i] = texture;
    }
    std::array<GLuint, 3> selected{};
    for (unsigned unit = 0; unit < 3; ++unit) {
        glActiveTexture(GL_TEXTURE0 + unit);
        selected[unit] = cache.get_texture(ctx, stage(unit == 0 ? 0 : 511 + unit));
        glBindTexture(GL_TEXTURE_2D, selected[unit]);
    }
    std::array<GLint, 3> bindings{};
    for (unsigned unit = 0; unit < 3; ++unit) {
        glActiveTexture(GL_TEXTURE0 + unit);
        glGetIntegerv(GL_TEXTURE_BINDING_2D, &bindings[unit]);
    }
    assert(glGetError() == GL_NO_ERROR);
    if (!corrected) {
        assert(bindings[0] == 0 && bindings[1] == 0 && bindings[2] == GLint(selected[2]));
        std::cout << "BOUND_TEXTURE_EVICTION_LOSS_REPRODUCED units0and1zero\n";
    } else {
        for (unsigned unit = 0; unit < 3; ++unit) { assert(bindings[unit] == GLint(selected[unit])); }
        assert(glIsTexture(first));
        unsigned survivingNames = 0;
        for (auto name : prefilled) { survivingNames += glIsTexture(name) == GL_TRUE; }
        assert(survivingNames <= 3);
        glActiveTexture(GL_TEXTURE7);
        glBindTexture(GL_TEXTURE_2D, selected[0]);
        for (unsigned i = 514; i < 1600; ++i) {
            glActiveTexture(GL_TEXTURE2);
            cache.get_texture(ctx, stage(i));
            GLint active = 0, unit0 = 0;
            glGetIntegerv(GL_ACTIVE_TEXTURE, &active);
            assert(active == GL_TEXTURE2);
            glActiveTexture(GL_TEXTURE0);
            glGetIntegerv(GL_TEXTURE_BINDING_2D, &unit0);
            assert(unit0 == GLint(selected[0]));
        }
        assert(glIsTexture(first));
        std::cout << "BOUND_TEXTURE_EVICTION_PROTECTION_PASS1600 activeunitPreserved\n";
    }
    std::cout << "DRIVER " << glGetString(GL_VERSION) << '\n';
    cache.clear();
    SDL_GL_DeleteContext(context);
    SDL_DestroyWindow(window);
    SDL_Quit();
}
