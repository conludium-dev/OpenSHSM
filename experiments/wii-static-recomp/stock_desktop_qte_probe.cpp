#include "stock_desktop_qte.h"
#include <cassert>
#include <cstdio>
#include <initializer_list>
#include <fstream>
using openshsm::experiment::DesktopQTEState;

int main(int argc, char** argv) {
    assert(argc == 1 || argc == 2);
    unsigned cases = 0;
    for (unsigned target = 0; target < 4; ++target) {
        for (unsigned before = 0; before < 16; ++before) {
            for (unsigned buttons = 0; buttons < 16; ++buttons) {
                DesktopQTEState state;
                state.enter(1, target);
                state.consume(before, true, 100, 1);
                assert(state.request(100) == -1);
                state.consume(buttons, true, 116, 2);
                const unsigned edges = buttons & ~before;
                const unsigned correct = 1u << target;
                const bool wrong = (edges & ~correct) != 0;
                assert(state.request(116) == (!wrong && (edges & correct) ? int(target) : -1));
                assert(state.remaining_ms(116) == (wrong ? 5000u : 0u));
                assert(state.request(116) == -1);
                state.consume(buttons, true, 132, 3);
                assert(state.request(132) == -1);
                ++cases;
            }
        }
    }
    DesktopQTEState state;
    state.enter(1, 0);
    state.consume(0, true, 0, 1);
    state.consume(1, true, 10, 2);
    state.consume(0, true, 11, 3);
    assert(state.request(12) == 0);
    state.acknowledge();
    state.consume(1, true, 20, 4);
    assert(state.request(20) == -1);
    state.enter(2, 0);
    state.consume(1, true, 30, 5);
    assert(state.request(30) == -1);
    state.consume(0, true, 40, 6);
    state.consume(1, true, 50, 7);
    assert(state.request(50) == 0);
    state.consume(0, false, 60, 8);
    state.consume(1, true, 70, 9);
    assert(state.request(70) == -1);
    state.consume(0, true, 80, 10);
    state.consume(1, true, 90, 11);
    assert(state.request(341) == -1);
    state.consume(1, true, 350, 12);
    assert(state.request(350) == -1);
    state.consume(0, true, 360, 13);
    state.consume(1, true, 370, 14);
    state.consume(2, true, 371, 14);
    assert(state.request(371) == 0);
    state.consume(0x80, true, 380, 15);
    assert(state.request(380) == -1);
    state.consume(1, true, 390, 16);
    assert(state.request(390) == -1);
    for (uint32_t base : {1000u, 0xFFFFFF00u}) {
        DesktopQTEState timer;
        timer.enter(1, 0);
        uint64_t generation = 1;
        timer.consume(0, true, base, generation++);
        timer.consume(3, true, base + 1, generation++);
        assert(timer.request(base + 1) == -1 && timer.remaining_ms(base + 1) == 5000);
        for (unsigned ms = 17; ms <= 4980; ms += 17) {
            timer.consume(0, true, base + ms, generation++);
            timer.consume(1, true, base + ms + 1, generation++);
            assert(timer.request(base + ms + 1) == -1);
        }
        assert(timer.remaining_ms(base + 5000) == 1);
        timer.consume(0, true, base + 5000, generation++);
        timer.consume(1, true, base + 5001, generation++);
        assert(timer.request(base + 5001) == 0 && timer.remaining_ms(base + 5001) == 0);
        timer.enter(0, 0);
        timer.consume(0, true, base + 5010, generation++);
        timer.consume(1, true, base + 5020, generation++);
        assert(timer.request(base + 5020) == -1);
        timer.enter(1, 4);
        timer.consume(0, true, base + 5030, generation++);
        timer.consume(1, true, base + 5040, generation++);
        assert(timer.request(base + 5040) == -1);
    }
    {
        DesktopQTEState retry;
        retry.enter(1, 0);
        retry.consume(0, true, 0, 1);
        retry.consume(1, true, 16, 2);
        assert(retry.request(16) == 0);
        retry.acknowledge();
        retry.consume(0, true, 32, 3);
        retry.consume(1, true, 48, 4);
        assert(retry.request(48) == -1);
        retry.rearm();
        assert(retry.request(48) == -1);
        retry.consume(0, true, 64, 5);
        retry.consume(1, true, 80, 6);
        assert(retry.request(80) == 0);
        retry.acknowledge();
        retry.rearm();
        retry.consume(0, true, 96, 7);
        assert(retry.request(96) == -1);
        retry.consume(2, true, 112, 8);
        assert(retry.request(112) == -1 && retry.remaining_ms(112) == 5000);
        retry.rearm();
        retry.consume(0, true, 128, 9);
        retry.consume(1, true, 144, 10);
        assert(retry.request(144) == -1 && retry.remaining_ms(144) == 4968);
    }
    unsigned oracle_cases = 0;
    if (argc == 2) {
        std::ifstream oracle(argv[1]);
        assert(oracle.good());
        unsigned target, before, buttons, request, penalty;
        while (oracle >> target >> before >> buttons >> request >> penalty) {
            DesktopQTEState actual;
            actual.enter(1, target);
            actual.acknowledge();
            actual.consume(before, true, 0, 1);
            actual.consume(buttons, true, 16, 2);
            assert((actual.request(16) >= 0) == bool(request));
            assert(actual.remaining_ms(16) == (penalty ? 5000u : 0u));
            ++oracle_cases;
        }
        assert(oracle.eof() && oracle_cases == 1536);
    }
    std::printf("DESKTOP_QTE_EDGES_FOCUS_GENERATION_ACK_TIMEOUT_WRAP_PASS cases=%u ps2Oracle=%u\n", cases, oracle_cases);
}
