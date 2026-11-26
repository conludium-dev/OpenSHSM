#include "stock_vi_timer_profile.h"
#include <cassert>
struct Memory {
    unsigned value = 0;
    unsigned reads = 0;
    unsigned read32(unsigned address) {
        assert(address == 0x800000E4);
        ++reads;
        return value;
    }
};
struct Context {
    bool in_callback;
    unsigned dispatch_saved_ctx;
    Memory mmu;
};
int main() {
    unsigned cases = 0;
    for (unsigned bits = 0; bits < 32; ++bits) {
        const unsigned mask = (bits & 1) ? 0x100 : 0;
        const unsigned status = (bits & 4) ? 0x100 : 0;
        Context original{bool(bits & 2), (bits & 8) ? 1u : 0u, {(bits & 16) ? 1u : 0u, 0}};
        Context candidate = original;
        const bool expected = (mask & 0x100) && !original.in_callback &&
            !(status & 0x100) && (original.dispatch_saved_ctx == 0 || original.mmu.read32(0x800000E4) == 0);
        const auto reason = stock_vi_timer_profile::classify(candidate, mask, status);
        assert(expected == (reason == stock_vi_timer_profile::Reason::Raised));
        assert(original.mmu.reads == candidate.mmu.reads);
        assert(original.mmu.value == candidate.mmu.value);
        ++cases;
    }
    auto& observer = stock_vi_timer_profile::observer();
    observer.registration(1012500, 60750000);
    observer.record(stock_vi_timer_profile::Reason::Raised, 9, 60750000);
    assert(observer.due == (observer.enabled ? 1u : 0u));
    if (observer.enabled) {
        assert(observer.reasons[4] == 1 && observer.late == 9 && observer.maximum_late == 9);
    }
    std::printf("VI_GATE_CASES=%u MMU_READ_COUNTS_EQUAL observer=%s\n", cases, observer.enabled ? "enabled" : "disabled");
}
