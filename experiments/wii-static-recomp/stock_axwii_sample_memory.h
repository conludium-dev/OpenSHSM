// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <cstdint>
#include <span>
#include <stdexcept>

namespace openshsm::experiment {

struct AxWiiSampleMemory {
    std::span<const uint8_t> mem1, mem2;
    uint32_t mem1_mask, mem2_mask;

    uint8_t operator()(uint32_t address) const {
        const bool extended = (address & 0x10000000u) != 0;
        const auto bytes = extended ? mem2 : mem1;
        const uint32_t offset = address & (extended ? mem2_mask : mem1_mask);
        if (offset >= bytes.size()) {
            throw std::runtime_error("AXWii sample outside backed Wii RAM");
        }
        return bytes[offset];
    }
};

}
