#include "stock_buffer_flush_observation.h"
#include <array>
#include <cassert>
#include <memory>

int main() {
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    ctx.gpr[1] = 0x80700000;
    ctx.gpr[3] = ctx.gpr[29] = 0x80560000;
    ctx.gpr[4] = 0x80561000;
    ctx.gpr[6] = 32;
    ctx.pc = 0x8035AEF8;
    ctx.lr = 0x80352E94;
    std::array<uint32_t, 32> before{};
    for (unsigned i = 0; i < 32; ++i) {
        before[i] = ctx.gpr[i];
    }
    std::ostringstream stream;
    auto* old = std::cout.rdbuf(stream.rdbuf());
    for (unsigned i = 0; i < 40; ++i) {
        openshsm::experiment::observe_buffer_flush(ctx, true);
    }
    for (unsigned i = 0; i < 32; ++i) {
        assert(ctx.gpr[i] == before[i]);
    }
    ctx.gpr[4] = 0xFFFFFFFF;
    ctx.gpr[6] = 0xFFFFFFFF;
    for (unsigned i = 0; i < 40; ++i) {
        openshsm::experiment::observe_buffer_flush(ctx, true);
    }
    assert(ctx.pc == 0x8035AEF8 && ctx.lr == 0x80352E94 && ctx.gpr[4] == 0xFFFFFFFF);
    ctx.gpr[3] = 0x80561000;
    ctx.gpr[4] = 32;
    for (unsigned i = 0; i < 40; ++i) {
        openshsm::experiment::observe_buffer_flush(ctx, false);
    }
    ctx.gpr[4] = 0xFFFFFFFF;
    for (unsigned i = 0; i < 40; ++i) {
        openshsm::experiment::observe_buffer_flush(ctx, false);
    }
    std::cout.rdbuf(old);
    const auto text = stream.str();
    unsigned lines = 0;
    for (auto byte : text) {
        lines += byte == '\n';
    }
    assert(lines == 64);
    assert(text.find("valid=0") != std::string::npos);
    assert(!openshsm::experiment::observed_buffer_span(0x817FFFF0, 32));
    assert(!openshsm::experiment::observed_buffer_span(0xCD000000, 32));
    assert(!openshsm::experiment::observed_buffer_span(0xFFFFFFF0, 32));
    std::cout << "BUFFER_FLUSH_OBSERVER_COMPONENT_PASS separate-normal-abnormal-caps/registers/bounds\n";
}
