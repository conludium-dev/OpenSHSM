#pragma once
#include "runtime/cpu_context.h"
#include "stock_axwii_commands.h"
#include "stock_axwii_pb.h"
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fcntl.h>
#include <string>
#ifdef _WIN32
#include <io.h>
#include <sys/stat.h>
#else
#include <unistd.h>
#endif

namespace openshsm::experiment {

inline const uint8_t* dsp_capture_ram(const nwii::runtime::CPUContext& ctx, uint32_t address, size_t size) {
    const uint32_t physical = address & 0x3fffffffu;
    if (ctx.mmu.mem1.size() >= 8 && uint64_t(physical) + size <= ctx.mmu.mem1.size() - 8) {
        return ctx.mmu.mem1.data() + physical;
    }
    if (physical >= 0x10000000u && ctx.mmu.mem2.size() >= 8 &&
            uint64_t(physical - 0x10000000u) + size <= ctx.mmu.mem2.size() - 8) {
        return ctx.mmu.mem2.data() + physical - 0x10000000u;
    }
    return nullptr;
}

class DspCommandCapture {
public:
    DspCommandCapture() {
        const char* directory = std::getenv("OPENSHSM_DSP_CAPTURE_DIR");
        if (!directory || !std::filesystem::path(directory).is_absolute() ||
                std::char_traits<char>::length(directory) > 1024) {
            return;
        }
        try {
            prefix = directory;
            metadata = open_file("dsp-events.jsonl");
        } catch (...) {
            metadata = nullptr;
        }
    }

    ~DspCommandCapture() {
        if (metadata) {
            std::fclose(metadata);
        }
    }

    void mail(const nwii::runtime::CPUContext& ctx, uint32_t value, uint16_t control, int state) noexcept {
        if (!metadata) {
            return;
        }
        firmware_mail(ctx, value);
        ++mail_seen;
        if (mail_rows < 512 && (mail_seen <= 128 || mail_seen % 600 == 0)) {
            ++mail_rows;
            std::fprintf(metadata,
                "{\"kind\":\"mail\",\"index\":%llu,\"value\":%u,\"control\":%u,\"adapterState\":%d,\"dispatchPC\":%u,\"instructions\":%llu}\n",
                static_cast<unsigned long long>(mail_seen), value, unsigned(control), state, ctx.pc,
                static_cast<unsigned long long>(ctx.inst_count));
            std::fflush(metadata);
        }
        if (state == 1) {
            ++list_seen;
            if (list_rows < 256 && (list_seen <= 8 || list_seen % 600 == 0)) {
                const size_t size = size_t(declared_units) * 2;
                const uint8_t* bytes = declared_units && declared_units <= 256 ? dsp_capture_ram(ctx, value, size) : nullptr;
                const unsigned index = ++list_rows;
                char name[64];
                std::snprintf(name, sizeof(name), "dsp-list-%03u.bin", index);
                const bool saved = bytes && save(name, bytes, size);
                std::fprintf(metadata,
                    "{\"kind\":\"list\",\"index\":%u,\"ordinal\":%llu,\"address\":%u,\"declaredUnits\":%u,\"wordSizeAssumption\":2,\"capturedBytes\":%zu,\"saved\":%s}\n",
                    index, static_cast<unsigned long long>(list_seen), value, unsigned(declared_units),
                    saved ? size : size_t(0), saved ? "true" : "false");
                std::fflush(metadata);
                if (bytes && live_profile == 0x4cc52064 && pb_jobs < 4) {
                    capture_pbs(ctx, index, bytes, size);
                }
            }
            declared_units = 0;
        } else if ((value & 0xffff0000u) == 0xbabe0000u) {
            declared_units = uint16_t(value);
        }
    }

    void dma(const nwii::runtime::CPUContext& ctx, uint32_t source, uint32_t destination,
        uint32_t requested, bool from_aram) noexcept {
        if (!metadata || from_aram || dma_rows >= 8 || !requested) {
            return;
        }
        const unsigned index = ++dma_rows;
        const size_t size = std::min<size_t>(requested, 8192);
        const uint8_t* bytes = dsp_capture_ram(ctx, source, size);
        char name[64];
        std::snprintf(name, sizeof(name), "dsp-dma-%02u.bin", index);
        const bool saved = bytes && save(name, bytes, size);
        std::fprintf(metadata,
            "{\"kind\":\"dma-to-aram\",\"index\":%u,\"source\":%u,\"destination\":%u,\"requestedBytes\":%u,\"capturedBytes\":%zu,\"truncated\":%s,\"saved\":%s}\n",
            index, source, destination, requested, saved ? size : size_t(0),
            size < requested ? "true" : "false", saved ? "true" : "false");
        std::fflush(metadata);
    }

private:
    void firmware_mail(const nwii::runtime::CPUContext& ctx, uint32_t value) noexcept {
        if (value == 0x80f3a001) {
            live_profile = 0;
            firmware_pending = 1;
            return;
        }
        if (firmware_pending == 1) {
            firmware_address = value;
            firmware_pending = 0;
            return;
        }
        if (value == 0x80f3a002) {
            firmware_pending = 2;
            return;
        }
        if (firmware_pending != 2) {
            return;
        }
        firmware_pending = 0;
        if (firmware_attempted) {
            return;
        }
        firmware_attempted = true;
        const uint8_t* bytes = value == 8192 ? dsp_capture_ram(ctx, firmware_address, value) : nullptr;
        uint32_t hash = 0;
        if (bytes) {
            for (size_t index = 0; index < value; ++index) {
                hash ^= bytes[index];
                hash = (hash << 3) | (hash >> 29);
            }
        }
        const bool saved = bytes && save("dsp-firmware-01.bin", bytes, value);
        if (saved && hash == 0x4cc52064) {
            live_profile = hash;
        }
        std::fprintf(metadata,
            "{\"kind\":\"firmware-ram-candidate\",\"address\":%u,\"requestedBytes\":%u,\"capturedBytes\":%u,\"ectorHash\":%u,\"saved\":%s}\n",
            firmware_address, value, saved ? value : 0, hash, saved ? "true" : "false");
        std::fflush(metadata);
    }

