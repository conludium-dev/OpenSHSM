#pragma once
#include <processor_adapter.h>
#include <algorithm>
#include <bit>
#include <limits>
#include <span>
#include <stdexcept>

namespace stock_thp_snapshot::cpu_section {

using Identity = std::array<uint8_t, 32>;
constexpr size_t max_bytes = 66 * 1024 * 1024;
constexpr uint32_t max_callbacks = 1024;
constexpr uint32_t max_backups = 64;
constexpr uint32_t max_images = 4096;

struct Writer {
    std::vector<uint8_t> bytes;

    void word(uint32_t value) {
        for (unsigned shift = 0; shift < 32; shift += 8) {
            bytes.push_back(uint8_t(value >> shift));
        }
    }

    void wide(uint64_t value) {
        word(uint32_t(value));
        word(uint32_t(value >> 32));
    }
};

struct Reader {
    std::span<const uint8_t> bytes;
    size_t offset = 0;

    std::span<const uint8_t> take(size_t count) {
        if (count > bytes.size() - offset) {
            throw std::runtime_error("Truncated CPU snapshot section");
        }
        const auto result = bytes.subspan(offset, count);
        offset += count;
        return result;
    }

    uint32_t word() {
        const auto data = take(4);
        return uint32_t(data[0]) | (uint32_t(data[1]) << 8)
            | (uint32_t(data[2]) << 16) | (uint32_t(data[3]) << 24);
    }

    uint64_t wide() {
        const uint64_t low = word();
        return low | (uint64_t(word()) << 32);
    }

