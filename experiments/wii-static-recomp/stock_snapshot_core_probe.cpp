#include "stock_thp_snapshot.h"
#include <cassert>
#include <iterator>
#include <memory>

namespace cpu = stock_thp_snapshot::cpu_section;
namespace ram = stock_thp_snapshot::ram_section;
namespace core = stock_thp_snapshot::core_section;
using Context = nwii::runtime::ProcessorContext;

static cpu::Identity identity() {
    cpu::Identity id{};
    for (size_t i = 0; i < id.size(); ++i) { id[i] = uint8_t(19 * i + 5); }
    return id;
}

static std::vector<uint8_t> cpu_bytes(Context& ctx) {
    auto bytes = cpu::capture(ctx, identity());
    cpu::Writer writer;
    cpu::write_registers(writer, ctx);
    const size_t time = 48 + writer.bytes.size() + 7 * 4 + 3 * 8;
    std::fill(bytes.begin() + time, bytes.begin() + time + 8, 0);
    std::fill(bytes.begin() + 12, bytes.begin() + 16, 0);
    return bytes;
}

static void seed(Context& ctx) {
    ctx.sprg.fill(0);
    ctx.gpr[3] = 0x12345678;
    ctx.pc = 0x8000B5DC;
    ctx.lr = 0x8009BB80;
    ctx.inst_count = 0x123456789ull;
    ctx.fpr[4] = std::bit_cast<double>(0x7FF8000000000012ull);
    ctx.ps1[5] = -0.0;
    ctx.hid2 = 0xA0000000;
    ctx.tb_start = std::chrono::steady_clock::now() - std::chrono::seconds(3);
    ctx.dec_written_tb = ctx.read_timebase();
    ctx.queue_callback(0x80020000, 0x87654321, 19, true);
    unsigned tag = 0;
    for (auto* bank : {&ctx.mmu.mem1, &ctx.mmu.mem2, &ctx.mmu.locked_cache}) {
        ++tag;
        for (size_t i = 0; i < bank->size(); ++i) { (*bank)[i] = uint8_t(i * 131 + (i >> 17) + tag); }
    }
}

static void repair(std::vector<uint8_t>& bytes, size_t start, size_t size) {
    const auto sum = cpu::checksum(std::span(bytes).subspan(start + 16, size - 16));
    for (unsigned i = 0; i < 4; ++i) { bytes[start + 12 + i] = uint8_t(sum >> (8 * i)); }
}

static void word(std::vector<uint8_t>& bytes, size_t offset, uint32_t value) {
    for (unsigned i = 0; i < 4; ++i) { bytes.at(offset + i) = uint8_t(value >> (8 * i)); }
}

