#pragma once
#include "runtime/cpu_context.h"
#include "runtime/gx/fifo_parser.h"
#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace openshsm::experiment {

// Private diagnostic interchange; decoded attributes are re-encoded as direct GX inputs.
class GxReplayCapture {
    using Bytes = std::vector<uint8_t>;
    struct Update { uint32_t offset, address; Bytes bytes; };
    std::string path;
    std::chrono::steady_clock::time_point start = std::chrono::steady_clock::now();
    FILE* file = nullptr;
    bool armed = false, done = false;
    unsigned frames = 0;
    unsigned delay_ms;
    size_t total = 0;
    size_t pending = 0, cached = 0;
    Bytes fifo;
    std::vector<Update> updates;
    std::map<uint32_t, Bytes> memory;
    std::set<uint32_t> copies;
    static constexpr size_t limit = 64 * 1024 * 1024;
    static_assert(std::endian::native == std::endian::little);

    static void be(Bytes& b, uint32_t value, unsigned width = 4) {
        for (unsigned i = width; i; --i) { b.push_back(uint8_t(value >> ((i - 1) * 8))); }
    }
    static void fp(Bytes& b, float value) {
        if (!std::isfinite(value)) { throw std::runtime_error("nonfinite direct attribute"); }
        uint32_t word; std::memcpy(&word, &value, 4); be(b, word);
    }
    void bp(unsigned reg, uint32_t value) { fifo.push_back(0x61); be(fifo, (reg << 24) | (value & 0xffffff)); }
    void cp(unsigned reg, uint32_t value) { fifo.push_back(0x08); fifo.push_back(uint8_t(reg)); be(fifo, value); }
    void chunk(uint32_t type, const void* data, size_t size) {
        if (size > limit || total + size + 8 > limit) { throw std::runtime_error("capture byte limit"); }
        uint32_t length = uint32_t(size);
        if (std::fwrite(&type, 4, 1, file) != 1 || std::fwrite(&length, 4, 1, file) != 1 ||
            (size && std::fwrite(data, 1, size, file) != size)) { throw std::runtime_error("capture write failed"); }
        total += size + 8;
    }
    void initial(const nwii::runtime::gx::GXState& state, const float* post) {
        file = std::fopen(path.c_str(), "wbx");
        if (!file) { throw std::runtime_error("capture file exists or cannot be created"); }
        const char magic[] = "OSGXCAP1";
        if (std::fwrite(magic, 1, 8, file) != 8) { throw std::runtime_error("capture header write failed"); }
        total = 8;
        std::array<uint32_t, 4096> xf{};
        std::memcpy(xf.data(), state.posMatrices, sizeof(state.posMatrices));
        std::memcpy(xf.data() + 0x400, state.normalMatrices, sizeof(state.normalMatrices));
        std::memcpy(xf.data() + 0x500, post, 256 * 4);
        std::memcpy(xf.data() + 0x600, state.lights, sizeof(state.lights));
        Bytes data;
        const auto append = [&](const void* ptr, size_t size) {
            const auto* bytes = static_cast<const uint8_t*>(ptr); data.insert(data.end(), bytes, bytes + size);
        };
        append(state.bp, 256 * 4); append(state.cp, 256 * 4);
        append(xf.data(), xf.size() * 4); append(state.xf, 88 * 4);
        append(state.tlutMem, sizeof(state.tlutMem));
        data.resize(data.size() + 1024 * 1024 - sizeof(state.tlutMem), 0);
        chunk(1, data.data(), data.size());
        bp(0xfe, 0xffffff);
        for (unsigned bank = 0; bank < 2; ++bank) {
            for (unsigned i = 0; i < 8; ++i) { bp(0xe0 + i, state.tevColorWords[bank][i]); }
        }
        bp(0xfe, state.bp[0xfe]);
        std::fprintf(stderr, "[GX REPLAY] started %s\n", path.c_str());
    }
    void texture(nwii::runtime::CPUContext& ctx, const nwii::runtime::gx::TexStage& t) {
        if (!t.base_addr || copies.contains(t.base_addr)) { return; }
        unsigned tw = 4, th = 4, block = 32;
        switch (t.format) {
            case 0: case 8: case 14: tw = th = 8; break;
            case 1: case 2: case 9: tw = 8; th = 4; break;
            case 3: case 4: case 5: case 10: break;
            case 6: block = 64; break;
            default: throw std::runtime_error("unsupported texture format");
        }
        size_t size = 0;
        for (unsigned w = t.width, h = t.height; w && h;) {
            size += ((w + tw - 1) / tw) * ((h + th - 1) / th) * block;
            if (w == 1 && h == 1) { break; }
            w = std::max(1u, w / 2); h = std::max(1u, h / 2);
        }
        resource(ctx, t.base_addr, size);
    }
    void resource(nwii::runtime::CPUContext& ctx, uint32_t base, size_t size) {
        const uint32_t address = base & 0x3fffffff;
        const auto& ram = address >= 0x10000000 ? ctx.mmu.mem2 : ctx.mmu.mem1;
        const size_t offset = address >= 0x10000000 ? address - 0x10000000 : address;
        if (offset > ram.size() - 8 || size > ram.size() - 8 - offset) { throw std::runtime_error("texture outside RAM"); }
        const uint8_t* ptr = ram.data() + offset;
        auto& old = memory[address];
        if (old.size() == size && std::equal(old.begin(), old.end(), ptr)) { return; }
        if (size > limit || total + pending + fifo.size() + size + 24 > limit ||
            cached - old.size() + size > limit / 2) { throw std::runtime_error("texture capture byte limit"); }
        cached = cached - old.size() + size;
        old.assign(ptr, ptr + size);
        updates.push_back({uint32_t(fifo.size()), address, old});
        pending += size + 24;
    }
    void draw(const nwii::runtime::gx::GXCommand& cmd, const nwii::runtime::gx::GXState& state,
              nwii::runtime::CPUContext& ctx) {
        if (!cmd.raw || cmd.raw->sources.size() != cmd.vertices.size() || cmd.vertices.size() > 65535) {
            throw std::runtime_error("missing decoded vertex sources");
        }
        std::set<unsigned> maps;
        for (unsigned i = 0; i < state.numTevStages; ++i) {
            if (state.tevStages[i].texMap < 8) { maps.insert(state.tevStages[i].texMap); }
        }
        for (unsigned map : maps) { texture(ctx, state.texStages[map]); }
        if (total + pending + fifo.size() + 129 * cmd.vertices.size() + 40 > limit) {
            throw std::runtime_error("vertex capture byte limit");
        }
        cp(0x50, 0x1ff | (1 << 9) | (1 << 11) | (1 << 13) | (1 << 15));
        cp(0x60, 0x5555);
        cp(0x70, 1 | (4 << 1) | (1 << 9) | (4 << 10) | (1 << 13) | (5 << 14) |
            (1 << 17) | (5 << 18) | (1 << 21) | (4 << 22));
        cp(0x80, 1 | (4 << 1) | (1 << 9) | (4 << 10) | (1 << 18) | (4 << 19) | (1u << 27) | (4u << 28));
        cp(0x90, (1 << 5) | (4 << 6) | (1 << 14) | (4 << 15) | (1 << 23) | (4 << 24));
        fifo.push_back(cmd.prim_type & 0xf8); be(fifo, uint32_t(cmd.vertices.size()), 2);
        for (size_t i = 0; i < cmd.vertices.size(); ++i) {
            const auto& source = cmd.raw->sources[i];
            fifo.push_back(cmd.vertices[i].posMtxIdx);
            for (unsigned j = 0; j < 8; ++j) { fifo.push_back(source.matrix_indices[j]); }
            for (float value : source.position) { fp(fifo, value); }
            for (const auto& normal : source.normals) { for (float value : normal) { fp(fifo, value); } }
            for (unsigned c = 0; c < 2; ++c) {
                for (float value : source.colors[c]) {
                    fifo.push_back(source.has_color[c] ? uint8_t(std::clamp(std::lround(value * 255), 0l, 255l)) : 255);
                }
            }
            for (const auto& uv : source.uv) { for (float value : uv) { fp(fifo, value); } }
        }
    }
    void finish_frame() {
        chunk(2, fifo.data(), fifo.size());
        for (const auto& update : updates) {
            Bytes data(8); std::memcpy(data.data(), &update.offset, 4); std::memcpy(data.data() + 4, &update.address, 4);
            data.insert(data.end(), update.bytes.begin(), update.bytes.end()); chunk(3, data.data(), data.size());
        }
        chunk(4, &frames, 4); ++frames; fifo.clear(); updates.clear(); pending = 0;
        if (frames == 3) {
            chunk(5, &frames, 4); std::fclose(file); file = nullptr; done = true;
            std::fprintf(stderr, "[GX REPLAY] complete frames=%u bytes=%zu\n", frames, total);
        }
    }

public:
    explicit GxReplayCapture(std::string output, unsigned delay = 108000) : path(std::move(output)), delay_ms(delay) {}
    ~GxReplayCapture() { if (file) { std::fclose(file); } }
    unsigned frames_written() const { return frames; }
    void observe(const nwii::runtime::gx::GXCommand& cmd, const nwii::runtime::gx::GXState& state,
                 nwii::runtime::CPUContext* ctx, const float* post) {
        using nwii::runtime::gx::GXCommandType;
        if (done || !ctx) { return; }
        const bool boundary = cmd.type == GXCommandType::BPRegister && cmd.reg == 0x52 && (cmd.val & 0x4000);
        try {
            if (!armed) {
                if (boundary && std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start).count() >= delay_ms) { armed = true; }
                return;
            }
            if (!file) { initial(state, post); }
            if (cmd.type == GXCommandType::BPRegister) {
                if (cmd.reg == 0x65) {
                    resource(*ctx, state.tlutSrcAddr, ((cmd.val >> 10) & 0x7ff) * 32);
                }
                if (cmd.reg == 0x63 && cmd.val) { throw std::runtime_error("manual TMEM preload not captured"); }
                bp(cmd.reg, cmd.val);
                if (cmd.reg == 0x52 && !(cmd.val & 0x4000)) { copies.insert(state.efbCopyDest); }
            } else if (cmd.type == GXCommandType::XFRegister) {
                if (cmd.payload.empty() || cmd.payload.size() > 16) { throw std::runtime_error("invalid XF packet length"); }
                fifo.push_back(0x10); be(fifo, (uint32_t(cmd.payload.size() - 1) << 16) | cmd.reg);
                for (float value : cmd.payload) { uint32_t word; std::memcpy(&word, &value, 4); be(fifo, word); }
            } else if (cmd.type == GXCommandType::DrawPrimitive) {
                draw(cmd, state, *ctx);
            }
            if (fifo.size() > limit || total + fifo.size() > limit) { throw std::runtime_error("FIFO capture byte limit"); }
            if (boundary) { finish_frame(); }
        } catch (const std::exception& error) {
            std::fprintf(stderr, "[GX REPLAY] incomplete: %s\n", error.what());
            if (file) { std::fclose(file); file = nullptr; }
            done = true;
        }
    }
};
}
