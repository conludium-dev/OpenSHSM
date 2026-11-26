#pragma once
#include "stock_snapshot_cpu_section.h"

namespace stock_thp_snapshot::ram_section {

using Image = std::array<std::vector<uint8_t>, 3>;
using Identity = cpu_section::Identity;
constexpr std::array<size_t, 3> bank_sizes = {
    24 * 1024 * 1024 + 8, 64 * 1024 * 1024 + 8, 256 * 1024 + 8};
constexpr size_t section_bytes = 48 + 3 * 8 + bank_sizes[0] + bank_sizes[1] + bank_sizes[2];

inline void validate(const Image& image) {
    for (size_t i = 0; i < bank_sizes.size(); ++i) {
        if (image[i].size() != bank_sizes[i]) {
            throw std::runtime_error("Invalid RAM snapshot bank size");
        }
    }
}

inline void validate_destination(const nwii::runtime::ProcessorContext& ctx) {
    if (ctx.mmu.mem1.size() != bank_sizes[0] || ctx.mmu.mem2.size() != bank_sizes[1]
        || ctx.mmu.locked_cache.size() != bank_sizes[2]) {
        throw std::runtime_error("RAM snapshot destination layout mismatch");
    }
}

inline std::vector<uint8_t> capture(const nwii::runtime::ProcessorContext& ctx, const Identity& identity) {
    validate_destination(ctx);
    cpu_section::Writer out;
    out.bytes.reserve(section_bytes);
    out.bytes.insert(out.bytes.end(), {'S', 'H', 'S', 'M', 'R', 'A', 'M', '1'});
    out.word(uint32_t(section_bytes));
    out.word(0);
    out.bytes.insert(out.bytes.end(), identity.begin(), identity.end());
    unsigned index = 0;
    for (const auto* bank : {&ctx.mmu.mem1, &ctx.mmu.mem2, &ctx.mmu.locked_cache}) {
        out.word(++index);
        out.word(uint32_t(bank->size()));
        out.bytes.insert(out.bytes.end(), bank->begin(), bank->end());
    }
    const auto sum = cpu_section::checksum(std::span(out.bytes).subspan(16));
    for (unsigned i = 0; i < 4; ++i) { out.bytes[12 + i] = uint8_t(sum >> (8 * i)); }
    return std::move(out.bytes);
}

inline Image decode(std::span<const uint8_t> bytes, const Identity& identity) {
    if (bytes.size() != section_bytes || std::memcmp(bytes.data(), "SHSMRAM1", 8) != 0) {
        throw std::runtime_error("Invalid RAM snapshot section header");
    }
    cpu_section::Reader input{bytes, 8};
    if (input.word() != bytes.size() || input.word() != cpu_section::checksum(bytes.subspan(16))) {
        throw std::runtime_error("RAM snapshot section integrity mismatch");
    }
    const auto stored_identity = input.take(identity.size());
    if (!std::equal(stored_identity.begin(), stored_identity.end(), identity.begin())) {
        throw std::runtime_error("Incompatible RAM snapshot identity");
    }
    Image image;
    for (size_t i = 0; i < bank_sizes.size(); ++i) {
        if (input.word() != i + 1 || input.word() != bank_sizes[i]) {
            throw std::runtime_error("RAM snapshot bank tag or size mismatch");
        }
        const auto data = input.take(bank_sizes[i]);
        image[i].assign(data.begin(), data.end());
    }
    return image;
}

// Requires validated banks/destination and all memory users quiesced; backing addresses stay stable.
inline void commit_locked(nwii::runtime::ProcessorContext& ctx, const Image& image) noexcept {
    std::copy(image[0].begin(), image[0].end(), ctx.mmu.mem1.begin());
    std::copy(image[1].begin(), image[1].end(), ctx.mmu.mem2.begin());
    std::copy(image[2].begin(), image[2].end(), ctx.mmu.locked_cache.begin());
}

}

namespace stock_thp_snapshot::core_section {

using Identity = cpu_section::Identity;
constexpr size_t max_bytes = 56 + cpu_section::max_bytes + ram_section::section_bytes;

struct Image {
    cpu_section::Image cpu;
    ram_section::Image ram;
};

// CPU+RAM only. The outer game snapshot must quiesce workers and stage every device before commit.
inline std::vector<uint8_t> capture(nwii::runtime::ProcessorContext& ctx, const Identity& identity) {
    const auto cpu = cpu_section::capture(ctx, identity);
    const auto ram = ram_section::capture(ctx, identity);
    cpu_section::Writer out;
    out.bytes.reserve(56 + cpu.size() + ram.size());
    out.bytes.insert(out.bytes.end(), {'S', 'H', 'S', 'M', 'C', 'R', '0', '1'});
    out.word(uint32_t(56 + cpu.size() + ram.size()));
    out.word(0);
    out.bytes.insert(out.bytes.end(), identity.begin(), identity.end());
    out.word(uint32_t(cpu.size()));
    out.bytes.insert(out.bytes.end(), cpu.begin(), cpu.end());
    out.word(uint32_t(ram.size()));
    out.bytes.insert(out.bytes.end(), ram.begin(), ram.end());
    const auto sum = cpu_section::checksum(std::span(out.bytes).subspan(16));
    for (unsigned i = 0; i < 4; ++i) { out.bytes[12 + i] = uint8_t(sum >> (8 * i)); }
    return std::move(out.bytes);
}

inline Image decode(std::span<const uint8_t> bytes, const Identity& identity) {
    if (bytes.size() < 56 || bytes.size() > max_bytes || std::memcmp(bytes.data(), "SHSMCR01", 8) != 0) {
        throw std::runtime_error("Invalid core snapshot section header");
    }
    cpu_section::Reader input{bytes, 8};
    if (input.word() != bytes.size() || input.word() != cpu_section::checksum(bytes.subspan(16))) {
        throw std::runtime_error("Core snapshot section integrity mismatch");
    }
    const auto stored_identity = input.take(identity.size());
    if (!std::equal(stored_identity.begin(), stored_identity.end(), identity.begin())) {
        throw std::runtime_error("Incompatible core snapshot identity");
    }
    const auto cpu_size = input.word();
    if (cpu_size > cpu_section::max_bytes) { throw std::runtime_error("Core CPU section too large"); }
    auto cpu = cpu_section::decode(input.take(cpu_size), identity);
    const auto ram_size = input.word();
    auto ram = ram_section::decode(input.take(ram_size), identity);
    if (input.offset != bytes.size()) { throw std::runtime_error("Trailing core snapshot data"); }
    return {std::move(cpu), std::move(ram)};
}

inline void validate_for_apply(const nwii::runtime::ProcessorContext& ctx, const Image& image) {
    cpu_section::validate_for_apply(image.cpu);
    ram_section::validate(image.ram);
    ram_section::validate_destination(ctx);
}

inline void apply(nwii::runtime::ProcessorContext& ctx, Image&& image) {
    validate_for_apply(ctx, image);
    std::lock_guard<std::mutex> lock(ctx.cb_mutex);
    ram_section::commit_locked(ctx, image.ram);
    cpu_section::commit_locked(ctx, std::move(image.cpu));
}

}
