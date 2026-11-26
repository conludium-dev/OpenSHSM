#define main unused_quantization_main
#include "stock_quantization_contract.cpp"
#undef main
#include "stock_dsp_capture.h"
#include <memory>

static int pb_fixture(const char* firmware_path, const char* mode) {
    auto owned = std::make_unique<nwii::runtime::CPUContext>();
    auto& ctx = *owned;
    constexpr uint32_t firmware = 0x80004000, list = 0x80007000, first = 0x80008000;
    std::array<uint8_t, 8192> image{};
    FILE* file = std::fopen(firmware_path, "rb");
    if (!file) {
        return 10;
    }
    const size_t read = std::fread(image.data(), 1, image.size(), file);
    const bool closed = std::fclose(file) == 0;
    if (read != image.size() || !closed) {
        return 11;
    }
    if (std::string(mode) == "unsupported") {
        image[0] ^= 1;
    }
    for (size_t index = 0; index < image.size(); ++index) {
        ctx.mmu.write8(firmware + index, image[index]);
    }
    for (unsigned node = 0; node < 17; ++node) {
        const uint32_t address = first + node * 320;
        ctx.mmu.write32(address, node == 16 ? 0 : address + 320);
        ctx.mmu.write16(address + 16, 1);
    }
    const auto initial1 = ctx.mmu.mem1;
    const auto initial2 = ctx.mmu.mem2;
    auto& observer = openshsm::experiment::dsp_command_capture;
    observer.mail(ctx, 0x80f3a001, 0, 0);
    observer.mail(ctx, firmware, 0, 0);
    observer.mail(ctx, 0x80f3c002, 0, 0);
    observer.mail(ctx, 0, 0, 0);
    observer.mail(ctx, 0x80f3a002, 0, 0);
    observer.mail(ctx, std::string(mode) == "badsize" ? 8193 : 8192, 0, 0);
    if (ctx.mmu.mem1 != initial1 || ctx.mmu.mem2 != initial2) {
        return 12;
    }
    if (std::string(mode) == "active") {
        for (unsigned node = 0; node < 257; ++node) {
            const uint32_t address = first + node * 320;
            ctx.mmu.write32(address, node == 256 ? 0 : address + 320);
            ctx.mmu.write16(address + 16, 0);
        }
        ctx.mmu.write16(list, 4);
        ctx.mmu.write32(list + 2, first);
        ctx.mmu.write16(list + 6, 14);
        for (unsigned attempt = 0; attempt < 7; ++attempt) {
            if (attempt == 5) {
                ctx.mmu.write16(first + 32 * 320 + 16, 1);
                ctx.mmu.write32(first + 33 * 320, 0);
            } else if (attempt == 6) {
                ctx.mmu.write16(first + 32 * 320 + 16, 0);
                ctx.mmu.write16(first + 33 * 320 + 16, 1);
            }
            const auto before1 = ctx.mmu.mem1;
            const auto before2 = ctx.mmu.mem2;
            observer.mail(ctx, 0xbabe0004, 0, 0);
            observer.mail(ctx, list, 0, 1);
            if (ctx.mmu.mem1 != before1 || ctx.mmu.mem2 != before2) {
                return 14;
            }
        }
        std::puts("BOUNDED_DSP_CAPTURE_RAM_STATE_PRESERVATION_PASS");
        return 0;
    }
    for (unsigned job = 0; job < 6; ++job) {
        if (job == 0) {
            ctx.mmu.write32(first + 320, 0);
        } else if (job == 1) {
            ctx.mmu.write32(first + 320, 0xc0008000);
        } else {
            ctx.mmu.write32(first + 320, first + 640);
        }
        ctx.mmu.write16(list, 4);
        ctx.mmu.write32(list + 2, job == 2 ? 0xcc005000 : first);
        ctx.mmu.write16(list + 6, 14);
        const auto before1 = ctx.mmu.mem1;
        const auto before2 = ctx.mmu.mem2;
        observer.mail(ctx, 0xbabe0004, 0, 0);
        observer.mail(ctx, list, 0, 1);
        if (ctx.mmu.mem1 != before1 || ctx.mmu.mem2 != before2 || ctx.inst_count || ctx.pc) {
            return 13;
        }
    }
    std::puts("BOUNDED_DSP_CAPTURE_RAM_STATE_PRESERVATION_PASS");
    return 0;
}

int main(int argc, char** argv) {
    if (argc == 3) {
        return pb_fixture(argv[1], argv[2]);
    }
    auto owned = std::make_unique<nwii::runtime::CPUContext>();
    auto& ctx = *owned;
    constexpr uint32_t base = 0x80004000;
    for (unsigned i = 0; i < 8192; ++i) {
        ctx.mmu.write8(base + i, uint8_t(i));
    }
    ctx.pc = 0x80236c60;
    ctx.inst_count = 17;
    ctx.gpr[3] = 0x12345678;
    const auto before1 = ctx.mmu.mem1;
    const auto before2 = ctx.mmu.mem2;
    auto& observer = openshsm::experiment::dsp_command_capture;
    for (unsigned i = 0; i < 150000; ++i) {
        observer.mail(ctx, 0xbabe0080, 0x0100, 0);
        observer.mail(ctx, i == 0 ? 0xfffffffcu : base, 0x0100, 1);
    }
    observer.dma(ctx, base, 0, 8193, true);
    observer.dma(ctx, base, 0, 8193, false);
    observer.dma(ctx, 0xfffffffcu, 0, 64, false);
    for (unsigned i = 0; i < 100; ++i) {
        observer.dma(ctx, base, i * 32, 32, false);
    }
    for (uint32_t address : {0x80004000u, 0xc0004000u, 0x00004000u}) {
        const uint8_t* ptr = openshsm::experiment::dsp_capture_ram(ctx, address, 256);
        if (!ptr || ptr[255] != 255) {
            return 2;
        }
    }
    const uint32_t end = uint32_t(ctx.mmu.mem1.size() - 8);
    if (openshsm::experiment::dsp_capture_ram(ctx, end - 128, 256) ||
            openshsm::experiment::dsp_capture_ram(ctx, 0xcc005000, 2) ||
            openshsm::experiment::dsp_capture_ram(ctx, 0xfffffffcu, 256) ||
            !openshsm::experiment::dsp_capture_ram(ctx, 0x90004000, 256) ||
            !openshsm::experiment::dsp_capture_ram(ctx, 0xd0004000, 256)) {
        return 3;
    }
    if (ctx.mmu.mem1 != before1 || ctx.mmu.mem2 != before2 || ctx.pc != 0x80236c60 ||
            ctx.inst_count != 17 || ctx.gpr[3] != 0x12345678) {
        return 4;
    }
    std::puts("BOUNDED_DSP_CAPTURE_RAM_STATE_PRESERVATION_PASS");
}
