#include <processor_adapter.h>
#include <array>
#include <bit>
#include <chrono>
#include <cstring>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>

extern "C" void func_80209D80(nwii::runtime::CPUContext&);

static void load(nwii::runtime::ProcessorContext& ctx, const char* path) {
    static_assert(std::endian::native == std::endian::little);
    std::ifstream file(path, std::ios::binary);
    auto read = [&](auto& value) {
        file.read(reinterpret_cast<char*>(&value), sizeof(value));
        if (!file) {
            throw std::runtime_error("Truncated snapshot");
        }
    };
    std::array<char, 8> magic{};
    read(magic);
    if (std::memcmp(magic.data(), "SHSMFP01", 8) != 0) {
        throw std::runtime_error("Invalid snapshot format");
    }
    read(ctx.gpr);
    read(ctx.fpr);
    read(ctx.ps1);
    read(ctx.gqr);
    read(ctx.sprg);
    for (auto& cr : ctx.cr) {
        uint32_t packed;
        read(packed);
        cr.lt = packed & 8;
        cr.gt = packed & 4;
        cr.eq = packed & 2;
        cr.so = packed & 1;
    }
    for (auto* value : {&ctx.pc, &ctx.lr, &ctx.ctr, &ctx.xer, &ctx.msr, &ctx.fpscr,
            &ctx.srr0, &ctx.srr1, &ctx.hid0, &ctx.hid2, &ctx.dma_u, &ctx.dma_l}) {
        read(*value);
    }
    read(ctx.inst_count);
    for (auto* memory : {&ctx.mmu.mem1, &ctx.mmu.mem2, &ctx.mmu.locked_cache}) {
        uint64_t size;
        read(size);
        if (!file || size != memory->size()) {
            throw std::runtime_error("Invalid snapshot bank size");
        }
        file.read(reinterpret_cast<char*>(memory->data()), size);
    }
    if (!file || file.peek() != std::char_traits<char>::eof() || ctx.pc != 0x80209D80) {
        throw std::runtime_error("Incomplete snapshot or wrong entry");
    }
}

int main(int argc, char** argv) {
    if (argc != 3) {
        return 8;
    }
    try {
        auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
        auto& ctx = *owned;
        load(ctx, argv[1]);
        const auto caller = ctx.lr;
        const auto y = ctx.gpr[4], u = ctx.gpr[5], v = ctx.gpr[6];
        if (y < 0x90000000 || uint64_t(y) + 460800 > 0x94000000
            || u - y != 307200 || v - u != 76800 || !ctx.mmu.get_ptr(v + 76799)) {
            return 9;
        }
        ctx.msr = (ctx.msr | 0x2000u) & ~0x8000u;
        if (setjmp(ctx.exception_jmp_buf) != 0) {
            std::cerr << "REPLAY_TRAP " << std::hex << ctx.pc << '\n';
            return 10;
        }
        const auto start = std::chrono::steady_clock::now();
        func_80209D80(ctx);
        const auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now() - start).count();
        if (ctx.pc != caller || ctx.gpr[3] != 0) {
            std::cerr << "REPLAY_RETURN " << std::hex << ctx.pc << ' ' << ctx.gpr[3] << '\n';
            return 11;
        }
        std::ofstream output(argv[2], std::ios::binary);
        for (const auto& [address, size] : {std::pair{y, 307200u}, std::pair{u, 76800u}, std::pair{v, 76800u}}) {
            output.write(reinterpret_cast<const char*>(ctx.mmu.get_ptr(address)), size);
        }
        if (!output) {
            return 12;
        }
        std::cout << "COMPLETE_FRAME_REPLAY_RETURN0 ns=" << ns << '\n';
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 13;
    }
}
