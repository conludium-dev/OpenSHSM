#define main loading_metadata_contract_main
#include "stock_loading_observation_contract.cpp"
#undef main
#include "stock_loading_payload_observation.h"

int main() {
    if (loading_metadata_contract_main() != 0) {
        return 1;
    }
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    ctx.gpr[5] = 0x80600300; ctx.gpr[6] = 16;
    for (unsigned i = 0; i < 16; ++i) { ctx.mmu.write8(ctx.gpr[5] + i, uint8_t(i + 100)); }
    const auto gpr = ctx.gpr;
    const auto data = stock_loading_observation::copy_ram(ctx, ctx.gpr[5], 16);
    stock_loading_observation::capture_payload(ctx);
    if (ctx.gpr != gpr || stock_loading_observation::copy_ram(ctx, ctx.gpr[5], 16) != data) {
        return 2;
    }
    ctx.gpr[5] = 0xCC000000;
    stock_loading_observation::capture_payload(ctx);
    std::cout << "LOADING_PAYLOAD_COPY_COMPONENT_PASS\n";
}
