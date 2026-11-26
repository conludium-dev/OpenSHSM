#pragma once
#include "ai_clock_profile.h"
#include "flush_syscall.h"
#include "dsp_startup_backend.h"

namespace nwii::runtime {
inline void experiment_dsp_startup_mapping(CPUContext& context, uint32_t address) {
    const auto mapping = resolve_reference_bat(bat_context(context).dbat, bat_context(context).hid4, context.msr, address, false);
    if (context.msr != 0x2032 || mapping.physical != (address & 0x1fffffffu) || mapping.slot != 1 || mapping.wimg != 5) {
        throw std::runtime_error("DSP startup mapping unverified");
    }
}
inline uint16_t experiment_audio_read16(CPUContext& context, uint32_t address, uint32_t instruction) {
    uint32_t expected = 0;
    switch (instruction) {
        case 0x80212d4c: case 0x80212d58: case 0x80212da0: case 0x80212da8:
        case 0x80212df0: case 0x80212df8: case 0x80212e0c: case 0x80212e18:
        case 0x80212e28: case 0x80212e58: case 0x80212e68: case 0x80212e78:
            expected = 0xcc00500a;
            break;
        case 0x80212d70: case 0x80212e34: case 0x80212e40:
            expected = 0xcc005004;
            break;
        case 0x80212d74: case 0x80212e54:
            expected = 0xcc005006;
            break;
        default:
            throw std::runtime_error("DSP startup read caller unverified");
    }
    if (address != expected) { throw std::runtime_error("DSP startup caller/address mismatch"); }
    experiment_dsp_startup_mapping(context, address);
    const uint16_t value = hw::experiment_dsp_startup_read(context, address, 2);
    if (instruction == 0x80212d4c || instruction == 0x80212e0c || instruction == 0x80212e28 ||
        instruction == 0x80212e34 || instruction == 0x80212e54 || instruction == 0x80212e58 || instruction == 0x80212e68) {
        hw::experimentDspStartup.accesses.push_back({instruction, value, address});
        hw::experimentDspStartup.accessTicks.push_back(experiment_read_timebase(context));
    }
    return value;
}
inline void experiment_audio_write(CPUContext& context, uint32_t address, uint32_t value, unsigned width, uint32_t instruction) {
    static constexpr std::array<uint32_t, 17> callers{0x80212d40, 0x80212d48, 0x80212d54, 0x80212d6c,
        0x80212d8c, 0x80212d98, 0x80212d9c, 0x80212db8, 0x80212ddc, 0x80212de8, 0x80212dec,
        0x80212e08, 0x80212e14, 0x80212e30, 0x80212e60, 0x80212e64, 0x80212e70};
    if (hw::experimentDspStartup.command >= callers.size() || instruction != callers[hw::experimentDspStartup.command]) {
        throw std::runtime_error("DSP startup write caller unverified");
    }
    experiment_dsp_startup_mapping(context, address);
    hw::experiment_dsp_startup_write(context, address, value, width);
    hw::experimentDspStartup.accesses.push_back({instruction, value, address});
    hw::experimentDspStartup.accessTicks.push_back(experiment_read_timebase(context));
}
inline void experiment_audio_write16(CPUContext& context, uint32_t address, uint16_t value, uint32_t instruction) {
    experiment_audio_write(context, address, value, 2, instruction);
}
inline void experiment_audio_write32(CPUContext& context, uint32_t address, uint32_t value, uint32_t instruction) {
    experiment_audio_write(context, address, value, 4, instruction);
}
}
