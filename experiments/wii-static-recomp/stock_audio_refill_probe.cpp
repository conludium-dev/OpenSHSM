#include "stock_audio_refill.h"
#include <cassert>
#include <cstring>
#include <vector>

struct DeviceFixture {
    uint32_t queued_bytes = 0, available = 0, max_supply = 1024;
    uint32_t source_index = 0;
    bool fail_queue = false, instant_drain = false;
    std::vector<int16_t> output;

    auto run() {
        return openshsm::experiment::refill_audio(
            [&] { if (instant_drain) { queued_bytes = 0; } return queued_bytes; },
            [&](int16_t* data, uint32_t requested) -> size_t {
                const auto supplied = std::min({available, requested, max_supply});
                std::fill(data, data + requested * 2, int16_t(-12345));
                for (unsigned i = 0; i < supplied * 2; ++i) {
                    data[i] = int16_t(source_index++ + 17);
                }
                available -= supplied;
                return supplied;
            },
            [&](const int16_t* data, uint32_t frames) {
                if (fail_queue) {
                    return -1;
                }
                queued_bytes += frames * 4;
                output.insert(output.end(), data, data + frames * 2);
                return 0;
            },
            [](uint32_t, size_t, bool, bool, size_t) {});
    }
};

int main() {
    DeviceFixture empty;
    const auto a = empty.run();
    assert(a.pulls == 1 && a.empty == 1 && a.queued == 0 && empty.output.empty());
    DeviceFixture partial;
    partial.available = 100;
    const auto b = partial.run();
    assert(b.supplied == 100 && b.queued == 100 && b.empty == 1 && b.after == 400);
    for (unsigned i = 0; i < partial.output.size(); ++i) {
        assert(partial.output[i] == int(i) + 17);
    }
    DeviceFixture backlog;
    backlog.available = 10000;
    const auto c = backlog.run();
    assert(c.pulls == 2 && c.queued == 2048 && c.after == 8192 && backlog.available == 7952);
    DeviceFixture nearly_full;
    nearly_full.queued_bytes = 7000;
    nearly_full.available = 10000;
    const auto d = nearly_full.run();
    assert(d.pulls == 1 && d.supplied == 298 && d.after == 8192);
    DeviceFixture full;
    full.queued_bytes = 12000;
    full.available = 10000;
    assert(full.run().pulls == 0 && full.output.empty());
    DeviceFixture failed;
    failed.available = 32;
    failed.fail_queue = true;
    const auto e = failed.run();
    assert(e.supplied == 32 && e.queued == 0 && e.errors == 1 && e.pulls == 1);
    DeviceFixture draining;
    draining.available = 10000;
    draining.instant_drain = true;
    const auto f = draining.run();
    assert(f.queued == 4096 && f.pulls == 4 && f.limited);
    DeviceFixture tiny;
    tiny.available = 10000;
    tiny.max_supply = 1;
    const auto g = tiny.run();
    assert(g.supplied == 8 && g.pulls == 8 && g.limited);
    bool refused = false;
    try {
        openshsm::experiment::refill_audio([] { return 0u; },
            [](int16_t*, uint32_t requested) { return requested + 1; },
            [](const int16_t*, uint32_t) { return 0; },
            [](uint32_t, size_t, bool, bool, size_t) {});
    } catch (const std::runtime_error&) {
        refused = true;
    }
    assert(refused);
    std::cout << "AUDIO_REFILL_VALID_PCM_CAP_BOUNDS_ERRORS_PASS9\n";
}