    bool flag() {
        const auto value = word();
        if (value > 1) {
            throw std::runtime_error("Invalid CPU snapshot boolean");
        }
        return value != 0;
    }
};

inline uint32_t checksum(std::span<const uint8_t> bytes) {
    uint32_t value = 2166136261u;
    for (const auto byte : bytes) {
        value = (value ^ byte) * 16777619u;
    }
    return value;
}

template<class Registers>
inline void write_registers(Writer& out, const Registers& state) {
    for (auto value : state.gpr) { out.word(value); }
    for (auto value : state.fpr) { out.wide(std::bit_cast<uint64_t>(value)); }
    for (auto value : state.ps1) { out.wide(std::bit_cast<uint64_t>(value)); }
    for (auto value : state.gqr) { out.word(value); }
    for (auto value : state.sprg) { out.word(value); }
    for (const auto& field : state.cr) {
        out.word((uint32_t(field.lt) << 3) | (uint32_t(field.gt) << 2)
            | (uint32_t(field.eq) << 1) | uint32_t(field.so));
    }
    for (auto value : {state.pc, state.lr, state.ctr, state.xer, state.msr,
            state.fpscr, state.srr0, state.srr1}) {
        out.word(value);
    }
}

template<class Registers>
inline void read_registers(Reader& input, Registers& state) {
    for (auto& value : state.gpr) { value = input.word(); }
    for (auto& value : state.fpr) { value = std::bit_cast<double>(input.wide()); }
    for (auto& value : state.ps1) { value = std::bit_cast<double>(input.wide()); }
    for (auto& value : state.gqr) { value = input.word(); }
    for (auto& value : state.sprg) { value = input.word(); }
    for (auto& field : state.cr) {
        const auto value = input.word();
        if (value > 15) {
            throw std::runtime_error("Invalid CPU snapshot condition field");
        }
        field.lt = value & 8;
        field.gt = value & 4;
        field.eq = value & 2;
        field.so = value & 1;
    }
    for (auto* value : {&state.pc, &state.lr, &state.ctr, &state.xer, &state.msr,
            &state.fpscr, &state.srr0, &state.srr1}) {
        *value = input.word();
    }
}

struct Image {
    nwii::runtime::CPUContext::BackupState registers{};
    std::stack<nwii::runtime::CPUContext::BackupState> backups;
    std::queue<nwii::runtime::CallbackInfo> callbacks;
    std::vector<std::pair<uint32_t, std::vector<uint8_t>>> instructions;
    std::array<uint32_t, 7> words{};
    uint64_t inst_count = 0;
    uint64_t invalidations = 0;
    uint64_t tb_freq = 0;
    uint64_t elapsed_us = 0;
    uint64_t dec_value = 0;
    uint64_t dec_written_tb = 0;
    uint32_t depth = 0;
    bool in_callback = false;
    bool running = false;
    bool vblank = false;
    bool reschedule = false;
    bool dec_irq = false;
    bool wall = false;
};

inline void validate(const Image& state) {
    if (state.depth > max_backups || state.depth != state.backups.size()
        || state.in_callback != (state.depth != 0)
        || state.callbacks.size() > max_callbacks || state.instructions.size() > max_images
        || state.tb_freq == 0 || state.tb_freq > 1000000000
        || state.elapsed_us > 3155760000000000ull) {
        throw std::runtime_error("Invalid CPU snapshot state limits");
    }
    size_t total = 0;
    for (const auto& [address, data] : state.instructions) {
        total += data.size();
        if (data.empty() || total > 64 * 1024 * 1024
            || uint64_t(address) + data.size() > 0x100000000ull) {
            throw std::runtime_error("Invalid CPU snapshot instruction image");
        }
    }
}

// Caller must quiesce guest dispatch and every state producer before capture/apply.
// This section excludes RAM and devices; it is not an independently loadable game state.
// The outer snapshot must validate all sections before committing any of them.
inline std::vector<uint8_t> capture(nwii::runtime::ProcessorContext& ctx, const Identity& identity) {
    Image state;
    {
        std::lock_guard<std::mutex> lock(ctx.cb_mutex);
        state.callbacks = ctx.pending_callbacks;
        if (ctx.pending_cb_count.load() < 0
            || size_t(ctx.pending_cb_count.load()) != state.callbacks.size()) {
            throw std::runtime_error("CPU snapshot callback count mismatch");
        }
    }
    state.backups = ctx.backup_stack;
    state.instructions = ctx.instructionImages;
    state.depth = uint32_t(ctx.callback_depth);
    state.in_callback = ctx.in_callback;
    state.tb_freq = ctx.tb_freq;
    const auto elapsed = std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::steady_clock::now() - ctx.tb_start).count();
    if (elapsed < 0) {
        throw std::runtime_error("CPU snapshot timebase starts in future");
    }
    state.elapsed_us = uint64_t(elapsed);
    validate(state);
    Writer out;
    out.bytes.insert(out.bytes.end(), {'S', 'H', 'S', 'M', 'C', 'P', 'U', '1'});
    out.word(0);
    out.word(0);
    out.bytes.insert(out.bytes.end(), identity.begin(), identity.end());
    write_registers(out, ctx);
    for (auto value : {ctx.hid0, ctx.hid2, ctx.dma_u, ctx.dma_l, ctx.exception_pc,
            ctx.reservation_addr, ctx.dispatch_saved_ctx}) {
        out.word(value);
    }
    for (auto value : {ctx.inst_count, ctx.instructionCacheInvalidations, ctx.tb_freq,
            state.elapsed_us, ctx.dec_value, ctx.dec_written_tb}) {
        out.wide(value);
    }
    out.word(state.depth);
    for (bool value : {ctx.in_callback, ctx.is_running.load(), ctx.vblank_pending.load(),
            ctx.ext_resched_pending, ctx.dec_irq_pending, std::getenv("NWII_WALLTB") != nullptr}) {
        out.word(value);
    }
    out.word(uint32_t(state.backups.size()));
    while (!state.backups.empty()) {
        write_registers(out, state.backups.top());
        state.backups.pop();
    }
    out.word(uint32_t(state.callbacks.size()));
    while (!state.callbacks.empty()) {
        const auto& cb = state.callbacks.front();
        out.word(cb.cb_addr);
        out.word(cb.arg1);
        out.word(cb.arg2);
        out.word(cb.is_irq);
        state.callbacks.pop();
    }
    out.word(uint32_t(state.instructions.size()));
    for (const auto& [address, data] : state.instructions) {
        out.word(address);
        out.word(uint32_t(data.size()));
        out.bytes.insert(out.bytes.end(), data.begin(), data.end());
    }
    if (out.bytes.size() > max_bytes) {
        throw std::runtime_error("CPU snapshot section too large");
    }
    const uint32_t size = uint32_t(out.bytes.size());
    const uint32_t sum = checksum(std::span(out.bytes).subspan(16));
    for (unsigned i = 0; i < 4; ++i) {
        out.bytes[8 + i] = uint8_t(size >> (i * 8));
        out.bytes[12 + i] = uint8_t(sum >> (i * 8));
    }
    return std::move(out.bytes);
}

