#define main unused_event_order_main
#include "ipc_event_order_probe.cpp"
#undef main
#include "ipc_open_packet.h"
#include "runtime/devices.h"
#include <cstring>
#include <iomanip>

int main(int argc, char** argv) {
    if (argc != 2) { return 2; }
    if (std::string(argv[1]) != "startup" && std::string(argv[1]) != "ix1") { return 2; }
    const uint32_t send = std::string(argv[1]) == "startup" ? 0x31 : 0x39;
    CPUContext context;
    context.msr = 0x2032;
    IOSKernel::get().init();
    IOSKernel::get().register_device(devices::create_stm_device());
    auto& dispatcher = MMIODispatcher::get();
    hw::register_ipc(dispatcher);
    for (unsigned index = 0; index < 16; ++index) {
        EventScheduler::get().reset();
        const uint32_t request = 0x135e0020 + index * 64;
        const uint32_t pathAddress = index < 8 ? 0x4398f0 : 0x6a1000;
        const char* path = index < 8 ? "/dev/stm/immediate" : "/dev/openshsm_missing";
        auto* packet = experiment_ipc_mem1_span(context, request, 64);
        std::memset(packet, 0, 64);
        std::memcpy(context.mmu.get_ptr(pathAddress), path, std::strlen(path) + 1);
        experiment_ipc_store_be32(packet, 1);
        experiment_ipc_store_be32(packet + 12, pathAddress);
        hw::ipc_ppc_ctrl = 0x38;
        hw::ipc_arm_msg = hw::ipc_arm_ctrl = hw::experimentPpcFlags = 0;
        hw::pi_intsr = 0x10000;
        hw::pi_intmr = 0x40f8;
        dispatcher.write32(0xcd000000, request);
        hw::ipc_ppc_ctrl = send;
        EventScheduler::get().schedule_after(1, [](CPUContext&, uint64_t) {
            hw::ipc_ppc_ctrl = (hw::ipc_ppc_ctrl & ~1u) | 2;
        });
        unsigned produced = 0;
        hw::experiment_fixture_reply_after(request, 2, [&](CPUContext& active, uint64_t) {
#ifndef SHSM_DROP_STM_PRODUCER
            experiment_ipc_open_packet(active, request);
            ++produced;
#endif
        });
        EventScheduler::get().advance(context, 1);
        const auto ack = hw::experiment_ipc_snapshot();
        EventScheduler::get().advance(context, 8);
        if (produced || experiment_ipc_be32(packet) != 1 || hw::ipc_arm_msg) { return 3; }
        hw::experiment_ipc_control_latched_irq((send & 0x38) | 2);
        hw::experiment_ipc_irq_clear(0x40000000);
        EventScheduler::get().advance(context, 9);
        const auto reply = hw::experiment_ipc_snapshot();
        if (produced != 1) { return 4; }
        hw::experiment_ipc_control_latched_irq((send & 0x38) | 4);
        hw::experiment_ipc_irq_clear(0x40000000);
        const auto clear = hw::experiment_ipc_snapshot();
        EventScheduler::get().advance(context, 32);
        if (produced != 1) { return 5; }
#ifdef SHSM_WRONG_STM_RESULT
        experiment_ipc_store_be32(packet + 4, 0x42);
#endif
        std::cout << "STM_TRANSPORT " << index << ' ' << ack.ppcControl << ' ' << ack.armMessage << ' '
            << reply.ppcControl << ' ' << reply.armMessage << ' ' << clear.ppcControl << ' '
            << int32_t(experiment_ipc_be32(packet + 4)) << ' ' << produced << '\n';
        std::cout << "STM_TRANSPORT_PACKET " << index << ' ' << std::hex << std::setfill('0');
        for (unsigned offset = 0; offset < 64; ++offset) { std::cout << std::setw(2) << unsigned(packet[offset]); }
        std::cout << std::dec << '\n';
    }
    return 0;
}
