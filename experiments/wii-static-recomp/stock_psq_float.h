// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <cstdint>

inline uint32_t shsm_psq_single_ftz(uint64_t value) {
    const uint32_t exponent = static_cast<uint32_t>((value >> 52) & 0x7ff);
    if (exponent > 896 || (value & 0x7fffffffffffffffull) == 0) {
        return static_cast<uint32_t>(((value >> 32) & 0xc0000000) | ((value >> 29) & 0x3fffffff));
    }
    return static_cast<uint32_t>((value >> 32) & 0x80000000);
}

inline uint64_t shsm_psq_double(uint32_t value) {
    const uint64_t bits = value;
    uint64_t exponent = (bits >> 23) & 0xff;
    uint64_t fraction = bits & 0x007fffff;
    if (exponent > 0 && exponent < 255) {
        const uint64_t high = !(exponent >> 7);
        const uint64_t extension = (high << 61) | (high << 60) | (high << 59);
        return ((bits & 0xc0000000) << 32) | extension | ((bits & 0x3fffffff) << 29);
    }
    if (exponent == 0 && fraction != 0) {
        exponent = 1023 - 126;
        do {
            fraction <<= 1;
            --exponent;
        } while ((fraction & 0x00800000) == 0);
        return ((bits & 0x80000000) << 32) | (exponent << 52) | ((fraction & 0x007fffff) << 29);
    }
    const uint64_t high = exponent >> 7;
    const uint64_t extension = (high << 61) | (high << 60) | (high << 59);
    return ((bits & 0xc0000000) << 32) | extension | ((bits & 0x3fffffff) << 29);
}
