#include "stock_audio_callback.h"
#include "runtime/cpu_context.h"
#include "runtime/event_scheduler.h"
#include "runtime/hw/hw.h"
#include <SDL.h>
#include <cassert>
#include <memory>
#include <stdexcept>
#include <vector>

namespace nwii::runtime {
extern MMU* g_mmu;
extern CPUContext* g_ctx_ptr;
}
size_t bad_pull(int16_t*, size_t frames) { return frames + 1; }
size_t throwing_pull(int16_t*, size_t) { throw std::runtime_error("fixture"); }

int main() {
    using namespace nwii::runtime;
    using openshsm::experiment::AudioCallback;
    auto owned = std::make_unique<CPUContext>();
    auto& ctx = *owned;
    g_ctx_ptr = &ctx;
    g_mmu = &ctx.mmu;
    ctx.tb_freq = 60750000;
    auto& scheduler = EventScheduler::get();
    scheduler.reset();
    auto& mmio = MMIODispatcher::get();
    mmio.clear();
    hw::register_ai(mmio);
    hw::register_dsp(mmio);
    mmio.write32(0xCC006C00, 0x40);
    for (unsigned i = 0; i < 192; ++i) {
        ctx.mmu.write16(0x80560000 + i * 2, uint16_t(int16_t(int(i) * 113 - 12000)));
    }
    mmio.write16(0xCC005030, 0x56);
    mmio.write16(0xCC005032, 0);
    mmio.write16(0xCC005036, 0x800C);
    scheduler.advance(ctx, ctx.tb_freq * 8 * 10 / 32000);
    AudioCallback callback(hw::dsp_audio_pull);
    std::vector<uint8_t> data(4100, 0xAB);
    AudioCallback::render(&callback, data.data() + 1, 4096);
    assert(data.front() == 0xAB && data[4097] == 0xAB);
    for (unsigned i = 0; i < 160; ++i) {
        int16_t value;
        std::memcpy(&value, data.data() + 1 + i * 2, 2);
        assert(value == int16_t(int(i) * 113 - 12000));
    }
    for (unsigned i = 321; i < 4097; ++i) {
        assert(data[i] == 0);
    }
    auto stats = callback.snapshot();
    assert(stats.requested == 1024 && stats.supplied == 80 && stats.missing == 944 && stats.errors == 0);
    AudioCallback::render(&callback, data.data() + 1, 4);
    assert(callback.snapshot().missing == 945);
    for (int length : {0, -1, 3}) {
        AudioCallback::render(&callback, data.data() + 1, length);
    }
    assert(callback.snapshot().errors == 1);
    AudioCallback::render(&callback, nullptr, 4);
    AudioCallback::render(nullptr, data.data(), 4);
    AudioCallback bad(bad_pull), throwing(throwing_pull), absent(nullptr);
    for (AudioCallback* fixture : {&bad, &throwing, &absent}) {
        std::fill(data.begin(), data.end(), 0xAB);
        AudioCallback::render(fixture, data.data(), 4096);
        assert(fixture->snapshot().errors == 1);
        for (unsigned i = 0; i < 4096; ++i) { assert(data[i] == 0); }
        assert(data[4096] == 0xAB);
    }
    scheduler.advance(ctx, ctx.tb_freq);
    mmio.write16(0xCC005036, 12);
    std::vector<uint8_t> large(8192);
    AudioCallback::render(&callback, large.data(), int(large.size()));
    stats = callback.snapshot();
    assert(stats.supplied == 2128 && stats.errors == 1);
    assert(SDL_Init(SDL_INIT_AUDIO) == 0);
    SDL_AudioSpec want{}, have{};
    want.freq = 32000;
    want.format = AUDIO_S16SYS;
    want.channels = 2;
    want.samples = 1024;
    want.callback = AudioCallback::render;
    want.userdata = &callback;
    const auto device = SDL_OpenAudioDevice(nullptr, 0, &want, &have, 0);
    assert(device && have.freq == 32000 && have.format == AUDIO_S16SYS && have.channels == 2);
    const auto paused = callback.snapshot().calls;
    SDL_Delay(80);
    assert(callback.snapshot().calls == paused);
    SDL_PauseAudioDevice(device, 0);
    SDL_Delay(200);
    SDL_CloseAudioDevice(device);
    const auto closed = callback.snapshot();
    assert(closed.calls >= paused + 2 && closed.supplied > stats.supplied && closed.errors == 1);
    assert(closed.requested == closed.supplied + closed.missing);
    SDL_Delay(80);
    assert(callback.snapshot().calls == closed.calls);
    SDL_Quit();
    scheduler.reset();
    g_ctx_ptr = nullptr;
    g_mmu = nullptr;
    std::printf("AUDIO_CALLBACK_DSP_PCM_BOUNDS_SDL_LIFETIME_PASS calls=%llu\n", (unsigned long long)closed.calls);
}
