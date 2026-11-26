#pragma once
#include <array>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <string>

namespace stock_scan_observation {
struct Snapshot {
    bool pending = false;
    const void* context = nullptr;
    uint32_t sp = 0, lr = 0, input = 0, format = 0;
    std::string text, spec;
    std::array<uint32_t, 6> destinations{};
    std::array<std::string, 6> before{};
};
static std::array<Snapshot, 32> snapshots;
static unsigned used = 0;

static const uint8_t* ram(nwii::runtime::CPUContext& ctx, uint32_t address, unsigned bytes) {
    const uint64_t end = uint64_t(address) + bytes;
    if (!bytes || !((address >= 0x80004000 && end <= 0x81800000)
        || (address >= 0x90000000 && end <= 0x94000000))) {
        return nullptr;
    }
    return ctx.mmu.get_ptr(address);
}

static std::string hex_bytes(const uint8_t* data, unsigned size) {
    std::ostringstream stream;
    for (unsigned i = 0; i < size; ++i) {
        stream << std::hex << std::setw(2) << std::setfill('0') << unsigned(data[i]);
    }
    return stream.str();
}

static bool string_copy(nwii::runtime::CPUContext& ctx, uint32_t address, std::string& value) {
    value.clear();
    for (unsigned i = 0; i < 256; ++i) {
        const uint8_t* byte = ram(ctx, address + i, 1);
        if (!byte || address > 0xFFFFFFFFu - i) {
            return false;
        }
        if (*byte == 0) {
            return true;
        }
        value.push_back(char(*byte));
    }
    return false;
}

static void begin(nwii::runtime::CPUContext& ctx) {
    if (!std::getenv("NWII_THPDUMP") || used == snapshots.size()) {
        return;
    }
    Snapshot next;
    next.context = &ctx; next.sp = ctx.gpr[1]; next.lr = ctx.lr;
    next.input = ctx.gpr[3]; next.format = ctx.gpr[4];
    if (!string_copy(ctx, next.input, next.text) || !string_copy(ctx, next.format, next.spec)) {
        return;
    }
    unsigned format_count = 0;
    for (unsigned i = 0; i < used; ++i) {
        const auto& old = snapshots[i];
        if (old.spec == next.spec) {
            ++format_count;
            if (old.text == next.text) {
                return;
            }
        }
        if (old.pending && old.context == &ctx && old.sp == next.sp) {
            return;
        }
    }
    if (format_count >= 4) {
        return;
    }
    for (unsigned i = 0; i < 6; ++i) {
        next.destinations[i] = ctx.gpr[5 + i];
        if (const uint8_t* data = ram(ctx, next.destinations[i], 8)) {
            next.before[i] = hex_bytes(data, 8);
        }
    }
    next.pending = true;
    snapshots[used++] = next;
}

static void finish(nwii::runtime::CPUContext& ctx) {
    const char* prefix = std::getenv("NWII_THPDUMP");
    if (!prefix) {
        return;
    }
    for (unsigned index = 0; index < used; ++index) {
        auto& state = snapshots[index];
        if (!state.pending || state.context != &ctx || uint64_t(ctx.gpr[1]) + 128 != state.sp) {
            continue;
        }
        std::ofstream file(std::string(prefix) + "-scan.jsonl", std::ios::app);
        if (!file) {
            return;
        }
        file << "{\"index\":" << index << ",\"sp\":" << state.sp << ",\"lr\":" << state.lr
            << ",\"inputAddress\":" << state.input << ",\"formatAddress\":" << state.format
            << ",\"inputHex\":\"" << hex_bytes(reinterpret_cast<const uint8_t*>(state.text.data()), state.text.size())
            << "\",\"formatHex\":\"" << hex_bytes(reinterpret_cast<const uint8_t*>(state.spec.data()), state.spec.size())
            << "\",\"count\":" << ctx.gpr[3] << ",\"outputs\":[";
        for (unsigned i = 0; i < 6; ++i) {
            const uint8_t* data = ram(ctx, state.destinations[i], 8);
            file << (i ? "," : "") << "{\"address\":" << state.destinations[i]
                << ",\"before\":\"" << state.before[i] << "\",\"after\":\""
                << (data ? hex_bytes(data, 8) : "") << "\"}";
        }
        file << "]}\n";
        file.close();
        state.pending = false;
    }
}
}
