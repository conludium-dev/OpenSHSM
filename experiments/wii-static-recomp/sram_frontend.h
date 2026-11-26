#pragma once
#include "exi_getid_frontend.h"

namespace nwii::runtime {
inline void experiment_sram_attach_memory(CPUContext& context) {
    hw::experimentExiTransfer.dmaWrite = [&context](uint32_t address, const std::array<uint8_t, 64>& bytes) {
        if (address != 0x00492600 || !context.mmu.get_ptr(address + 63)) {
            throw std::runtime_error("SRAM DMA destination backing unverified");
        }
        for (const auto& [start, image] : memory_context(context).instructionImages) {
            const auto code = start & 0x1fffffffu;
            if (uint64_t(address) < uint64_t(code) + image.size() && uint64_t(address) + 64 > code) {
                throw std::runtime_error("SRAM DMA overlaps compiled code");
            }
        }
        std::copy(bytes.begin(), bytes.end(), context.mmu.get_ptr(address));
    };
}
inline bool experiment_sram_dma_mapping(CPUContext& context, uint32_t address, uint32_t instruction, bool write) {
    if (address != 0xcd006804 && address != 0xcd006808) {
        return false;
    }
    const auto& state = bat_context(context);
    const auto mapping = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, false);
    const bool caller = write && ((address == 0xcd006804 && instruction == 0x8020dc60)
        || (address == 0xcd006808 && instruction == 0x8020dc64));
    if (!caller || !hw::experimentExiTransfer.sramAllowed || context.msr != 0x2030
        || mapping.physical != (address & 0x1fffffffu) || mapping.wimg != 5 || mapping.slot != 1) {
        throw std::runtime_error("SRAM DMA MMIO caller/mapping unverified");
    }
    return true;
}
inline uint32_t experiment_sram_read32(CPUContext& context, uint32_t address, uint32_t instruction) {
    if (experiment_sram_dma_mapping(context, address, instruction, false)) {
        return MMIODispatcher::get().read32(address);
    }
    return experiment_getid_read32(context, address, instruction);
}
inline void experiment_sram_write32(CPUContext& context, uint32_t address, uint32_t value, uint32_t instruction) {
    if (experiment_sram_dma_mapping(context, address, instruction, true)) {
        MMIODispatcher::get().write32(address, value);
        return;
    }
    experiment_getid_write32(context, address, value, instruction);
}
}
