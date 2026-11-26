#include <processor_adapter.h>
#include "runtime/hw/hw.h"
#include <SDL.h>
#include <glad/glad.h>
#include <cassert>
#include <cstdio>
#include <memory>
#include <mutex>
#include <vector>

extern void GX_SetWindow(void*);
extern void ProcessGXFifo();
extern std::mutex g_fifo_mutex;
extern std::vector<uint8_t> g_hw_fifo;
namespace nwii::runtime { extern CPUContext* g_ctx_ptr; }
static PFNGLFINISHPROC actual_finish;
static std::vector<uint32_t> expected_before;
static size_t calls = 0;

static void checked_finish() {
    assert(calls < expected_before.size());
    assert(nwii::runtime::hw::g_pe_sr.load() == expected_before[calls]);
    actual_finish();
    unsigned char pixel[4];
    glReadPixels(16, 16, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, pixel);
    assert(std::abs(int(pixel[0]) - 32) <= 1 && std::abs(int(pixel[1]) - 64) <= 1);
    assert(std::abs(int(pixel[2]) - 96) <= 1);
    ++calls;
}
static void append(uint8_t reg, uint32_t value, bool partial = false) {
    std::lock_guard<std::mutex> lock(g_fifo_mutex);
    g_hw_fifo.insert(g_hw_fifo.end(), {0x61, reg, uint8_t(value >> 16), uint8_t(value >> 8)});
    if (!partial) {
        g_hw_fifo.push_back(uint8_t(value));
    }
}
int main() {
    using namespace nwii::runtime;
    assert(SDL_Init(SDL_INIT_VIDEO) == 0);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
    auto* window = SDL_CreateWindow("OpenSHSM PE pipeline probe", SDL_WINDOWPOS_UNDEFINED,
        SDL_WINDOWPOS_UNDEFINED, 32, 32, SDL_WINDOW_OPENGL | SDL_WINDOW_HIDDEN);
    assert(window);
    auto context = SDL_GL_CreateContext(window);
    assert(context && gladLoadGLLoader(reinterpret_cast<GLADloadproc>(SDL_GL_GetProcAddress)));
    std::printf("DRIVER %s\n", glGetString(GL_VERSION));
    auto owned = std::make_unique<CPUContext>();
    g_ctx_ptr = owned.get();
    auto& bus = MMIODispatcher::get();
    hw::register_pe(bus);
    GX_SetWindow(window);
    actual_finish = glad_glFinish;
    glad_glFinish = checked_finish;
    for (unsigned mode = 0; mode < 6; ++mode) {
        bus.write32(0xCC00100A, 0x0F);
        hw::pi_intsr = 0;
        calls = 0;
        expected_before = mode == 5 ? std::vector<uint32_t>{0, 8, 8} : std::vector<uint32_t>{0};
        glViewport(0, 0, 32, 32);
        glDisable(GL_SCISSOR_TEST);
        glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
        glClearColor(0.125f, 0.25f, 0.375f, 1);
        glClear(GL_COLOR_BUFFER_BIT);
        if (mode == 1 || mode == 2) {
            append(mode == 1 ? 0x47 : 0x48, 0x5678);
        } else if (mode == 3) {
            append(0x45, 2, true);
            ProcessGXFifo();
            assert(calls == 0 && hw::g_pe_sr.load() == 0);
            {
                std::lock_guard<std::mutex> lock(g_fifo_mutex);
                g_hw_fifo.push_back(2);
            }
        } else {
            if (mode == 4) {
                append(0x45, 3);
                ProcessGXFifo();
                assert(calls == 0 && hw::g_pe_sr.load() == 0);
            }
            append(0x45, 2);
            if (mode == 5) {
                append(0x47, 0x1234);
                append(0x48, 0xABCD);
            }
        }
        assert(hw::g_pe_sr.load() == 0);
        ProcessGXFifo();
        assert(calls == expected_before.size());
        const uint32_t pe = mode == 1 ? 0 : mode == 2 ? 4 : mode == 5 ? 12 : 8;
        const uint32_t pi = mode == 1 ? 0 : mode == 2 ? 0x200 : mode == 5 ? 0x600 : 0x400;
        assert(hw::g_pe_sr.load() == pe && (hw::pi_intsr.load() & 0x600) == pi);
        if (mode == 1 || mode == 2 || mode == 5) {
            assert(bus.read32(0xCC00100E) == (mode == 5 ? 0xABCDu : 0x5678u));
        }
        assert(glGetError() == GL_NO_ERROR);
        std::printf("PIPELINE mode=%u realFences=%zu pe=%u pi=%u\n", mode, calls, pe, pi);
    }
    glad_glFinish = actual_finish;
    GX_SetWindow(nullptr);
    g_ctx_ptr = nullptr;
    SDL_GL_DeleteContext(context);
    SDL_DestroyWindow(window);
    SDL_Quit();
    std::puts("ACTUAL_FIFO_RENDER_REAL_GL_FENCE_BEFORE_PE_ACK_PASS6");
}
