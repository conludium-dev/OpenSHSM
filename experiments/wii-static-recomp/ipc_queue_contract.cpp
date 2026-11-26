#include "runtime/hw/hw.h"
#include "runtime/cpu_context.h"
#include <cassert>
#include <iostream>

namespace nwii::runtime {
CPUContext* g_ctx_ptr = nullptr;
MMU* g_mmu = nullptr;
int g_ipc_interrupt_delay = 0;
}

namespace nwii::runtime::hw {
std::atomic<uint32_t> pi_intsr = 0;
}

static int mode = 0;
extern "C" int32_t handle_ios_ipc(nwii::runtime::CPUContext&, uint32_t) {
    if (mode == 0) {
        return -0x70000001;
    }
    nwii::runtime::hw::ipc_post_reply(0x90001200);
    return 0;
}

int main() {
    using namespace nwii::runtime;
    CPUContext context{};
    g_ctx_ptr = &context;
    auto& bus = MMIODispatcher::get();
    hw::register_ipc(bus);
    bus.write32(0xCD000000, 0x80001000);
    bus.write32(0xCD000004, 0x31);
    assert(bus.read32(0xCD000004) == 0x32);
    assert(bus.read32(0xCD000008) == 0);
    bus.write32(0xCD000004, 0x32);
    mode = 1;
    bus.write32(0xCD000000, 0x80002000);
    bus.write32(0xCD000004, 0x31);
    assert(bus.read32(0xCD000004) == 0x36);
    assert(bus.read32(0xCD000008) == 0x10001200);
    hw::ipc_post_reply(0x80003000);
    assert(bus.read32(0xCD000008) == 0x10001200);
    bus.write32(0xCD000004, 0x36);
    assert(bus.read32(0xCD000008) == 0x2000);
    assert(bus.read32(0xCD000004) == 0x34);
    bus.write32(0xCD000004, 0x34);
    assert(bus.read32(0xCD000008) == 0x3000);
    bus.write32(0xCD000004, 0x34);
    assert(bus.read32(0xCD000004) == 0x30);
    bus.write32(0xCD000004, 0);
    hw::ipc_post_reply(0x80004000);
    assert(bus.read32(0xCD000004) == 0x04);
    assert(bus.read32(0x0D000008) == 0x4000);
    bus.write32(0x0D000004, 0x04);
    assert(bus.read32(0xCD000004) == 0);
    std::cout << "PASS pending exclusion, nested completion FIFO, mailbox ownership, W1C, enables and mirror\n";
}
