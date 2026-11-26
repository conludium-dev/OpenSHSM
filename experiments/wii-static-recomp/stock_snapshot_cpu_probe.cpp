#include "stock_thp_snapshot.h"
#include <cassert>
#include <iterator>
#include <memory>

namespace section = stock_thp_snapshot::cpu_section;
using Context = nwii::runtime::ProcessorContext;

static section::Identity identity() {
    section::Identity value{};
    for (unsigned i = 0; i < value.size(); ++i) { value[i] = uint8_t(i * 7 + 3); }
    return value;
}

static void seed(Context& ctx) {
    for (unsigned i = 0; i < 32; ++i) {
        ctx.gpr[i] = 0x12340000u + i;
        ctx.fpr[i] = std::bit_cast<double>(0x7FF8000000000000ull + i);
        ctx.ps1[i] = -0.25 * i;
    }
    ctx.fpr[4] = -0.0;
    ctx.fpr[5] = std::numeric_limits<double>::infinity();
    for (unsigned i = 0; i < 8; ++i) {
        ctx.gqr[i] = 0x100u + i;
        ctx.cr[i].lt = i & 1;
        ctx.cr[i].gt = i & 2;
        ctx.cr[i].eq = i & 4;
        ctx.cr[i].so = i & 1;
    }
    for (unsigned i = 0; i < 4; ++i) { ctx.sprg[i] = 0x300u + i; }
    ctx.pc = 0x80010000; ctx.lr = 0x80010004; ctx.ctr = 3; ctx.xer = 4;
    ctx.msr = 0xA000; ctx.fpscr = 6; ctx.srr0 = 0x80020000; ctx.srr1 = 8;
    ctx.hid0 = 9; ctx.hid2 = 0xA0000000; ctx.dma_u = 11; ctx.dma_l = 12;
    ctx.exception_pc = 0x80030000; ctx.reservation_addr = 0x80040000;
    ctx.dispatch_saved_ctx = 0x80050000;
    ctx.inst_count = 0x123456789ull; ctx.instructionCacheInvalidations = 0x234567890ull;
    ctx.tb_freq = 40500000;
    ctx.tb_start = std::chrono::steady_clock::now() - std::chrono::seconds(3);
    ctx.dec_value = 0x12345678; ctx.dec_written_tb = ctx.read_timebase() - 9;
    ctx.is_running = true; ctx.vblank_pending = true;
    ctx.ext_resched_pending = true; ctx.dec_irq_pending = true;
    section::Writer writer;
    section::write_registers(writer, ctx);
    section::Reader reader{writer.bytes};
    nwii::runtime::CPUContext::BackupState backup{};
    section::read_registers(reader, backup);
    backup.pc = 0x80060000;
    ctx.backup_stack.push(backup);
    backup.pc = 0x80070000;
    ctx.backup_stack.push(backup);
    ctx.callback_depth = 2;
    ctx.in_callback = true;
    ctx.queue_callback(0x80080000, 0x12345678, 0x87654321, false);
    ctx.queue_callback(0x80090000, 0xFFFFFFFF, 0, true);
    ctx.instructionImages = {{0x800A0000, {0x4E, 0x80, 0, 0x20}},
        {0x90000000, {1, 2, 3, 4, 5, 6, 7, 8}}};
}

static size_t clock_offset() {
    static const size_t offset = [] {
        Context ctx;
        section::Writer writer;
        ctx.sprg.fill(0);
        section::write_registers(writer, ctx);
        return 48 + writer.bytes.size() + 7 * 4 + 3 * 8;
    }();
    return offset;
}

static std::vector<uint8_t> stable_bytes(Context& ctx) {
    auto bytes = section::capture(ctx, identity());
    std::fill(bytes.begin() + 12, bytes.begin() + 16, 0);
    std::fill(bytes.begin() + clock_offset(), bytes.begin() + clock_offset() + 8, 0);
    return bytes;
}

static void repair_checksum(std::vector<uint8_t>& bytes) {
    const auto sum = section::checksum(std::span(bytes).subspan(16));
    for (unsigned i = 0; i < 4; ++i) { bytes[12 + i] = uint8_t(sum >> (8 * i)); }
}

static void set_word(std::vector<uint8_t>& bytes, size_t offset, uint32_t value) {
    for (unsigned i = 0; i < 4; ++i) { bytes.at(offset + i) = uint8_t(value >> (8 * i)); }
    repair_checksum(bytes);
}

static void check_loaded(Context& ctx, const std::vector<uint8_t>& bytes) {
    auto expected = bytes;
    std::fill(expected.begin() + 12, expected.begin() + 16, 0);
    std::fill(expected.begin() + clock_offset(), expected.begin() + clock_offset() + 8, 0);
    assert(stable_bytes(ctx) == expected);
    assert(ctx.backup_stack.top().pc == 0x80070000);
    auto stack = ctx.backup_stack;
    stack.pop();
    assert(stack.top().pc == 0x80060000);
    assert(ctx.pending_callbacks.front().cb_addr == 0x80080000);
    auto queue = ctx.pending_callbacks;
    queue.pop();
    assert(queue.front().is_irq && queue.front().cb_addr == 0x80090000);
    const auto remaining = ctx.read_dec();
    if (std::getenv("NWII_WALLTB")) {
        assert(remaining > 0 && remaining <= 0x12345678);
    } else {
        assert(remaining == 0x12345678 - 9);
    }
    const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now() - ctx.tb_start).count();
    assert(elapsed >= 3000 && elapsed < 10000);
}