int main(int argc, char** argv) {
    assert(argc == 3);
    auto owned = std::make_unique<Context>();
    auto& ctx = *owned;
    ctx.sprg.fill(0);
    if (std::string(argv[1]) == "write") {
        seed(ctx);
        const auto bytes = core::capture(ctx, identity());
        std::ofstream output(argv[2], std::ios::binary);
        output.write(reinterpret_cast<const char*>(bytes.data()), bytes.size());
        output.close();
        assert(output);
        std::printf("CORE_SECTION_WRITTEN bytes=%zu\n", bytes.size());
        return 0;
    }
    std::ifstream input(argv[2], std::ios::binary | std::ios::ate);
    assert(input && input.tellg() > 0 && uint64_t(input.tellg()) <= core::max_bytes);
    std::vector<uint8_t> bytes(size_t(input.tellg()));
    input.seekg(0);
    input.read(reinterpret_cast<char*>(bytes.data()), bytes.size());
    assert(input);
    const std::array<const uint8_t*, 3> addresses = {
        ctx.mmu.mem1.data(), ctx.mmu.mem2.data(), ctx.mmu.locked_cache.data()};
    auto state = core::decode(bytes, identity());
    core::apply(ctx, std::move(state));
    assert(ctx.mmu.mem1.data() == addresses[0] && ctx.mmu.mem2.data() == addresses[1]
        && ctx.mmu.locked_cache.data() == addresses[2]);
    assert(ctx.gpr[3] == 0x12345678 && ctx.pc == 0x8000B5DC && ctx.hid2 == 0xA0000000);
    assert(ctx.pending_cb_count == 1 && ctx.pending_callbacks.front().is_irq);
    assert(std::bit_cast<uint64_t>(ctx.fpr[4]) == 0x7FF8000000000012ull);
    assert(std::bit_cast<uint64_t>(ctx.ps1[5]) == 0x8000000000000000ull);
    unsigned tag = 0;
    for (const auto* bank : {&ctx.mmu.mem1, &ctx.mmu.mem2, &ctx.mmu.locked_cache}) {
        ++tag;
        for (size_t i = 0; i < bank->size(); ++i) { assert((*bank)[i] == uint8_t(i * 131 + (i >> 17) + tag)); }
    }
    const auto before = cpu_bytes(ctx);
    size_t rejected = 0;
    const auto unchanged = [&] {
        assert(cpu_bytes(ctx) == before);
        assert(ctx.mmu.mem1 == state.ram[0] && ctx.mmu.mem2 == state.ram[1]
            && ctx.mmu.locked_cache == state.ram[2]);
        assert(ctx.mmu.mem1.data() == addresses[0] && ctx.mmu.mem2.data() == addresses[1]
            && ctx.mmu.locked_cache.data() == addresses[2]);
    };
    const auto reject = [&](std::span<const uint8_t> bad, const cpu::Identity& key) {
        bool refused = false;
        try { core::apply(ctx, core::decode(bad, key)); }
        catch (const std::runtime_error&) { refused = true; }
        assert(refused);
        unchanged();
        ++rejected;
    };
    cpu::Reader reader{bytes, 48};
    const auto cpu_size = reader.word();
    reader.take(cpu_size);
    const size_t ram_size_offset = reader.offset;
    const auto ram_size = reader.word();
    const size_t ram_start = reader.offset;
    for (size_t at : {size_t(0), size_t(15), size_t(47), size_t(51), ram_size_offset,
            ram_start + 48, ram_start + 56 + ram::bank_sizes[0], bytes.size() - 1}) {
        reject(std::span(bytes).first(at), identity());
    }
    auto bad = bytes;
    for (size_t at : {size_t(0), size_t(12), size_t(32), size_t(51),
            ram_start, ram_start + 64, ram_start + 56 + ram::bank_sizes[0] - 1, bytes.size() - 1}) {
        bad[at] ^= 0x80;
        reject(bad, identity());
        bad[at] ^= 0x80;
    }
    auto wrong = identity(); wrong[0] ^= 1;
    reject(bytes, wrong);
    for (size_t at : {size_t(48), ram_size_offset, ram_start + 48, ram_start + 52,
            ram_start + 56 + ram::bank_sizes[0] + 4}) {
        const auto saved = std::array<uint8_t, 4>{bad[at], bad[at + 1], bad[at + 2], bad[at + 3]};
        word(bad, at, 0xFFFFFFFF);
        repair(bad, ram_start, ram_size);
        repair(bad, 0, bad.size());
        reject(bad, identity());
        std::copy(saved.begin(), saved.end(), bad.begin() + at);
        repair(bad, ram_start, ram_size);
        repair(bad, 0, bad.size());
    }
    for (const auto target : {size_t(52), ram_start}) {
        bad[target + 16] ^= 1;
        const auto size = target == 52 ? cpu_size : ram_size;
        repair(bad, target, size);
        repair(bad, 0, bad.size());
        reject(bad, identity());
        bad[target + 16] ^= 1;
        repair(bad, target, size);
        repair(bad, 0, bad.size());
    }
    auto invalid = core::decode(bytes, identity());
    invalid.cpu.wall = !invalid.cpu.wall;
    bool refused = false;
    try { core::apply(ctx, std::move(invalid)); }
    catch (const std::runtime_error&) { refused = true; }
    assert(refused); unchanged();
    invalid.cpu.wall = !invalid.cpu.wall;
    invalid.ram[2].pop_back();
    refused = false;
    try { core::apply(ctx, std::move(invalid)); }
    catch (const std::runtime_error&) { refused = true; }
    assert(refused); unchanged();
    const auto tail = ctx.mmu.mem1.back();
    ctx.mmu.mem1.pop_back();
    refused = false;
    try { core::apply(ctx, core::decode(bytes, identity())); }
    catch (const std::runtime_error&) { refused = true; }
    assert(refused && cpu_bytes(ctx) == before && ctx.mmu.mem1.data() == addresses[0]);
    ctx.mmu.mem1.push_back(tail);
    unchanged();
    std::printf("CORE_SECTION_COLD_ROUNDTRIP_PASS rejected=%zu bytes=%zu wall=%u stableRamPointers=1\n",
        rejected + 3, bytes.size(), unsigned(std::getenv("NWII_WALLTB") != nullptr));
}
