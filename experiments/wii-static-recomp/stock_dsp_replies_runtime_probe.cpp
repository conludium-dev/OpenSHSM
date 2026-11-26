#include <processor_adapter.h>
#include "hw_dsp.cpp"
#include <iostream>

int main() {
    using namespace nwii::runtime;
    auto owned = std::make_unique<ProcessorContext>();
    auto& ctx = *owned;
    g_mmu = &ctx.mmu;
    g_ctx_ptr = &ctx;
    ctx.tb_freq = 60750000;
    EventScheduler::get().reset();
    auto& mmio = MMIODispatcher::get();
    mmio.clear();
    hw::register_dsp(mmio);
    mmio.write16(0xcc00500a, 0x0100);
    (void)mmio.read16(0xcc005004);
    (void)mmio.read16(0xcc005006);
    hw::dsp_queue_reply(4);
    hw::dsp_queue_reply(2);
    const auto read = [&]() {
        return uint32_t(mmio.read16(0xcc005004)) << 16 | mmio.read16(0xcc005006);
    };
    if (read() != 0xdcd10004 || !(mmio.read16(0xcc00500a) & 0x80) ||
        read() != 0xdcd10002 || (mmio.read16(0xcc00500a) & 0x80) ||
        mmio.read16(0xcc005004) != 0x5cd1) {
        return 2;
    }
    for (unsigned index = 0; index < 32; ++index) {
        hw::dsp_queue_reply(uint16_t(index));
    }
    for (unsigned index = 0; index < 32; ++index) {
        if (read() != (0xdcd10000u | index)) {
            return 3;
        }
    }
    mmio.write16(0xcc00500a, 0x0800);
    hw::dsp_queue_reply(4);
    hw::dsp_queue_reply(2);
    if (mmio.read16(0xcc005004) != 0xdcd1) {
        return 4;
    }
    mmio.write16(0xcc00500a, 0x0804);
    if (mmio.read16(0xcc005006) != 4 || mmio.read16(0xcc005004) != 0x5cd1) {
        return 5;
    }
    mmio.write16(0xcc00500a, 0x0800);
    if (read() != 0xdcd10004 || read() != 0xdcd10002) {
        return 6;
    }
    EventScheduler::get().reset();
    g_mmu = nullptr;
    g_ctx_ptr = nullptr;
    std::cout << "CURRENT_DSP_ORDERED_REPLY_MMIO_PASS SYNC4,YIELD2;32 replies;next IRQ retained;INIT0800 distinct HALT0004\n";
}
