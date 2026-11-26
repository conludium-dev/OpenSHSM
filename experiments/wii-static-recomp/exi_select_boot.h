#pragma once
#include "exi_init_boot.h"
#include "exi_select_backend.h"

namespace nwii::runtime {
inline void experiment_exi_select_boot_guard(CPUContext& context, uint32_t address) {
    if (address != 0xcd006800 || context.gpr[27] != 0 || context.gpr[28] != 2 || context.gpr[29] != 0) {
        throw std::runtime_error("EXI selection caller inputs outside verified boot profile");
    }
    experiment_exi_init_boot_guard(context, address);
}

inline uint32_t experiment_exi_select_boot_read32(CPUContext& context, uint32_t address, uint32_t instruction) {
    if (instruction != 0x8020e3c0) {
        throw std::runtime_error("EXI selection reader unverified");
    }
    experiment_exi_select_boot_guard(context, address);
    const auto value = MMIODispatcher::get().read32(address);
    if (value != 0x3800) {
        throw std::runtime_error("EXI selection preceding state unverified");
    }
    std::cout << "EXI_SELECT_BOOT_READ_ACCEPTED value=3800\n";
    return value;
}

inline void experiment_exi_select_boot_write32(CPUContext& context, uint32_t address, uint32_t value, uint32_t instruction) {
    if (instruction != 0x8020e3e0 || value != 0x200 || MMIODispatcher::get().read32(address) != 0x3800) {
        throw std::runtime_error("EXI selection write/value/preceding state unverified");
    }
    experiment_exi_select_boot_guard(context, address);
    const auto cause = hw::pi_intsr.load();
    hw::experiment_exi_select_csr_write(address, value);
    if (MMIODispatcher::get().read32(address) != 0x1a00 || hw::pi_intsr.load() != cause) {
        throw std::runtime_error("EXI selection readback/PI mismatch");
    }
    std::cout << "EXI_SELECT_BOOT_WRITE_ACCEPTED value=200 readback=1a00\n";
}
}
