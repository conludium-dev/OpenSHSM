#include "ipc_open_packet.h"
#include "runtime/devices.h"
#include <array>
#include <cstring>
#include <iostream>

int main(int argc, char** argv) {
    using namespace nwii::runtime;
    if (argc != 2) { return 2; }
    CPUContext context;
    auto& kernel = IOSKernel::get();
    kernel.init();
    kernel.register_device(devices::create_stm_device());
    const bool packetMode = std::string(argv[1]) == "packet";
    if (!packetMode && std::string(argv[1]) != "kernel") { return 2; }
    for (unsigned index = 0; index < 16; ++index) {
        const std::string path = index < 8 ? "/dev/stm/immediate" : "/dev/openshsm_missing";
        if (!packetMode) {
            const auto result = kernel.open(context, path, 0);
            std::cout << "STM_KERNEL " << index << ' ' << result << '\n';
            continue;
        }
        const uint32_t physical = 0x135e0020 + index * 64;
        const uint32_t pathAddress = index < 8 ? 0x4398f0 : 0x6a1000;
        auto* packet = context.mmu.get_ptr(physical);
        auto* pathBytes = context.mmu.get_ptr(pathAddress);
        if (!packet || !pathBytes) { return 3; }
        std::memcpy(pathBytes, path.c_str(), path.size() + 1);
        std::memset(packet, 0, 64);
        experiment_ipc_store_be32(packet, 1);
        experiment_ipc_store_be32(packet + 12, pathAddress);
        const auto result = experiment_ipc_open_packet(context, physical);
        std::cout << "STM_PACKET " << index << ' ' << result;
        for (unsigned offset = 0; offset < 64; ++offset) { std::cout << ' ' << unsigned(packet[offset]); }
        std::cout << '\n';
    }
    if (packetMode) {
        auto* packet = context.mmu.get_ptr(0x135e0020);
        for (unsigned test = 0; test < 8; ++test) {
            std::memset(packet, 0, 64);
            experiment_ipc_store_be32(packet, test == 1 ? 2 : 1);
            experiment_ipc_store_be32(packet + 12, test == 3 ? 0xffffffff : 0x4398f0);
            experiment_ipc_store_be32(packet + 16, test == 2 ? 3 : test == 7 ? 1 : 0);
            if (test == 4) { std::memset(context.mmu.get_ptr(0x4398f0), 'x', 64); }
            if (test == 5) { std::memcpy(context.mmu.get_ptr(0x4398f0), "bad", 4); }
            if (test == 6) { std::memcpy(context.mmu.get_ptr(0x4398f0), "/dev/stm/unverified", 20); }
            if (test == 7) { std::memcpy(context.mmu.get_ptr(0x4398f0), "/dev/stm/immediate", 19); }
            std::array<uint8_t, 64> before;
            std::copy(packet, packet + 64, before.begin());
            bool refused = false;
            try { experiment_ipc_open_packet(context, test == 0 ? 0x135e0021 : 0x135e0020); }
            catch (const std::runtime_error&) { refused = true; }
            if (!refused || !std::equal(before.begin(), before.end(), packet)) { return 4; }
        }
        std::cout << "STM_PACKET_GUARDS 8\n";
    }
    return 0;
}
