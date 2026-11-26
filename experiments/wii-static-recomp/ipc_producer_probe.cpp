#define main experiment_previous_event_probe_main
#include "ipc_event_order_probe.cpp"
#undef main
#include "ipc_open_packet.h"
#include <cstring>
#include <iomanip>

int main() {
    CPUContext context;
    context.msr = 0x2030;
    IOSKernel::get().init();
    const uint32_t pathAddress = 0x6a1000;
    auto path = experiment_ipc_mem1_span(context, pathAddress, 64);
    std::memset(path, 0, 64);
    std::memcpy(path, "/dev/openshsm_missing", 21);
    for (unsigned index = 0; index < 8; ++index) {
        EventScheduler::get().reset();
        context.fpscr = index >= 4 ? 4 : 0;
        const auto request = 0x6a0000u + index * 64;
        auto packet = experiment_ipc_mem1_span(context, request, 64);
        std::memset(packet, 0, 64);
        experiment_ipc_store_be32(packet, 1);
        experiment_ipc_store_be32(packet + 12, pathAddress);
        experiment_ipc_store_be32(packet + 16, 1);
        const std::vector<uint8_t> tail(packet + 12, packet + 64);
        const auto result = experiment_ipc_open_packet(context, request);
        if (result != -6 || !std::equal(tail.begin(), tail.end(), packet + 12)) {
            return 9;
        }
        hw::ipc_ppc_ctrl = 0x32;
        hw::ipc_arm_msg = 0;
        hw::ipc_ppc_msg = request;
        hw::ipc_arm_ctrl = 0;
        hw::experiment_fixture_reply_after(request, 1);
        if (index & 2) {
            hw::ipc_ppc_ctrl = 0x30;
            EventScheduler::get().advance(context, 1);
        }
        hw::experiment_fixture_mask(index & 1 ? 0x40000000 : 0);
        const auto immediate = hw::experiment_ipc_snapshot();
        EventScheduler::get().advance(context, EventScheduler::get().now() + 1);
        const auto later = hw::experiment_ipc_snapshot();
        std::cout << "IPC_PRODUCER_CASE " << index << ' ' << immediate.ppcControl << ' ' << immediate.armMessage
                  << ' ' << later.ppcControl << ' ' << later.armMessage << ' ' << experiment_ipc_be32(packet)
                  << ' ' << int32_t(experiment_ipc_be32(packet + 4)) << ' ' << experiment_ipc_be32(packet + 8)
                  << ' ' << context.fpscr << '\n';
        std::cout << "IPC_PRODUCER_PACKET " << index << ' ' << std::hex << std::setfill('0');
        for (unsigned offset = 0; offset < 64; ++offset) {
            std::cout << std::setw(2) << unsigned(packet[offset]);
        }
        std::cout << std::dec << '\n';
    }
    const uint32_t request = 0x6a0800;
    auto packet = experiment_ipc_mem1_span(context, request, 64);
    auto seed = [&] {
        std::memset(packet, 0, 64);
        std::memset(path, 0, 64);
        std::memcpy(path, "/dev/openshsm_missing", 21);
        experiment_ipc_store_be32(packet, 1);
        experiment_ipc_store_be32(packet + 12, pathAddress);
        experiment_ipc_store_be32(packet + 16, 1);
    };
    unsigned guards = 0;
    auto refused = [&](uint32_t address) {
        const std::vector<uint8_t> before(packet, packet + 64);
        const auto gpr = context.gpr;
        const auto fpscr = context.fpscr;
        bool caught = false;
        try {
            experiment_ipc_open_packet(context, address);
        } catch (const std::runtime_error&) {
            caught = true;
        }
        if (!caught || !std::equal(before.begin(), before.end(), packet) || context.gpr != gpr || context.fpscr != fpscr) {
            throw std::runtime_error("Malformed IPC packet mutated response/state");
        }
        ++guards;
    };
    seed(); refused(request + 1);
    refused(0);
    refused(0x17fffe0);
    refused(0xffffffe0);
    experiment_ipc_store_be32(packet, 2); refused(request);
    seed(); experiment_ipc_store_be32(packet + 16, 2); refused(request);
    seed(); experiment_ipc_store_be32(packet + 12, 0); refused(request);
    seed(); experiment_ipc_store_be32(packet + 12, 0xfffffff0); refused(request);
    seed(); std::memset(path, 'A', 64); refused(request);
    seed(); path[0] = 255; refused(request);
    seed(); path[0] = 'X'; refused(request);
    seed(); experiment_ipc_store_be32(packet + 12, 0x17fffff);
    *experiment_ipc_mem1_span(context, 0x17fffff, 1) = 'A'; refused(request);
    std::cout << "IPC_PRODUCER_GUARDS " << guards << '\n';
    return 0;
}
