#pragma once

namespace nwii::runtime {
inline bool experiment_di_burst_wait(CPUContext& context) {
    const auto ipc = hw::experiment_ipc_snapshot();
    if (stmSubmitted != 32 || ipc.ppcMessage != 0x135e0080 || ipc.ppcControl != 0x32 ||
        bat_memory_read32(context, 0x80492934) != 0x935e016c ||
        bat_memory_read32(context, 0x935e016c) != 0x80492658 ||
        bat_memory_read32(context, 0x935e0170) != 0x80492658 ||
        bat_memory_read32(context, 0x935e00ac) || bat_memory_read32(context, 0x935e00b0) ||
        bat_memory_read32(context, 0x804b2a80) != 16 ||
        bat_memory_read32(context, 0x804b2a84) != 18 ||
        bat_memory_read32(context, 0x804b2a88) != 0 ||
        bat_memory_read32(context, 0x804b2a8c) != 2 ||
        bat_memory_read32(context, 0x804b2a90) != 0x935e00e0 ||
        bat_memory_read32(context, 0x804b2a94) != 0x935e0140 ||
        bat_memory_read32(context, 0x804983a8) != 0x01000000 ||
        bat_memory_read32(context, 0x804983c8) != 0x01000000 ||
        bat_memory_read32(context, 0x804983c0) != 0x80222f80 ||
        bat_memory_read32(context, 0x804983cc) != 0xfeebdaed) {
        return false;
    }
    const std::array<uint32_t, 8> inquiry{6, 0, 3, 0x12, 0x135e2580, 32, 0x492260, 32};
    const std::array<uint32_t, 8> es{1, 0, 0, 0x528cf0, 0, 0, 0, 0};
    for (unsigned index = 0; index < 8; ++index) {
        if (bat_memory_read32(context, 0x935e00e0 + index * 4) != inquiry[index] ||
            bat_memory_read32(context, 0x935e0140 + index * 4) != es[index]) {
            return false;
        }
    }
    return bat_memory_read32(context, 0x935e0100) == 0x802258a0 &&
        bat_memory_read32(context, 0x935e0104) == 0x804983c0;
}
}