int main(int argc, char** argv) {
    assert(argc == 3);
    auto owned = std::make_unique<Context>();
    auto& ctx = *owned;
    ctx.sprg.fill(0);
    if (std::string(argv[1]) == "write") {
        seed(ctx);
        const auto bytes = section::capture(ctx, identity());
        std::ofstream output(argv[2], std::ios::binary);
        output.write(reinterpret_cast<const char*>(bytes.data()), bytes.size());
        output.close();
        assert(output);
        std::puts("CPU_SECTION_WRITTEN");
        return 0;
    }
    std::ifstream input(argv[2], std::ios::binary);
    const std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(input)), {});
    assert(input && !bytes.empty());
    ctx.mmu.mem1[123] = 0xAB; ctx.mmu.mem2[456] = 0xCD; ctx.mmu.locked_cache[789] = 0xEF;
    clock_offset();
    auto state = section::decode(bytes, identity());
    const uint64_t saved_tb = state.elapsed_us / 1000000 * state.tb_freq
        + state.elapsed_us % 1000000 * state.tb_freq / 1000000;
    section::apply(ctx, std::move(state));
    if (std::getenv("NWII_WALLTB")) {
        const auto now = ctx.read_timebase();
        assert(now >= saved_tb && now - saved_tb < ctx.tb_freq / 100);
    }
    check_loaded(ctx, bytes);
    assert(ctx.mmu.mem1[123] == 0xAB && ctx.mmu.mem2[456] == 0xCD && ctx.mmu.locked_cache[789] == 0xEF);
    const auto before = stable_bytes(ctx);
    size_t rejected = 0;
    const auto reject = [&](std::span<const uint8_t> bad, const section::Identity& key) {
        bool refused = false;
        try { section::apply(ctx, section::decode(bad, key)); }
        catch (const std::runtime_error&) { refused = true; }
        assert(refused && stable_bytes(ctx) == before);
        ++rejected;
    };
    for (size_t i = 0; i < bytes.size(); ++i) { reject(std::span(bytes).first(i), identity()); }
    for (size_t i = 0; i < bytes.size(); ++i) {
        auto bad = bytes;
        bad[i] ^= 0x80;
        reject(bad, identity());
    }
    auto wrong_identity = identity();
    wrong_identity[0] ^= 1;
    reject(bytes, wrong_identity);
    const size_t depth = clock_offset() + 3 * 8;
    const size_t register_bytes = clock_offset() - 48 - 7 * 4 - 3 * 8;
    const size_t callbacks = depth + 32 + 2 * register_bytes;
    const size_t images = callbacks + 4 + 2 * 16;
    for (const auto [offset, value] : std::array<std::pair<size_t, uint32_t>, 15>{{
            {depth, 0}, {depth, 65}, {depth + 4, 2}, {depth + 28, 65},
            {clock_offset() - 8, 0}, {clock_offset(), 0xFFFFFFFF},
            {48 + 32 * 4 + 64 * 8 + 12 * 4, 16},
            {depth + 24, std::getenv("NWII_WALLTB") ? 0 : 1},
            {depth + 4, 0}, {callbacks, section::max_callbacks + 1},
            {callbacks + 16, 2}, {images, section::max_images + 1},
            {images + 8, 0}, {images + 8, 0xFFFFFFFF}, {images + 4, 0xFFFFFFFF}}}) {
        auto bad = bytes;
        set_word(bad, offset, value);
        if (offset == clock_offset()) { set_word(bad, offset + 4, 0xFFFFFFFF); }
        reject(bad, identity());
    }
    auto trailing = bytes;
    trailing.push_back(0);
    set_word(trailing, 8, uint32_t(trailing.size()));
    reject(trailing, identity());
    auto invalid = section::decode(bytes, identity());
    invalid.instructions.push_back({0xFFFFFFFF, {1, 2}});
    bool refused = false;
    try { section::apply(ctx, std::move(invalid)); }
    catch (const std::runtime_error&) { refused = true; }
    assert(refused && stable_bytes(ctx) == before);
    ctx.pending_cb_count = 99;
    refused = false;
    try { section::capture(ctx, identity()); }
    catch (const std::runtime_error&) { refused = true; }
    assert(refused);
    std::printf("CPU_SECTION_COLD_ROUNDTRIP_PASS rejected=%zu bytes=%zu wall=%u\n", rejected,
        bytes.size(), unsigned(std::getenv("NWII_WALLTB") != nullptr));
}
