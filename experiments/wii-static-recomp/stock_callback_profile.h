#pragma once
#include <array>
#include <cstdint>
#include <cstdlib>
#include <time.h>
#include <type_traits>

namespace stock_callback_profile {

inline std::array<uint64_t, 10>& stats() {
    static std::array<uint64_t, 10> values{};
    return values;
}

inline bool enabled() {
    static const bool value = std::getenv("NWII_MOVIE_TIMING") != nullptr;
    return value;
}

inline int64_t cpu_ns() {
    timespec time{};
    if (clock_gettime(CLOCK_THREAD_CPUTIME_ID, &time) != 0) {
        return -1;
    }
    return int64_t(time.tv_sec) * 1000000000 + time.tv_nsec;
}

struct Ticket {
    int64_t started_ns = -1;
    bool active = false;
    bool sampled = false;
};
static_assert(std::is_trivially_destructible_v<Ticket>);

template<class Context>
Ticket enter(const Context& ctx) {
    Ticket ticket;
    if (!enabled()) {
        return ticket;
    }
    ticket.active = true;
    auto& values = stats();
    ++values[0];
    values[3] += (ctx.msr & 0x8000) == 0;
    values[4] += ctx.in_callback;
    ticket.sampled = (values[0] % 1024) == 0;
    if (ticket.sampled) {
        ++values[5];
        ticket.started_ns = cpu_ns();
    }
    return ticket;
}

inline bool leave(const Ticket& ticket, bool result) {
    if (!ticket.active) {
        return result;
    }
    auto& values = stats();
    ++values[1];
    values[2] += result;
    if (ticket.sampled) {
        ++values[6];
        const int64_t ended_ns = cpu_ns();
        if (ticket.started_ns < 0 || ended_ns < ticket.started_ns) {
            ++values[8];
        } else {
            values[7] += uint64_t(ended_ns - ticket.started_ns);
        }
    }
    return result;
}

inline void restored() {
    if (enabled()) {
        ++stats()[9];
    }
}

inline void snapshot(uint64_t* destination) {
    for (unsigned i = 0; i < stats().size(); ++i) {
        destination[i] = stats()[i];
    }
}

}
