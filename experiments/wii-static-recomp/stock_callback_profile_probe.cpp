#include "stock_callback_profile.h"
#include <csetjmp>
#include <cstdio>

struct Context {
    uint32_t msr = 0x8000;
    bool in_callback = false;
};

int main() {
    using namespace stock_callback_profile;
    Context ctx;
    const bool active = enabled();
    for (unsigned i = 0; i < 2048; ++i) {
        const auto ticket = enter(ctx);
        const bool result = (i % 2) == 0;
        if (leave(ticket, result) != result) {
            return 1;
        }
        restored();
    }
    uint64_t values[10]{};
    snapshot(values);
    if (!active) {
        for (auto value : values) {
            if (value != 0) {
                return 2;
            }
        }
        std::puts("CALLBACK_PROFILE_DISABLED_PASS");
        return 0;
    }
    if (values[0] != 2048 || values[1] != 2048 || values[2] != 1024 ||
        values[3] != 0 || values[4] != 0 || values[5] != 2 || values[6] != 2 ||
        values[8] != 0 || values[9] != 2048 || ctx.msr != 0x8000 || ctx.in_callback) {
        return 3;
    }
    stats() = {};
    ctx.msr = 0;
    ctx.in_callback = true;
    for (unsigned i = 0; i < 1023; ++i) {
        const auto ticket = enter(ctx);
        leave(ticket, false);
    }
    std::jmp_buf target;
    if (setjmp(target) == 0) {
        const auto ticket = enter(ctx);
        (void)ticket;
        longjmp(target, 1);
    }
    snapshot(values);
    if (values[0] != 1024 || values[1] != 1023 || values[2] != 0 || values[3] != 1024 ||
        values[4] != 1024 || values[5] != 1 || values[6] != 0 || values[7] != 0 ||
        values[8] != 0 || values[9] != 0 || ctx.msr != 0 || !ctx.in_callback) {
        return 4;
    }
    std::puts("CALLBACK_PROFILE_RETURN_EE_CALLBACK_NONLOCAL_COUNTS_PASS");
    return 0;
}
