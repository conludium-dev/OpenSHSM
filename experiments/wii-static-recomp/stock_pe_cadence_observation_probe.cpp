#include "stock_pe_cadence_observation.h"
#include <cassert>
#include <cstdio>

int main() {
    using namespace nwii::runtime::gx;
    GXCommand copy{}, finish{}, token{};
    copy.type = finish.type = token.type = GXCommandType::BPRegister;
    copy.reg = 0x52; copy.val = 0x4000;
    finish.reg = 0x45; finish.val = 2;
    token.reg = 0x48; token.val = 0x5678;
    const std::vector<GXCommand> commands{copy, finish, token};
    unsigned emissions = 0;
    auto fail = [&](auto...) { ++emissions; };
    for (const char* refused : {static_cast<const char*>(nullptr), "", "invalid", "180001"}) {
        StockPECadenceObservation observer(refused);
        assert(!observer.inspect(commands, stock_gx_completed_frame_bounds(commands), 100, fail));
        assert(observer.consumed == 0 && observer.batch == 0 && emissions == 0);
    }
    StockPECadenceObservation observer("1");
    assert(!observer.inspect(commands, stock_gx_completed_frame_bounds(commands), 100, fail));
    assert(observer.consumed == 1 && observer.batch == 1);
    const std::vector<GXCommand> tail{finish, token};
    assert(observer.inspect(tail, stock_gx_completed_frame_bounds(tail), 1100,
        [&](uint64_t batch, uint64_t id, uint16_t reg, uint32_t val, bool selected, uint64_t host) {
            assert(batch == 2 && id == 1 + emissions && selected && host == 1100);
            assert(reg == (emissions ? 0x48 : 0x45) && val == (emissions ? 0x5678 : 2));
            ++emissions;
        }));
    assert(emissions == 2 && observer.consumed == 3);
    StockPECadenceObservation bounded("0");
    unsigned seen = 0;
    for (unsigned index = 0; index < 130; ++index) {
        assert(bounded.inspect(commands, stock_gx_completed_frame_bounds(commands), index,
            [&](uint64_t batch, uint64_t id, uint16_t, uint32_t, bool selected, uint64_t) {
                assert(batch == index + 1 && id == index + 1 + seen % 2 && !selected);
                ++seen;
            }) == (index < 128));
    }
    assert(bounded.samples == 128 && seen == 256 && bounded.consumed == 130);
    StockPECadenceObservation marker_cap("0");
    const std::vector<GXCommand> many(1024, token);
    unsigned marker_count = 0;
    assert(marker_cap.inspect(many, stock_gx_completed_frame_bounds(many), 0,
        [&](auto...) { ++marker_count; }));
    assert(marker_count == 512 && marker_cap.markers == 512);
    assert(marker_cap.inspect(many, stock_gx_completed_frame_bounds(many), 1,
        [&](auto...) { ++marker_count; }));
    assert(marker_count == 512 && marker_cap.consumed == 2048);
    StockPECadenceObservation overflow("0");
    overflow.consumed = std::numeric_limits<uint64_t>::max();
    assert(!overflow.inspect(commands, stock_gx_completed_frame_bounds(commands), 0, fail));
    assert(!overflow.enabled && emissions == 2);
    assert(commands[0].reg == 0x52 && commands[1].val == 2 && commands[2].val == 0x5678);
    std::puts("PE_CADENCE_DISABLED_INVALID_DELAY_STABLE_ID_CAP_READ_ONLY_PASS");
}