inline Image decode(std::span<const uint8_t> bytes, const Identity& identity) {
    if (bytes.size() < 48 || bytes.size() > max_bytes
        || std::memcmp(bytes.data(), "SHSMCPU1", 8) != 0) {
        throw std::runtime_error("Invalid CPU snapshot section header");
    }
    Reader input{bytes, 8};
    if (input.word() != bytes.size() || input.word() != checksum(bytes.subspan(16))) {
        throw std::runtime_error("CPU snapshot size or checksum mismatch");
    }
    const auto stored_identity = input.take(identity.size());
    if (!std::equal(stored_identity.begin(), stored_identity.end(), identity.begin())) {
        throw std::runtime_error("Incompatible CPU snapshot identity");
    }
    Image state;
    read_registers(input, state.registers);
    for (auto& value : state.words) { value = input.word(); }
    state.inst_count = input.wide();
    state.invalidations = input.wide();
    state.tb_freq = input.wide();
    state.elapsed_us = input.wide();
    state.dec_value = input.wide();
    state.dec_written_tb = input.wide();
    state.depth = input.word();
    state.in_callback = input.flag();
    state.running = input.flag();
    state.vblank = input.flag();
    state.reschedule = input.flag();
    state.dec_irq = input.flag();
    state.wall = input.flag();
    auto count = input.word();
    if (count > max_backups) { throw std::runtime_error("Too many CPU snapshot backups"); }
    std::vector<nwii::runtime::CPUContext::BackupState> backups(count);
    for (auto& backup : backups) { read_registers(input, backup); }
    for (auto it = backups.rbegin(); it != backups.rend(); ++it) { state.backups.push(*it); }
    count = input.word();
    if (count > max_callbacks) { throw std::runtime_error("Too many CPU snapshot callbacks"); }
    for (uint32_t i = 0; i < count; ++i) {
        const auto address = input.word(), arg1 = input.word(), arg2 = input.word();
        const bool irq = input.flag();
        state.callbacks.push({address, arg1, arg2, irq});
    }
    count = input.word();
    if (count > max_images) { throw std::runtime_error("Too many CPU snapshot instruction images"); }
    size_t image_bytes = 0;
    for (uint32_t i = 0; i < count; ++i) {
        const auto address = input.word(), size = input.word();
        if (size == 0 || size > 64 * 1024 * 1024 - image_bytes
            || uint64_t(address) + size > 0x100000000ull) {
            throw std::runtime_error("Invalid CPU snapshot instruction image size");
        }
        image_bytes += size;
        const auto data = input.take(size);
        state.instructions.emplace_back(address, std::vector<uint8_t>(data.begin(), data.end()));
    }
    if (input.offset != bytes.size()) { throw std::runtime_error("Trailing CPU snapshot data"); }
    validate(state);
    return state;
}

inline void validate_for_apply(const Image& state) {
    validate(state);
    if (state.wall != (std::getenv("NWII_WALLTB") != nullptr)) {
        throw std::runtime_error("CPU snapshot timebase mode mismatch");
    }
}

// Requires validated state, a quiesced runtime and the caller holding ctx.cb_mutex.
inline void commit_locked(nwii::runtime::ProcessorContext& ctx, Image&& state) noexcept {
    const auto anchor = std::chrono::steady_clock::now()
        - std::chrono::microseconds(state.elapsed_us);
    const auto& saved = state.registers;
    ctx.gpr = saved.gpr; ctx.fpr = saved.fpr; ctx.ps1 = saved.ps1;
    ctx.cr = saved.cr; ctx.gqr = saved.gqr; ctx.sprg = saved.sprg;
    ctx.pc = saved.pc; ctx.lr = saved.lr; ctx.ctr = saved.ctr; ctx.xer = saved.xer;
    ctx.msr = saved.msr; ctx.fpscr = saved.fpscr; ctx.srr0 = saved.srr0; ctx.srr1 = saved.srr1;
    ctx.hid0 = state.words[0]; ctx.hid2 = state.words[1]; ctx.dma_u = state.words[2];
    ctx.dma_l = state.words[3]; ctx.exception_pc = state.words[4];
    ctx.reservation_addr = state.words[5]; ctx.dispatch_saved_ctx = state.words[6];
    ctx.inst_count = state.inst_count;
    ctx.instructionCacheInvalidations = state.invalidations;
    ctx.tb_freq = state.tb_freq; ctx.tb_start = anchor;
    ctx.dec_value = state.dec_value; ctx.dec_written_tb = state.dec_written_tb;
    ctx.callback_depth = int(state.depth); ctx.in_callback = state.in_callback;
    ctx.is_running.store(state.running); ctx.vblank_pending.store(state.vblank);
    ctx.ext_resched_pending = state.reschedule; ctx.dec_irq_pending = state.dec_irq;
    ctx.backup_stack.swap(state.backups);
    ctx.pending_callbacks.swap(state.callbacks);
    ctx.pending_cb_count.store(int(ctx.pending_callbacks.size()));
    ctx.instructionImages.swap(state.instructions);
}

inline void apply(nwii::runtime::ProcessorContext& ctx, Image&& state) {
    validate_for_apply(state);
    std::lock_guard<std::mutex> lock(ctx.cb_mutex);
    commit_locked(ctx, std::move(state));
}

}
