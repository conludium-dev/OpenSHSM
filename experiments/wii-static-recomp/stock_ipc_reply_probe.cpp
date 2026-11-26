#include <processor_adapter.h>
#include "runtime/hw/hw.h"
#include "runtime/ios_kernel.h"
#include "runtime/devices.h"
#include "stock_ipc_reply.h"
#include <array>
#include <cassert>
#include <iostream>
#include <memory>

namespace nwii::runtime {
extern MMU* g_mmu;
}
namespace nwii::runtime::hw {
int32_t ipc_dispatch_request(CPUContext&, uint32_t);
}

int main(int argc, char**) {
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    nwii::runtime::g_mmu = &ctx.mmu;
    auto& kernel = nwii::runtime::IOSKernel::get();
    kernel.init();
    kernel.register_device(nwii::runtime::devices::create_fs_device());
    auto& bus = nwii::runtime::MMIODispatcher::get();
    nwii::runtime::hw::register_ipc(bus);
    constexpr uint32_t packet = 0x80560000, path = 0x80561000;
    const char* missing = "/does-not-exist";
    for (unsigned i = 0; missing[i]; ++i) {
        ctx.mmu.write8(path + i, missing[i]);
    }
    ctx.mmu.write8(path + 15, 0);
    unsigned cases = 0;
    for (uint32_t command = 1; command <= 7; ++command) {
        for (auto fd : {0u, 7u, 23u, 0xFFFFFFFFu}) {
            for (unsigned i = 0; i < 80; ++i) {
                ctx.mmu.write8(packet - 8 + i, 0xCD);
            }
            for (unsigned i = 0; i < 16; ++i) {
                ctx.mmu.write32(packet + i * 4, 0);
            }
            ctx.mmu.write32(packet, command);
            ctx.mmu.write32(packet + 4, 0xBADC0FFE);
            ctx.mmu.write32(packet + 8, fd);
            ctx.mmu.write32(packet + 12, command == 1 ? path : 0);
            std::array<uint8_t, 64> before{};
            for (unsigned i = 0; i < before.size(); ++i) {
                before[i] = ctx.mmu.read8(packet + i);
            }
            const auto result = nwii::runtime::hw::ipc_dispatch_request(ctx, packet);
            if (argc > 1) {
                assert(ctx.mmu.read32(packet) == command && ctx.mmu.read32(packet + 8) == fd);
            } else {
                assert(ctx.mmu.read32(packet) == 8 && ctx.mmu.read32(packet + 8) == command);
            }
            assert(ctx.mmu.read32(packet + 4) == uint32_t(result));
            for (unsigned i = 12; i < 64; ++i) {
                assert(ctx.mmu.read8(packet + i) == before[i]);
            }
            assert(ctx.mmu.read8(packet - 1) == 0xCD && ctx.mmu.read8(packet + 64) == 0xCD);
            assert(bus.read32(0xCD000008) == (packet & 0x1FFFFFFF));
            bus.write32(0xCD000004, 4);
            std::cout << "REPLY " << command << ' ' << fd << ' ' << ctx.mmu.read32(packet)
                << ' ' << int32_t(ctx.mmu.read32(packet + 4)) << ' ' << ctx.mmu.read32(packet + 8) << '\n';
            ++cases;
        }
    }
    if (argc > 1) {
        std::cout << "BASELINE_REPLY_HEADER_BUG_REPRODUCED " << cases << '\n';
        return 0;
    }
    for (auto alias : {0x00560000u, 0x80560000u, 0xC0560000u, 0x10001000u, 0x90001000u, 0xD0001000u}) {
        ctx.mmu.write32(alias, 7);
        ctx.mmu.write32(alias + 4, 0xFFFFFFFA);
        ctx.mmu.write32(alias + 8, 0xFFFFFFFF);
        nwii::runtime::hw::ipc_post_reply(alias);
        assert(ctx.mmu.read32(alias) == 8 && ctx.mmu.read32(alias + 4) == 0xFFFFFFFA
            && ctx.mmu.read32(alias + 8) == 7);
        bus.write32(0xCD000004, 4);
        assert(openshsm::experiment::prepare_ipc_reply(ctx.mmu, alias));
        assert(ctx.mmu.read32(alias + 8) == 7);
    }
    for (auto invalid : {0x80560001u, 0x817FFFE0u, 0x93FFFFE0u, 0xCD000000u, 0xFFFFFFFFu}) {
        assert(!openshsm::experiment::prepare_ipc_reply(ctx.mmu, invalid));
    }
    for (auto invalid : {0u, 9u, 0xFFFFFFFFu}) {
        ctx.mmu.write32(packet, invalid);
        ctx.mmu.write32(packet + 8, 0xCDCDCDCD);
        assert(!openshsm::experiment::prepare_ipc_reply(ctx.mmu, packet));
        assert(ctx.mmu.read32(packet) == invalid && ctx.mmu.read32(packet + 8) == 0xCDCDCDCD);
    }
    std::cout << "IPC_REPLY_COMPONENT_PASS " << cases << " dispatch/6async-aliases/idempotence/8refusals\n";
}
