#pragma once
#include "runtime/cpu_context.h"
#include <array>
#include <chrono>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <sstream>

namespace stock_loading_observation {
struct Pending {
    const void* context = nullptr;
    uint32_t sp = 0, request = 0, callback = 0;
    bool active = false;
};

inline std::string copy_ram(nwii::runtime::CPUContext& ctx, uint32_t address, unsigned size) {
    const uint64_t end = uint64_t(address) + size;
    if (!((address >= 0x80004000 && end <= 0x81800000) || (address >= 0x90000000 && end <= 0x94000000))) {
        return "";
    }
    const uint8_t* data = ctx.mmu.get_ptr(address);
    if (!data) {
        return "";
    }
    std::ostringstream stream;
    for (unsigned i = 0; i < size; ++i) {
        stream << std::hex << std::setw(2) << std::setfill('0') << unsigned(data[i]);
    }
    return stream.str();
}

inline void observe(nwii::runtime::CPUContext& ctx, uint32_t pc) {
    const char* prefix = std::getenv("NWII_THPDUMP");
    if (!prefix) {
        return;
    }
    static std::array<Pending, 512> pending{};
    static unsigned callbacks = 0, frames = 0;
    static const auto start = std::chrono::steady_clock::now();
    unsigned id = frames;
    const char* event = nullptr;
    uint32_t request = 0, callback = 0;
    if (pc == 0x8018FA50 || pc == 0x8018FA5C) {
        if (pc == 0x8018FA50) {
            ++frames;
        }
        id = frames;
        if (frames > 8 && frames % 60 != 0) {
            return;
        }
        event = pc == 0x8018FA50 ? "frame-before" : "frame-after";
    } else if (pc == 0x801B51D4) {
        if (callbacks == pending.size()) {
            return;
        }
        id = callbacks++;
        request = ctx.gpr[31]; callback = ctx.ctr;
        pending[id] = {&ctx, ctx.gpr[1], request, callback, true};
        event = "callback-before";
    } else if (pc == 0x801B51D8) {
        bool found = false;
        for (unsigned i = callbacks; i > 0; --i) {
            auto& state = pending[i - 1];
            if (state.active && state.context == &ctx && state.sp == ctx.gpr[1] && state.request == ctx.gpr[31]) {
                id = i - 1; request = state.request; callback = state.callback;
                state.active = false;
                found = true;
                break;
            }
        }
        if (!found) {
            return;
        }
        event = "callback-after";
    } else {
        return;
    }
    std::ofstream file(std::string(prefix) + "-loading.jsonl", std::ios::app);
    if (!file) {
        return;
    }
    const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start).count();
    file << "{\"event\":\"" << event << "\",\"id\":" << id << ",\"hostMs\":" << ms
        << ",\"pc\":" << pc << ",\"sp\":" << ctx.gpr[1] << ",\"request\":" << request
        << ",\"callback\":" << callback << ",\"queueHex\":\"" << copy_ram(ctx, 0x8048E078, 16)
        << "\",\"gateHex\":\"" << copy_ram(ctx, 0x8052A5E0, 1) << "\",\"requestHex\":\""
        << (request ? copy_ram(ctx, request, 32) : "") << "\",\"gpr3to7\":[";
    for (unsigned i = 3; i < 8; ++i) {
        file << (i > 3 ? "," : "") << ctx.gpr[i];
    }
    file << "]}\n";
}
}
