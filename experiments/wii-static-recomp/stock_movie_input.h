#pragma once
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>

namespace stock_movie_input {

template<class Context>
const uint8_t* ram(const Context& ctx, uint32_t address, uint32_t size) {
    if (size == 0 || size > 1024 * 1024) {
        return nullptr;
    }
    const uint64_t end = uint64_t(address) + size;
    if (address >= 0x80000000 && end <= 0x81800000) {
        return ctx.mmu.mem1.data() + (address - 0x80000000);
    }
    if (address >= 0x90000000 && end <= 0x94000000) {
        return ctx.mmu.mem2.data() + (address - 0x90000000);
    }
    return nullptr;
}

template<class Context>
bool word(const Context& ctx, uint32_t address, uint32_t& value) {
    const auto* bytes = ram(ctx, address, 4);
    if (!bytes) {
        return false;
    }
    value = (uint32_t(bytes[0]) << 24) | (uint32_t(bytes[1]) << 16) |
        (uint32_t(bytes[2]) << 8) | bytes[3];
    return true;
}

struct Packet {
    const uint8_t* bytes = nullptr;
    uint32_t size = 0;
    uint32_t descriptor_field4 = 0;
    uint32_t thread = 0;
};

template<class Context>
bool prepare(const Context& ctx, Packet& packet) {
    packet = {};
    uint32_t count = 0;
    uint32_t frame = 0;
    const uint32_t index = ctx.gpr[26];
    if (ctx.gpr[30] > UINT32_MAX - 0x6C || !word(ctx, ctx.gpr[30] + 0x6C, count) ||
        count == 0 || count > 16 || index >= count || !word(ctx, ctx.gpr[23], frame)) {
        return false;
    }
    uint64_t address = uint64_t(frame) + 8 + 4 * count;
    for (uint32_t i = 0; i <= index; ++i) {
        uint32_t size = 0;
        const uint64_t slot = uint64_t(frame) + 8 + 4 * i;
        if (slot > UINT32_MAX || !word(ctx, uint32_t(slot), size)) {
            return false;
        }
        if (i == index) {
            if (slot != ctx.gpr[25]) {
                return false;
            }
            packet.size = size;
        } else {
            address += size;
        }
    }
    const uint64_t type_address = uint64_t(ctx.gpr[30]) + index + 0x70;
    const auto* type = type_address <= UINT32_MAX ? ram(ctx, uint32_t(type_address), 1) : nullptr;
    if (address != ctx.gpr[3] || address != ctx.gpr[24] || address > UINT32_MAX ||
        uint64_t(ctx.gpr[30]) + index != ctx.gpr[28] || !type || *type != 0 ||
        ctx.gpr[23] > UINT32_MAX - 4 || !word(ctx, ctx.gpr[23] + 4, packet.descriptor_field4) ||
        !word(ctx, 0x800000D4, packet.thread)) {
        return false;
    }
    packet.bytes = ram(ctx, uint32_t(address), packet.size);
    return packet.bytes && packet.size >= 2 && packet.bytes[0] == 0xFF && packet.bytes[1] == 0xD8;
}

struct Recorder {
    FILE* data = nullptr;
    FILE* metadata = nullptr;
    uint32_t count = 0;
    uint32_t total = 0;
    bool failed = false;
    ~Recorder() {
        if (data) {
            std::fclose(data);
        }
        if (metadata) {
            std::fclose(metadata);
        }
    }
};

template<class Context>
void observe(const Context& ctx, uint32_t site, unsigned serial) {
    if (site != 0x8009C5E0) {
        return;
    }
    static Recorder recorder;
    static const bool initialized = [&]() {
        const char* prefix = std::getenv("NWII_MOVIE_TIMING");
        if (!prefix || !*prefix) {
            return false;
        }
        try {
            recorder.data = std::fopen((std::string(prefix) + ".inputs.bin").c_str(), "wbx");
            recorder.metadata = std::fopen((std::string(prefix) + ".inputs.jsonl").c_str(), "wx");
        } catch (...) {
            recorder.failed = true;
        }
        return recorder.data && recorder.metadata && !recorder.failed;
    }();
    if (!initialized || recorder.failed || recorder.count >= 128) {
        return;
    }
    Packet packet;
    if (!prepare(ctx, packet) || packet.size > 16 * 1024 * 1024 - recorder.total) {
        return;
    }
    if (std::fwrite(packet.bytes, 1, packet.size, recorder.data) != packet.size ||
        std::fflush(recorder.data) != 0) {
        recorder.failed = true;
        return;
    }
    const int result = std::fprintf(recorder.metadata,
        "{\"index\":%u,\"serial\":%u,\"offset\":%u,\"bytes\":%u,\"input\":%u,"
        "\"thread\":%u,\"sp\":%u,\"component\":%u,\"descriptor\":%u,\"descriptorField4\":%u}\n",
        recorder.count, serial, recorder.total, packet.size, ctx.gpr[3], packet.thread,
        ctx.gpr[1], ctx.gpr[26], ctx.gpr[23], packet.descriptor_field4);
    if (result < 0 || std::fflush(recorder.metadata) != 0) {
        recorder.failed = true;
        return;
    }
    ++recorder.count;
    recorder.total += packet.size;
}

}
