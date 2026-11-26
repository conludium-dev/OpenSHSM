#include <processor_adapter.h>
#include <iostream>
#include <memory>

extern "C" int sdk_enable_route(uint32_t);
extern "C" void sdk_enable_dispatch(nwii::runtime::CPUContext&);

int main(int argc, char**) {
    const int route = sdk_enable_route(0x8021750C);
    std::cout << "ROUTE " << route << '\n';
    if (argc > 1) {
        return route == 0 ? 0 : 1;
    }
    if (route != 2) {
        return 2;
    }
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    for (uint32_t value : {0u, 1u, 0x8000u, 0x8032u, 0xFFFFu, 0x80000000u, 0xFFFFFFFFu}) {
        for (unsigned i = 0; i < 32; ++i) {
            ctx.gpr[i] = 0x12340000u + i * 256u;
        }
        ctx.gpr[3] = value;
        const auto gpr = ctx.gpr;
        ctx.pc = 0x8021750C;
        ctx.lr = 0x8009BB80;
        const auto msr = ctx.msr, xer = ctx.xer, ctr = ctx.ctr;
        sdk_enable_dispatch(ctx);
        if (ctx.gpr[3] != ((value >> 15) & 1u) || ctx.pc != 0x8009BB80
            || ctx.msr != msr || ctx.xer != xer || ctx.ctr != ctr || ctx.lr != 0x8009BB80) {
            return 3;
        }
        for (unsigned i = 0; i < 32; ++i) {
            if (i != 3 && ctx.gpr[i] != gpr[i]) {
                return 4;
            }
        }
        std::cout << "RESUME " << value << ' ' << ctx.gpr[3] << ' ' << ctx.pc << '\n';
    }
    return 0;
}
