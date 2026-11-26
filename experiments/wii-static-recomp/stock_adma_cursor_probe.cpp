#include "stock_adma_cursor.h"
#include <cassert>
#include <iostream>
#include <utility>

int main() {
    using namespace openshsm::experiment;
    uint64_t chunks = 0;
    for (uint16_t count : {0u, 1u, 12u, 32767u}) {
        AdmaCursor cursor;
        cursor.latch(0x80560003, count);
        const unsigned transfers = count ? count : 1;
        for (unsigned i = 0; i < transfers; ++i) {
            assert(cursor.blocks_left_register() == (count ? count - i - 1 : 0));
            const auto chunk = cursor.transfer(0x9060001F, 3);
            assert(chunk.address == 0x00560000 + i * 32);
            assert(chunk.interrupt == (i + 1 == transfers));
            ++chunks;
        }
        assert(cursor.blocks_left_register() == 2);
        for (unsigned i = 0; i < 3; ++i) {
            const auto chunk = cursor.transfer(0x9060001F, 3);
            assert(chunk.address == 0x10600000 + i * 32 && chunk.interrupt == (i == 2));
            ++chunks;
        }
    }
    uint64_t periods = 0;
    for (uint64_t frequency : {40500000ull, 60750000ull}) {
        for (uint32_t rate : {32000u, 48000u}) {
            AdmaTickPhase phase;
            uint64_t ticks = 0;
            for (unsigned i = 0; i < rate / 8; ++i) {
                ticks += phase.next(frequency, rate);
                const uint64_t exact_numerator = uint64_t(i + 1) * frequency * 8;
                assert(ticks == exact_numerator / rate);
                ++periods;
            }
            assert(ticks == frequency);
        }
    }
    AdmaTickPhase switch_phase;
    assert(switch_phase.next(60750000, 32000) == 15187);
    assert(switch_phase.next(60750000, 32000) == 15188);
    assert(switch_phase.next(60750000, 48000) == 10125);
    assert(switch_phase.next(60750000, 32000) == 15187);
    unsigned refused = 0;
    for (auto [frequency, rate] : {std::pair{0ull, 32000u}, std::pair{1ull, 32000u},
        std::pair{60750000ull, 0u}, std::pair{60750000ull, 44100u},
        std::pair{std::numeric_limits<uint64_t>::max(), 48000u}}) {
        try {
            switch_phase.next(frequency, rate);
        } catch (const std::runtime_error&) {
            ++refused;
        }
    }
    assert(refused == 5);
    std::cout << "ADMA_CURSOR_PHASE_PASS chunks=" << chunks << " periods=" << periods << '\n';
}
