#include <processor_adapter.h>
#include "runtime/devices.h"
#include "runtime/ios_kernel.h"
#include "runtime/config.h"
#include "stock_sysconf.h"
#include <fstream>
#include <memory>

extern "C" void func_80247AC0(nwii::runtime::CPUContext& ctx);
extern "C" void func_80248DE0(nwii::runtime::CPUContext& ctx);

int main(int argc, char** argv) {
    if (argc != 3) {
        return 2;
    }
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    nwii::runtime::Config::get().game_id = "R5WEA4";
    auto& kernel = nwii::runtime::IOSKernel::get();
    kernel.init();
    kernel.register_device(nwii::runtime::devices::create_fs_device());
    constexpr uint32_t buffer = 0x804b31a0;
    const auto fd = kernel.open(ctx, "/shared2/sys/SYSCONF", 1);
    if (fd < 0 || kernel.read(ctx, fd, buffer, 0x4000) != 0x4000 || kernel.close(ctx, fd) != 0) {
        return 3;
    }
    std::vector<uint8_t> read(0x4000);
    for (unsigned i = 0; i < read.size(); ++i) {
        read[i] = ctx.mmu.read8(buffer + i);
    }
    if (read != openshsm::experiment::wii_sysconf_aspect(true)) {
        return 4;
    }
    std::ofstream output(argv[2], std::ios::binary);
    output.write(reinterpret_cast<const char*>(read.data()), read.size());
    output.close();
    if (!output) {
        return 5;
    }
    std::ifstream stream(argv[1], std::ios::binary);
    std::vector<uint8_t> dol(std::istreambuf_iterator<char>(stream), {});
    if (dol.size() < 256) {
        return 6;
    }
    const auto word = [&](unsigned offset) {
        return uint32_t(dol.at(offset)) << 24 | uint32_t(dol.at(offset + 1)) << 16 |
            uint32_t(dol.at(offset + 2)) << 8 | uint32_t(dol.at(offset + 3));
    };
    for (unsigned section = 0; section < 18; ++section) {
        const uint32_t offset = word(section * 4);
        const uint32_t address = word((18 + section) * 4);
        const uint32_t size = word((36 + section) * 4);
        if (uint64_t(offset) + size > dol.size()) {
            return 7;
        }
        for (uint32_t i = 0; i < size; ++i) {
            ctx.mmu.write8(address + i, dol[offset + i]);
        }
    }
    for (unsigned i = 0; i < read.size(); ++i) {
        ctx.mmu.write8(buffer + i, read[i]);
    }
    for (unsigned i = 0; i < 16; ++i) {
        ctx.mmu.write8(0x8052e720 - 14100 + i, 0);
    }
    ctx.gpr[1] = 0x80010000;
    ctx.gpr[13] = 0x8052e720;
    ctx.lr = 0x80008000;
    ctx.pc = 0x80247ac0;
    ctx.gpr[3] = buffer;
    ctx.gpr[4] = 0x4000;
    func_80247AC0(ctx);
    if (ctx.pc != 0x80008000 || ctx.gpr[3] != 0 || ctx.gpr[1] != 0x80010000) {
        std::fprintf(stderr, "parser pc=%08x result=%u sp=%08x\n", ctx.pc, ctx.gpr[3], ctx.gpr[1]);
        return 8;
    }
    ctx.lr = 0x80008000;
    ctx.pc = 0x80248de0;
    func_80248DE0(ctx);
    if (ctx.pc != 0x80008000 || ctx.gpr[3] != 1 || ctx.gpr[1] != 0x80010000) {
        return 9;
    }
    std::puts("EXISTING_FS_NATIVE_ORIGINAL_PARSER_WIDESCREEN_BYTE_PASS");
}