    void capture_pbs(const nwii::runtime::CPUContext& ctx, unsigned list_index,
        const uint8_t* bytes, size_t size) noexcept {
        try {
            const auto commands = decode_axwii_commands(std::span(bytes, size), live_profile);
            for (const auto& command : commands) {
                if (command.opcode != 4 || pb_jobs >= 4) {
                    continue;
                }
                unsigned job = 0;
                uint32_t address = uint32_t(command.arguments[0]) << 16 | command.arguments[1];
                std::array<uint32_t, 256> visited{};
                unsigned count = 0, scanned = 0;
                const char* stop = "end";
                while (address) {
                    if (count == 16 || scanned == visited.size()) {
                        stop = "limit";
                        break;
                    }
                    const uint32_t physical = address & 0x3fffffffu;
                    if (std::find(visited.begin(), visited.begin() + scanned, physical) != visited.begin() + scanned) {
                        stop = "cycle";
                        break;
                    }
                    const uint8_t* wire = address % 2 == 0 ? dsp_capture_ram(ctx, address, 300) : nullptr;
                    if (!wire) {
                        stop = "invalid-ram";
                        break;
                    }
                    const auto pb = decode_axwii_pb(std::span(wire, size_t(300)), live_profile);
                    visited[scanned++] = physical;
                    if (pb.running() != 1) {
                        address = pb.next_address();
                        continue;
                    }
                    if (!job) {
                        job = ++pb_jobs;
                    }
                    ++count;
                    char name[64];
                    std::snprintf(name, sizeof(name), "dsp-pb-%02u-%02u.bin", job, count);
                    const bool saved = save(name, wire, 300);
                    std::fprintf(metadata,
                        "{\"kind\":\"pb\",\"job\":%u,\"node\":%u,\"listIndex\":%u,\"address\":%u,\"nextAddress\":%u,\"running\":%u,\"profile\":%u,\"capturedBytes\":%u,\"saved\":%s}\n",
                        job, count, list_index, address, pb.next_address(), unsigned(pb.running()),
                        live_profile, saved ? 300 : 0, saved ? "true" : "false");
                    if (!saved) {
                        stop = "write-failed";
                        break;
                    }
                    address = pb.next_address();
                }
                if (job || pb_diagnostics < 4) {
                    if (!job) {
                        ++pb_diagnostics;
                    }
                    std::fprintf(metadata,
                        "{\"kind\":\"pb-chain\",\"job\":%u,\"listIndex\":%u,\"nodes\":%u,\"scanned\":%u,\"stop\":\"%s\"}\n",
                        job, list_index, count, scanned, stop);
                    std::fflush(metadata);
                }
            }
        } catch (...) {
        }
    }

    FILE* open_file(const char* name) noexcept {
        char path[1152];
        if (std::snprintf(path, sizeof(path), "%s/%s", prefix.c_str(), name) >= int(sizeof(path))) {
            return nullptr;
        }
#ifdef _WIN32
        const int fd = ::_open(path, _O_WRONLY | _O_CREAT | _O_EXCL | _O_BINARY,
            _S_IREAD | _S_IWRITE);
#else
        const int fd = ::open(path, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
#endif
        if (fd < 0) {
            return nullptr;
        }
#ifdef _WIN32
        FILE* file = ::_fdopen(fd, "wb");
#else
        FILE* file = ::fdopen(fd, "wb");
#endif
        if (!file) {
#ifdef _WIN32
            ::_close(fd);
#else
            ::close(fd);
#endif
        }
        return file;
    }

    bool save(const char* name, const uint8_t* bytes, size_t size) noexcept {
        FILE* file = open_file(name);
        if (!file) {
            return false;
        }
        const bool written = std::fwrite(bytes, 1, size, file) == size;
        const bool closed = std::fclose(file) == 0;
        return written && closed;
    }

    std::string prefix;
    FILE* metadata = nullptr;
    uint64_t mail_seen = 0, list_seen = 0;
    unsigned mail_rows = 0, list_rows = 0, dma_rows = 0;
    uint16_t declared_units = 0;
    uint32_t live_profile = 0, firmware_address = 0;
    unsigned firmware_pending = 0, pb_jobs = 0, pb_diagnostics = 0;
    bool firmware_attempted = false;
};

inline DspCommandCapture dsp_command_capture;

}
