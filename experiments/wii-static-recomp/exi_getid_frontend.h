#pragma once
#include "exi_select_boot.h"
#include "exi_getid_backend.h"

namespace nwii::runtime {
inline bool experimentExiRiUart = false;
inline bool experiment_getid_mmio(CPUContext& context, uint32_t address, uint32_t instruction = 0) {
    const bool exi = address == 0xcd006800 || address == 0xcd006814 || address == 0xcd006828
        || address == 0xcd00680c || address == 0xcd006810 || address == 0xcd006820 || address == 0xcd006834;
    const bool pi = address == 0xcc003000 || address == 0xcc003004;
    const bool sram_dma = hw::experimentExiTransfer.sramAllowed && (address == 0xcd006804 || address == 0xcd006808);
    if (!exi && !pi && !sram_dma && address != 0xcd006024) {
        return false;
    }
    const auto& state = bat_context(context);
    const auto mapping = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, false);
    const auto selected = hw::experimentExiMaskState[0] & 0x3f0;
    const bool riUart = experimentExiRiUart && hw::experimentExiTransfer.uartAllowed && context.msr == 0x2032 &&
        (((instruction >= 0x8020d000 && instruction < 0x8020ff00) &&
        (address == 0xcd006800 || address == 0xcd00680c || address == 0xcd006810)) ||
        (address == 0xcd006800 && (instruction == 0x80217760 || instruction == 0x80217794)) ||
        (address == 0xcd006814 && (instruction == 0x802177a4 || instruction == 0x802177d8)) ||
        (address == 0xcd006828 && (instruction == 0x802177e8 || instruction == 0x8021780c)) ||
        (address == 0xcc003004 && instruction == 0x802178a4) ||
        (address == 0xcd006024 && instruction == 0x80211d04)) &&
        (selected == 0 || selected == 0x140);
    if ((context.msr != 0x2030 && !riUart) || mapping.physical != (address & 0x1fffffffu) || mapping.wimg != 5 || mapping.slot != 1) {
        throw std::runtime_error("GetID MMIO profile mapping unverified");
    }
    return true;
}
inline uint32_t experiment_getid_read32(CPUContext& context, uint32_t address, uint32_t instruction = 0) {
    if (experiment_getid_mmio(context, address, instruction)) {
        return MMIODispatcher::get().read32(address);
    }
    return bat_memory_read32(context, address);
}
inline void experiment_getid_write32(CPUContext& context, uint32_t address, uint32_t value, uint32_t instruction = 0) {
    if (experiment_getid_mmio(context, address, instruction)) {
        if (context.msr == 0x2032 && ((address == 0xcd006800 && (value & 0x380) && (value & 0x3f0) != 0x140) ||
            ((address == 0xcd006814 || address == 0xcd006828) && (value & 0x380)))) {
            throw std::runtime_error("RI UART other selection unverified");
        }
        if ((address == 0xcd006804 && instruction != 0x8020dc60) || (address == 0xcd006808 && instruction != 0x8020dc64)) {
            throw std::runtime_error("SRAM DMA caller unverified");
        }
        if (address == 0xcc003000) {
            throw std::runtime_error("GetID PI cause writes unverified");
        }
        if (address == 0xcd006800 || address == 0xcd006814 || address == 0xcd006828) {
            hw::experiment_getid_csr_write(address, value);
        } else {
            MMIODispatcher::get().write32(address, value);
        }
        return;
    }
    bat_memory_write32(context, address, value);
}
}
