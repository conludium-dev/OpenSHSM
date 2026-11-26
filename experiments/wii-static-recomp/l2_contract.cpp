#include "l2_adapter.h"
#define main unused_frontend_main
#include "memory_frontend_probe.cpp"
#undef main

int main() {
    using namespace nwii::runtime;
    L2Context context;
    context.msr = 0x30;
    for (uint32_t value : {0u, 1u, 0x200000u, 0x80000000u, 0x85000000u, 0x7fffffffu, 0xfffffffeu, 0xffffffffu}) {
        experiment_write_l2cr(context, value);
        assert(experiment_read_l2cr(context) == value);
    }
    context.msr = 0x4030;
    unsigned refused = 0;
    try {
        experiment_read_l2cr(context);
    } catch (const std::runtime_error&) {
        ++refused;
    }
    try {
        experiment_write_l2cr(context, 0);
    } catch (const std::runtime_error&) {
        ++refused;
    }
    assert(refused == 2 && context.l2cr == 0xffffffffu);
    std::cout << "L2_REFERENCE_CONTRACT 8roundtrips 2privilege refusals PASS\n";
}
