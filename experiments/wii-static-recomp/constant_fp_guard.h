#pragma once
#include "stock_fp_unavailable.h"
namespace nwii::runtime {
inline uint32_t stock_inline_read_hid2(CPUContext& context) {
    if (context.msr & 0x4000) {
        throw std::runtime_error("Privileged HID2 access in user mode is not implemented");
    }
    return static_cast<ProcessorContext&>(context).hid2;
}
constexpr bool stock_constant_uses_fp(uint32_t opcode) {
    const uint32_t primary = opcode >> 26;
    const uint32_t xo = (opcode >> 1) & 1023;
    const uint32_t short_xo = xo & 31;
    if ((primary >= 48 && primary <= 57) || primary == 60 || primary == 61) {
        return true;
    }
    if (primary == 31) {
        switch (xo) {
            case 535: case 567: case 599: case 631: case 663:
            case 695: case 727: case 759: case 983: return true;
            default: return false;
        }
    }
    if (primary == 59) {
        switch (short_xo) {
            case 18: case 20: case 21: case 24: case 25:
            case 28: case 29: case 30: case 31: return true;
            default: return false;
        }
    }
    if (primary == 63) {
        switch (xo) {
            case 0: case 12: case 14: case 15: case 32: case 38: case 40: case 64:
            case 70: case 72: case 134: case 136: case 264: case 583: case 711: return true;
        }
        switch (short_xo) {
            case 18: case 20: case 21: case 23: case 25: case 26:
            case 28: case 29: case 30: case 31: return true;
            default: return false;
        }
    }
    if (primary == 4) {
        switch (xo) {
            case 0: case 32: case 40: case 64: case 72: case 96:
            case 136: case 264: case 528: case 560: case 592: case 624: return true;
        }
        switch (xo & 63) {
            case 6: case 7: case 38: case 39: return true;
        }
        switch (short_xo) {
            case 10: case 11: case 12: case 13: case 14: case 15: case 18:
            case 20: case 21: case 23: case 24: case 25: case 26:
            case 28: case 29: case 30: case 31: return true;
            default: return false;
        }
    }
    return false;
}
template<uint32_t Opcode>
inline void stock_constant_fp_preinstruction(CPUContext& ctx, uint32_t instruction) {
    constexpr uint32_t primary = Opcode >> 26;
    constexpr bool quantized = primary == 56 || primary == 57 || primary == 60 || primary == 61;
    if constexpr (primary == 4 || quantized) {
        const uint32_t hid2 = stock_inline_read_hid2(ctx);
        if (!(hid2 & 0x20000000u) || (quantized && !(hid2 & 0x80000000u))) {
            throw std::runtime_error("Invalid paired execution: original program exception routing unverified");
        }
    }
    if constexpr (stock_constant_uses_fp(Opcode)) {
        if (!stock_scalar_fp_available(ctx, instruction)) {
            longjmp(ctx.exception_jmp_buf, 1);
        }
    }
}
}
